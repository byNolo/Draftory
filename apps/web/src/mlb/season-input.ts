import type fixture from '../../../../crates/baseball-sim/tests/fixtures/season-modern-2024.json';
import {
  DataError,
  object,
  parseProfile,
  type Dataset,
  type Player,
  type PreparedProfile,
} from '../lib/api/player-data';
import { PILOT_ID } from '../generated/pilot-meta';

// Shapes reuse the existing v1 season fixture; no fixture bytes enter this module.
export type SeasonInput = Omit<typeof fixture, 'profiles'> & {
  profiles: PreparedProfile[];
};
export interface Pilot {
  id: string;
  schemaVersion: string;
  engineVersion: string;
  fixtureSha256: string;
  year: number;
  sourceId: string;
  policyId: string;
  leagueContextId: string;
  transitionModelId: string;
  userTeamId: string;
  userPlayerIds: string[];
  season: Omit<SeasonInput, 'profiles' | 'userTeam' | 'seed'>;
  opponentProfiles: PreparedProfile[];
}
export function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.entries(value)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([k, v]) => [k, canonical(v)]),
    );
  return value;
}
export async function hash(value: unknown) {
  if (!crypto.subtle)
    throw new DataError(
      'unsupportedEnvironment',
      'Verified data loading requires HTTPS or localhost Web Crypto',
    );
  const bytes = new TextEncoder().encode(JSON.stringify(canonical(value)));
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
function requireMatch(condition: unknown, message: string): asserts condition {
  if (!condition) throw new DataError('incompatibleInput', message);
}

export async function parsePilot(payload: unknown): Promise<Pilot> {
  const value = object(payload);
  const { id, ...body } = value;
  requireMatch(
    id === PILOT_ID && id === 'pilot:' + (await hash(body)),
    'Pilot artifact digest mismatch',
  );
  requireMatch(
    value.schemaVersion === '1.0.0' &&
      value.engineVersion === '0.4.0' &&
      value.fixtureSha256 ===
        'd02959d2673eeeec2951644cf327434babefeddeb1cb5b516d809d3aa8a562a4',
    'Unsupported pilot/engine/fixture version',
  );
  const pilot = value as unknown as Pilot;
  requireMatch(
    pilot.season.schemaVersion === '1.0.0' &&
      pilot.season.gameSchemaVersion === '1.2.0' &&
      pilot.season.rulesVersion === 'contextual-nine-inning-v1' &&
      pilot.season.config.advancementPolicy === 'retrosheet-contextual-v1',
    'Unsupported season/game rules',
  );
  requireMatch(
    pilot.season.modelVersion === 'round-robin-season-v1' &&
      pilot.season.seedDerivationVersion === 'splitmix64-index-v1' &&
      pilot.season.sampling.rngVersion === 'splitmix64-v1' &&
      pilot.season.games === 162,
    'Unsupported season sampling/configuration',
  );
  requireMatch(
    pilot.season.config.contextualModel.id === pilot.transitionModelId &&
      pilot.season.config.contextualModel.modelVersion ===
        'retrosheet-contact-transitions-v1',
    'Missing/incompatible contextual transition model',
  );
  requireMatch(
    pilot.season.pitchingEnvironment.mode === 'leagueAverage' &&
      pilot.season.pitchingEnvironment.contextId === pilot.leagueContextId,
    'League context is not compatible with pilot',
  );
  requireMatch(
    pilot.userPlayerIds.length === 9 &&
      new Set(pilot.userPlayerIds).size === 9 &&
      pilot.season.opponents.length === 1,
    'Pilot lineup shape is invalid',
  );
  await Promise.all(
    pilot.opponentProfiles.map((p) => validateProfile(p, pilot)),
  );
  return pilot;
}

export function validateDataset(dataset: Dataset, pilot: Pilot) {
  requireMatch(
    dataset.schemaVersion === '1.0.0' &&
      dataset.sport === 'mlb' &&
      dataset.year === pilot.year &&
      dataset.inputSchemaVersion === '1.2.0' &&
      dataset.modelVersion === 'lahman-contact-adapter-v1' &&
      dataset.profileType === 'season' &&
      dataset.aggregation === 'aggregate',
    'Choose the compatible 2024 MLB season-aggregate dataset',
  );
  requireMatch(
    dataset.sourceId === pilot.sourceId &&
      dataset.policy.id === pilot.policyId &&
      dataset.contextId === pilot.leagueContextId,
    'Source, preparation policy or league baseline differs from pilot',
  );
}
export async function validateProfile(value: PreparedProfile, pilot: Pilot) {
  const p = parseProfile(value);
  const { id, ...body } = p;
  requireMatch(
    id === 'prepared:' + (await hash(body)),
    'Prepared profile digest mismatch',
  );
  const keys = [
    'single',
    'double',
    'triple',
    'homeRun',
    'walk',
    'hitByPitch',
    'strikeout',
    'battedBallOut',
    'otherContact',
  ];
  requireMatch(
    Object.keys(p.weights).length === keys.length &&
      keys.every((k) => Object.hasOwn(p.weights, k)) &&
      Object.values(p.weights).reduce((a, b) => a + b, 0) === 1000000 &&
      p.weights.battedBallOut === 0,
    'Invalid contextual outcome weights',
  );
  requireMatch(
    p.modelVersion === 'lahman-contact-adapter-v1' &&
      p.provenance.transformationVersion === p.modelVersion &&
      p.provenance.sourceId === pilot.sourceId &&
      p.provenance.policyId === pilot.policyId &&
      p.provenance.contextId === pilot.leagueContextId,
    'Profile source/model/policy/context is incompatible',
  );
}

export async function assembleSeason(
  dataset: Dataset,
  players: Player[],
  supplied: PreparedProfile[],
  pilot: Pilot,
  seed: string,
  mode: 'pilot' | 'draft' = 'pilot',
): Promise<SeasonInput> {
  pilot = await parsePilot(pilot);
  validateDataset(dataset, pilot);
  requireMatch(
    /^(0|[1-9][0-9]{0,19})$/.test(seed) &&
      BigInt(seed) <= 18446744073709551615n,
    'Seed must be a lossless canonical unsigned 64-bit decimal string',
  );
  requireMatch(
    players.length === 9 &&
      new Set(players.map((p) => p.id)).size === 9 &&
      players.every((p) => p.year === dataset.year) &&
      (mode === 'draft' ||
        pilot.userPlayerIds.every(
          (id, i) => players[i].id === id && players[i].year === dataset.year,
        )),
    'User player identities/year/order do not match pilot',
  );
  const profiles = new Map<string, PreparedProfile>();
  for (const p of [...supplied, ...pilot.opponentProfiles]) {
    await validateProfile(p, pilot);
    const previous = profiles.get(p.id);
    requireMatch(
      !previous ||
        JSON.stringify(canonical(previous)) === JSON.stringify(canonical(p)),
      'Conflicting duplicate profile',
    );
    profiles.set(p.id, p);
  }
  const used = new Set<string>();
  const userTeamId = mode === 'draft' ? 'draft:2024' : pilot.userTeamId;
  const userTeam = {
    id: userTeamId,
    lineup: players.map((p) => {
      const profile = profiles.get(p.profileId);
      requireMatch(
        profile?.provenance.playerId === p.id,
        'A selected profile is missing or belongs to another player',
      );
      used.add(p.profileId);
      return { id: `${userTeamId}:${p.id}`, profileId: p.profileId };
    }),
  };
  const userIds = new Set(players.map((p) => p.id));
  for (const team of pilot.season.opponents) {
    requireMatch(
      team.lineup.length === 9 && team.id !== userTeam.id,
      'Invalid opponent lineup',
    );
    const identities = team.lineup.map((b) => {
      const p = profiles.get(b.profileId);
      requireMatch(
        p && (mode === 'draft' || !userIds.has(p.provenance.playerId)),
        'Missing opponent profile or overlapping player identity',
      );
      used.add(p.id);
      return p.provenance.playerId;
    });
    requireMatch(
      new Set(identities).size === 9,
      'Duplicate opponent identities',
    );
  }
  const input = {
    ...structuredClone(pilot.season),
    ...(mode === 'draft' ? { userLineupKind: 'synthetic' } : {}),
    seed,
    userTeam,
    profiles: [...profiles.values()]
      .filter((p) => used.has(p.id))
      .map((p) => structuredClone(p)),
  };
  // Retain separate identities: baseline in pitchingEnvironment, observed model in config.
  return input;
}
