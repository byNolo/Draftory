"""Offline policy experiments only; no application draft state or production prices."""

import hashlib
import math
import random
from dataclasses import asdict, dataclass
from functools import lru_cache
from statistics import mean

from .source import DataError, canonical_bytes

POSITIONS = ("C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH")
INF = 10**9


@dataclass(frozen=True)
class EligibilityPolicy:
    name: str
    min_games: int
    universal_dh: bool = False
    broad_of: bool = False
    min_pa: int = 50

    def __post_init__(self):
        if type(self.min_games) is not int or self.min_games < 1 or self.min_pa < 1:
            raise DataError("Positive appearance/PA thresholds required")


POLICIES = (
    EligibilityPolicy("recorded-1", 1),
    EligibilityPolicy("recorded-5", 5),
    EligibilityPolicy("recorded-10", 10),
    EligibilityPolicy("games-10-dh-all", 10, True),
    EligibilityPolicy("games-20-dh-all", 20, True),
    EligibilityPolicy("games-10-broad-of-dh-all", 10, True, True),
    EligibilityPolicy("games-10-dh-all-pa200", 10, True, min_pa=200),
    EligibilityPolicy("games-10-dh-all-pa400", 10, True, min_pa=400),
)


def eligibility(player: dict, policy: EligibilityPolicy) -> tuple[str, ...]:
    if player["pa"] < policy.min_pa:
        return ()
    games = player["appearances"]
    result = []
    for pos in POSITIONS:
        observed = games.get(pos)
        qualifies = observed is not None and observed >= policy.min_games
        if pos == "DH" and policy.universal_dh:
            qualifies = True
        if pos in ("LF", "CF", "RF") and policy.broad_of:
            of = games.get("OF")
            qualifies |= of is not None and of >= policy.min_games
        if qualifies:
            result.append(pos)
    return tuple(result)


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    if not values or any(not math.isfinite(v) for v in values.values()):
        raise DataError("Finite, nonempty valuation sample required")
    ordered = sorted(values, key=lambda pid: (values[pid], pid))
    ranks = {}
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = (start + end - 1) / (2 * (len(ordered) - 1)) if len(ordered) > 1 else 0.5
        ranks.update(dict.fromkeys(ordered[start:end], rank))
        start = end
    return ranks


def price_quotes(values: dict[str, float], pools: dict[str, list[str]], curve: str):
    """Illustrative currency only, scaled linearly/quadratically over measured values."""
    percentile_ranks(values)  # Validate the finite, nonempty sample.
    low, high = min(values.values()), max(values.values())
    if curve not in ("linear", "elite", "scarcity"):
        raise DataError("Unknown research price curve")
    quotes = {}
    for pos, ids in pools.items():
        premium = 2 * math.log2(len(values) / len(ids)) if ids and curve == "scarcity" else 0
        for pid in ids:
            q = (values[pid] - low) / (high - low) if high > low else 0.5
            base = 1 + (29 * q * q if curve == "elite" else 19 * q)
            quotes[pid, pos] = math.floor(base + premium + 0.5)
    return quotes


