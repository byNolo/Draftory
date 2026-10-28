// Offline research using the actual TypeScript game engine, not a Python imitation.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import ts from 'typescript';

const output = resolve('data/processed/m8c2');
mkdirSync('target/m8c2', { recursive: true });
const enginePath = resolve('target/m8c2/engine.mjs');
const engineSource = readFileSync('apps/web/src/mlb/draft/engine.ts', 'utf8');
writeFileSync(
  enginePath,
  ts.transpileModule(engineSource, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ES2022,
    },
  }).outputText,
);
const { DraftEngine, DEFAULTS, POSITIONS } = await import(
  pathToFileURL(enginePath).href
);
const base = JSON.parse(
  readFileSync('data/publications/mlb-draft-2024-v1.json', 'utf8'),
);
const study = JSON.parse(
  readFileSync(resolve(output, 'pa-pricing.json'), 'utf8'),
);
const records = new Map(study.records.map((p) => [p.id, p]));
const policies = ['linear', 'elite', 'confidence-discount', 'tier-cap'];
const agents = ['first', 'cheapest', 'price-max', 'value-tier'];
const trials = Number(process.argv[2] ?? 100);
if (!Number.isInteger(trials) || trials < 10 || trials > 1000)
  throw Error('Trials must be 10..1000 per case');
if (
  base.datasetId !== study.datasetId ||
  base.sourceSqlSha256 !== study.sourceSqlSha256 ||
  records.size !== base.players.length ||
  base.players.some((p) => records.get(p.id)?.profileId !== p.profileId)
)
  throw Error('Study/catalog provenance differs');
const canonical = (value) =>
  Array.isArray(value)
    ? value.map(canonical)
    : value && typeof value === 'object'
      ? Object.fromEntries(
          Object.entries(value)
            .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
            .map(([k, v]) => [k, canonical(v)]),
        )
      : value;
const digest = (value) =>
  createHash('sha256')
    .update(JSON.stringify(canonical(value)))
    .digest('hex');
const stats = (values) => {
  const v = [...values].sort((a, b) => a - b),
    n = v.length;
  return {
    n,
    min: v[0],
    p25: v[Math.floor((n - 1) / 4)],
    median: n % 2 ? v[(n - 1) / 2] : (v[n / 2 - 1] + v[n / 2]) / 2,
    mean: v.reduce((a, b) => a + b, 0) / n,
    p75: v[Math.floor((3 * (n - 1)) / 4)],
    p95: v[Math.floor(0.95 * (n - 1))],
    max: v[n - 1],
  };
};
const tierIndex = { low: 0, middle: 1, aboveAverage: 2, elite: 3 };
const catalogs = Object.fromEntries(
  policies.map((policy) => {
    const body = { ...base };
    delete body.id;
    body.schemaVersion = '2.0.0';
    body.defaultBudget = 90;
    body.pricingPolicy = `study-${policy}`;
    body.players = base.players.map((p) => ({
      ...p,
      price: records.get(p.id).prices[policy],
      valueTier: records.get(p.id).tier,
    }));
    return [policy, { id: 'draft-catalog:' + digest(body), ...body }];
  }),
);
function choose(e, s, agent) {
  const offered = s.offers.map((id) => e.player(id));
  if (agent === 'first') return offered[0];
  return offered.sort((a, b) => {
    const delta =
      agent === 'value-tier'
        ? tierIndex[b.valueTier] - tierIndex[a.valueTier] || a.price - b.price
        : (a.price - b.price) * (agent === 'price-max' ? -1 : 1);
    return delta || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  })[0];
}
// Warm JS/JIT without warming any engine's matching cache.
for (const policy of policies)
  for (let seed = 0; seed < 5; seed++) {
    const e = new DraftEngine(catalogs[policy]);
    let s = e.start(String(seed));
    while (s.status !== 'complete') s = e.select(s, s.offers[0]);
  }
