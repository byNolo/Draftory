import { withOpponents, type OpponentPublication } from '../opponents';
import { PlayerDataClient, type Player } from '../../lib/api/player-data';
import { PilotLoader } from '../pilot-loader';
import { assembleSeason, canonical, validateDataset } from '../season-input';
import { DraftEngine, DraftError, type DraftState } from './engine';
import {
  defaultBattingOrder,
  validateBattingOrder,
  type BattingOrder,
} from './batting-order';

export async function draftedSeason(
  engine: DraftEngine,
  state: DraftState,
  api: PlayerDataClient,
  shared: PilotLoader,
  seed: string,
  battingOrder: BattingOrder = defaultBattingOrder(state),
  opponents?: OpponentPublication,
) {
  const replayed = engine.replay(
    state.seed,
    state.history.map((p) => p.playerId),
    state.rerollRounds,
  );
  if (
    replayed.status !== 'complete' ||
    JSON.stringify(canonical(replayed)) !== JSON.stringify(canonical(state))
  )
    throw new DraftError('Complete, valid replay required for simulation');
  const order = validateBattingOrder(state, battingOrder);
  const [dataset, pilot] = await Promise.all([
    api.dataset(engine.catalog.datasetId),
    shared.load(),
  ]);
  validateDataset(dataset, pilot);
  if (
    dataset.id !== engine.catalog.datasetId ||
    dataset.sourceId !== engine.catalog.sourceId ||
    dataset.policy.id !== engine.catalog.profilePolicyId ||
    dataset.contextId !== engine.catalog.contextId ||
    dataset.profileCount !== engine.catalog.players.length
  )
    throw new DraftError(
      'Offer catalog and published simulation dataset differ',
    );
  const players: Player[] = order.map((id) => {
    const p = engine.player(id);
    return {
      id: p.id,
      displayName: p.name,
      profileId: p.profileId,
      year: engine.catalog.year,
      metadata: {},
      stints: [],
      positions: [],
    };
  });
  const profiles = await api.profiles(
    dataset.id,
    // Keep profile-pool serialization stable; only userTeam.lineup is reordered.
    defaultBattingOrder(state).map((id) => engine.player(id).profileId),
  );
  const input = await assembleSeason(
    dataset,
    players,
    profiles,
    pilot,
    seed,
    'draft',
  );
  return opponents ? withOpponents(input, opponents, pilot, dataset.id) : input;
}
