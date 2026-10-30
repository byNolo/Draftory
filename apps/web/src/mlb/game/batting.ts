import { object, type Player } from '../../lib/api/player-data';
import type { BattingLine } from '../../workers/protocol';
import type { DraftPlayer } from '../draft/engine';

export function ratio(n: number | null, d: number | null) {
  return n === null || d === null || d === 0 ? null : n / d;
}
export function rate(value: number | null) {
  return value === null ? '—' : value.toFixed(3).replace(/^0\./, '.');
}
export function simulatedRates(s: BattingLine) {
  return {
    avg: ratio(s.hits, s.atBats),
    obp: ratio(
      s.hits + s.walks + s.hitByPitch,
      s.atBats + s.walks + s.hitByPitch,
    ),
    slg: ratio(
      s.singles + 2 * s.doubles + 3 * s.triples + 4 * s.homeRuns,
      s.atBats,
    ),
  };
}
export interface HistoricalBatting {
  avg: number | null;
  obp: number | null;
  slg: number | null;
  hr: number | null;
  sb: number | null;
  cs: number | null;
  sbPct: number | null;
  pa: number | null;
  teams: string[];
}
// Sum source-grain stints once. Unknown is never silently replaced by zero.
export function historicalBatting(
  player: Player,
  expected: DraftPlayer,
  year: number,
): HistoricalBatting {
  if (
    player.id !== expected.id ||
    player.profileId !== expected.profileId ||
    player.year !== year ||
    !player.stints.length
  )
    throw new Error('Historical player metadata does not match this draft.');
  const seen = new Set<string>();
  for (const stint of player.stints) {
    const key = JSON.stringify([stint.stint, stint.teamId, stint.leagueId]);
    if (seen.has(key)) throw new Error('Duplicate historical batting stint.');
    seen.add(key);
  }
  function total(key: string) {
    let sum = 0;
    for (const stint of player.stints) {
      const n = object(stint.counts)[key];
      if (n === null || n === undefined) return null;
      if (typeof n !== 'number' || !Number.isSafeInteger(n) || n < 0)
        throw new Error('Invalid historical batting count.');
      sum += n;
    }
    return sum;
  }
  const ab = total('AB'),
    h = total('H'),
    bb = total('BB'),
    hbp = total('HBP'),
    sf = total('SF'),
    sh = total('SH');
  const doubles = total('2B'),
    triples = total('3B'),
    hr = total('HR');
  const add = (...ns: (number | null)[]) =>
    ns.some((n) => n === null)
      ? null
      : (ns as number[]).reduce((a, b) => a + b, 0);
  const bases =
    h === null || doubles === null || triples === null || hr === null
      ? null
      : h + doubles + 2 * triples + 3 * hr;
  if (
    (ab !== null && h !== null && h > ab) ||
    (h !== null &&
      doubles !== null &&
      triples !== null &&
      hr !== null &&
      doubles + triples + hr > h)
  )
    throw new Error('Inconsistent historical batting totals.');
  const pa = add(ab, bb, hbp, sh, sf);
  const sb = total('SB'),
    cs = total('CS');
  if (pa !== null && pa !== expected.pa)
    throw new Error(
      'Historical plate appearances differ from the pinned catalog.',
    );
  return {
    avg: ratio(h, ab),
    obp: ratio(add(h, bb, hbp), add(ab, bb, hbp, sf)),
    slg: ratio(bases, ab),
    hr,
    sb,
    cs,
    sbPct: ratio(sb, add(sb, cs)),
    pa,
    teams: [
      ...new Set(player.stints.map((s) => String(s.teamName ?? s.teamId))),
    ],
  };
}
