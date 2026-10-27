import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { distribution } from './benchmark-support';
import { nativeResult, session } from './helpers';

async function captureInputs(page: Page) {
  await page.addInitScript(() => {
    const state = window as unknown as { m6bInputs: string[] };
    state.m6bInputs = [];
    const original = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (
      message: unknown,
      options?: StructuredSerializeOptions | Transferable[],
    ) {
      const request = message as { type?: string; inputJson?: string };
      if (request.type === 'simulate' && request.inputJson)
        state.m6bInputs.push(request.inputJson);
      return Reflect.apply(original, this, [message, options]);
    };
  });
}
async function preparedPage(page: Page) {
  await page.goto('/dev');
  await expect(page.getByRole('status')).toHaveText('Ready');
  await page.getByRole('button', { name: 'Load published datasets' }).click();
  await expect(
    page.getByRole('button', { name: 'Load pilot data', exact: true }),
  ).toBeEnabled();
  await page
    .getByRole('button', { name: 'Load pilot data', exact: true })
    .click();
  await expect(page.getByTestId('data-status')).toHaveText(
    'Published input ready',
  );
}
async function run(page: Page) {
  await page
    .getByRole('button', { name: 'Simulate published 162 games' })
    .click();
  await expect(
    page.getByRole('region', { name: 'Season result' }),
  ).toContainText('105–57');
  await expect(page.getByTestId('data-status')).toHaveText(
    'Published input ready',
  );
  const node = page.getByLabel('Data integration measurements');
  return node.evaluate((element) => {
    const d = (element as HTMLElement).dataset;
    return {
      fetchMs: Number(d.fetchMs),
      assemblyMs: Number(d.assemblyMs),
      wasmMs: Number(d.wasmMs),
      roundTripMs: Number(d.roundtripMs),
      requests: Number(d.requests),
      bytes: Number(d.bytes),
    };
  });
}

test('local D1 → API → React → WASM: exact native parity, cache reuse and measured selective transfers', async ({
  page,
}, info) => {
  await captureInputs(page);
  const transfers: Promise<{ path: string; bytes: number; status: number }>[] =
    [];
  const requests: string[] = [];
  const batches: string[][] = [];
  page.on('request', (request) => {
    requests.push(new URL(request.url()).pathname);
    if (
      request.method() === 'POST' &&
      request.url().endsWith('/api/profiles/batch')
    )
      batches.push(request.postDataJSON().profileIds);
  });
  page.on('response', (response) => {
    const path = new URL(response.url()).pathname;
    if (path.startsWith('/api/') || /mlb-pilot.*\.json$/.test(path))
      transfers.push(
        response.body().then((body) => ({
          path,
          bytes: body.byteLength,
          status: response.status(),
        })),
      );
  });
  await preparedPage(page);
  expect(batches).toHaveLength(1);
  expect(batches[0]).toHaveLength(9);
  expect(new Set(batches[0]).size).toBe(9);
  expect(requests.some((p) => p === '/api/players')).toBe(false);
  const before = requests.length;
  const first = await run(page);
  expect(first.requests).toBe(13);
  const warm = [];
  for (let i = 0; i < 5; i++) warm.push(await run(page));
  expect(requests.slice(before)).toEqual([]);
  expect(
    warm.every((s) => s.requests === first.requests && s.bytes === first.bytes),
  ).toBe(true);
  const inputs = await page.evaluate(
    () => (window as unknown as { m6bInputs: string[] }).m6bInputs,
  );
  expect(new Set(inputs).size).toBe(1);
  const input = JSON.parse(inputs[0]);
  expect(input.games).toBe(162);
  expect(input.profiles).toHaveLength(18);
  expect(input.pitchingEnvironment.contextId).not.toBe(
    input.config.contextualModel.id,
  );
  const expected = nativeResult(input);
  expect([
    expected.wins,
    expected.losses,
    expected.runsScored,
    expected.runsAllowed,
  ]).toEqual([105, 57, 759, 580]);
  // A separately initialized production worker returns the complete result. Its
  // initialization is outside the no-network simulation interval.
  const worker = await session(page);
  await worker.evaluate((w) =>
    w.send({ type: 'initialize', requestId: 'init' }),
  );
  const initialized = requests.length;
  const full = await worker.evaluate(
    (w, inputJson) =>
      w.send({
        type: 'simulate',
        requestId: 'full',
        inputJson,
        output: 'full',
      }),
    inputs[0],
  );
  expect(full.type).toBe('result');
  if (full.type !== 'result') throw new Error(JSON.stringify(full));
  expect(JSON.parse(full.resultJson!)).toEqual(expected);
  expect(requests.slice(initialized)).toEqual([]);
  await worker.evaluate((w) => w.terminate());
  await page
    .getByLabel('Season seed', { exact: true })
    .fill('18446744073709551615');
  await page
    .getByRole('button', { name: 'Simulate published 162 games' })
    .click();
  await expect(page.getByTestId('data-status')).toHaveText(
    'Published input ready',
  );
  const maximum = JSON.parse(
    await page.evaluate(() =>
      (window as unknown as { m6bInputs: string[] }).m6bInputs.at(-1)!,
    ),
  );
  expect(maximum.seed).toBe('18446744073709551615');
  const maximumExpected = nativeResult(maximum);
  await expect(
    page.getByRole('region', { name: 'Season result' }),
  ).toContainText(`${maximumExpected.wins}–${maximumExpected.losses}`);
  await page
    .getByText('Inspect selected players and profiles', { exact: true })
    .click();
  await expect(
    page.getByRole('region', { name: 'Published player data' }),
  ).toContainText('lahman:judgeaa01');
  const dataTransfers = await Promise.all(transfers);
  expect(dataTransfers).toHaveLength(13);
  expect(dataTransfers.every((t) => t.status === 200)).toBe(true);
  mkdirSync('target/m6b', { recursive: true });
  const report = {
    schemaVersion: '1.0.0',
    project: info.project.name,
    sourceMode: process.env.M6B_IMPORT_SQL
      ? 'verified-M6A-export'
      : 'M4-prepared-fixture-derived-test-publication',
    first,
    warm,
    transfers: dataTransfers,
    warmAssemblyMs: distribution(warm.map((s) => s.assemblyMs)),
    warmWasmMs: distribution(warm.map((s) => s.wasmMs)),
    warmRoundTripMs: distribution(warm.map((s) => s.roundTripMs)),
    seed: input.seed,
    wins: expected.wins,
    losses: expected.losses,
    runsScored: expected.runsScored,
    runsAllowed: expected.runsAllowed,
    scope:
      'Loopback selective data load; WASM initialized before API run; same-page repetitions. Not first-visit WAN or physical mobile.',
  };
  writeFileSync(
    `target/m6b/${process.env.M6B_IMPORT_SQL ? 'real' : 'fixture'}-${info.project.name}.json`,
    JSON.stringify(report, null, 2),
  );
  writeFileSync(
    `target/m6b/${process.env.M6B_IMPORT_SQL ? 'real' : 'fixture'}-input.json`,
    inputs[0],
  );
});

