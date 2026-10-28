import { expect, test } from '@playwright/test';
import { readdirSync } from 'node:fs';

test('single origin routes API to real D1 and serves production assets with strict misses', async ({
  request,
  page,
}) => {
  const health = await request.get('/api/health');
  expect(await health.json()).toEqual({
    status: 'ok',
    service: 'draftory-api',
  });
  expect(health.headers()['x-robots-tag']).toBe('noindex, nofollow');
  for (const route of ['/api', '/api/missing']) {
    const response = await request.get(route);
    expect(response.status()).toBe(404);
    expect(response.headers()['content-type']).toContain('application/json');
    expect(response.headers()['cache-control']).toBe('no-store');
  }
  const catalog = await request.get('/api/datasets');
  const dataset = (await catalog.json()).datasets[0];
  expect(dataset.profileCount).toBe(process.env.M6B_IMPORT_SQL ? 526 : 9);
  const players = await request.get(
    `/api/players?dataset=${encodeURIComponent(dataset.id)}&limit=9`,
  );
  const ids = (await players.json()).players.map(
    (p: { profileId: string }) => p.profileId,
  );
  expect(ids).toHaveLength(9);
  const batch = await request.post('/api/profiles/batch', {
    data: { datasetId: dataset.id, profileIds: ids },
  });
  expect(batch.status()).toBe(200);
  expect(
    (await batch.json()).profiles.map((p: { id: string }) => p.id),
  ).toEqual(ids);
  expect(batch.headers()['cache-control']).toBe('no-store');
  for (const path of ['/', '/index.html', '/dev/', '/dev/index.html']) {
    const html = await request.get(path);
    expect(html.ok()).toBe(true);
    expect(html.headers()['cache-control']).toBe('no-cache');
    expect(html.headers()['content-security-policy']).toContain(
      "worker-src 'self'",
    );
  }
  for (const file of readdirSync('apps/web/dist/assets')) {
    const asset = await request.get(`/assets/${file}`);
    expect(asset.status()).toBe(200);
    expect(asset.headers()['cache-control']).toContain('immutable');
    expect(asset.headers()['content-security-policy']).toContain(
      "'wasm-unsafe-eval'",
    );
    if (file.endsWith('.wasm'))
      expect(asset.headers()['content-type']).toContain('application/wasm');
    if (file.endsWith('.js'))
      expect(asset.headers()['content-type']).toMatch(/javascript/);
  }
  for (const path of [
    '/assets/stale-worker.js',
    '/assets/stale-module.wasm',
    '/unknown/deep-link',
    '/_headers',
  ]) {
    const missing = await request.get(path);
    expect(missing.status()).toBe(404);
    expect(missing.headers()['cache-control']).toBe('no-store');
    expect(await missing.text()).toContain('Return to Draftory');
  }
  await page.goto('/dev');
  await expect(page.getByRole('status')).toHaveText('Ready');
});
