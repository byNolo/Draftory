import { expect, test } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { DraftEngine, type Catalog } from '../src/mlb/draft/engine';
import {
  historicalBatting,
  simulatedRates,
  rate,
} from '../src/mlb/game/batting';
import type { BattingLine } from '../src/workers/protocol';
import type { Player } from '../src/lib/api/player-data';
import { PlayerDataClient } from '../src/lib/api/player-data';
import { draftedSeason } from '../src/mlb/draft/season';
import type { PilotLoader } from '../src/mlb/pilot-loader';
import { parsePilot } from '../src/mlb/season-input';
import { nativeResult } from './helpers';
import {
  defaultBattingOrder,
  moveBatter,
  validateBattingOrder,
} from '../src/mlb/draft/batting-order';

test('batting order is a roster permutation independent of positions and draft replay', () => {
  const state = engine.replay(
    '20261027',
    fixture.draft.history.map((p: { playerId: string }) => p.playerId),
  );
  const original = structuredClone(state);
  const order = defaultBattingOrder(state);
  expect(
    order.map((id) => state.history.find((p) => p.playerId === id)!.position),
  ).toEqual(['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']);
  const up = moveBatter(order, order[4], 3);
  expect(up[3]).toBe(order[4]);
  expect(moveBatter(up, order[4], 4)).toEqual(order);
  expect(moveBatter(order, order[8], 0)).toEqual([
    order[8],
    ...order.slice(0, 8),
  ]);
  expect(defaultBattingOrder(state)).toEqual(order);
  expect(state).toEqual(original);
  for (const invalid of [
    [],
    order.slice(1),
    [...order, order[0]],
    [order[0], ...order.slice(0, 8)],
    ['not-drafted', ...order.slice(1)],
  ])
    expect(() => validateBattingOrder(state, invalid)).toThrow(/nine drafted/);
  expect(() => defaultBattingOrder(engine.start('1'))).toThrow(/complete/);
  expect(() => moveBatter(order, 'missing', 0)).toThrow();
  expect(() => moveBatter(order, order[0], 9)).toThrow();
});

test('custom order changes actual native input/results, retains profile identities, and rejects bad orders before network', async () => {
  const state = fixture.draft;
  const order = defaultBattingOrder(state);
  let requests = 0;
  const api = new PlayerDataClient('/api', async (_url, init) => {
    requests++;
    return Response.json({
      schemaVersion: '1.0.0',
      ...(init?.body
        ? {
            datasetId: catalog.datasetId,
            profiles: JSON.parse(String(init.body)).profileIds.map(
              (id: string) =>
                fixture.profiles.find((p: { id: string }) => p.id === id),
            ),
          }
        : { dataset: fixture.dataset }),
    });
  });
  const pilot = await parsePilot(
    JSON.parse(
      readFileSync('apps/web/src/generated/mlb-pilot-2024.json', 'utf8'),
    ),
  );
  const shared = { load: async () => pilot } as PilotLoader;
  await expect(
    draftedSeason(engine, state, api, shared, '20261025', order.slice(1)),
  ).rejects.toThrow(/nine drafted/);
  expect(requests).toBe(0);
  const normal = await draftedSeason(engine, state, api, shared, '20261025');
  const reversed = [...order].reverse();
  const custom = await draftedSeason(
    engine,
    state,
    api,
    shared,
    '20261025',
    reversed,
  );
  expect(custom.userTeam.lineup.map((p) => p.id)).toEqual(
    reversed.map((id) => `draft:2024:${id}`),
  );
  for (const p of custom.userTeam.lineup)
    expect(p.profileId).toBe(
      engine.player(p.id.replace('draft:2024:', '')).profileId,
    );
  expect({ ...custom, userTeam: normal.userTeam }).toEqual(normal);
  const result = nativeResult(custom);
  expect(nativeResult(custom)).toEqual(result);
  expect(result.team).not.toEqual(nativeResult(normal).team);
  const newSeed = await draftedSeason(
    engine,
    state,
    api,
    shared,
    '42',
    reversed,
  );
  expect(newSeed.userTeam).toEqual(custom.userTeam);
  expect({ ...newSeed, seed: custom.seed }).toEqual(custom);
  expect(state).toEqual(fixture.draft);
});

