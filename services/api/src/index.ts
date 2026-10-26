import { PlayerData, ApiError, type DatasetRow } from './player-data';

const IMMUTABLE = 'public, max-age=31536000, immutable';
const CATALOG = 'public, max-age=60';
const POSITIONS = new Set([
  'P',
  'C',
  '1B',
  '2B',
  '3B',
  'SS',
  'LF',
  'CF',
  'RF',
  'OF',
  'DH',
]);

function json(data: unknown, cache = 'no-store', status = 200, extra = {}) {
  const body = JSON.stringify(data);
  if (new TextEncoder().encode(body).byteLength > 1048576)
    throw new ApiError(
      422,
      'responseTooLarge',
      'Response exceeds the 1 MiB API budget',
    );
  return new Response(body, {
    status,
    headers: {
      'Cache-Control': cache,
      'Content-Type': 'application/json; charset=utf-8',
      'X-Content-Type-Options': 'nosniff',
      ...extra,
    },
  });
}

function identifier(value: unknown, kind: 'dataset' | 'prepared' | 'player') {
  const pattern =
    kind === 'player'
      ? /^lahman:[a-z0-9]{1,32}$/
      : new RegExp(`^${kind}:[a-f0-9]{64}$`);
  if (typeof value !== 'string' || !pattern.test(value))
    throw new ApiError(400, 'invalidIdentifier', `Invalid ${kind} identifier`);
  return value;
}

function integer(
  value: string | null,
  fallback: number,
  min: number,
  max: number,
) {
  if (value === null) return fallback;
  if (
    !/^(0|[1-9][0-9]{0,8})$/.test(value) ||
    Number(value) < min ||
    Number(value) > max
  )
    throw new ApiError(
      400,
      'invalidParameter',
      'Integer parameter is outside its supported range',
    );
  return Number(value);
}

function parameters(url: URL, allowed: string[]) {
  const seen = new Set<string>();
  for (const key of url.searchParams.keys()) {
    if (!allowed.includes(key) || seen.has(key))
      throw new ApiError(
        400,
        'invalidParameter',
        'Unknown or repeated query parameter',
      );
    seen.add(key);
  }
}

async function batchBody(
  request: Request,
): Promise<{ datasetId: string; profileIds: string[] }> {
  if (
    request.headers.get('content-type')?.split(';')[0].trim().toLowerCase() !==
    'application/json'
  )
    throw new ApiError(415, 'invalidContentType', 'Use application/json');
  if (!request.body)
    throw new ApiError(400, 'invalidBody', 'A JSON object is required');
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 16384) {
        await reader.cancel();
        throw new ApiError(
          413,
          'bodyTooLarge',
          'Request body must be at most 16 KiB',
        );
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.length;
    }
    const body = JSON.parse(
      new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(bytes),
    );
    if (
      !body ||
      Array.isArray(body) ||
      Object.keys(body).sort().join(',') !== 'datasetId,profileIds'
    )
      throw new Error('shape');
    const datasetId = identifier(body.datasetId, 'dataset');
    if (
      !Array.isArray(body.profileIds) ||
      body.profileIds.length < 1 ||
      body.profileIds.length > 20
    )
      throw new ApiError(
        400,
        'invalidBatch',
        'Supply between 1 and 20 distinct profile IDs',
      );
    const profileIds: string[] = body.profileIds.map((id: unknown) =>
      identifier(id, 'prepared'),
    );
    if (new Set(profileIds).size !== profileIds.length)
      throw new ApiError(400, 'invalidBatch', 'Profile IDs must be distinct');
    return { datasetId, profileIds };
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(400, 'invalidBody', 'Invalid JSON batch body');
  } finally {
    reader.releaseLock();
  }
}