test('API errors recover by retry; invalid seed stays outside WASM; clear cache causes selective refetch', async ({
  page,
}) => {
  await captureInputs(page);
  await page.route('**/api/datasets?limit=50', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'testUnavailable', message: 'Temporary test failure' },
      }),
    }),
  );
  await page.goto('/dev');
  await expect(page.getByRole('status')).toHaveText('Ready');
  await page.getByRole('button', { name: 'Load published datasets' }).click();
  await expect(page.getByRole('alert')).toContainText('Temporary test failure');
  await page.unroute('**/api/datasets?limit=50');
  await page.getByRole('button', { name: 'Load published datasets' }).click();
  await expect(
    page.getByRole('button', { name: 'Load pilot data', exact: true }),
  ).toBeEnabled();
  await page
    .getByRole('button', { name: 'Load pilot data', exact: true })
    .click();
  await expect(page.getByTestId('data-status')).toHaveText(
    'Published input ready',
  );
  const baseline = await page.evaluate(
    () => (window as unknown as { m6bInputs: string[] }).m6bInputs.length,
  );
  await page
    .getByLabel('Season seed', { exact: true })
    .fill('18446744073709551616');
  await page
    .getByRole('button', { name: 'Simulate published 162 games' })
    .click();
  await expect(page.getByRole('alert')).toContainText('unsigned 64-bit');
  expect(
    await page.evaluate(
      () => (window as unknown as { m6bInputs: string[] }).m6bInputs.length,
    ),
  ).toBe(baseline);
  await page.getByLabel('Season seed', { exact: true }).fill('20261025');
  await run(page);
  let requests = 0;
  page.on('request', (r) => {
    if (r.url().includes('/api/') || /mlb-pilot.*\.json$/.test(r.url()))
      requests++;
  });
  await page
    .getByRole('button', { name: 'Load pilot data', exact: true })
    .click();
  await expect(page.getByTestId('data-status')).toHaveText(
    'Published input ready',
  );
  expect(requests).toBe(0);
  await page.getByRole('button', { name: 'Clear session cache' }).click();
  await expect(
    page.getByRole('button', { name: 'Simulate published 162 games' }),
  ).toBeDisabled();
  await page
    .getByRole('button', { name: 'Load pilot data', exact: true })
    .click();
  await expect(page.getByTestId('data-status')).toHaveText(
    'Published input ready',
  );
  expect(requests).toBe(12);
  await run(page);
});

test('incompatible dataset or unavailable shared context is visible and retryable', async ({
  page,
}) => {
  await page.goto('/dev');
  await page.getByRole('button', { name: 'Load published datasets' }).click();
  await expect(
    page.getByRole('button', { name: 'Load pilot data', exact: true }),
  ).toBeEnabled();
  await page.route('**/api/datasets/*?view=simulation', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.dataset.contextId = 'wrong-baseline';
    await route.fulfill({ response, json: body });
  });
  await page
    .getByRole('button', { name: 'Load pilot data', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText('league baseline');
  await expect(
    page.getByRole('button', { name: 'Simulate published 162 games' }),
  ).toBeDisabled();
  await page.unroute('**/api/datasets/*?view=simulation');
  await page.getByRole('button', { name: 'Clear session cache' }).click();
  await page.route('**/assets/mlb-pilot*.json', (route) => route.abort());
  await page
    .getByRole('button', { name: 'Load pilot data', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText('pilot artifact');
  await page.unroute('**/assets/mlb-pilot*.json');
  await page
    .getByRole('button', { name: 'Load pilot data', exact: true })
    .click();
  await expect(page.getByTestId('data-status')).toHaveText(
    'Published input ready',
  );
});