const cases = [];
for (const policy of policies)
  for (const budget of [65, 70, 75, 90])
    for (const agent of agents) {
      const catalog = catalogs[policy],
        costs = [],
        remaining = [],
        values = [],
        eliteCounts = [],
        lowPaCounts = [],
        firstMs = [],
        selectionMs = [],
        totalMs = [],
        rosters = new Set(),
        picked = new Set();
      const choices = Array.from({ length: 9 }, () => ({
        one: 0,
        two: 0,
        three: 0,
      }));
      const tierCounts = { low: 0, middle: 0, aboveAverage: 0, elite: 0 };
      let minimumCost = null,
        checkedOffers = 0;
      for (let seed = 0; seed < trials; seed++) {
        const start = performance.now(),
          e = new DraftEngine(catalog, { ...DEFAULTS, budget });
        let s = e.start(String(seed));
        const initial = performance.now() - start;
        firstMs.push(initial);
        let pureMs = initial;
        minimumCost = e.minimum(POSITIONS);
        while (s.status !== 'complete') {
          const round = s.history.length;
          choices[round][['', 'one', 'two', 'three'][s.offers.length]]++;
          for (const id of s.offers) {
            const rest = e.minimum(s.config.order.slice(round + 1), [
              ...s.history.map((p) => p.playerId),
              id,
            ]);
            if (rest === null || e.player(id).price + rest > s.remainingBudget)
              throw Error('Unsafe offer');
            checkedOffers++;
          }
          const p = choose(e, s, agent),
            clock = performance.now();
          s = e.select(s, p.id);
          const elapsed = performance.now() - clock;
          selectionMs.push(elapsed);
          pureMs += elapsed;
        }
        const ids = s.history.map((p) => p.playerId),
          sum = s.history.reduce((a, p) => a + p.price, 0);
        if (
          new Set(ids).size !== 9 ||
          new Set(s.history.map((p) => p.position)).size !== 9 ||
          s.remainingBudget < 0 ||
          sum + s.remainingBudget !== budget
        )
          throw Error('Invalid completed draft');
        costs.push(sum);
        remaining.push(s.remainingBudget);
        totalMs.push(pureMs);
        values.push(ids.reduce((a, id) => a + records.get(id).value, 0) / 9);
        eliteCounts.push(
          ids.filter((id) => records.get(id).tier === 'elite').length,
        );
        lowPaCounts.push(
          ids.filter((id) => records.get(id).historicalPa < 200).length,
        );
        ids.forEach((id) => {
          picked.add(id);
          tierCounts[records.get(id).tier]++;
        });
        rosters.add([...ids].sort().join(','));
      }
      const row = {
        policy,
        budget,
        agent,
        trials,
        completed: costs.length,
        minimumCost,
        cost: stats(costs),
        remaining: stats(remaining),
        choices,
        oneChoiceRoundRate:
          choices.reduce((a, r) => a + r.one, 0) / (9 * trials),
        meanSelectableOffers:
          choices.reduce((a, r) => a + r.one + 2 * r.two + 3 * r.three, 0) /
          (9 * trials),
        meanMarginalValueIndex: stats(values),
        elitePlayersPerDraft: stats(eliteCounts),
        draftsWithEliteRate: eliteCounts.filter((x) => x > 0).length / trials,
        lowPaPlayersPerDraft: stats(lowPaCounts),
        selectedTierCounts: tierCounts,
        distinctRosters: rosters.size,
        distinctPickedPlayers: picked.size,
        checkedSafeOffers: checkedOffers,
        timings: {
          initializationAndFirstOfferMs: stats(firstMs),
          selectionMs: stats(selectionMs),
          totalComputeMs: stats(totalMs),
        },
      };
      cases.push(row);
      console.log(
        `${policy}/${budget}/${agent}: ${trials} complete, cost ${row.cost.mean.toFixed(1)}, one-choice ${(100 * row.oneChoiceRoundRate).toFixed(2)}%, elite ${row.elitePlayersPerDraft.mean.toFixed(2)}`,
      );
    }
const report = {
  schemaVersion: '1.0.0',
  studyVersion: 'mlb-pricing-draft-study-v1',
  datasetId: study.datasetId,
  measurementSha256: study.measurementSha256,
  paStudySha256: digest(study),
  engineSourceSha256: createHash('sha256').update(engineSource).digest('hex'),
  trialsPerCase: trials,
  totalDrafts: cases.reduce((a, c) => a + c.completed, 0),
  note: 'Actual protected-offer TypeScript engine; all displayed branches checked; fixed common draft seeds; value index is a roster-construction diagnostic, not additive predicted runs. Fresh engine/cache per draft, warmed JS/JIT; timings exclude agent selection and safety assertions, not first-visit/browser/mobile costs.',
  cases,
};
writeFileSync(
  resolve(output, 'draft-budgets.json'),
  JSON.stringify(report, null, 2) + '\n',
);
