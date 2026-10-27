import { PlayerDataClient, type Player } from '../../lib/api/player-data';
import { PilotLoader } from '../pilot-loader';
import { assembleSeason, canonical, validateDataset } from '../season-input';
import { DraftEngine, DraftError, POSITIONS, type DraftState } from './engine';

export async function draftedSeason(
  engine: DraftEngine,
  state: DraftState,
  api: PlayerDataClient,
  shared: PilotLoader,
  seed: string,
) {
  const replayed = engine.replay(
    state.seed,
    state.history.map((p) => p.playerId),
  );
  if (
    replayed.status !== 'complete' ||
    JSON.stringify(canonical(replayed)) !== JSON.stringify(canonical(state))
  )
    throw new DraftError('Complete, valid replay required for simulation');
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
  // Batting order is the named position order, independent of the drafting order.
  const players: Player[] = POSITIONS.map((pos) => {
    const pick = state.history.find((p) => p.position === pos)!;
    const p = engine.player(pick.playerId);
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
    players.map((p) => p.profileId),
  );
  return assembleSeason(dataset, players, profiles, pilot, seed, 'draft');
}
