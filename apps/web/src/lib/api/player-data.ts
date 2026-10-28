import { SessionCache } from './session-cache';

export class DataError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = 'DataError';
  }
}
export type JsonObject = Record<string, unknown>;
export function object(value: unknown): JsonObject {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new DataError('invalidResponse', 'Expected a JSON object');
  return value as JsonObject;
}
export function text(value: unknown): string {
  if (typeof value !== 'string' || !value)
    throw new DataError('invalidResponse', 'Expected a nonempty string');
  return value;
}
export interface PreparedProfile {
  id: string;
  modelVersion: string;
  sampleOpportunities: number;
  weights: Record<string, number>;
  qualityFlags: string[];
  provenance: {
    playerId: string;
    sourceProfileId: string;
    sourceId: string;
    transformationVersion: string;
    policyId: string;
    contextId: string;
  };
}
export interface Dataset {
  id: string;
  schemaVersion: string;
  sport: string;
  year: number;
  sourceId: string;
  inputSchemaVersion: string;
  modelVersion: string;
  profileType: string;
  aggregation: string;
  policy: { id: string };
  contextId?: string;
  profileCount: number;
}
export interface Player {
  id: string;
  displayName: string;
  profileId: string;
  year: number;
  metadata: JsonObject;
  stints: JsonObject[];
  positions: JsonObject[];
}
export function parseDataset(value: unknown): Dataset {
  const d = object(value);
  for (const key of [
    'id',
    'schemaVersion',
    'sport',
    'sourceId',
    'inputSchemaVersion',
    'modelVersion',
    'profileType',
    'aggregation',
  ])
    text(d[key]);
  text(object(d.policy).id);
  if (!Number.isInteger(d.year) || !Number.isInteger(d.profileCount))
    throw new DataError('invalidResponse', 'Invalid dataset counts/year');
  return d as unknown as Dataset;
}
export function parseProfile(value: unknown): PreparedProfile {
  const p = object(value);
  const fields = [
    'id',
    'modelVersion',
    'sampleOpportunities',
    'weights',
    'qualityFlags',
    'provenance',
  ];
  if (
    Object.keys(p).length !== fields.length ||
    fields.some((key) => !Object.hasOwn(p, key))
  )
    throw new DataError(
      'invalidProfile',
      'Unsupported prepared profile fields',
    );
  const id = (value: unknown) => {
    if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(text(value)))
      throw new DataError('invalidProfile', 'Invalid simulation identifier');
  };
  for (const key of ['id', 'modelVersion']) id(p[key]);
  const provenance = object(p.provenance);
  const provenanceFields = [
    'playerId',
    'sourceProfileId',
    'sourceId',
    'transformationVersion',
    'policyId',
    'contextId',
  ];
  if (Object.keys(provenance).length !== provenanceFields.length)
    throw new DataError('invalidProfile', 'Unsupported provenance fields');
  for (const key of provenanceFields) id(provenance[key]);
  const weights = object(p.weights);
  if (
    !Number.isSafeInteger(p.sampleOpportunities) ||
    Number(p.sampleOpportunities) < 1 ||
    Number(p.sampleOpportunities) > 4294967295 ||
    !Array.isArray(p.qualityFlags) ||
    p.qualityFlags.length > 32 ||
    p.qualityFlags.some(
      (f) => typeof f !== 'string' || f.length < 1 || [...f].length > 128,
    ) ||
    Object.values(weights).some(
      (w) => !Number.isSafeInteger(w) || Number(w) < 0 || Number(w) > 1000000,
    )
  )
    throw new DataError('invalidProfile', 'Malformed prepared profile');
  return p as unknown as PreparedProfile;
}