const catalog: Catalog = JSON.parse(
  readFileSync('data/publications/mlb-draft-2024-v1.json', 'utf8'),
);
const fixture = JSON.parse(
  readFileSync('data/fixtures/mlb-game-2024-v1.json', 'utf8'),
);
const engine = new DraftEngine(catalog);
const player: Player = fixture.players[0];
const expected = engine.player(player.id);

test('historical cards use verified counts and official SF denominator, not modeled weights', () => {
  const s = historicalBatting(player, expected, 2024);
  expect(player.displayName).toBe('Will Smith');
  expect(s.pa).toBe(expected.pa);
  const c = player.stints[0].counts as Record<string, number>;
  expect(s.avg).toBe(c.H / c.AB);
  expect(s.obp).toBe((c.H + c.BB + c.HBP) / (c.AB + c.BB + c.HBP + c.SF));
  expect(s.slg).toBe((c.H + c['2B'] + 2 * c['3B'] + 3 * c.HR) / c.AB);
  expect(s.hr).toBe(c.HR);
  expect(() =>
    historicalBatting({ ...player, year: 2023 }, expected, 2024),
  ).toThrow(/match/);
  expect(() =>
    historicalBatting(
      { ...player, stints: [...player.stints, ...player.stints] },
      expected,
      2024,
    ),
  ).toThrow(/Duplicate/);
});

test('multi-team cards sum stints once, preserve unknowns, reject inconsistent counts', () => {
  const p = structuredClone(player);
  const counts = {
    AB: 10,
    H: 3,
    '2B': 1,
    '3B': 0,
    HR: 1,
    BB: 2,
    HBP: 1,
    SH: 0,
    SF: 1,
  };
  p.stints = [
    { stint: 1, teamId: 'A', leagueId: 'AL', counts },
    { stint: 2, teamId: 'B', leagueId: 'NL', counts },
  ];
  const e = { ...expected, pa: 28 };
  expect(historicalBatting(p, e, 2024)).toMatchObject({
    avg: 0.3,
    obp: 6 / 14,
    slg: 0.7,
    pa: 28,
    hr: 2,
    teams: ['A', 'B'],
  });
  p.stints[0] = { ...p.stints[0], counts: { ...counts, SF: null } };
  expect(historicalBatting(p, e, 2024)).toMatchObject({
    avg: 0.3,
    obp: null,
    pa: null,
  });
  p.stints[0] = { ...p.stints[0], counts: { ...counts, H: 25 } };
  expect(() => historicalBatting(p, e, 2024)).toThrow(/Inconsistent/);
});

test('simulated rates handle zero denominators and walks already including IBB', () => {
  const s: BattingLine = {
    plateAppearances: 14,
    atBats: 10,
    hits: 3,
    singles: 1,
    doubles: 1,
    triples: 0,
    homeRuns: 1,
    walks: 3,
    intentionalWalks: 2,
    hitByPitch: 1,
    strikeouts: 2,
    runs: 2,
    runsBattedIn: 3,
  };
  expect(simulatedRates(s)).toEqual({ avg: 0.3, obp: 0.5, slg: 0.7 });
  expect(
    simulatedRates({
      ...s,
      atBats: 0,
      hits: 0,
      singles: 0,
      doubles: 0,
      homeRuns: 0,
      walks: 0,
      hitByPitch: 0,
    }),
  ).toEqual({ avg: null, obp: null, slg: null });
  expect(rate(null)).toBe('—');
  expect(rate(0)).toBe('.000');
  expect(rate(1)).toBe('1.000');
});

