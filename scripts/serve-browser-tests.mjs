// Local Pages runtime only: the test origin serves copied production artifacts.
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
const child = spawn(
  process.execPath,
  [
    'node_modules/wrangler/bin/wrangler.js',
    'pages',
    'dev',
    current,
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
