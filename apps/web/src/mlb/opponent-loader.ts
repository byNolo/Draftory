import url from '../../../../data/publications/opponents-2024-v1.json?url';
import { parseOpponents, type OpponentPublication } from './opponents';
let pending: Promise<OpponentPublication> | undefined;
export function loadOpponents() {
  pending ??= fetch(url)
    .then(async (r) => {
      if (!r.ok)
        throw new Error('Opponent data unavailable. Retry the season.');
      return parseOpponents(await r.json());
    })
    .catch((e: unknown) => {
      pending = undefined;
      throw e;
    });
  return pending;
}
