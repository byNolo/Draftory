// Local preparation only: no login, Cloudflare API, resource creation or deployment.
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { digest, pilotArtifact } from './build-pilot.mjs';

const root = fileURLToPath(new URL('..', import.meta.url));
const { values: options } = parseArgs({
  options: {
    'check-build': { type: 'boolean' },
    'publication-dir': { type: 'string', default: 'data/processed/d1-2024' },
    'account-id': { type: 'string' },
    'database-id': { type: 'string' },
    'enable-workers-dev': { type: 'boolean', default: false },
  },
});
const account = options['account-id'],
  database = options['database-id'];
if (
  Boolean(account) !== Boolean(database) ||
  (options['enable-workers-dev'] && !account)
)
  throw new Error(
    'Supply both approved account/database IDs before preparing a hosted target.',
  );
if (account && (!/^[a-f0-9]{32}$/.test(account) || /^0+$/.test(account)))
  throw new Error('An approved, non-placeholder account ID is required.');
if (
  database &&
  (!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(database) ||
    /^0+-0+-0+-0+-0+$/.test(database))
)
  throw new Error('An approved, non-placeholder alpha D1 UUID is required.');
if (options['check-build'] && account)
  throw new Error('Build-only checks cannot prepare hosted configuration.');
if (
  account &&
  process.env.CLOUDFLARE_ACCOUNT_ID &&
  process.env.CLOUDFLARE_ACCOUNT_ID !== account
)
  throw new Error(
    'CLOUDFLARE_ACCOUNT_ID differs from the selected alpha account.',
  );

const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const catalogPath = resolve(root, 'data/publications/mlb-draft-2024-v1.json');
const catalogBytes = readFileSync(catalogPath),
  catalog = JSON.parse(catalogBytes);
const { id, ...body } = catalog;
if (id !== 'draft-catalog:' + digest(body))
  throw new Error('Catalog content ID mismatch.');
const config = readJson(resolve(root, 'services/api/wrangler.alpha.json'));
const dist = resolve(root, 'apps/web/dist');
const assets = readdirSync(resolve(dist, 'assets'));
const find = (pattern) => {
  const matches = assets.filter((name) => pattern.test(name));
  if (matches.length !== 1)
    throw new Error(`Expected one built asset: ${pattern}`);
  return matches[0];
};
const catalogAsset = find(/^mlb-draft-2024-v1-.*\.json$/);
const pilotAsset = find(/^mlb-pilot-2024-.*\.json$/);
find(/^season\.worker-.*\.js$/);
find(/^sim_wasm_bg-.*\.wasm$/);
if (
  sha(readFileSync(resolve(dist, 'assets', catalogAsset))) !== sha(catalogBytes)
)
  throw new Error(
    'Built catalog differs from the reviewed publication. Rebuild the frontend.',
  );
const pilot = readJson(resolve(dist, 'assets', pilotAsset));
const { id: pilotId, ...pilotBody } = pilot;
if (pilotId !== 'pilot:' + digest(pilotBody) || pilotId !== pilotArtifact().id)
  throw new Error('Built pilot differs from this engine build.');
const files = [];
function inspect(directory, prefix = '') {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = prefix + entry.name;
    if (entry.isDirectory()) {
      inspect(resolve(directory, entry.name), path + '/');
      continue;
    }
    if (
      !entry.isFile() ||
      !(
        /^(index\.html|dev\/index\.html|404\.html|_headers)$/.test(path) ||
        /^assets\/[\w.-]+-[\w-]+\.(js|css|wasm|json)$/.test(path)
      )
    )
      throw new Error(`Unexpected public build file: ${path}`);
    const bytes = readFileSync(resolve(directory, entry.name));
    files.push({ path, bytes: bytes.length, sha256: sha(bytes) });
  }
}
inspect(dist);
for (const name of ['index.html', 'dev/index.html', '404.html', '_headers'])
  if (!files.some((f) => f.path === name))
    throw new Error(`Required static file missing: ${name}`);
const migrations = readdirSync(resolve(root, 'infra/d1/migrations'))
  .filter((n) => /^\d.*\.sql$/.test(n))
  .sort()
  .map((name) => ({
    name,
    sha256: sha(readFileSync(resolve(root, 'infra/d1/migrations', name))),
  }));
const release = {
  schemaVersion: '1.0.0',
  target: 'draftory-alpha',
  catalogId: id,
  datasetId: catalog.datasetId,
  sourceSqlSha256: catalog.sourceSqlSha256,
  pilotId: pilot.id,
  files: files.sort((a, b) => a.path.localeCompare(b.path)),
  migrations,
  cloudActionsExecuted: false,
  hostedTarget: account
    ? {
        accountId: account,
        databaseId: database,
        workersDevEnabled: options['enable-workers-dev'],
        accountVerified: false,
      }
    : null,
};
if (!options['check-build']) {
  const directory = resolve(root, options['publication-dir']);
  const manifest = readJson(resolve(directory, 'manifest.json'));
  const sql = readFileSync(resolve(directory, 'import.sql'));
  if (
    manifest.schemaVersion !== '1.0.0' ||
    sha(sql) !== catalog.sourceSqlSha256 ||
    manifest.sqlSha256 !== catalog.sourceSqlSha256 ||
    manifest.datasetId !== catalog.datasetId ||
    manifest.metadata.year !== 2024 ||
    manifest.metadata.sourceId !== catalog.sourceId ||
    manifest.metadata.policy.id !== catalog.profilePolicyId ||
    manifest.metadata.context.id !== catalog.contextId ||
    manifest.metadata.profileCount !== catalog.players.length
  )
    throw new Error(
      'The verified 2024 publication does not match this frontend. Do not import it.',
    );
  release.publication = {
    sqlBytes: sql.length,
    rows: manifest.rowCounts,
    sqlitePageBytes: manifest.sqlitePageBytes,
  };
}
const output = resolve(root, 'target/alpha');
mkdirSync(output, { recursive: true });
writeFileSync(
  resolve(output, 'release.json'),
  JSON.stringify(release, null, 2) + '\n',
);
if (account) {
  config.account_id = account;
  config.workers_dev = options['enable-workers-dev'];
  config.main = resolve(root, 'services/api/src/alpha.ts');
  config.assets.directory = dist;
  config.$schema = resolve(root, 'node_modules/wrangler/config-schema.json');
  config.d1_databases[0].database_id = database;
  config.d1_databases[0].migrations_dir = resolve(root, 'infra/d1/migrations');
  writeFileSync(
    resolve(output, 'wrangler.hosted.json'),
    JSON.stringify(config, null, 2) + '\n',
  );
}
console.log(
  JSON.stringify({
    release: resolve(output, 'release.json'),
    hostedConfig: account ? resolve(output, 'wrangler.hosted.json') : null,
    workersDevEnabled: config.workers_dev,
    cloudActionsExecuted: false,
  }),
);
