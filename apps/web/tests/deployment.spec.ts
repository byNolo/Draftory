import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import {
  cpSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { dirname, resolve, sep } from 'node:path';
import { createRequire } from 'node:module';
import { workerUrl } from './helpers';

test('new deployment revalidates HTML, retains an active worker, and recovers stale asset URLs', async ({
  browser,
  request,
}) => {
  test.setTimeout(90_000);
  const root = process.cwd();
  const current = resolve(root, 'target/browser-site/current');
  const next = resolve(root, 'target/browser-site/next');
  const generated = resolve(root, 'target/browser-site') + sep;
  if (!current.startsWith(generated) || !next.startsWith(generated))
    throw new Error('Test deployment must stay in generated target directory');
  function replaceAssets(source: string) {
    const sourceAssets = resolve(source, 'assets');
    const assets = resolve(current, 'assets');
    // Keep the watched directory alive (Windows disables a removed directory's
    // watcher). Replace files, then wait for Wrangler's manifest below.
    cpSync(sourceAssets, assets, { recursive: true });
    const keep = new Set(readdirSync(sourceAssets));
    for (const name of readdirSync(assets))
      if (!keep.has(name)) rmSync(resolve(assets, name), { force: true });
  }
  // Build the same source without minification: genuine new Vite worker/JS hashes,
  // with identical WASM/engine semantics. No source or production output is edited.
  const require = createRequire(resolve(root, 'apps/web/package.json'));
  const vite = resolve(
    dirname(require.resolve('vite/package.json')),
    'bin/vite.js',
  );
  execFileSync(
    process.execPath,
    [vite, 'build', '--minify', 'false', '--outDir', next, '--emptyOutDir'],
    { cwd: resolve(root, 'apps/web'), stdio: 'pipe' },
  );
  const beforeHtml = await request.get('/').then((response) => response.text());
  const oldWorker = workerUrl();
  const nextWorker = readdirSync(resolve(next, 'assets')).find((name) =>
    name.startsWith('season.worker-'),
  );
  expect(`/assets/${nextWorker}`).not.toBe(oldWorker);
  const oldTab = await browser.newPage();
  const staleTab = await browser.newPage();
  let release = () => {};
  const gate = new Promise<void>((resolveGate) => {
    release = resolveGate;
  });
  try {
    await oldTab.goto('http://127.0.0.1:4173/');
    await expect(oldTab.getByRole('status')).toHaveText('Ready');
    // Explicit uncached/unfetched old worker, not a claim about a browser cache hit.
    await staleTab.route(`**${oldWorker}`, async (route) => {
      await gate;
      await route.continue();
    });
    const waiting = staleTab.waitForRequest(`**${oldWorker}`);
    await staleTab.goto('http://127.0.0.1:4173/');
    await waiting;
    replaceAssets(next);
    writeFileSync(
      resolve(current, 'index.html'),
      readFileSync(resolve(next, 'index.html')),
    );
    await expect
      .poll(async () => request.get('/').then((response) => response.text()))
      .not.toBe(beforeHtml);
    await expect
      .poll(async () => (await request.get(oldWorker)).status())
      .toBe(404);
    await oldTab.getByRole('button', { name: 'Simulate 162 games' }).click();
    await expect(
      oldTab.getByRole('region', { name: 'Season result' }),
    ).toContainText('105–57');
    release();
    await expect(staleTab.getByRole('alert')).toBeVisible();
    await staleTab.getByRole('button', { name: 'Reload app' }).click();
    await expect(staleTab.getByRole('status')).toHaveText('Ready');
    await staleTab.getByRole('button', { name: 'Simulate 162 games' }).click();
    await expect(
      staleTab.getByRole('region', { name: 'Season result' }),
    ).toContainText('105–57');
  } finally {
    release();
    await oldTab.close();
    await staleTab.close();
    replaceAssets(resolve(root, 'apps/web/dist'));
    cpSync(resolve(root, 'apps/web/dist'), current, { recursive: true });
  }
});