def assignment(costs: list[list[int]]) -> tuple[int, list[int]] | None:
    """Rectangular Hungarian minimization; missing edges use INF. No external solver."""
    n = len(costs)
    if not n:
        return 0, []
    m = len(costs[0])
    if m < n or any(len(row) != m for row in costs):
        return None
    u, v, matched, previous = [0] * (n + 1), [0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        matched[0] = i
        j0 = 0
        distance, used = [INF] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = matched[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    current = costs[i0 - 1][j - 1] - u[i0] - v[j]
                    if current < distance[j]:
                        distance[j], previous[j] = current, j0
                    if distance[j] < delta:
                        delta, j1 = distance[j], j
            if delta >= INF:
                return None
            for j in range(m + 1):
                if used[j]:
                    u[matched[j]] += delta
                    v[j] -= delta
                else:
                    distance[j] -= delta
            j0 = j1
            if not matched[j0]:
                break
        while j0:
            j1 = previous[j0]
            matched[j0] = matched[j1]
            j0 = j1
    columns = [-1] * n
    for j in range(1, m + 1):
        if matched[j]:
            columns[matched[j] - 1] = j - 1
    chosen = [costs[i][j] for i, j in enumerate(columns)]
    return None if max(chosen) >= INF else (sum(chosen), columns)


class CompletionCosts:
    """Exact cheapest distinct-player completion, not nine independent slot minima."""

    def __init__(self, pools: dict[str, list[str]], quotes: dict):
        self.quotes = quotes
        self.ordered = {
            pos: sorted(ids, key=lambda pid: (quotes[pid, pos], pid)) for pos, ids in pools.items()
        }
        self.relevant = {pid for ids in self.ordered.values() for pid in ids[:18]}
        self.cached_solve = lru_cache(maxsize=8192)(self._solve)

    def minimum(self, positions: tuple[str, ...], selected: frozenset[str] = frozenset()):
        # With <=9 blocked identities, only the first 18 in any position can affect
        # its cheapest nine available choices. Normalize cache keys, not constraints.
        blocked = selected & self.relevant if len(selected) <= 9 else selected
        return self.cached_solve(positions, tuple(sorted(blocked)))

    def _solve(self, positions: tuple[str, ...], blocked: tuple[str, ...]):
        if not positions:
            return 0, {}
        banned = set(blocked)
        candidates = sorted(
            {
                pid
                for pos in positions
                for pid in [p for p in self.ordered[pos] if p not in banned][: len(positions)]
            }
        )
        # An optimum needs only the n cheapest available candidates per slot:
        # at most n-1 can be occupied by other slots, leaving a cheaper swap.
        matrix = [[self.quotes.get((pid, pos), INF) for pid in candidates] for pos in positions]
        result = assignment(matrix)
        if result is None:
            return None
        cost, columns = result
        return cost, {pos: candidates[j] for pos, j in zip(positions, columns, strict=True)}


def experiment(
    values: dict[str, float],
    pools: dict[str, list[str]],
    quotes: dict,
    *,
    budget: int,
    offers: str,
    selection: str,
    trials: int,
    seed: int,
    order: tuple[str, ...] = POSITIONS,
) -> dict:
    if offers not in ("global", "position", "tier") or selection not in (
        "greedy",
        "reserve",
        "protected",
    ):
        raise DataError("Unknown offline experiment")
    if trials < 1 or len(order) != 9 or set(order) != set(POSITIONS):
        raise DataError("Require positive trials and all nine slots")
    solver = CompletionCosts(pools, quotes)
    minimum = solver.minimum(order)
    config = {"budget": budget, "offers": offers, "selection": selection, "order": order}
    rng = random.Random(int(hashlib.sha256(canonical_bytes([seed, config])).hexdigest(), 16))
    failures, completed, rescued, rounds, multiple, choices, spreads = {}, 0, 0, 0, 0, [], []
    pool_sets = {pos: set(ids) for pos, ids in pools.items()}
    global_ids = sorted(values)
    tier_pools = {}
    for pos, ids in pools.items():
        ordered = sorted(ids, key=lambda pid: (values[pid], pid))
        tier_pools[pos] = [ordered[i * len(ids) // 3 : (i + 1) * len(ids) // 3] for i in range(3)]
    initially_feasible = minimum is not None and minimum[0] <= budget
    for _ in range(trials if initially_feasible else 0):
        selected, remaining_budget = frozenset(), budget
        for index, pos in enumerate(order):
            remaining = order[index + 1 :]
            if offers == "tier":
                offered = []
                for tier in tier_pools[pos]:
                    options = [p for p in tier if p not in selected]
                    if options:
                        offered.append(rng.choice(options))
            else:
                options = [
                    p
                    for p in (global_ids if offers == "global" else pools[pos])
                    if p not in selected
                ]
                offered = rng.sample(options, min(3, len(options)))
            eligible = [p for p in offered if p in pool_sets[pos]]
            affordable = [p for p in eligible if quotes[p, pos] <= remaining_budget]

            safe_options = []
            for pid in affordable:
                completion = solver.minimum(remaining, selected | {pid})
                if completion is not None and quotes[pid, pos] + completion[0] <= remaining_budget:
                    safe_options.append(pid)
            if selection == "protected" and not safe_options:
                completion = solver.minimum(order[index:], selected)
                if completion is None or completion[0] > remaining_budget:
                    raise DataError("Protected experiment lost its completion invariant")
                safe_options = [completion[1][pos]]
                rescued += 1
            rounds += 1
            multiple += len(safe_options) >= 2
            choices.append(len(safe_options))
            if len(safe_options) >= 2:
                spreads.append(
                    max(values[p] for p in safe_options) - min(values[p] for p in safe_options)
                )
            options = affordable if selection == "greedy" else safe_options
            if not options:
                reason = (
                    "noEligibleOffer"
                    if not eligible
                    else "noAffordableOffer"
                    if not affordable
                    else "noCompletableOffer"
                )
                failures[reason] = failures.get(reason, 0) + 1
                break
            chosen = max(options, key=lambda pid: (values[pid], pid))
            remaining_budget -= quotes[chosen, pos]
            selected |= {chosen}
            if selection == "greedy":
                completion = solver.minimum(remaining, selected)
                if completion is None or completion[0] > remaining_budget:
                    failures["choiceDestroyedCompletion"] = (
                        failures.get("choiceDestroyedCompletion", 0) + 1
                    )
                    break
        else:
            if len(selected) != 9:
                raise DataError("Duplicate identity in completed research lineup")
            completed += 1
    rate = completed / trials
    # Wilson interval remains informative at zero/all successes. Structural
    # infeasibility is exact for this pool/price matrix, not a sampling estimate.
    z = 1.959963984540054
    denominator = 1 + z * z / trials
    center = (rate + z * z / (2 * trials)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials**2)) / denominator
    return {
        **config,
        "seed": seed,
        "rngVersion": "python-random-mt19937-sha256-config-v1",
        "offerSize": 3,
        "trials": trials,
        "simulatedTrials": trials if initially_feasible else 0,
        "initiallyFeasible": initially_feasible,
        "minimumLineupCost": minimum[0] if minimum else None,
        "completed": completed,
        "completionRate": rate,
        "completionMonteCarloSe": math.sqrt(rate * (1 - rate) / trials)
        if initially_feasible
        else None,
        "completionWilson95": [max(0, center - radius), min(1, center + radius)]
        if initially_feasible
        else None,
        "failures": failures,
        "protectedInsertions": rescued,
        "observedRounds": rounds,
        "meanSafeOfferCount": mean(choices) if choices else None,
        "multipleSafeChoiceRate": multiple / rounds if rounds else None,
        "meanSafeValueSpread": mean(spreads) if spreads else None,
    }


def policy_counts(players: list[dict], policy: EligibilityPolicy) -> dict:
    qualified = {p["id"]: eligibility(p, policy) for p in players}
    return {
        "policy": asdict(policy),
        "counts": {
            pos: sum(pos in eligible for eligible in qualified.values()) for pos in POSITIONS
        },
        "multipleFieldingPositions": sum(len(set(e) - {"DH"}) > 1 for e in qualified.values()),
        "noFieldingPosition": sum(not (set(e) - {"DH"}) for e in qualified.values()),
        "noEligiblePosition": sum(not e for e in qualified.values()),
    }
