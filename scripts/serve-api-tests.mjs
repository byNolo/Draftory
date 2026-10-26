// Isolated synthetic D1 state. Every Wrangler invocation is explicitly local.
import { execFileSync, spawn } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { resolve, sep } from 'node:path';

const root = process.cwd();
const parent = resolve(root, 'target');
const state = resolve(parent, 'api-tests');
if (!state.startsWith(parent + sep))
  throw new Error('Invalid generated state path');
rmSync(state, { recursive: true, force: true });
mkdirSync(state, { recursive: true });
const cli = resolve(root, 'node_modules/wrangler/bin/wrangler.js');
const config = resolve(root, 'services/api/wrangler.jsonc');
const options = { cwd: root, stdio: 'inherit', windowsHide: true };
const args = ['--config', config];
for (const command of [
  ['d1', 'migrations', 'apply', 'DB', '--local', '--persist-to', state],
  [
    'd1',
    'execute',
    'DB',
    '--local',
    '--persist-to',
    state,
    '--file',
    resolve(root, 'data/fixtures/d1-player-data.synthetic.sql'),
  ],
  // Verify the real D1 runtime also accepts an identical second import.
  [
    'd1',
    'execute',
    'DB',
    '--local',
    '--persist-to',
    state,
    '--file',
    resolve(root, 'data/fixtures/d1-player-data.synthetic.sql'),
  ],
])
  execFileSync(process.execPath, [cli, ...command, ...args], options);

const child = spawn(
  process.execPath,
  [
    cli,
    'dev',
    '--local',
    '--ip',
    '127.0.0.1',
    '--port',
    '4174',
    '--persist-to',
    state,
    '--show-interactive-dev-session=false',
    ...args,
  ],
  options,
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
