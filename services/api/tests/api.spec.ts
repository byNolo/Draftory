import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';

const expected = JSON.parse(
  readFileSync('data/fixtures/player-data-api.synthetic.json', 'utf8'),
) as {
  profiles: { id: string }[];
};

const DATASET =
  'dataset:582776b91caf3e25d4deb2c59a4106a56c2743bd71d9b26538778c82171923f7';
const ABSENT = 'prepared:' + '0'.repeat(64);
const query = `?dataset=${DATASET}`;

// Test-only direct local D1 maintenance; there is no API write route.
function execute(sql: string) {
  const root = process.cwd();
  return execFileSync(
    process.execPath,
    [
      resolve(root, 'node_modules/wrangler/bin/wrangler.js'),
      'd1',
      'execute',
      'DB',
      '--local',
      '--config',
      resolve(root, 'services/api/wrangler.jsonc'),
      '--persist-to',
      resolve(root, 'target/api-tests'),
      '--command',
      sql,
      '--json',
    ],
    { stdio: 'pipe', encoding: 'utf8' },
  );
}

test('catalog, seasons and immutable dataset include provenance and policy versions', async ({
  request,
}) => {
  const health = await request.get('/api/health');
  expect((await health.json()).status).toBe('ok');
  const seasons = await request.get('/api/seasons');
  expect(await seasons.json()).toEqual({
    schemaVersion: '1.0.0',
    seasons: [2000],
    nextAfter: null,
  });
  const catalog = await request.get('/api/datasets?season=2000&limit=1');
  expect(catalog.headers()['cache-control']).toContain('max-age=60');
  const datasets = (await catalog.json()).datasets;
  expect(datasets).toHaveLength(1);
  expect(datasets[0].id).toBe(DATASET);
  const detail = await request.get(`/api/datasets/${DATASET}`);
  expect(detail.headers()['cache-control']).toContain('immutable');
  const body = (await detail.json()).dataset;
  expect(body.inputSchemaVersion).toBe('1.2.0');
  expect(body.source.source).toBe('synthetic-test-only');
  expect(body.policy.version).toBe('modern-neutral-v1');
  expect(body.attribution.license).toBe('CC-BY-SA-3.0');
  expect(
    (await (await request.get('/api/datasets?season=2024')).json()).datasets,
  ).toEqual([]);
  expect(
    (await (await request.get(`/api/datasets?after=${DATASET}`)).json())
      .datasets,
  ).toEqual([]);
});

test('keyset pagination, position filters and traded identity have no duplicates', async ({
  request,
}) => {
  const first = await (
    await request.get(`/api/players${query}&limit=1`)
  ).json();
  expect(first.players).toHaveLength(1);
  expect(first.players[0].id).toBe('lahman:synthetic01');
  expect(first.nextAfter).toBe(0);
  const second = await (
    await request.get(`/api/players${query}&limit=1&after=${first.nextAfter}`)
  ).json();
  expect(second.players[0].id).toBe('lahman:synthetic02');
  expect(second.nextAfter).toBeNull();
  const catcher = await (
    await request.get(`/api/players${query}&position=C`)
  ).json();
  expect(catcher.players).toHaveLength(1);
  expect(catcher.players[0].positionGames).toBe(30);
  const dh = await (
    await request.get(`/api/players${query}&position=DH`)
  ).json();
  expect(dh.players.map((p: { id: string }) => p.id)).toEqual([
    'lahman:synthetic02',
  ]);
  expect(
    (await (await request.get(`/api/players${query}&position=SS`)).json())
      .players,
  ).toEqual([]);
  const player = await (
    await request.get(`/api/players/lahman:synthetic01${query}`)
  ).json();
  expect(player.player.stints).toHaveLength(2);
  expect(
    player.player.stints.reduce(
      (n: number, s: { counts: { AB: number } }) => n + s.counts.AB,
      0,
    ),
  ).toBe(200);
  expect(
    player.player.stints.map((s: { leagueId: string }) => s.leagueId),
  ).toEqual(['AL', 'NL']);
  expect(
    player.player.positions.some(
      (p: { games: number | null }) => p.games === null,
    ),
  ).toBe(true);
});

