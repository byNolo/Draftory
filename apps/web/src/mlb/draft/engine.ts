// MLB-only, deterministic local computation. No React, fetch, clocks or simulator.
export const POSITIONS = [
  'C',
  '1B',
  '2B',
  '3B',
  'SS',
  'LF',
  'CF',
  'RF',
  'DH',
] as const;
export type Position = (typeof POSITIONS)[number];
export const RULES = 'mlb-protected-draft-v1';
export const RNG = 'mulberry32-rejection-v1';
export interface DraftPlayer {
  id: string;
  name: string;
  profileId: string;
  positions: Position[];
  games: Record<Position, number | null>;
  pa: number;
  price: number;
}
export interface Catalog {
  id: string;
  schemaVersion: string;
  datasetId: string;
  year: number;
  sourceId: string;
  profilePolicyId: string;
  contextId: string;
  pricingPolicy: string;
  eligibilityPolicy: string;
  researchMeasurementSha256: string;
  sourceSqlSha256: string;
  attribution: string;
  players: DraftPlayer[];
}
export interface DraftConfig {
  budget: number;
  offers: number;
  order: Position[];
  minGames: number;
  minPa: number;
  universalDh: boolean;
}
export const DEFAULTS: DraftConfig = {
  budget: 90,
  offers: 3,
  order: ['C', 'SS', 'CF', '1B', '2B', '3B', 'LF', 'RF', 'DH'],
  minGames: 10,
  minPa: 50,
  universalDh: true,
};
export interface Pick {
  position: Position;
  playerId: string;
  price: number;
  offers: string[];
}
export interface DraftState {
  schemaVersion: '1.0.0';
  rulesVersion: typeof RULES;
  rngVersion: typeof RNG;
  catalogId: string;
  seed: string;
  config: DraftConfig;
  rngState: number;
  remainingBudget: number;
  history: Pick[];
  offers: string[];
  excludedUnsafeCandidates: number;
  status: 'drafting' | 'complete';
}
export class DraftError extends Error {}
function frozen<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    Object.values(value).forEach(frozen);
    Object.freeze(value);
  }
  return value;
}
function check(ok: unknown, message: string): asserts ok {
  if (!ok) throw new DraftError(message);
}
export function eligible(p: DraftPlayer, pos: Position, config: DraftConfig) {
  return (
    p.pa >= config.minPa &&
    ((pos === 'DH' && config.universalDh) ||
      (p.games[pos] !== null && p.games[pos] >= config.minGames))
  );
}
// Integer Hungarian assignment; INF represents absent eligibility edges.
const INF = 1_000_000;
export function minimumAssignment(costs: number[][]): number | null {
  const n = costs.length;
  if (!n) return 0;
  const m = costs[0].length;
  if (m < n) return null;
  const u = Array<number>(n + 1).fill(0),
    v = Array<number>(m + 1).fill(0);
  const p = Array<number>(m + 1).fill(0),
    way = Array<number>(m + 1).fill(0);
  for (let i = 1; i <= n; i++) {
    p[0] = i;
    let j0 = 0;
    const d = Array<number>(m + 1).fill(INF),
      used = Array<boolean>(m + 1).fill(false);
    do {
      used[j0] = true;
      const i0 = p[j0];
      let delta = INF,
        j1 = 0;
      for (let j = 1; j <= m; j++)
        if (!used[j]) {
          const cur = costs[i0 - 1][j - 1] - u[i0] - v[j];
          if (cur < d[j]) {
            d[j] = cur;
            way[j] = j0;
          }
          if (d[j] < delta) {
            delta = d[j];
            j1 = j;
          }
        }
      if (delta >= INF) return null;
      for (let j = 0; j <= m; j++) {
        if (used[j]) {
          u[p[j]] += delta;
          v[j] -= delta;
        } else d[j] -= delta;
      }
      j0 = j1;
    } while (p[j0]);
    do {
      const j1 = way[j0];
      p[j0] = p[j1];
      j0 = j1;
    } while (j0);
  }
  let total = 0;
  for (let j = 1; j <= m; j++)
    if (p[j]) {
      const c = costs[p[j] - 1][j - 1];
      if (c >= INF) return null;
      total += c;
    }
  return total;
}
export function drawIndex(state: number, bound: number): [number, number] {
  check(
    Number.isInteger(bound) && bound > 0 && bound <= 0xffffffff,
    'Invalid RNG bound',
  );
  const limit = 4294967296 - (4294967296 % bound);
  for (;;) {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    const value = (t ^ (t >>> 14)) >>> 0;
    if (value < limit) return [value % bound, state];
  }
}

