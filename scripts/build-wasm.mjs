import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const version = '0.2.105'; // Must match crates/sim-wasm/Cargo.toml and Cargo.lock.
const executable =
  process.platform === 'win32' ? 'wasm-bindgen.exe' : 'wasm-bindgen';
const local = resolve(root, 'target/wasm-tools/bin', executable);
const bindgen = existsSync(local) ? local : executable;

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, encoding: 'utf8' });
  if (result.status !== 0 || result.error) {
    throw new Error(
      `${command} failed: ${result.error?.message ?? result.stderr}`,
    );
  }
  return result.stdout.trim();
}

try {
  if (run(bindgen, ['--version']) !== `wasm-bindgen ${version}`) {
    throw new Error(
      `Install matching CLI: cargo install wasm-bindgen-cli --version ${version} --locked --root target/wasm-tools`,
    );
  }
  console.log(
    run('cargo', [
      'build',
      '--locked',
      '--release',
      '-p',
      'sim-wasm',
      '--target',
      'wasm32-unknown-unknown',
    ]),
  );
  mkdirSync(resolve(root, 'apps/web/src/wasm'), { recursive: true });
  console.log(
    run(bindgen, [
      'target/wasm32-unknown-unknown/release/sim_wasm.wasm',
      '--target',
      'web',
      '--out-dir',
      'apps/web/src/wasm',
      '--out-name',
      'sim_wasm',
    ]),
  );
  console.log(
    `Generated release WASM and bindings with wasm-bindgen ${version}.`,
  );
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
