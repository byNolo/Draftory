import supplementUrl from '../../../../data/publications/defense-2024-v1.json?url';
import { hash, type SeasonInput } from './season-input';
import type { DraftEngine, DraftState } from './draft/engine';
import { DataError } from '../lib/api/player-data';

export const DEFENSE_POSITIONS = [
  'C',
  '1B',
  '2B',
  '3B',
  'SS',
  'LF',
  'CF',
  'RF',
] as const;
export const DEFENSE_SUPPLEMENT_ID =
  'defense-supplement:bc23560d196fa7f10a7424906a6460d3c4a546f018fb356287b64526eba24611';
export interface DefenseProfile {
  id: string;
  schemaVersion: string;
  modelId: string;
  sourceId: string;
  playerId: string;
  battingProfileId: string;
  year: number;
  position: string;
  status: 'observed' | 'insufficient' | 'unknown' | 'modelNeutral';
  errorRatio: number;
  games: number | null;
  innOuts: number | null;
  chances: number | null;
  errors: number | null;
}
export interface DefenseModel {
  id: string;
  schemaVersion: string;
  modelVersion: string;
  year: number;
  sourceId: string;
  transitionModelId: string;
  retrosheetLockSha256: string;
  supportedPositions: string[];
  minimumAttributedEvents: number;
  cells: {
    outs: number;
    baseMask: number;
    ordinaryIndex: number | null;
    components: { choiceIndex: number; position: number; weight: number }[];
  }[];
}
export interface DefenseSupplement {
  id: string;
  schemaVersion: string;
  modelVersion: string;
  datasetId: string;
  year: number;
  model: DefenseModel;
  profiles: DefenseProfile[];
}
export interface DefenseConfig {
  schemaVersion: string;
  supplementId: string;
  datasetId: string;
  teamId: string;
  model: DefenseModel;
  assignments: DefenseProfile[];
}
function check(value: unknown, message: string): asserts value {
  if (!value) throw new DataError('incompatibleInput', message);
}
export async function parseDefense(
  payload: unknown,
): Promise<DefenseSupplement> {
  check(payload && typeof payload === 'object', 'Missing defense supplement');
  const { id, ...body } = payload as Record<string, unknown>;
  check(
    id === DEFENSE_SUPPLEMENT_ID &&
      id === 'defense-supplement:' + (await hash(body)),
    'Defense supplement is stale or changed',
  );
  const value = payload as DefenseSupplement;
  check(
    value.schemaVersion === '1.0.0' &&
      value.modelVersion === 'error-avoidance-v1' &&
      value.year === 2024 &&
      value.model.schemaVersion === '1.0.0',
    'Unsupported defense version',
  );
  return value;
}
let pending: Promise<DefenseSupplement> | undefined;
export function loadDefense() {
  pending ??= fetch(supplementUrl)
    .then(async (r) => {
      if (!r.ok)
        throw new Error(
          'Defensive data is unavailable. Retry or use neutral defense.',
        );
      return parseDefense(await r.json());
    })
    .catch((e: unknown) => {
      pending = undefined;
      throw e;
    });
  return pending;
}
export function fieldingAssignments(
  engine: DraftEngine,
  state: DraftState,
  supplement: DefenseSupplement,
) {
  check(
    state.status === 'complete' &&
      supplement.id === DEFENSE_SUPPLEMENT_ID &&
      supplement.datasetId === engine.catalog.datasetId &&
      supplement.year === engine.catalog.year &&
      supplement.model.sourceId === engine.catalog.sourceId,
    'Incompatible batting and defense data',
  );
  return DEFENSE_POSITIONS.map((position) => {
    const pick = state.history.find((p) => p.position === position);
    check(pick, 'Missing fielding assignment');
    const rows = supplement.profiles.filter(
      (p) => p.playerId === pick.playerId && p.position === position,
    );
    const profile = rows[0];
    check(
      rows.length === 1 &&
        profile.battingProfileId === engine.player(pick.playerId).profileId &&
        profile.year === supplement.year &&
        profile.sourceId === supplement.model.sourceId &&
        profile.modelId === supplement.model.id,
      'Wrong player, year, position or defensive model',
    );
    return structuredClone(profile);
  });
}
export function withDefense(
  input: SeasonInput,
  engine: DraftEngine,
  state: DraftState,
  supplement: DefenseSupplement,
): SeasonInput {
  check(
    input.config.contextualModel.id === supplement.model.transitionModelId,
    'Defense and contact-transition models differ',
  );
  const assignments = fieldingAssignments(engine, state, supplement);
  check(
    assignments.every((p) =>
      input.userTeam.lineup.some((b) => b.profileId === p.battingProfileId),
    ),
    'Fielders do not match the batting roster',
  );
  return {
    ...input,
    schemaVersion: '1.1.0',
    gameSchemaVersion: '1.3.0',
    rulesVersion: 'error-avoidance-nine-inning-v1',
    config: {
      ...input.config,
      defense: {
        schemaVersion: '1.0.0',
        supplementId: supplement.id,
        datasetId: supplement.datasetId,
        teamId: input.userTeam.id,
        model: structuredClone(supplement.model),
        assignments,
      },
    },
  };
}
