import { expect, test } from '@playwright/test';
import { fixture, largeFixture, nativeResult, session } from './helpers';

for (const seed of ['0', '9007199254740993', '18446744073709551615']) {
  test(`native/browser full-season parity, summary/events, seed ${seed}`, async ({
    page,
  }) => {
    await page.goto('/dev');
    const browser = await session(page);
    const results = [];
    for (const detail of ['summary', 'events']) {
      const input = { ...fixture, seed, detail };
      const expected = nativeResult(input);
      const response = await browser.evaluate(
        (worker, request) => worker.send(request),
        {
          type: 'simulate' as const,
          requestId: detail,
          inputJson: JSON.stringify(input),
          output: 'full' as const,
        },
      );
      expect(response.type).toBe('result');
      if (response.type !== 'result') throw new Error(JSON.stringify(response));
      const actual = JSON.parse(response.resultJson!);
      // Parsed deep equality ignores JSON key ordering; includes every score, seed,
      // box, runner, credited event, transition index and engine/model version.
      expect(actual).toEqual(expected);
      expect(actual.input.seed).toBe(seed);
      const compact = await browser.evaluate(
        (worker, request) => worker.send(request),
        {
          type: 'simulate' as const,
          requestId: `compact-${detail}`,
          inputJson: JSON.stringify(input),
          output: 'summary' as const,
        },
      );
      expect(compact.type).toBe('result');
      if (compact.type !== 'result') throw new Error(JSON.stringify(compact));
      expect(compact.summary).toEqual(response.summary);
      expect(compact).not.toHaveProperty('resultJson');
      expect(compact.timings.resultJsonBytes).toBeLessThan(300);
      const batting = await browser.evaluate(
        (worker, request) => worker.send(request),
        {
          type: 'simulate' as const,
          requestId: `batting-${detail}`,
          inputJson: JSON.stringify(input),
          output: 'batting' as const,
        },
      );
      expect(batting.type).toBe('result');
      if (batting.type !== 'result') throw new Error(JSON.stringify(batting));
      expect(batting.summary).toEqual(response.summary);
      expect(batting.batting).toEqual({
        schemaVersion: '1.0.0',
        teamId: expected.team.teamId,
        totals: expected.team.totals,
        batters: expected.team.batters,
      });
      expect(batting).not.toHaveProperty('resultJson');
      expect(batting.timings.resultJsonBytes).toBeLessThan(6000);

      if (detail === 'events')
        expect(
          actual.games.every(
            (game: { eventLog: unknown[] }) => game.eventLog.length > 0,
          ),
        ).toBe(true);
      actual.input.detail = 'summary';
      for (const game of actual.games) delete game.eventLog;
      results.push(actual);
    }
    expect(results[0]).toEqual(results[1]);
    await browser.evaluate((worker) => worker.terminate());
  });
}

test('29 synthetic opponents and 270 profiles preserve exact full/native results', async ({
  page,
}) => {
  await page.goto('/dev');
  const worker = await session(page);
  const input = {
    ...largeFixture(),
    seed: '18446744073709551615',
    detail: 'events',
  };
  expect(input.opponents).toHaveLength(29);
  expect(input.profiles).toHaveLength(270);
  const expected = nativeResult(input);
  const response = await worker.evaluate(
    (instance, request) => instance.send(request),
    {
      type: 'simulate' as const,
      requestId: 'capacity',
      inputJson: JSON.stringify(input),
      output: 'full' as const,
    },
  );
  expect(response.type).toBe('result');
  if (response.type !== 'result') throw new Error(JSON.stringify(response));
  expect(JSON.parse(response.resultJson!)).toEqual(expected);
  const compact = await worker.evaluate(
    (instance, request) => instance.send(request),
    {
      type: 'simulate' as const,
      requestId: 'capacity-compact',
      inputJson: JSON.stringify(input),
      output: 'summary' as const,
    },
  );
  expect(compact.type).toBe('result');
  if (compact.type !== 'result') throw new Error(JSON.stringify(compact));
  expect(compact.summary).toEqual(response.summary);
  await worker.evaluate((instance) => instance.terminate());
});

test('structured errors, aborts and recovery; initialization runs once', async ({
  page,
}) => {
  const loads: string[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('.wasm')) loads.push(request.url());
  });
  // A same-origin blank page avoids counting the app's own worker initialization.
  await page.route('**/test-blank', (route) =>
    route.fulfill({ contentType: 'text/html', body: '<title>Parity</title>' }),
  );
  await page.goto('/test-blank');
  const browser = await session(page);
  for (let i = 0; i < 2; i++) {
    const response = await browser.evaluate(
      (worker, request) => worker.send(request),
      { type: 'initialize' as const, requestId: `init${i}` },
    );
    expect(response.type).toBe('ready');
  }
  const cases = [
    ['{', 'invalidJson'],
    [JSON.stringify({ ...fixture, seed: 9007199254740992 }), 'invalidJson'],
    [
      JSON.stringify({ ...fixture, seed: '18446744073709551616' }),
      'invalidInput',
    ],
    [
      JSON.stringify({
        ...fixture,
        config: { ...fixture.config, maxPlateAppearances: 1 },
      }),
      'gameFailed',
    ],
  ];
  for (const [inputJson, code] of cases) {
    const response = await browser.evaluate(
      (worker, request) => worker.send(request),
      {
        type: 'simulate' as const,
        requestId: code,
        inputJson,
        output: 'summary' as const,
      },
    );
    expect(response.type).toBe('error');
    if (response.type !== 'error')
      throw new Error('Expected a structured error');
    expect(response.error.code).toBe(code);
    if (code === 'gameFailed') expect(response.error.gameNumber).toBe(1);
  }
  const recovered = await browser.evaluate(
    (worker, request) => worker.send(request),
    {
      type: 'simulate' as const,
      requestId: 'recovered',
      inputJson: JSON.stringify(fixture),
      output: 'summary' as const,
    },
  );
  expect(recovered.type).toBe('result');
  expect(recovered).not.toHaveProperty('resultJson');
  expect(loads).toHaveLength(1);
  await browser.evaluate((worker) => worker.terminate());
});