function datasetDocument(row: DatasetRow) {
  return {
    id: row.id,
    ...JSON.parse(row.metadata_json),
    attribution: JSON.parse(row.attribution_json),
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      const url = new URL(request.url);
      let path: string;
      try {
        path = decodeURIComponent(url.pathname);
      } catch {
        throw new ApiError(400, 'invalidIdentifier', 'Malformed URL encoding');
      }
      const batch = path === '/api/profiles/batch';
      if (request.method !== (batch ? 'POST' : 'GET'))
        return json(
          {
            error: { code: 'methodNotAllowed', message: 'Method not allowed' },
          },
          'no-store',
          405,
          { Allow: batch ? 'POST' : 'GET' },
        );
      if (path === '/api/health')
        return json({ status: 'ok', service: 'draftory-api' });
      const data = new PlayerData(env.DB);
      if (path === '/api/datasets' || path === '/api/seasons') {
        parameters(
          url,
          path === '/api/datasets'
            ? ['limit', 'after', 'season']
            : ['limit', 'after'],
        );
        const limit = integer(url.searchParams.get('limit'), 20, 1, 50);
        if (path === '/api/seasons') {
          const after = integer(
            url.searchParams.get('after'),
            1999,
            1999,
            2025,
          );
          const rows = await data.seasons(after, limit + 1);
          const items = rows.slice(0, limit).map((r) => r.year);
          return json(
            {
              schemaVersion: '1.0.0',
              seasons: items,
              nextAfter: rows.length > limit ? items.at(-1) : null,
            },
            CATALOG,
          );
        }
        const after = url.searchParams.get('after');
        if (after !== null) identifier(after, 'dataset');
        const year = url.searchParams.has('season')
          ? integer(url.searchParams.get('season'), 0, 2000, 2025)
          : null;
        const rows = await data.datasets(after ?? '', year, limit + 1);
        const items = rows.slice(0, limit).map(datasetDocument);
        return json(
          {
            schemaVersion: '1.0.0',
            datasets: items,
            nextAfter: rows.length > limit ? items.at(-1)!.id : null,
          },
          CATALOG,
        );
      }
      if (path.startsWith('/api/datasets/')) {
        parameters(url, ['view']);
        const view = url.searchParams.get('view');
        if (view !== null && view !== 'simulation')
          throw new ApiError(
            400,
            'invalidParameter',
            'Unsupported dataset view',
          );
        const row = await data.dataset(
          identifier(path.slice('/api/datasets/'.length), 'dataset'),
          view !== 'simulation',
        );
        return json(
          { schemaVersion: '1.0.0', dataset: datasetDocument(row) },
          IMMUTABLE,
        );
      }
      if (batch) {
        parameters(url, []);
        const body = await batchBody(request);
        const dataset = await data.dataset(body.datasetId);
        return json({
          schemaVersion: '1.0.0',
          datasetId: dataset.id,
          profiles: await data.profiles(dataset.id, body.profileIds),
        });
      }
      if (path === '/api/players') {
        parameters(url, ['dataset', 'position', 'limit', 'after']);
        const dataset = await data.dataset(
          identifier(url.searchParams.get('dataset'), 'dataset'),
        );
        const position = url.searchParams.get('position');
        if (position !== null && !POSITIONS.has(position))
          throw new ApiError(
            400,
            'invalidPosition',
            'Unsupported recorded position',
          );
        const limit = integer(url.searchParams.get('limit'), 20, 1, 50);
        const after = integer(url.searchParams.get('after'), -1, 0, 1000000);
        const rows = await data.players(dataset.id, position, after, limit + 1);
        const players = rows.slice(0, limit);
        return json(
          {
            schemaVersion: '1.0.0',
            datasetId: dataset.id,
            position,
            players,
            nextAfter: rows.length > limit ? players.at(-1)!.ordinal : null,
          },
          IMMUTABLE,
        );
      }
      if (path.startsWith('/api/players/')) {
        parameters(url, ['dataset']);
        const dataset = await data.dataset(
          identifier(url.searchParams.get('dataset'), 'dataset'),
        );
        const id = identifier(path.slice('/api/players/'.length), 'player');
        return json(
          {
            schemaVersion: '1.0.0',
            datasetId: dataset.id,
            player: await data.player(dataset, id),
          },
          IMMUTABLE,
        );
      }
      if (path.startsWith('/api/profiles/')) {
        parameters(url, ['dataset']);
        const dataset = await data.dataset(
          identifier(url.searchParams.get('dataset'), 'dataset'),
        );
        const id = identifier(path.slice('/api/profiles/'.length), 'prepared');
        const [profile] = await data.profiles(dataset.id, [id]);
        return json(
          { schemaVersion: '1.0.0', datasetId: dataset.id, profile },
          IMMUTABLE,
        );
      }
      throw new ApiError(404, 'notFound', 'Route not found');
    } catch (error) {
      if (error instanceof ApiError)
        return json(
          {
            error: {
              code: error.code,
              message: error.message,
              ...(error.details ? { details: error.details } : {}),
            },
          },
          'no-store',
          error.status,
        );
      console.error('Player data request failed', error);
      return json(
        {
          error: {
            code: 'internalError',
            message: 'Player data is temporarily unavailable',
          },
        },
        'no-store',
        500,
      );
    }
  },
} satisfies ExportedHandler<Env>;
