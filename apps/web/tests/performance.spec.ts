import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from '@playwright/test';
import { artifacts, fixture, session } from './helpers';

test('measure browser and equivalent native JSON boundaries (no speed gate)', async ({
  page,
  browser: engine,
}) => {
  await page.route('**/test-blank', (route) =>
    route.fulfill({
      contentType: 'text/html',
      body: '<title>Benchmark</title>',
    }),
  );
  await page.goto('/test-blank');
  const worker = await session(page);
  const initialization = await worker.evaluate(async (instance) => {
    const response = await instance.send({
      type: 'initialize',
      requestId: 'init',
    });
    return {
      response,
      workerReadyRoundTripMs: performance.now() - instance.createdAt,
    };
  });
  const measurements = [];
  for (const detail of ['summary', 'events']) {
    const inputJson = JSON.stringify({ ...fixture, detail });
    const inputPath = resolve(artifacts, `benchmark-${detail}.json`);
    writeFileSync(inputPath, inputJson);
    const binary = resolve(
      process.cwd(),
      `target/release/examples/measure_boundary${process.platform === 'win32' ? '.exe' : ''}`,
    );
    const native = JSON.parse(
      execFileSync(binary, [inputPath, '11'], { encoding: 'utf8' }),
    );
    const samples = [];
    for (let i = 0; i < 11; i++) {
      samples.push(
        await worker.evaluate(
          async (instance, request) => {
            const start = performance.now();
            const response = await instance.send(request);
            if (response.type !== 'result')
              throw new Error(JSON.stringify(response));
            return { response, roundTripMs: performance.now() - start };
          },
          {
            type: 'simulate' as const,
            requestId: `${detail}${i}`,
            inputJson,
            output: 'summary' as const,
          },
        ),
      );
    }
    measurements.push({ detail, native, samples });
  }
  await worker.evaluate((instance) => instance.terminate());
  const report = {
    browser: engine.version(),
    userAgent: await page.evaluate(() => navigator.userAgent),
    hardwareConcurrency: await page.evaluate(
      () => navigator.hardwareConcurrency,
    ),
    ...initialization,
    measurements,
  };
  writeFileSync(
    resolve(artifacts, 'performance.json'),
    JSON.stringify(report, null, 2),
  );
  console.log(
    `Browser performance report: ${resolve(artifacts, 'performance.json')}`,
  );
});