export class DraftEngine {
  readonly catalog: Catalog;
  readonly config: DraftConfig;
  private readonly players: Map<string, DraftPlayer>;
  private readonly pools: Record<Position, DraftPlayer[]>;
  private readonly relevant: Set<string>;
  private readonly costs = new Map<string, number | null>();
  constructor(catalog: Catalog, config: DraftConfig = DEFAULTS) {
    check(
      Number.isInteger(config.budget) &&
        config.budget >= 0 &&
        config.budget <= 180,
      'Budget must be 0..180',
    );
    check(
      Number.isInteger(config.offers) &&
        config.offers >= 1 &&
        config.offers <= 10,
      'Offer count must be 1..10',
    );
    check(
      config.order.length === 9 &&
        new Set(config.order).size === 9 &&
        config.order.every((p) => POSITIONS.includes(p)),
      'Order must contain each position once',
    );
    check(
      Number.isInteger(config.minGames) &&
        config.minGames >= 1 &&
        Number.isInteger(config.minPa) &&
        config.minPa >= 50 &&
        typeof config.universalDh === 'boolean',
      'Invalid eligibility settings (published floor is 50 PA)',
    );
    check(
      catalog.players.length > 0 && catalog.players.length <= 2000,
      'Invalid catalog size',
    );
    check(
      new Set(catalog.players.map((p) => p.id)).size ===
        catalog.players.length &&
        new Set(catalog.players.map((p) => p.profileId)).size ===
          catalog.players.length,
      'Duplicate player/profile identity',
    );
    for (const p of catalog.players) {
      check(
        typeof p.id === 'string' &&
          typeof p.profileId === 'string' &&
          typeof p.name === 'string' &&
          Number.isInteger(p.price) &&
          p.price >= 1 &&
          p.price <= 20 &&
          Number.isInteger(p.pa) &&
          p.pa >= 50 &&
          POSITIONS.every(
            (pos) =>
              p.games[pos] === null ||
              (Number.isInteger(p.games[pos]) && p.games[pos]! >= 0),
          ),
        'Invalid draft player',
      );
    }
    this.catalog = frozen(structuredClone(catalog));
    this.config = frozen(structuredClone(config));
    this.players = new Map(this.catalog.players.map((p) => [p.id, p]));
    this.pools = Object.fromEntries(
      POSITIONS.map((pos) => [
        pos,
        this.catalog.players
          .filter((p) => eligible(p, pos, this.config))
          .sort(
            (a, b) =>
              a.price - b.price || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
          ),
      ]),
    ) as Record<Position, DraftPlayer[]>;
    // Only first 18/slot can affect nine choices with at most nine excluded IDs.
    this.relevant = new Set(
      Object.values(this.pools).flatMap((pool) =>
        pool.slice(0, 18).map((p) => p.id),
      ),
    );
  }
  player(id: string) {
    const p = this.players.get(id);
    check(p, 'Unknown player');
    return structuredClone(p);
  }
  minimum(
    positions: Position[],
    selected: readonly string[] = [],
  ): number | null {
    check(
      positions.length <= 9 &&
        new Set(positions).size === positions.length &&
        selected.length <= 9,
      'Matching supports nine distinct slots and at most nine excluded identities',
    );
    const banned = new Set(selected);
    const key =
      positions.join(',') +
      ':' +
      selected
        .filter((p) => this.relevant.has(p))
        .sort()
        .join(',');
    if (this.costs.has(key)) return this.costs.get(key)!;
    const candidates = new Map<string, DraftPlayer>();
    for (const pos of positions)
      for (const p of this.pools[pos]
        .filter((p) => !banned.has(p.id))
        .slice(0, positions.length))
        candidates.set(p.id, p);
    const value = minimumAssignment(
      positions.map((pos) =>
        [...candidates.values()].map((p) =>
          eligible(p, pos, this.config) ? p.price : INF,
        ),
      ),
    );
    if (this.costs.size >= 8192) this.costs.clear();
    this.costs.set(key, value);
    return value;
  }
  start(seed: string): DraftState {
    check(
      /^(0|[1-9][0-9]{0,9})$/.test(seed) && BigInt(seed) <= 4294967295n,
      'Draft seed must be a canonical unsigned 32-bit decimal',
    );
    const cost = this.minimum(this.config.order);
    check(
      cost !== null && cost <= this.config.budget,
      'No legal continuation: initial budget or eligible pool is infeasible',
    );
    return this.next({
      schemaVersion: '1.0.0',
      rulesVersion: RULES,
      rngVersion: RNG,
      catalogId: this.catalog.id,
      seed,
      config: structuredClone(this.config),
      rngState: Number(seed),
      remainingBudget: this.config.budget,
      history: [],
      offers: [],
      excludedUnsafeCandidates: 0,
      status: 'drafting',
    });
  }
  private next(state: DraftState): DraftState {
    const pos = this.config.order[state.history.length];
    const selected = state.history.map((p) => p.playerId);
    const candidates = this.pools[pos]
      .filter((p) => !selected.includes(p.id))
      .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const safe = candidates.filter((p) => {
      if (p.price > state.remainingBudget) return false;
      const cost = this.minimum(
        this.config.order.slice(state.history.length + 1),
        [...selected, p.id],
      );
      return cost !== null && p.price + cost <= state.remainingBudget;
    });
    check(safe.length, 'No legal continuation: no safe offer');
    // Uniform without replacement on safe eligible identities. Protection conditions
    // the distribution on affordability and completion, not the unfiltered pool.
    let rng = state.rngState;
    const offers: string[] = [];
    for (let i = 0; i < Math.min(this.config.offers, safe.length); i++) {
      let offset: number;
      [offset, rng] = drawIndex(rng, safe.length - i);
      [safe[i], safe[i + offset]] = [safe[i + offset], safe[i]];
      offers.push(safe[i].id);
    }
    return frozen({
      ...state,
      rngState: rng,
      offers,
      excludedUnsafeCandidates:
        state.excludedUnsafeCandidates + candidates.length - safe.length,
    });
  }
  select(state: DraftState, id: string): DraftState {
    // States are values from this engine. Imported histories must use replay().
    check(
      state.schemaVersion === '1.0.0' &&
        state.catalogId === this.catalog.id &&
        state.config.budget === this.config.budget &&
        state.config.offers === this.config.offers &&
        state.config.minGames === this.config.minGames &&
        state.config.minPa === this.config.minPa &&
        state.config.universalDh === this.config.universalDh &&
        state.config.order.length === this.config.order.length &&
        state.config.order.every(
          (position, i) => position === this.config.order[i],
        ) &&
        state.rulesVersion === RULES &&
        state.rngVersion === RNG,
      'Draft versions/configuration differ',
    );
    check(
      state.status === 'drafting' &&
        state.history.length < 9 &&
        state.offers.includes(id),
      'Selection is not a current selectable offer',
    );
    const p = this.player(id),
      pos = this.config.order[state.history.length];
    const selected = state.history.map((p) => p.playerId);
    check(
      !selected.includes(id) && eligible(p, pos, this.config),
      'Duplicate or ineligible selection',
    );
    check(
      new Set(selected).size === selected.length &&
        state.history.every(
          (pick, i) =>
            pick.position === this.config.order[i] &&
            pick.price === this.player(pick.playerId).price &&
            eligible(this.player(pick.playerId), pick.position, this.config),
        ) &&
        state.remainingBudget ===
          this.config.budget -
            state.history.reduce((sum, p) => sum + p.price, 0),
      'Invalid history or remaining budget; import drafts through replay',
    );
    const budget = state.remainingBudget - p.price;
    const minimum = this.minimum(
      this.config.order.slice(state.history.length + 1),
      [...selected, id],
    );
    check(
      minimum !== null && minimum <= budget,
      'Selection would leave no legal continuation',
    );
    const next: DraftState = {
      ...state,
      remainingBudget: budget,
      history: [
        ...structuredClone(state.history),
        {
          position: pos,
          playerId: id,
          price: p.price,
          offers: [...state.offers],
        },
      ],
      offers: [],
      status: state.history.length === 8 ? 'complete' : 'drafting',
    };
    return next.status === 'complete' ? frozen(next) : this.next(next);
  }
  replay(seed: string, picks: readonly string[]): DraftState {
    let state = this.start(seed);
    for (const id of picks) state = this.select(state, id);
    return state;
  }
}
