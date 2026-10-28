import { DraftError, POSITIONS, type DraftState } from './engine';

// Player identities in batting sequence; fielding assignments live in DraftState.
export type BattingOrder = readonly string[];

export function defaultBattingOrder(draft: DraftState): BattingOrder {
  if (draft.status !== 'complete' || draft.history.length !== 9)
    throw new DraftError('A complete roster is required for batting order.');
  const order = POSITIONS.map((position) => {
    const pick = draft.history.find((p) => p.position === position);
    if (!pick) throw new DraftError('Missing fielding assignment.');
    return pick.playerId;
  });
  return validateBattingOrder(draft, order);
}

export function validateBattingOrder(
  draft: DraftState,
  order: BattingOrder,
): BattingOrder {
  const roster = new Set(draft.history.map((p) => p.playerId));
  if (
    draft.status !== 'complete' ||
    draft.history.length !== 9 ||
    roster.size !== 9 ||
    order.length !== 9 ||
    new Set(order).size !== 9 ||
    order.some((id) => !roster.has(id))
  )
    throw new DraftError(
      'Batting order must contain all nine drafted players exactly once.',
    );
  // Snapshot before asynchronous profile loading or simulation begins.
  return Object.freeze([...order]);
}

export function moveBatter(
  order: BattingOrder,
  playerId: string,
  destination: number,
): BattingOrder {
  const from = order.indexOf(playerId);
  if (
    from < 0 ||
    !Number.isInteger(destination) ||
    destination < 0 ||
    destination >= order.length
  )
    throw new DraftError('Invalid batting-order move.');
  const next = [...order];
  next.splice(from, 1);
  next.splice(destination, 0, playerId);
  return Object.freeze(next);
}
