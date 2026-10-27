import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { nativeResult, session } from './helpers';

async function finish(page: Page) {
  await page.getByRole('button', { name: 'Start / replay draft' }).click();
  await expect(page.getByTestId('draft-status')).toHaveText('Drafting C');
  const first = await page.getByLabel('Selectable player offers').textContent();
  const actionMs: number[] = [];
  for (let i = 0; i < 9; i++) {
    const buttons = page
      .getByLabel('Selectable player offers')
      .getByRole('button');
    expect(await buttons.count()).toBeGreaterThan(0);
    expect(await buttons.count()).toBeLessThanOrEqual(3);
    const begin = performance.now();
    await buttons.first().click();
    actionMs.push(performance.now() - begin);
  }
  await expect(page.getByTestId('draft-status')).toHaveText('Draft complete');
  return { first, actionMs };
}
test('protected draft UI replays on mobile layout without downloading simulation profiles', async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const api: string[] = [];
  page.on('request', (r) => {
    if (new URL(r.url()).pathname.startsWith('/api/')) api.push(r.url());
  });
  await page.goto('/');
  const { first, actionMs } = await finish(page);
  const saved = JSON.parse(
    (await page.getByTestId('draft-json').textContent()) ?? '{}',
  );
  expect(saved.history.length).toBe(9);
  expect(
    new Set(saved.history.map((p: { playerId: string }) => p.playerId)).size,
  ).toBe(9);
  expect(saved.remainingBudget).toBeGreaterThanOrEqual(0);
  expect(api).toEqual([]);
  await page.getByRole('button', { name: 'Start / replay draft' }).click();
  await expect(page.getByLabel('Selectable player offers')).toHaveText(first!);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  mkdirSync('target/m7b', { recursive: true });
  writeFileSync(
    `target/m7b/browser-${info.project.name}.json`,
    JSON.stringify(
      { viewport: '390x844 desktop browser emulation', actionMs },
      null,
      2,
    ),
  );
  await page.screenshot({
    path: `target/m7b/draft-${info.project.name}.png`,
    fullPage: true,
  });
});
test('catalog load errors and infeasible budgets are visible and retryable', async ({
  page,
}) => {
  await page.route('**/assets/mlb-draft-2024-*.json', (route) =>
    route.fulfill({ status: 503, body: 'Unavailable' }),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Start / replay draft' }).click();
  await expect(page.getByRole('alert')).toContainText(
    'Offer catalog unavailable',
  );
  await page.unroute('**/assets/mlb-draft-2024-*.json');
  await page.getByLabel('Starting credits').fill('0');
  await page.getByRole('button', { name: 'Start / replay draft' }).click();
  await expect(page.getByRole('alert')).toContainText('infeasible');
  await page.getByLabel('Starting credits').fill('90');
  await page.getByRole('button', { name: 'Start / replay draft' }).click();
  await expect(page.getByTestId('draft-status')).toHaveText('Drafting C');
});
test('real published draft retrieves nine profiles and matches complete native/WASM season', async ({
  page,
}, info) => {
  test.skip(
    !process.env.M6B_IMPORT_SQL,
    'Requires the verified 526-player local M6A export; CI has only the named M4 test publication',
  );
  const requests: { path: string; ids?: string[] }[] = [];
  page.on('request', (r) => {
    const path = new URL(r.url()).pathname;
    if (path.startsWith('/api/'))
      requests.push({ path, ids: r.postDataJSON()?.profileIds });
  });
  await page.addInitScript(() => {
    const original = Worker.prototype.postMessage;
    (window as unknown as { draftInput: string }).draftInput = '';
    Worker.prototype.postMessage = function (
      message: unknown,
      ...args: unknown[]
    ) {
      const m = message as { type?: string; inputJson?: string };
      if (m.type === 'simulate' && m.inputJson)
        (window as unknown as { draftInput: string }).draftInput = m.inputJson;
      return Reflect.apply(original, this, [message, ...args]);
    };
  });
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Ready');
  await finish(page);
  expect(requests).toEqual([]);
  await page
    .getByRole('button', { name: 'Simulate drafted 162 games' })
    .click();
  await expect(page.getByTestId('draft-result')).toContainText('162 games');
  const inputJson = await page.evaluate(
    () => (window as unknown as { draftInput: string }).draftInput,
  );
  const expected = nativeResult(JSON.parse(inputJson));
  const batch = requests.filter((r) => r.path === '/api/profiles/batch');
  expect(batch).toHaveLength(1);
  expect(batch[0].ids).toHaveLength(9);
  expect(requests.some((r) => r.path.startsWith('/api/players'))).toBe(false);
  const worker = await session(page);
  await worker.evaluate((w) =>
    w.send({ type: 'initialize', requestId: 'draft-init' }),
  );
  const result = await worker.evaluate(
    (w, inputJson) =>
      w.send({
        type: 'simulate',
        requestId: 'draft-full',
        inputJson,
        output: 'full',
      }),
    inputJson,
  );
  expect(result.type).toBe('result');
  if (result.type !== 'result') throw new Error(JSON.stringify(result));
  expect(JSON.parse(result.resultJson!)).toEqual(expected);
  await worker.evaluate((w) => w.terminate());
  const before = requests.length;
  await page
    .getByRole('button', { name: 'Simulate drafted 162 games' })
    .click();
  await expect(page.getByTestId('draft-result')).toContainText('162 games');
  expect(requests.length).toBe(before);
  mkdirSync('target/m7b', { recursive: true });
  writeFileSync(
    `target/m7b/season-${info.project.name}.json`,
    JSON.stringify(
      {
        requests,
        wins: expected.wins,
        losses: expected.losses,
        runs: expected.runsScored,
        wasmMs: result.timings.wasmCallMs,
      },
      null,
      2,
    ),
  );
});
