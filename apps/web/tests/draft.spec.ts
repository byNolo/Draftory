import { expect, test } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import {
  DEFAULTS,
  DraftEngine,
  eligible,
  minimumAssignment,
  POSITIONS,
  drawIndex,
  type Catalog,
  type DraftState,
} from '../src/mlb/draft/engine';
import { draftedSeason } from '../src/mlb/draft/season';
import { canonical } from '../src/mlb/season-input';
import {
  PlayerDataClient,
  type PreparedProfile,
} from '../src/lib/api/player-data';
import type { PilotLoader } from '../src/mlb/pilot-loader';
import { nativeResult } from './helpers';

const catalog: Catalog = JSON.parse(
  readFileSync('data/publications/mlb-draft-2024-v1.json', 'utf8'),
);
test('frozen Mulberry32 sequence, rejection and golden initial offers', () => {
  expect(drawIndex(1, 4294967295)).toEqual([2693262067, 1831565814]);
  expect(drawIndex(1, 2147483649)).toEqual([11749833, 3663131627]);
  const engine = new DraftEngine(catalog);
  let state = engine.start('20261027');
  expect(state.offers).toEqual([
    'lahman:smithwi05',
    'lahman:perezsa02',
    'lahman:murphse01',
  ]);
  while (state.status !== 'complete')
    state = engine.select(state, state.offers[0]);
  expect(state.history.map((p) => p.playerId)).toEqual([
    'lahman:smithwi05',
    'lahman:baezja01',
    'lahman:margoma01',
    'lahman:rizzoan01',
    'lahman:grissva01',
    'lahman:smithjo09',
    'lahman:andujmi01',
    'lahman:delucjo01',
    'lahman:harribr02',
  ]);
  expect(state.remainingBudget).toBe(28);
});
test('invalid configurations and catalog prices/identities fail explicitly', () => {
  for (const config of [
    { ...DEFAULTS, budget: -1 },
    { ...DEFAULTS, offers: 0 },
    { ...DEFAULTS, minPa: 49 },
    { ...DEFAULTS, order: POSITIONS.map(() => 'DH' as const) },
  ])
    expect(() => new DraftEngine(catalog, config)).toThrow();
  const duplicate = structuredClone(catalog);
  duplicate.players.push(duplicate.players[0]);
  expect(() => new DraftEngine(duplicate)).toThrow(/Duplicate/);
  const bad = structuredClone(catalog);
  bad.players[0].price = 0;
  expect(() => new DraftEngine(bad)).toThrow(/Invalid draft player/);
});
function synthetic(): Catalog {
  return {
    ...catalog,
    id: 'synthetic:test',
    players: POSITIONS.map((pos, i) => ({
      id: `p${i}`,
      profileId: `profile:${i}`,
      name: `Synthetic ${i}`,
      pa: 50,
      price: 1,
      positions: [pos],
      games: Object.fromEntries(
        POSITIONS.map((p) => [p, p === pos ? 10 : 0]),
      ) as Record<typeof pos, number>,
    })),
  };
}
test('observed games, nulls, OF absence, PA floor and universal DH remain explicit', () => {
  const p = synthetic().players[0];
  expect(eligible(p, 'C', DEFAULTS)).toBe(true);
  expect(eligible(p, 'CF', DEFAULTS)).toBe(false);
  expect(eligible(p, 'DH', DEFAULTS)).toBe(true);
  expect(
    eligible({ ...p, games: { ...p.games, C: null } }, 'C', DEFAULTS),
  ).toBe(false);
  expect(eligible({ ...p, pa: 49 }, 'DH', DEFAULTS)).toBe(false);
  expect(eligible(p, 'DH', { ...DEFAULTS, universalDh: false })).toBe(false);
  const engine = new DraftEngine(catalog);
  expect(engine.player('lahman:judgeaa01').price).toBe(20);
  expect(engine.player('lahman:sotoju01').price).toBe(19);
  expect(eligible(engine.player('lahman:bettsmo01'), 'SS', DEFAULTS)).toBe(
    true,
  );
});
test('assignment matches brute force on rectangular matrices including shared identities', () => {
  function brute(matrix: number[][]): number | null {
    let best = Infinity;
    function visit(i: number, used: number[], sum: number) {
      if (i === matrix.length) {
        best = Math.min(best, sum);
        return;
      }
      matrix[i].forEach((v, j) => {
        if (v < 1_000_000 && !used.includes(j))
          visit(i + 1, [...used, j], sum + v);
      });
    }
    visit(0, [], 0);
    return Number.isFinite(best) ? best : null;
  }
  let rng = 7;
  for (let i = 0; i < 100; i++) {
    const matrix = Array.from({ length: 3 }, () =>
      Array.from({ length: 4 }, () => {
        let n;
        [n, rng] = drawIndex(rng, 5);
        return n === 4 ? 1_000_000 : n + 1;
      }),
    );
    expect(minimumAssignment(matrix)).toBe(brute(matrix));
  }
  expect(minimumAssignment([[1], [1]])).toBeNull();
  expect(minimumAssignment([])).toBe(0);
});
test('minimum budget, scarce identities and every offered branch preserve completion', () => {
  const c = synthetic();
  c.players[8].price = 2; // The unique C must never be consumed as DH first.
  const e = new DraftEngine(c, {
    ...DEFAULTS,
    budget: 10,
    order: ['DH', ...POSITIONS.slice(0, 8)],
  });
  const start = e.start('0');
  expect(start.offers).not.toContain('p0');
  function explore(state: DraftState) {
    if (state.status === 'complete') {
      expect(state.remainingBudget).toBe(0);
      return;
    }
    expect(state.offers.length).toBeGreaterThan(0);
    for (const id of state.offers) explore(e.select(state, id));
  }
  explore(start);
  expect(() =>
    new DraftEngine(c, { ...DEFAULTS, budget: 9 }).start('0'),
  ).toThrow(/infeasible/);
  c.players = c.players.filter((p) => p.id !== 'p0');
  expect(() => new DraftEngine(c).start('0')).toThrow(/infeasible/);
});
test('replay, restart, invalid picks, no replacement, immutability and budget accounting', () => {
  const e = new DraftEngine(catalog);
  let s = e.start('4294967295');
  expect(s).toEqual(new DraftEngine(catalog).start('4294967295'));
  const first = s;
  expect(e.select(canonical(s) as DraftState, s.offers[0])).toEqual(
    e.select(s, s.offers[0]),
  );
  expect(() => e.select(s, 'missing')).toThrow(/selectable/);
  expect(() => e.start('01')).toThrow();
  expect(() => e.start('4294967296')).toThrow();
  expect(() => {
    s.offers.push('forged');
  }).toThrow();
  while (s.status !== 'complete') {
    expect(new Set(s.offers).size).toBe(s.offers.length);
    expect(
      s.offers.some((id) => s.history.some((p) => p.playerId === id)),
    ).toBe(false);
    s = e.select(s, s.offers[0]);
  }
  expect(s.history.length).toBe(9);
  expect(s.remainingBudget).toBe(
    90 - s.history.reduce((n, p) => n + p.price, 0),
  );
  expect(
    e.replay(
      s.seed,
      s.history.map((p) => p.playerId),
    ),
  ).toEqual(s);
  expect(e.start(s.seed)).toEqual(first);
  expect(() => e.select(s, s.history[0].playerId)).toThrow();
  expect(() =>
    e.select({ ...first, remainingBudget: 180 }, first.offers[0]),
  ).toThrow(/budget/);
});
test('real catalog Monte Carlo: all offer choices safe, multiple budgets/agents/seeds', () => {
  test.setTimeout(180_000);
  const report = [];
  for (const budget of [25, 60, 90, 120])
    for (const strategy of ['first', 'expensive', 'cheap']) {
      const e = new DraftEngine(catalog, { ...DEFAULTS, budget });
      let rounds = 0,
        multiple = 0,
        three = 0,
        completed = 0;
      const times: number[] = [];
      const rosters = new Set<string>();
      for (let seed = 0; seed < 100; seed++) {
        const start = performance.now();
        let s = e.start(String(seed));
        let elapsed = performance.now() - start;
        while (s.status !== 'complete') {
          rounds++;
          multiple += Number(s.offers.length >= 2);
          three += Number(s.offers.length === 3);
          for (const id of s.offers) {
            const next = e.select(s, id);
            expect(next.remainingBudget).toBeGreaterThanOrEqual(0);
          }
          const options = [...s.offers].sort(
            (a, b) => e.player(a).price - e.player(b).price,
          );
          const id =
            strategy === 'first'
              ? s.offers[0]
              : strategy === 'cheap'
                ? options[0]
                : options.at(-1)!;
          const begin = performance.now();
          s = e.select(s, id);
          elapsed += performance.now() - begin;
        }
        completed++;
        times.push(elapsed);
        expect(new Set(s.history.map((p) => p.playerId)).size).toBe(9);
        rosters.add(s.history.map((p) => p.playerId).join(','));
      }
      times.sort((a, b) => a - b);
      report.push({
        budget,
        strategy,
        trials: 100,
        completed,
        multipleChoiceRate: multiple / rounds,
        threeChoiceRate: three / rounds,
        distinctRosters: rosters.size,
        medianDraftMs: times[50],
        p95DraftMs: times[95],
      });
    }
  mkdirSync('target/m7b', { recursive: true });
  writeFileSync('target/m7b/playtests.json', JSON.stringify(report, null, 2));
});
test('fresh-engine performance excludes test-agent branching, network and rendering', () => {
  const drafts: number[] = [],
    firstOffer: number[] = [],
    selections: number[] = [];
  for (let seed = 0; seed < 100; seed++) {
    const start = performance.now();
    const e = new DraftEngine(catalog);
    let s = e.start(String(seed));
    firstOffer.push(performance.now() - start);
    while (s.status !== 'complete') {
      const begin = performance.now();
      s = e.select(s, s.offers[0]);
      selections.push(performance.now() - begin);
    }
    drafts.push(performance.now() - start);
  }
  const stats = (values: number[]) => {
    values.sort((a, b) => a - b);
    return {
      n: values.length,
      min: values[0],
      p25: values[Math.floor(values.length * 0.25)],
      median: values[Math.floor(values.length * 0.5)],
      p75: values[Math.floor(values.length * 0.75)],
      p95: values[Math.floor(values.length * 0.95)],
      max: values.at(-1),
    };
  };
  mkdirSync('target/m7b', { recursive: true });
  writeFileSync(
    'target/m7b/engine-performance.json',
    JSON.stringify(
      {
        scope:
          '100 fresh engines; parsed catalog in memory; first offered player; no branch warming, network or React',
        draftMs: stats(drafts),
        firstOfferMs: stats(firstOffer),
        selectionMs: stats(selections),
      },
      null,
      2,
    ),
  );
});
test('eligibility, order and offer-count configurations retain safe completion', () => {
  for (const settings of [
    { minGames: 20, minPa: 50, universalDh: true, offers: 1 },
    { minGames: 10, minPa: 200, universalDh: true, offers: 5 },
    { minGames: 10, minPa: 400, universalDh: false, offers: 3 },
  ]) {
    const e = new DraftEngine(catalog, {
      ...DEFAULTS,
      ...settings,
      order: [...POSITIONS].reverse(),
    });
    for (let seed = 0; seed < 20; seed++) {
      let s = e.start(String(seed));
      while (s.status !== 'complete') s = e.select(s, s.offers.at(-1)!);
      expect(
        s.history.every((p) =>
          eligible(e.player(p.playerId), p.position, e.config),
        ),
      ).toBe(true);
    }
  }
});
test('small catalog exhaustive choice tree proves every permitted path completes', () => {
  const c = synthetic();
  c.players.push({
    ...c.players[0],
    id: 'flex',
    profileId: 'profile:flex',
    games: { ...c.players[0].games, SS: 10 },
  });
  const e = new DraftEngine(c, {
    ...DEFAULTS,
    budget: 9,
    order: ['DH', ...POSITIONS.slice(0, 8)],
  });
  let leaves = 0;
  function explore(s: DraftState) {
    if (s.status === 'complete') {
      leaves++;
      return;
    }
    for (const id of s.offers) explore(e.select(s, id));
  }
  explore(e.start('12'));
  expect(leaves).toBeGreaterThan(1);
});
test('drafted profile retrieval is selected-only, cached, versioned and runs native 162 games', async () => {
  const pilot = JSON.parse(
    readFileSync('apps/web/src/generated/mlb-pilot-2024.json', 'utf8'),
  );
  const fixture = JSON.parse(
    readFileSync(
      'crates/baseball-sim/tests/fixtures/season-modern-2024.json',
      'utf8',
    ),
  );
  const profiles: PreparedProfile[] = fixture.profiles.filter(
    (p: PreparedProfile) => pilot.userPlayerIds.includes(p.provenance.playerId),
  );
  const c = {
    ...catalog,
    datasetId: 'dataset:' + '1'.repeat(64),
    players: profiles.map((p) => ({
      ...catalog.players.find((q) => q.id === p.provenance.playerId)!,
      profileId: p.id,
      games: Object.fromEntries(POSITIONS.map((pos) => [pos, 10])) as Record<
        (typeof POSITIONS)[number],
        number
      >,
    })),
  };
  const e = new DraftEngine(c, { ...DEFAULTS, budget: 180 });
  let s = e.start('9');
  while (s.status !== 'complete') s = e.select(s, s.offers[0]);
  const calls: string[] = [];
  const api = new PlayerDataClient('/api', async (input, init) => {
    const path = String(input);
    calls.push(path);
    const dataset = {
      id: c.datasetId,
      schemaVersion: '1.0.0',
      sport: 'mlb',
      year: 2024,
      sourceId: c.sourceId,
      policy: { id: c.profilePolicyId },
      contextId: c.contextId,
      profileCount: 9,
      inputSchemaVersion: '1.2.0',
      modelVersion: 'lahman-contact-adapter-v1',
      profileType: 'season',
      aggregation: 'aggregate',
    };
    const ids = init?.body ? JSON.parse(String(init.body)).profileIds : [];
    return Response.json({
      schemaVersion: '1.0.0',
      ...(ids.length
        ? {
            datasetId: c.datasetId,
            profiles: ids.map((id: string) =>
              profiles.find((p) => p.id === id),
            ),
          }
        : { dataset }),
    });
  });
  const shared = { load: async () => pilot } as PilotLoader;
  const input = await draftedSeason(e, s, api, shared, '18446744073709551615');
  const repeated = await draftedSeason(
    e,
    s,
    api,
    shared,
    '18446744073709551615',
  );
  expect(repeated).toEqual(input);
  expect(
    await draftedSeason(
      e,
      canonical(s) as DraftState,
      api,
      shared,
      '18446744073709551615',
    ),
  ).toEqual(input);
  expect(calls.length).toBe(2);
  expect(input.userTeam.lineup.length).toBe(9);
  expect(input.seed).toBe('18446744073709551615');
  const result = nativeResult(input);
  expect(result.wins + result.losses).toBe(162);
  await expect(
    draftedSeason(e, { ...s, remainingBudget: 999 }, api, shared, '1'),
  ).rejects.toThrow(/replay/);
});
