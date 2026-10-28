// Default CI uses existing verified M4 prepared profiles with explicitly test-only
// identity labels/source-row placeholders. Real validation imports an M6A artifact.
import { execFileSync, spawn } from 'node:child_process';
import {
  closeSync,
  mkdirSync,
  openSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { dirname, resolve, sep } from 'node:path';
import { canonical, digest, pilotArtifact } from './build-pilot.mjs';

const root = process.cwd();
const parent = resolve(root, 'target');
const alpha = process.env.DRAFTORY_ALPHA_TEST === '1';
const state = resolve(parent, alpha ? 'm8a-api' : 'm6b-api');
if (!state.startsWith(parent + sep))
  throw new Error('Invalid generated integration directory');
rmSync(state, { recursive: true, force: true });
mkdirSync(state, { recursive: true });
const pilot = pilotArtifact();
const fixture = JSON.parse(
  readFileSync('crates/baseball-sim/tests/fixtures/season-modern-2024.json'),
);
const profiles = pilot.userPlayerIds.map((id) =>
  fixture.profiles.find((p) => p.provenance.playerId === id),
);
const metadata = {
  schemaVersion: '1.0.0',
  sport: 'mlb',
  year: 2024,
  sourceId: pilot.sourceId,
  inputSchemaVersion: '1.2.0',
  modelVersion: 'lahman-contact-adapter-v1',
  profileType: 'season',
  aggregation: 'aggregate',
  policy: { id: pilot.policyId },
  context: { id: pilot.leagueContextId },
  profileCount: profiles.length,
  fixtureOnly: true,
  fixtureSha256: pilot.fixtureSha256,
  positionCounts: {},
};
const datasetId = 'dataset:' + digest({ metadata, profiles });
const lines = [];
const quote = (v) => "'" + String(v).replaceAll("'", "''") + "'";
const json = (v) => JSON.stringify(canonical(v));
const add = (table, columns, values) =>
  lines.push(
    `INSERT INTO ${table} (${columns}) VALUES (${values.map(quote).join(',')});`,
  );
add('mlb_sources', 'id,provenance_json,attribution_json', [
  pilot.sourceId,
  json({
    fixtureSha256: pilot.fixtureSha256,
    note: 'Prepared-profile fixture only; metadata is test scaffolding',
  }),
  json({
    attribution: 'SABR Lahman / Retrosheet; existing verified M4 fixture',
    license: 'CC-BY-SA-3.0',
  }),
]);
for (const [ordinal, id] of pilot.userPlayerIds.entries()) {
  add(
    'mlb_players',
    'source_id,id,lahman_id,display_name,metadata_json,source_row',
    [
      pilot.sourceId,
      id,
      id.slice(7),
      `Fixture ${id}`,
      json({ fixtureOnly: true }),
      2,
    ],
  );
  add('mlb_player_seasons', 'source_id,player_id,year', [
    pilot.sourceId,
    id,
    2024,
  ]);
  const p = profiles[ordinal];
  add(
    'mlb_profiles',
    'id,source_id,player_id,model_version,input_schema_version,historical_profile_id,aggregation,definition_json,payload_json',
    [
      p.id,
      pilot.sourceId,
      id,
      p.modelVersion,
      '1.2.0',
      p.provenance.sourceProfileId,
      'aggregate',
      json({ fixtureOnly: true, scope: 'verified-M4-team-season' }),
      json(p),
    ],
  );
}
add('mlb_datasets', 'id,source_id,year,metadata_json', [
  datasetId,
  pilot.sourceId,
  2024,
  json(metadata),
]);
for (const [ordinal, id] of pilot.userPlayerIds.entries())
  add(
    'mlb_dataset_profiles',
    'dataset_id,profile_id,source_id,player_id,year,ordinal',
    [datasetId, profiles[ordinal].id, pilot.sourceId, id, 2024, ordinal],
  );
add('mlb_publications', 'dataset_id,player_count,position_counts_json', [
  datasetId,
  9,
  '{}',
]);
const generated = resolve(state, 'fixture.sql');
writeFileSync(generated, lines.join('\n'));
const source = process.env.M6B_IMPORT_SQL
  ? resolve(process.env.M6B_IMPORT_SQL)
  : generated;
const cli = resolve('node_modules/wrangler/bin/wrangler.js');
const config = resolve(
  alpha ? 'services/api/wrangler.alpha.json' : 'services/api/wrangler.jsonc',
);
const common = ['--config', config];
const options = { cwd: root, stdio: 'inherit', windowsHide: true };
if (alpha && process.env.M6B_IMPORT_SQL) {
  if (source !== resolve(dirname(source), 'import.sql'))
    throw new Error(
      'Use the verified publication import.sql for alpha validation',
    );
  execFileSync(
    process.execPath,
    ['scripts/prepare-alpha.mjs', '--publication-dir', dirname(source)],
    options,
  );
}
execFileSync(
  process.execPath,
  [
    cli,
    'd1',
    'migrations',
    'apply',
    'DB',
    '--local',
    '--persist-to',
    state,
    ...common,
  ],
  options,
);
const importLog = openSync(resolve(state, 'import.log'), 'w');
try {
  execFileSync(
    process.execPath,
    [
      cli,
      'd1',
      'execute',
      'DB',
      '--local',
      '--persist-to',
      state,
      '--file',
      source,
      ...common,
    ],
    { ...options, stdio: ['ignore', importLog, 'inherit'] },
  );
} finally {
  closeSync(importLog);
}
console.log(
  `Local SQL import complete; details: ${resolve(state, 'import.log')}`,
);
const child = spawn(
  process.execPath,
  [
    cli,
    'dev',
    '--local',
    '--ip',
    '127.0.0.1',
    '--port',
    alpha ? '4180' : '4176',
    '--persist-to',
    state,
    '--show-interactive-dev-session=false',
    ...common,
  ],
  options,
);
child.on('error', (e) => {
  console.error(e);
  process.exitCode = 1;
});
child.on('exit', (code) => {
  process.exitCode = code ?? 1;
});
process.on('SIGINT', () => child.kill('SIGINT'));
process.on('SIGTERM', () => child.kill('SIGTERM'));
