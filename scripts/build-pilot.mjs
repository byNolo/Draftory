// Extract an existing verified input. No fitting, player generation or raw data.
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));

export const fixturePath =
  'crates/baseball-sim/tests/fixtures/season-modern-2024.json';
export const fixtureSha256 =
  'd02959d2673eeeec2951644cf327434babefeddeb1cb5b516d809d3aa8a562a4';
export function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((k) => [k, canonical(value[k])]),
    );
  return value;
}
export function digest(value) {
  return createHash('sha256')
    .update(JSON.stringify(canonical(value)))
    .digest('hex');
}
export function pilotArtifact() {
  const bytes = readFileSync(resolve(root, fixturePath));
  if (createHash('sha256').update(bytes).digest('hex') !== fixtureSha256)
    throw new Error(
      'M4 fixture changed: review and version the pilot before rebuilding',
    );
  const fixture = JSON.parse(bytes);
  const byId = new Map(fixture.profiles.map((p) => [p.id, p]));
  const ids = fixture.userTeam.lineup.map(
    (b) => byId.get(b.profileId).provenance.playerId,
  );
  const opponentIds = new Set(
    fixture.opponents.flatMap((t) => t.lineup.map((b) => b.profileId)),
  );
  const first = fixture.profiles[0].provenance;
  if (
    fixture.profiles.some((p) =>
      ['sourceId', 'policyId', 'contextId'].some(
        (k) => p.provenance[k] !== first[k],
      ),
    )
  )
    throw new Error('Fixture profile contexts differ');
  const season = Object.fromEntries(
    Object.entries(fixture).filter(
      ([key]) => !['profiles', 'userTeam', 'seed'].includes(key),
    ),
  );
  const body = {
    schemaVersion: '1.0.0',
    engineVersion: '0.4.0',
    fixtureSha256,
    year: 2024,
    sourceId: first.sourceId,
    policyId: first.policyId,
    leagueContextId: first.contextId,
    transitionModelId: fixture.config.contextualModel.id,
    userTeamId: fixture.userTeam.id,
    userPlayerIds: ids,
    season,
    opponentProfiles: fixture.profiles.filter((p) => opponentIds.has(p.id)),
  };
  return { id: 'pilot:' + digest(body), ...body };
}
const output = resolve(root, 'apps/web/src/generated');
mkdirSync(output, { recursive: true });
const artifact = pilotArtifact();
writeFileSync(
  resolve(output, 'mlb-pilot-2024.json'),
  JSON.stringify(canonical(artifact)) + '\n',
);
writeFileSync(
  resolve(output, 'pilot-meta.ts'),
  `export const PILOT_ID = '${artifact.id}';\n`,
);
console.log(`Built ${artifact.id} from pinned M4 fixture`);
