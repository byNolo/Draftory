import { expect, test } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import {
  PlayerDataClient,
  DataError,
  type Dataset,
  type Player,
  type PreparedProfile,
} from '../src/lib/api/player-data';
import { SessionCache } from '../src/lib/api/session-cache';
import {
  assembleSeason,
  parsePilot,
  type Pilot,
} from '../src/mlb/season-input';
import { nativeResult } from './helpers';

const fixture = JSON.parse(
  readFileSync(
    'crates/baseball-sim/tests/fixtures/season-modern-2024.json',
    'utf8',
  ),
);
const rawPilot = JSON.parse(
  readFileSync('apps/web/src/generated/mlb-pilot-2024.json', 'utf8'),
);
const datasetId = 'dataset:' + '1'.repeat(64);
function setup() {
  const pilot = structuredClone(rawPilot) as Pilot;
  const dataset: Dataset = {
    id: datasetId,
    schemaVersion: '1.0.0',
    sport: 'mlb',
    year: 2024,
    sourceId: pilot.sourceId,
    inputSchemaVersion: '1.2.0',
    modelVersion: 'lahman-contact-adapter-v1',
    profileType: 'season',
    aggregation: 'aggregate',
    policy: { id: pilot.policyId },
    contextId: pilot.leagueContextId,
    profileCount: 9,
  };
  const profiles: PreparedProfile[] = pilot.userPlayerIds.map((id) =>
    fixture.profiles.find((p: PreparedProfile) => p.provenance.playerId === id),
  );
  const players: Player[] = profiles.map((p) => ({
    id: p.provenance.playerId,
    displayName: 'Fixture ' + p.provenance.playerId,
    profileId: p.id,
    year: 2024,
    metadata: {},
    stints: [],
    positions: [],
  }));
  const calls: { path: string; body?: { profileIds: string[] } }[] = [];
  let fail = false;
  const fetcher: typeof fetch = async (input, init) => {
    const url = new URL(String(input), 'http://localhost');
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ path: url.pathname, body });
    if (fail)
      return Response.json(
        { error: { code: 'temporaryFailure', message: 'Try again' } },
        { status: 503 },
      );
    let value: object;
    if (url.pathname === '/api/datasets')
      value = { datasets: [dataset], nextAfter: null };
    else if (url.pathname.startsWith('/api/datasets/')) value = { dataset };
    else if (url.pathname.startsWith('/api/players/'))
      value = {
        datasetId,
        player: players.find(
          (p) => p.id === decodeURIComponent(url.pathname.split('/').at(-1)!),
        ),
      };
    else if (body)
      value = {
        datasetId,
        profiles: body.profileIds.map((id: string) =>
          profiles.find((p) => p.id === id),
        ),
      };
    else {
      const profile = profiles.find(
        (p) => p.id === decodeURIComponent(url.pathname.split('/').at(-1)!),
      );
      if (!profile)
        return Response.json(
          { error: { code: 'profileNotFound', message: 'Missing' } },
          { status: 404 },
        );
      value = { datasetId, profile };
    }
    return Response.json({ schemaVersion: '1.0.0', ...value });
  };
  return {
    pilot,
    dataset,
    profiles,
    players,
    calls,
    api: new PlayerDataClient('/api', fetcher),
    setFail: (v: boolean) => {
      fail = v;
    },
  };
}

test('network outages and HTML access gates provide hosted-session recovery advice', async () => {
  const offline = new PlayerDataClient('/api', async () => {
    throw new TypeError('Failed to fetch');
  });
  await expect(offline.datasets()).rejects.toMatchObject({
    code: 'networkError',
    message: expect.stringContaining('connection or access session'),
  });
  const gate = new PlayerDataClient(
    '/api',
    async () =>
      new Response('<html>Sign in</html>', {
        headers: { 'Content-Type': 'text/html' },
      }),
  );
  await expect(gate.datasets()).rejects.toMatchObject({
    code: 'invalidResponse',
    message: expect.stringContaining('connection or access session'),
  });
});

