import { expect, test } from '@playwright/test';
import { execFileSync, spawnSync } from 'node:child_process';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';

test('alpha template is separate, unrouted, and scoped to API-first routing', () => {
  const alpha = JSON.parse(
    readFileSync('services/api/wrangler.alpha.json', 'utf8'),
  );
  expect(alpha.name).toBe('draftory-alpha');
  expect(alpha.account_id).toBe('0'.repeat(32));
  expect(alpha.workers_dev).toBe(false);
  expect(alpha.preview_urls).toBe(false);
  expect(alpha).not.toHaveProperty('routes');
  expect(alpha.assets.run_worker_first).toEqual(['/api', '/api/*']);
  expect(alpha.assets.not_found_handling).toBe('none');
  expect(alpha.d1_databases[0].database_name).toBe('draftory-alpha');
});

test('build audit records only deployment assets and compatibility pins', () => {
  execFileSync(process.execPath, [
    'scripts/prepare-alpha.mjs',
    '--check-build',
  ]);
  const report = JSON.parse(readFileSync('target/alpha/release.json', 'utf8'));
  expect(report.cloudActionsExecuted).toBe(false);
  expect(
    report.files.some((f: { path: string }) => f.path.endsWith('.wasm')),
  ).toBe(true);
  expect(
    report.files.some((f: { path: string }) => f.path === 'dev/index.html'),
  ).toBe(true);
  expect(report.migrations).toHaveLength(1);
  expect(report.datasetId).toMatch(/^dataset:[a-f0-9]{64}$/);
  expect(report.pilotId).toMatch(/^pilot:[a-f0-9]{64}$/);
});

test('target preparation rejects missing, placeholder and malformed IDs without cloud work', () => {
  for (const args of [
    ['--enable-workers-dev'],
    ['--account-id', '1'.repeat(32)],
    [
      '--account-id',
      '0'.repeat(32),
      '--database-id',
      '11111111-1111-1111-1111-111111111111',
    ],
    ['--account-id', '1'.repeat(32), '--database-id', 'production'],
    [
      '--account-id',
      '1'.repeat(32),
      '--database-id',
      '00000000-0000-0000-0000-000000000000',
    ],
    ['--remote'],
  ]) {
    const result = spawnSync(
      process.execPath,
      ['scripts/prepare-alpha.mjs', ...args],
      { encoding: 'utf8' },
    );
    expect(result.status).not.toBe(0);
  }
});

test('preparation refuses a stale catalog asset even if it is still valid JSON', () => {
  const name = readdirSync('apps/web/dist/assets').find((n) =>
    /^mlb-draft-2024-v1-.*\.json$/.test(n),
  )!;
  const path = `apps/web/dist/assets/${name}`;
  const original = readFileSync(path);
  try {
    writeFileSync(path, Buffer.concat([original, Buffer.from(' ')]));
    const result = spawnSync(
      process.execPath,
      ['scripts/prepare-alpha.mjs', '--check-build'],
      { encoding: 'utf8' },
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('Built catalog differs');
  } finally {
    writeFileSync(path, original);
  }
});

test('preparation rejects a conflicting account environment before reading publication files', () => {
  const result = spawnSync(
    process.execPath,
    [
      'scripts/prepare-alpha.mjs',
      '--account-id',
      '1'.repeat(32),
      '--database-id',
      '11111111-1111-1111-1111-111111111111',
    ],
    {
      encoding: 'utf8',
      env: { ...process.env, CLOUDFLARE_ACCOUNT_ID: '2'.repeat(32) },
    },
  );
  expect(result.status).not.toBe(0);
  expect(result.stderr).toContain('differs from the selected alpha account');
});

test('preparation rejects a changed pilot body even if its claimed ID is unchanged', () => {
  const name = readdirSync('apps/web/dist/assets').find((n) =>
    /^mlb-pilot-2024-.*\.json$/.test(n),
  )!;
  const path = `apps/web/dist/assets/${name}`,
    original = readFileSync(path);
  try {
    const value = JSON.parse(original.toString());
    value.season.games = 161;
    writeFileSync(path, JSON.stringify(value));
    const result = spawnSync(
      process.execPath,
      ['scripts/prepare-alpha.mjs', '--check-build'],
      { encoding: 'utf8' },
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('Built pilot differs');
  } finally {
    writeFileSync(path, original);
  }
});
