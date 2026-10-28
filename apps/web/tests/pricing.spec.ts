import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import {
  DraftEngine,
  DEFAULTS,
  POSITIONS,
  type Catalog,
} from '../src/mlb/draft/engine';
import { canonical } from '../src/mlb/season-input';
const catalog: Catalog = JSON.parse(
  readFileSync('data/publications/mlb-draft-2024-v2.json', 'utf8'),
);
const legacy: Catalog = JSON.parse(
  readFileSync('data/publications/mlb-draft-2024-v1.json', 'utf8'),
);

test('new catalog/default budget is versioned; legacy rules and price bounds remain replayable', () => {
  const { id, ...body } = catalog;
  expect(id).toBe(
    'draft-catalog:' +
      createHash('sha256')
        .update(JSON.stringify(canonical(body)))
        .digest('hex'),
  );
  expect(catalog.pricingPolicy).toBe('m8c2-elite-1-30-smoothed-v1');
  const current = new DraftEngine(catalog),
    old = new DraftEngine(legacy);
  expect(current.start('20261027').config.budget).toBe(65);
  expect(old.start('20261027').config.budget).toBe(90);
  expect(current.player('lahman:judgeaa01').price).toBe(30);
  expect(old.player('lahman:judgeaa01').price).toBe(20);
  expect(current.player('lahman:judgeaa01').profileId).toBe(
    old.player('lahman:judgeaa01').profileId,
  );
  const invalid = structuredClone(catalog);
  invalid.players[0].price = 31;
  expect(() => new DraftEngine(invalid)).toThrow(/Invalid draft player/);
  const oldInvalid = structuredClone(legacy);
  oldInvalid.players[0].price = 21;
  expect(() => new DraftEngine(oldInvalid)).toThrow(/Invalid draft player/);
  const oldState = old.start('20261027');
  expect(() => current.select(oldState, oldState.offers[0])).toThrow();
});

test('elite prices at all requested budgets preserve every safe choice and deterministic custom-order rosters', () => {
  test.setTimeout(90_000);
  for (const budget of [65, 70, 75, 90])
    for (const agent of ['first', 'cheapest', 'expensive', 'tier']) {
      const e = new DraftEngine(catalog, { ...DEFAULTS, budget });
      for (let seed = 0; seed < 25; seed++) {
        let s = e.start(String(seed));
        while (s.status !== 'complete') {
          for (const id of s.offers) {
            const next = e.select(s, id);
            expect(next.remainingBudget).toBeGreaterThanOrEqual(0);
            const suffix = e.minimum(
              next.config.order.slice(next.history.length),
              next.history.map((p) => p.playerId),
            );
            expect(suffix).not.toBeNull();
            expect(suffix!).toBeLessThanOrEqual(next.remainingBudget);
          }
          const tiers = { low: 0, middle: 1, aboveAverage: 2, elite: 3 };
          const chosen = [...s.offers].sort((a, b) =>
            agent === 'first'
              ? 0
              : agent === 'tier'
                ? tiers[e.player(b).valueTier!] - tiers[e.player(a).valueTier!]
                : (e.player(a).price - e.player(b).price) *
                  (agent === 'expensive' ? -1 : 1),
          )[0];
          s = e.select(s, chosen);
        }
        expect(new Set(s.history.map((p) => p.playerId)).size).toBe(9);
        expect([...s.history.map((p) => p.position)].sort()).toEqual(
          [...POSITIONS].sort(),
        );
        expect(
          e.replay(
            String(seed),
            s.history.map((p) => p.playerId),
          ),
        ).toEqual(s);
        expect(
          s.history.reduce((a, p) => a + p.price, 0) + s.remainingBudget,
        ).toBe(budget);
      }
    }
});