test('typed catalog, dataset and player caches return isolated snapshots', async () => {
  const s = setup();
  expect((await s.api.datasets()).datasets[0].id).toBe(datasetId);
  const [a, b] = await Promise.all([
    s.api.dataset(datasetId),
    s.api.dataset(datasetId),
  ]);
  a.policy.id = 'mutated';
  expect(b.policy.id).toBe(s.pilot.policyId);
  expect((await s.api.dataset(datasetId)).policy.id).toBe(s.pilot.policyId);
  await s.api.player(datasetId, s.players[0].id);
  await s.api.player(datasetId, s.players[0].id);
  expect(s.calls).toHaveLength(3);
});

test('batches deduplicate IDs, overlap and subsequent individual requests', async () => {
  const s = setup();
  const ids = s.profiles.map((p) => p.id);
  const [first, second] = await Promise.all([
    s.api.profiles(datasetId, [ids[0], ids[0], ids[1]]),
    s.api.profiles(datasetId, [ids[1], ids[2]]),
  ]);
  expect(first.map((p) => p.id)).toEqual(ids.slice(0, 2));
  expect(second.map((p) => p.id)).toEqual(ids.slice(1, 3));
  await s.api.profile(datasetId, ids[0]);
  await s.api.profiles(datasetId, ids.slice(0, 3));
  expect(s.calls).toHaveLength(2);
  expect(s.calls.map((c) => c.body?.profileIds)).toEqual([
    ids.slice(0, 2),
    [ids[2]],
  ]);
});

test('failed requests are retryable and cache clear invalidates metadata and profiles', async () => {
  const s = setup();
  s.setFail(true);
  await expect(s.api.dataset(datasetId)).rejects.toMatchObject({
    code: 'temporaryFailure',
    status: 503,
  });
  s.setFail(false);
  await s.api.dataset(datasetId);
  await s.api.profiles(datasetId, [s.profiles[0].id]);
  s.api.clear();
  await s.api.dataset(datasetId);
  await s.api.profile(datasetId, s.profiles[0].id);
  expect(s.calls).toHaveLength(5);
  await expect(
    s.api.profile(datasetId, 'prepared:' + '0'.repeat(64)),
  ).rejects.toMatchObject({ code: 'profileNotFound', status: 404 });
});

test('larger selected batches respect the API limit and retain caller order', async () => {
  const s = setup();
  const calls: string[][] = [];
  const api = new PlayerDataClient('/api', async (_input, init) => {
    const ids = JSON.parse(String(init?.body)).profileIds as string[];
    calls.push(ids);
    return Response.json({
      schemaVersion: '1.0.0',
      datasetId,
      profiles: ids.map((id) => ({ ...s.profiles[0], id })),
    });
  });
  const ids = Array.from(
    { length: 21 },
    (_, i) => 'prepared:' + i.toString(16).padStart(64, '0'),
  );
  expect(
    (await api.profiles(datasetId, [...ids, ids[0]])).map((p) => p.id),
  ).toEqual(ids);
  expect(calls.map((ids) => ids.length)).toEqual([20, 1]);
  await api.profile(datasetId, ids[20]);
  expect(calls).toHaveLength(2);
});

test('clearing an in-flight cache cannot repopulate the new cache epoch', async () => {
  const cache = new SessionCache();
  let release!: (value: number) => void;
  const old = cache.get(
    'same',
    () =>
      new Promise<number>((r) => {
        release = r;
      }),
  );
  await Promise.resolve();
  cache.clear();
  expect(await cache.get('same', async () => 2)).toBe(2);
  release(1);
  expect(await old).toBe(1);
  expect(await cache.get('same', async () => 3)).toBe(2);
});

test('wrong response dataset, duplicate/missing batch members and incompatible envelopes fail', async () => {
  const s = setup();
  for (const response of [
    { schemaVersion: '999', datasetId, profiles: s.profiles.slice(0, 1) },
    {
      schemaVersion: '1.0.0',
      datasetId: 'other',
      profiles: s.profiles.slice(0, 1),
    },
    { schemaVersion: '1.0.0', datasetId, profiles: [] },
    { schemaVersion: '1.0.0', datasetId, profiles: [s.profiles[1]] },
  ]) {
    const api = new PlayerDataClient('/api', async () =>
      Response.json(response),
    );
    await expect(
      api.profiles(datasetId, [s.profiles[0].id]),
    ).rejects.toBeInstanceOf(DataError);
  }
});