test('single and bounded batch profiles preserve canonical engine payloads and request order', async ({
  request,
}) => {
  const players = (await (await request.get(`/api/players${query}`)).json())
    .players;
  const ids = players.map((p: { profileId: string }) => p.profileId).reverse();
  const response = await request.post('/api/profiles/batch', {
    headers: { 'Content-Type': 'Application/JSON; charset=utf-8' },
    data: { datasetId: DATASET, profileIds: ids },
  });
  expect(response.status()).toBe(200);
  expect(response.headers()['cache-control']).toBe('no-store');
  const profiles = (await response.json()).profiles;
  expect(profiles.map((p: { id: string }) => p.id)).toEqual(ids);
  for (const profile of profiles) {
    expect(profile).toEqual(expected.profiles.find((p) => p.id === profile.id));
    const single = await request.get(`/api/profiles/${profile.id}${query}`);
    expect(single.headers()['cache-control']).toContain('immutable');
    expect((await single.json()).profile).toEqual(profile);
    expect(profile.modelVersion).toBe('lahman-contact-adapter-v1');
    expect(
      Object.values(profile.weights).reduce((a, b) => Number(a) + Number(b), 0),
    ).toBe(1000000);
    expect(profile.weights.battedBallOut).toBe(0);
    expect(profile.provenance.playerId).toMatch(/^lahman:synthetic/);
  }
});

test('missing resources return explicit structured errors, never partial batches', async ({
  request,
}) => {
  for (const [path, code] of [
    [`/api/profiles/${ABSENT}${query}`, 'profileNotFound'],
    [`/api/players/lahman:missing${query}`, 'playerNotFound'],
    [`/api/datasets/dataset:${'0'.repeat(64)}`, 'datasetNotFound'],
    ['/api/unknown', 'notFound'],
  ]) {
    const response = await request.get(path);
    expect(response.status()).toBe(404);
    expect((await response.json()).error.code).toBe(code);
    expect(response.headers()['cache-control']).toBe('no-store');
  }
  const known = (await (await request.get(`/api/players${query}`)).json())
    .players[0].profileId;
  const batch = await request.post('/api/profiles/batch', {
    data: { datasetId: DATASET, profileIds: [known, ABSENT] },
  });
  expect(batch.status()).toBe(404);
  const body = await batch.json();
  expect(body.error.details.missing).toEqual([ABSENT]);
  expect(body).not.toHaveProperty('profiles');
});

test('invalid identifiers, pagination, SQL-shaped filters and unbounded bodies are rejected', async ({
  request,
}) => {
  for (const path of [
    '/api/players',
    `/api/players${query}&limit=0`,
    `/api/players${query}&limit=51`,
    `/api/players${query}&limit=1&limit=2`,
    `/api/players${query}&after=-1`,
    `/api/players${query}&after=1.5`,
    `/api/players${query}&position=C%27%20OR%201=1`,
    `/api/players${query}&search=anything`,
    `/api/profiles/not-an-id${query}`,
    `/api/players/lahman:bad%27${query}`,
    '/api/datasets?season=1999',
    '/api/datasets?after=bad',
  ]) {
    const response = await request.get(path);
    expect(response.status(), path).toBe(400);
    expect((await response.json()).error.message).toBeTruthy();
  }
  for (const profileIds of [
    [],
    [ABSENT, ABSENT],
    Array(21).fill(ABSENT),
    [5],
    [null],
  ]) {
    const response = await request.post('/api/profiles/batch', {
      data: { datasetId: DATASET, profileIds },
    });
    expect(response.status()).toBe(400);
  }
  expect(
    (
      await request.post('/api/profiles/batch', {
        data: '{',
        headers: { 'Content-Type': 'application/json' },
      })
    ).status(),
  ).toBe(400);
  expect(
    (
      await request.post('/api/profiles/batch', {
        data: 'x'.repeat(16385),
        headers: { 'Content-Type': 'application/json' },
      })
    ).status(),
  ).toBe(413);
  expect(
    (await request.post('/api/profiles/batch', { data: 'text' })).status(),
  ).toBe(415);
  const wrong = await request.post('/api/players');
  expect(wrong.status()).toBe(405);
  expect(wrong.headers().allow).toBe('GET');
});