test('worker rejects overlap while initializing and the main thread keeps rendering', async ({
  page,
}) => {
  await page.goto('/dev');
  const browser = await session(page);
  const responses = await browser.evaluate(async (worker) =>
    Promise.all([
      worker.send({ type: 'initialize' as const, requestId: 'first' }),
      worker.send({ type: 'initialize' as const, requestId: 'overlap' }),
    ]),
  );
  expect(responses[0].type).toBe('ready');
  expect(responses[1]).toMatchObject({
    type: 'error',
    error: { code: 'busy' },
  });
  const rendering = await browser.evaluate(
    async (worker, request) => {
      // Start and stop inside the same task/request interval: frames between
      // separate test-driver calls must not satisfy the responsiveness check.
      let frames = 0;
      let frameId: number;
      const frame = () => {
        frames++;
        frameId = requestAnimationFrame(frame);
      };
      frameId = requestAnimationFrame(frame);
      try {
        const response = await worker.send(request);
        return { response, frames };
      } finally {
        cancelAnimationFrame(frameId);
      }
    },
    {
      type: 'simulate' as const,
      requestId: 'long-season',
      inputJson: JSON.stringify({ ...fixture, games: 1000, detail: 'events' }),
      output: 'summary' as const,
    },
  );
  expect(rendering.response.type).toBe('result');
  expect(rendering.frames).toBeGreaterThan(0);
  await browser.evaluate((worker) => worker.terminate());
});

test('React harness renders the fixture result and supports worker restart', async ({
  page,
}) => {
  await page.goto('/dev');
  await expect(page.getByRole('status')).toHaveText('Ready');
  await page.getByRole('button', { name: 'Simulate 162 games' }).click();
  await expect(
    page.getByRole('region', { name: 'Season result' }),
  ).toContainText('105–57');
  await expect(
    page.getByRole('region', { name: 'Season result' }),
  ).toContainText('759');
  await page.getByRole('button', { name: 'Stop worker' }).click();
  await expect(page.getByRole('status')).toHaveText('Worker stopped');
  await expect(
    page.getByRole('button', { name: 'Simulate 162 games' }),
  ).toBeDisabled();
  await page.getByRole('button', { name: 'Restart worker' }).click();
  await expect(page.getByRole('status')).toHaveText('Ready');
  await page.getByRole('button', { name: 'Simulate 162 games' }).click();
  await expect(
    page.getByRole('region', { name: 'Season result' }),
  ).toContainText('105–57');
});

test('initialization failure is visible and a fresh worker can recover', async ({
  page,
}) => {
  await page.route('**/*.wasm', (route) => route.abort());
  await page.goto('/dev');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Simulate 162 games' }),
  ).toBeDisabled();
  await page.unroute('**/*.wasm');
  await page.getByRole('button', { name: 'Restart worker' }).click();
  await expect(page.getByRole('status')).toHaveText('Ready');
});

test('stopping during initialization does not revive or error the stopped worker', async ({
  page,
}) => {
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/*.wasm', async (route) => {
    await gate;
    await route.continue().catch(() => {}); // Termination can cancel the routed fetch.
  });
  const requested = page.waitForRequest('**/*.wasm');
  await page.goto('/dev');
  await requested;
  await page.getByRole('button', { name: 'Stop worker' }).click();
  release();
  await expect(page.getByRole('status')).toHaveText('Worker stopped');
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('diagnostic data controls stay in place while WASM initialization completes', async ({
  page,
}) => {
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/*.wasm', async (route) => {
    await gate;
    await route.continue();
  });
  const requested = page.waitForRequest('**/*.wasm');
  await page.goto('/dev');
  await requested;
  const button = page.getByRole('button', { name: 'Load published datasets' });
  const before = await button.boundingBox();
  release();
  await expect(page.getByRole('status')).toHaveText('Ready');
  const after = await button.boundingBox();
  expect(after!.y).toBe(before!.y);
});

test('unsupported Worker construction is shown as an initialization error', async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(window, 'Worker', { value: undefined }),
  );
  await page.goto('/dev');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Simulate 162 games' }),
  ).toBeDisabled();
});