test('verified assembly preserves distinct contexts, deduplication, input seed and native golden', async () => {
  const s = setup();
  const pilot = await parsePilot(s.pilot);
  const input = await assembleSeason(
    s.dataset,
    s.players,
    [...s.profiles, s.profiles[0]],
    pilot,
    '20261025',
  );
  expect(input.profiles).toHaveLength(18);
  expect(input.games).toBe(162);
  expect(input.pitchingEnvironment.contextId).toBe(s.pilot.leagueContextId);
  expect(input.config.contextualModel.id).toBe(s.pilot.transitionModelId);
  expect(input.pitchingEnvironment.contextId).not.toBe(
    input.config.contextualModel.id,
  );
  expect(input).toEqual(
    await assembleSeason(s.dataset, s.players, s.profiles, pilot, '20261025'),
  );
  const result = nativeResult(input);
  expect([
    result.wins,
    result.losses,
    result.runsScored,
    result.runsAllowed,
  ]).toEqual([105, 57, 759, 580]);
  writeFileSync('target/m6b-unit-input.json', JSON.stringify(input));
});

test('canonical u64 strings survive assembly and invalid seeds fail without coercion', async () => {
  const s = setup();
  for (const seed of ['0', '9007199254740993', '18446744073709551615'])
    expect(
      (await assembleSeason(s.dataset, s.players, s.profiles, s.pilot, seed))
        .seed,
    ).toBe(seed);
  for (const seed of ['01', '-1', '1e4', '18446744073709551616', '1.5', ''])
    await expect(
      assembleSeason(s.dataset, s.players, s.profiles, s.pilot, seed),
    ).rejects.toBeInstanceOf(DataError);
});

test('dataset source, model, statistical baseline and schema incompatibility fail before simulation', async () => {
  const s = setup();
  for (const changed of [
    { year: 2023 },
    { inputSchemaVersion: '999' },
    { modelVersion: 'unknown' },
    { sourceId: 'other' },
    { policy: { id: 'other' } },
    { contextId: s.pilot.transitionModelId },
  ])
    await expect(
      assembleSeason(
        { ...s.dataset, ...changed },
        s.players,
        s.profiles,
        s.pilot,
        '0',
      ),
    ).rejects.toBeInstanceOf(DataError);
});

test('missing, mismatched and corrupted profiles or shared artifacts cannot assemble', async () => {
  const s = setup();
  await expect(
    assembleSeason(s.dataset, s.players, s.profiles.slice(1), s.pilot, '0'),
  ).rejects.toBeInstanceOf(DataError);
  const players = structuredClone(s.players);
  players[0].profileId = players[1].profileId;
  await expect(
    assembleSeason(s.dataset, players, s.profiles, s.pilot, '0'),
  ).rejects.toBeInstanceOf(DataError);
  const profiles = structuredClone(s.profiles);
  profiles[0].weights.homeRun++;
  await expect(
    assembleSeason(s.dataset, s.players, profiles, s.pilot, '0'),
  ).rejects.toBeInstanceOf(DataError);
  for (const malformed of [
    { ...s.profiles[0], unknown: true },
    { ...s.profiles[0], qualityFlags: [''] },
    {
      ...s.profiles[0],
      provenance: { ...s.profiles[0].provenance, unknown: true },
    },
  ])
    await expect(
      assembleSeason(
        s.dataset,
        s.players,
        [malformed, ...s.profiles.slice(1)],
        s.pilot,
        '0',
      ),
    ).rejects.toBeInstanceOf(DataError);
  const changed = structuredClone(s.pilot);
  changed.season.config.contextualModel.id = changed.leagueContextId;
  await expect(parsePilot(changed)).rejects.toBeInstanceOf(DataError);
  await expect(
    assembleSeason(s.dataset, s.players, s.profiles, changed, '0'),
  ).rejects.toBeInstanceOf(DataError);
});