test('unsupported dataset and profile versions are refused rather than reinterpreted', async ({
  request,
}) => {
  const players = (await (await request.get(`/api/players${query}`)).json())
    .players;
  const id = players[0].profileId;
  try {
    execute(
      `UPDATE mlb_datasets SET metadata_json=json_set(metadata_json,'$.inputSchemaVersion','999.0.0') WHERE id='${DATASET}'`,
    );
    expect((await request.get(`/api/profiles/${id}${query}`)).status()).toBe(
      409,
    );
  } finally {
    execute(
      `UPDATE mlb_datasets SET metadata_json=json_set(metadata_json,'$.inputSchemaVersion','1.2.0') WHERE id='${DATASET}'`,
    );
  }
  try {
    execute(
      `UPDATE mlb_profiles SET input_schema_version='999.0.0' WHERE id='${id}'`,
    );
    const response = await request.get(`/api/profiles/${id}${query}`);
    expect(response.status()).toBe(409);
    expect((await response.json()).error.code).toBe(
      'incompatibleProfileVersion',
    );
  } finally {
    execute(
      `UPDATE mlb_profiles SET input_schema_version='1.2.0' WHERE id='${id}'`,
    );
  }
});

test('unfinished imports stay hidden from catalogs and all dataset-scoped retrieval', async ({
  request,
}) => {
  const unfinished = 'dataset:' + '0'.repeat(64);
  try {
    execute(
      `INSERT INTO mlb_datasets SELECT '${unfinished}',source_id,year,metadata_json FROM mlb_datasets WHERE id='${DATASET}'`,
    );
    const catalog = await (await request.get('/api/datasets')).json();
    expect(catalog.datasets.map((d: { id: string }) => d.id)).toEqual([
      DATASET,
    ]);
    expect((await request.get(`/api/datasets/${unfinished}`)).status()).toBe(
      404,
    );
    expect(
      (await request.get(`/api/players?dataset=${unfinished}`)).status(),
    ).toBe(404);
    expect(
      (
        await request.post('/api/profiles/batch', {
          data: { datasetId: unfinished, profileIds: [ABSENT] },
        })
      ).status(),
    ).toBe(404);
  } finally {
    execute(`DELETE FROM mlb_datasets WHERE id='${unfinished}'`);
  }
});

test('unexpected oversized stored metadata returns a bounded structured error', async ({
  request,
}) => {
  try {
    const setup = JSON.parse(
      execute(
        `UPDATE mlb_datasets SET metadata_json=json_set(metadata_json,'$.testPadding',replace(hex(zeroblob(550000)),'0','x')) WHERE id='${DATASET}'; SELECT length(json_extract(metadata_json,'$.testPadding')) AS bytes FROM mlb_datasets WHERE id='${DATASET}';`,
      ),
    );
    expect(setup[1].results[0].bytes).toBe(1100000);
    const response = await request.get(`/api/datasets/${DATASET}`);
    expect(response.status()).toBe(422);
    expect((await response.json()).error.code).toBe('responseTooLarge');
    expect(response.headers()['cache-control']).toBe('no-store');
  } finally {
    execute(
      `UPDATE mlb_datasets SET metadata_json=json_remove(metadata_json,'$.testPadding') WHERE id='${DATASET}'`,
    );
  }
});
