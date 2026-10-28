import { DataError, type PreparedProfile } from '../lib/api/player-data';
import {
  hash,
  canonical,
  validateProfile,
  type Pilot,
  type SeasonInput,
} from './season-input';

export const OPPONENT_ID =
  'opponents:29182146a03008ee33def9b5474956da826163debf4c1b2b97baab43a9c12ce8';
export interface Opponent {
  id: string;
  sourceTeamId: string;
  name: string;
  abbreviation: string;
  year: number;
  lineup: {
    id: string;
    profileId: string;
    playerId: string;
    name: string;
    teamPa: number;
  }[];
}
export interface OpponentPublication {
  id: string;
  schemaVersion: string;
  datasetId: string;
  sourceId: string;
  policyId: string;
  contextId: string;
  transitionModelId: string;
  engineVersion: string;
  year: number;
  selectionVersion: string;
  scheduleVersion: string;
  opponentSetKind: 'reconstructedFixedLineups';
  opponents: Opponent[];
  profiles: PreparedProfile[];
}
function check(ok: unknown, message: string): asserts ok {
  if (!ok) throw new DataError('incompatibleInput', message);
}
const verified = new WeakSet<OpponentPublication>();
const verifiedProfiles = new WeakSet<OpponentPublication>();
function immutable<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    Object.values(value).forEach(immutable);
    Object.freeze(value);
  }
  return value;
}
export async function parseOpponents(
  payload: unknown,
): Promise<OpponentPublication> {
  check(payload && typeof payload === 'object', 'Missing opponent publication');
  if (verified.has(payload as OpponentPublication))
    return payload as OpponentPublication;
  // Snapshot before async hashing so caller mutation cannot race verification.
  const snapshot = structuredClone(payload);
  const { id, ...body } = snapshot as Record<string, unknown>;
  check(
    id === OPPONENT_ID && id === 'opponents:' + (await hash(body)),
    'Opponent publication digest/version differs from this build',
  );
  const p = snapshot as OpponentPublication;
  check(
    p.schemaVersion === '1.0.0' &&
      p.year === 2024 &&
      p.engineVersion === '0.4.0' &&
      p.selectionVersion === 'team-pa-ranked-nine-full-season-profiles-v1' &&
      p.scheduleVersion === 'round-robin-season-v1' &&
      p.opponentSetKind === 'reconstructedFixedLineups',
    'Unsupported opponent selection/schedule',
  );
  check(
    p.opponents.length === 9 &&
      new Set(p.opponents.map((t) => t.id)).size === 9 &&
      new Set(p.profiles.map((r) => r.id)).size === p.profiles.length,
    'Duplicate or missing opponents/profiles',
  );
  const profiles = new Map(p.profiles.map((r) => [r.id, r]));
  for (const t of p.opponents) {
    check(
      t.year === p.year &&
        t.lineup.length === 9 &&
        new Set(t.lineup.map((b) => b.playerId)).size === 9 &&
        t.lineup.every(
          (b) =>
            profiles.get(b.profileId)?.provenance.playerId === b.playerId &&
            b.id === `${t.id}:${b.playerId}`,
        ),
      'Invalid opponent lineup identities',
    );
  }
  immutable(p);
  verified.add(p);
  return p;
}
export async function withOpponents(
  input: SeasonInput,
  publication: OpponentPublication,
  pilot: Pilot,
  datasetId: string,
): Promise<SeasonInput> {
  const p = await parseOpponents(publication);
  check(
    p.datasetId === datasetId &&
      p.sourceId === pilot.sourceId &&
      p.policyId === pilot.policyId &&
      p.contextId === pilot.leagueContextId &&
      p.transitionModelId === input.config.contextualModel.id &&
      p.scheduleVersion === input.modelVersion,
    'Opponent source/context/model mismatch',
  );
  if (!verifiedProfiles.has(p)) {
    await Promise.all(
      p.profiles.map((profile) => validateProfile(profile, pilot)),
    );
    verifiedProfiles.add(p);
  }
  const used = new Set(input.userTeam.lineup.map((b) => b.profileId));
  const profiles = new Map(
    input.profiles.filter((r) => used.has(r.id)).map((r) => [r.id, r]),
  );
  for (const profile of p.profiles) {
    const previous = profiles.get(profile.id);
    check(
      !previous ||
        JSON.stringify(canonical(previous)) ===
          JSON.stringify(canonical(profile)),
      'Conflicting opponent profile',
    );
    profiles.set(profile.id, structuredClone(profile));
  }
  return {
    ...input,
    opponentSetKind: p.opponentSetKind,
    opponents: p.opponents.map((t) => ({
      id: t.id,
      lineup: t.lineup.map(({ id, profileId }) => ({ id, profileId })),
    })),
    profiles: [...profiles.values()].sort((a, b) =>
      a.id < b.id ? -1 : a.id > b.id ? 1 : 0,
    ),
  };
}
