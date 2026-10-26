import { expect, test } from '@playwright/test';
import { readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { workerUrl } from './helpers';

test('Pages local runtime serves hashed assets with MIME, cache and worker CSP headers', async ({
  request,
  page,
}) => {
  for (const path of ['/', '/index.html']) {
    const response = await request.get(path);
    expect(response.ok()).toBe(true);
    expect(response.headers()['cache-control']).toBe('no-cache');
  }
  for (const filename of readdirSync(resolve('apps/web/dist/assets'))) {
    const response = await request.get(`/assets/${filename}`);
    expect(response.ok()).toBe(true);
    const headers = response.headers();
    expect(headers['cache-control']).toContain('max-age=31536000');
    expect(headers['cache-control']).toContain('immutable');
    expect(headers['content-security-policy']).toContain("'wasm-unsafe-eval'");
    expect(headers['content-security-policy']).not.toContain("'unsafe-eval'");
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['cross-origin-embedder-policy']).toBeUndefined();
    expect(headers['cross-origin-opener-policy']).toBeUndefined();
    if (filename.endsWith('.wasm'))
      expect(headers['content-type']).toContain('application/wasm');
    if (filename.endsWith('.js'))
      expect(headers['content-type']).toMatch(
        /(?:application|text)\/javascript/,
      );
  }
  expect((await request.get('/assets/nonexistent-version.wasm')).status()).toBe(
    404,
  );
  expect((await request.get('/_headers')).status()).toBe(404);
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Ready');
  expect(await page.evaluate(() => crossOriginIsolated)).toBe(false);
});

test('production worker runs under CSP without Vite paths or policy violations', async ({
  page,
}) => {
  const paths: string[] = [];
  page.on('request', (request) => paths.push(new URL(request.url()).pathname));
  await page.addInitScript(() => {
    (window as unknown as { policyViolations: string[] }).policyViolations = [];
    addEventListener('securitypolicyviolation', (event) => {
      (
        window as unknown as { policyViolations: string[] }
      ).policyViolations.push(
        (event as SecurityPolicyViolationEvent).violatedDirective,
      );
    });
  });
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Ready');
  await page.getByRole('button', { name: 'Simulate 162 games' }).click();
  await expect(
    page.getByRole('region', { name: 'Season result' }),
  ).toContainText('105–57');
  expect(
    await page.evaluate(
      () =>
        (window as unknown as { policyViolations: string[] }).policyViolations,
    ),
  ).toEqual([]);
  expect(paths).toContain(workerUrl());
  expect(paths.some((path) => path.endsWith('.wasm'))).toBe(true);
  expect(paths.some((path) => /\/src\/|@vite|\.tsx?(?:$|\?)/.test(path))).toBe(
    false,
  );
});
