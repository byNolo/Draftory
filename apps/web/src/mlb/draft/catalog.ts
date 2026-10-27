import url from '../../../../../data/publications/mlb-draft-2024-v1.json?url';
import { hash } from '../season-input';
import {
  DEFAULTS,
  DraftEngine,
  DraftError,
  eligible,
  POSITIONS,
  type Catalog,
} from './engine';

export const CATALOG_ID =
  'draft-catalog:95602e268bcd87ff6f5640525e3cfc1936eff28ae57a3d715a2f990ba689f9f8';
export async function parseCatalog(value: unknown): Promise<Catalog> {
  if (!value || typeof value !== 'object')
    throw new DraftError('Invalid offer catalog');
  const c = value as Catalog;
  const { id, ...body } = c;
  if (
    id !== CATALOG_ID ||
    id !== 'draft-catalog:' + (await hash(body)) ||
    c.schemaVersion !== '1.0.0' ||
    c.year !== 2024 ||
    c.pricingPolicy !== 'm7a-linear-1-20-v1' ||
    c.eligibilityPolicy !== 'observed-10-universal-dh-v1'
  )
    throw new DraftError(
      'Offer catalog digest/version differs from this build',
    );
  const engine = new DraftEngine(c);
  for (const p of c.players)
    if (
      JSON.stringify(p.positions) !==
      JSON.stringify(POSITIONS.filter((pos) => eligible(p, pos, DEFAULTS)))
    )
      throw new DraftError('Catalog eligibility differs from observed games');
  return engine.catalog;
}
export async function loadCatalog(): Promise<Catalog> {
  const response = await fetch(url);
  if (!response.ok)
    throw new DraftError(`Offer catalog unavailable (${response.status})`);
  return parseCatalog(await response.json());
}
