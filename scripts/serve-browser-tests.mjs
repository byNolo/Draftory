// Local Cloudflare Static Assets runtime: copied production artifacts only.
// The empty benchmark document is test-only and never enters apps/web/dist.
import { cpSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { resolve, sep } from 'node:path';
import { spawn } from 'node:child_process';

const root = process.cwd();
const parent = resolve(root, 'target/browser-site');
const current = resolve(parent, 'current');
if (!current.startsWith(parent + sep))
  throw new Error('Invalid generated test directory');
mkdirSync(parent, { recursive: true });
rmSync(current, { recursive: true, force: true });
cpSync(resolve(root, 'apps/web/dist'), current, { recursive: true });
writeFileSync(
  resolve(current, '__bench.html'),
  '<!doctype html><html lang="en"><title>Worker benchmark</title></html>',
);
// The legacy Pages dev filesystem lookup throws ENOTDIR for /_headers on Linux.
// Use the current asset runtime, retaining the real headers and strict 404 checks.
const config = resolve(parent, 'wrangler.json');
writeFileSync(
  config,
  JSON.stringify({
    name: 'draftory-browser-tests',
    compatibility_date: '2026-10-26',
    assets: { directory: current, not_found_handling: '404-page' },
  }),
);
const child = spawn(
  process.execPath,
  [
    'node_modules/wrangler/bin/wrangler.js',
    'dev',
    '--local',
    '--config',
    config,
    '--ip',
    '127.0.0.1',
    '--port',
    '4173',
    '--compatibility-date',
    '2026-10-26',
    '--persist-to',
    resolve(parent, 'state'),
    '--show-interactive-dev-session=false',
  ],
  { cwd: root, stdio: 'inherit', windowsHide: true },
);
child.on('error', (error) => {
  console.error(error);
  process.exitCode = 1;
});
child.on('exit', (code) => {
  process.exitCode = code ?? 1;
});
process.on('SIGINT', () => child.kill('SIGINT'));
process.on('SIGTERM', () => child.kill('SIGTERM'));