test('all fixture historical cards reconcile to the catalog, selected profiles assemble with verified provenance', async () => {
  expect(fixture.sourceSqlSha256).toBe(catalog.sourceSqlSha256);
  for (const p of fixture.players)
    historicalBatting(p, engine.player(p.id), 2024);
  const state = engine.replay(
    '20261027',
    fixture.draft.history.map((h: { playerId: string }) => h.playerId),
  );
  expect(state).toEqual(fixture.draft);
  const api = new PlayerDataClient('/api', async (_url, init) =>
    Response.json({
      schemaVersion: '1.0.0',
      ...(init?.body
        ? {
            datasetId: catalog.datasetId,
            profiles: JSON.parse(String(init.body)).profileIds.map(
              (id: string) =>
                fixture.profiles.find((p: { id: string }) => p.id === id),
            ),
          }
        : { dataset: fixture.dataset }),
    }),
  );
  const pilot = await parsePilot(
    JSON.parse(
      readFileSync('apps/web/src/generated/mlb-pilot-2024.json', 'utf8'),
    ),
  );
  const input = await draftedSeason(
    engine,
    state,
    api,
    { load: async () => pilot } as PilotLoader,
    '20261025',
  );
  const first = nativeResult(input);
  expect([first.wins, first.losses, first.runsScored]).toEqual([81, 81, 593]);
  expect(nativeResult(input)).toEqual(first);
  const counters = Object.keys(first.team.batters[0].stats);
  for (const field of counters)
    expect(
      first.team.batters.reduce(
        (sum: number, b: { stats: Record<string, number> }) =>
          sum + (b.stats[field] ?? 0),
        0,
      ),
    ).toBe(first.team.totals[field] ?? 0);
  const seasons = Array.from({ length: 12 }, (_, i) => {
    const r = nativeResult({ ...input, seed: String(i) });
    return {
      seed: String(i),
      wins: r.wins,
      losses: r.losses,
      runs: r.runsScored,
    };
  });
  expect(new Set(seasons.map((r) => r.wins)).size).toBeGreaterThan(1);
  mkdirSync('target/m7c', { recursive: true });
  writeFileSync(
    'target/m7c/seasons.json',
    JSON.stringify(
      {
        note: 'One fixed first-offer lineup; seed variation, not roster-strength comparison',
        draft: state,
        seasons,
      },
      null,
      2,
    ),
  );
});

test('local balance diagnostics: first, cheapest and most expensive offered strategies', () => {
  test.setTimeout(120_000);
  const sessions = [];
  for (const strategy of ['first', 'cheapest', 'expensive'])
    for (let seed = 0; seed < 20; seed++) {
      let state = engine.start(String(seed));
      const safeChoices: number[] = [],
        prices: number[] = [];
      while (state.status === 'drafting') {
        safeChoices.push(state.offers.length);
        const ids = [...state.offers].sort((a, b) =>
          strategy === 'first'
            ? 0
            : (engine.player(a).price - engine.player(b).price) *
              (strategy === 'expensive' ? -1 : 1),
        );
        prices.push(engine.player(ids[0]).price);
        state = engine.select(state, ids[0]);
      }
      expect(state.remainingBudget).toBeGreaterThanOrEqual(0);
      expect(state.history).toHaveLength(9);
      expect(
        engine.replay(
          String(seed),
          state.history.map((p) => p.playerId),
        ),
      ).toEqual(state);
      sessions.push({
        strategy,
        seed,
        complete: state.status === 'complete',
        remaining: state.remainingBudget,
        prices,
        safeChoices,
        cheapestOffered: state.history.filter(
          (h) =>
            h.price ===
            Math.min(...h.offers.map((id) => engine.player(id).price)),
        ).length,
        mostExpensiveOffered: state.history.filter(
          (h) =>
            h.price ===
            Math.max(...h.offers.map((id) => engine.player(id).price)),
        ).length,
      });
    }
  mkdirSync('target/m7c', { recursive: true });
  writeFileSync(
    'target/m7c/playtests.json',
    JSON.stringify({ catalogId: catalog.id, sessions }, null, 2),
  );
});