export interface Transfer {
  path: string;
  method: string;
  bytes: number;
  ms: number;
}
export class PlayerDataClient {
  readonly cache = new SessionCache();
  readonly transfers: Transfer[] = [];
  constructor(
    private readonly base = '/api',
    private readonly fetcher: typeof fetch = globalThis.fetch.bind(globalThis),
  ) {}
  clear() {
    this.cache.clear();
    this.transfers.length = 0;
  }
  private async request(path: string, init?: RequestInit) {
    const start = performance.now();
    let response: Response;
    try {
      response = await this.fetcher(this.base + path, init);
    } catch {
      throw new DataError(
        'networkError',
        'Player data is unavailable. Check your connection or access session, then retry.',
      );
    }
    const bytes = new Uint8Array(await response.arrayBuffer());
    this.transfers.push({
      path,
      method: init?.method ?? 'GET',
      bytes: bytes.byteLength,
      ms: performance.now() - start,
    });
    let body: JsonObject;
    try {
      body = object(JSON.parse(new TextDecoder().decode(bytes)));
    } catch {
      throw new DataError(
        'invalidResponse',
        'Player data could not be read. Check your connection or access session, then retry.',
        response.status,
      );
    }
    if (!response.ok) {
      const error = object(body.error);
      throw new DataError(
        text(error.code),
        text(error.message),
        response.status,
      );
    }
    if (body.schemaVersion !== '1.0.0')
      throw new DataError(
        'incompatibleVersion',
        'Unsupported player API schema',
      );
    return body;
  }
  async datasets(
    after?: string,
  ): Promise<{ datasets: Dataset[]; nextAfter: string | null }> {
    const body = await this.request(
      '/datasets?limit=50' +
        (after ? `&after=${encodeURIComponent(after)}` : ''),
    );
    if (
      !Array.isArray(body.datasets) ||
      !(body.nextAfter === null || typeof body.nextAfter === 'string')
    )
      throw new DataError('invalidResponse', 'Invalid dataset catalog');
    return {
      datasets: body.datasets.map(parseDataset),
      nextAfter: body.nextAfter as string | null,
    };
  }
  dataset(id: string): Promise<Dataset> {
    return this.cache.get(`dataset:${id}:simulation-v1`, async () => {
      const d = parseDataset(
        (
          await this.request(
            `/datasets/${encodeURIComponent(id)}?view=simulation`,
          )
        ).dataset,
      );
      if (d.id !== id || typeof d.contextId !== 'string')
        throw new DataError(
          'datasetMismatch',
          'Dataset identity/context does not match the request',
        );
      return d;
    });
  }
  player(dataset: string, id: string): Promise<Player> {
    return this.cache.get(`player:${dataset}:${id}`, async () => {
      const body = await this.request(
        `/players/${encodeURIComponent(id)}?dataset=${encodeURIComponent(dataset)}`,
      );
      const p = object(body.player);
      if (body.datasetId !== dataset || p.id !== id)
        throw new DataError(
          'datasetMismatch',
          'Player identity/dataset does not match the request',
        );
      text(p.displayName);
      text(p.profileId);
      object(p.metadata);
      if (
        !Number.isInteger(p.year) ||
        !Array.isArray(p.stints) ||
        !Array.isArray(p.positions)
      )
        throw new DataError('invalidResponse', 'Invalid player metadata');
      p.stints.forEach(object);
      p.positions.forEach(object);
      return p as unknown as Player;
    });
  }
  profile(dataset: string, id: string): Promise<PreparedProfile> {
    return this.cache.get(`profile:${dataset}:${id}`, async () => {
      const body = await this.request(
        `/profiles/${encodeURIComponent(id)}?dataset=${encodeURIComponent(dataset)}`,
      );
      const p = parseProfile(body.profile);
      if (body.datasetId !== dataset || p.id !== id)
        throw new DataError(
          'datasetMismatch',
          'Profile identity/dataset does not match the request',
        );
      return p;
    });
  }
  async profiles(
    dataset: string,
    requested: string[],
  ): Promise<PreparedProfile[]> {
    const ids = [...new Set(requested)];
    for (let offset = 0; offset < ids.length; offset += 20) {
      const missing = ids
        .slice(offset, offset + 20)
        .filter((id) => !this.cache.has(`profile:${dataset}:${id}`));
      if (!missing.length) continue;
      const batch = this.request('/profiles/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ datasetId: dataset, profileIds: missing }),
      }).then((body) => {
        if (
          body.datasetId !== dataset ||
          !Array.isArray(body.profiles) ||
          body.profiles.length !== missing.length
        )
          throw new DataError(
            'datasetMismatch',
            'Profile batch does not match the request',
          );
        const profiles = body.profiles.map(parseProfile);
        if (profiles.some((p, i) => p.id !== missing[i]))
          throw new DataError(
            'invalidResponse',
            'Missing, reordered or duplicate profiles in batch',
          );
        return profiles;
      });
      // Reserve each key synchronously so overlapping/single requests share work.
      for (const [i, id] of missing.entries())
        void this.cache
          .get(`profile:${dataset}:${id}`, () => batch.then((p) => p[i]))
          .catch(() => {});
    }
    return Promise.all(ids.map((id) => this.profile(dataset, id)));
  }
}
