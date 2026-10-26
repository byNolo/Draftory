import { execFileSync } from 'node:child_process';
import { writeFileSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { gzipSync } from 'node:zlib';
import { test } from '@playwright/test';
import { artifacts, fixture, largeFixture, session } from './helpers';
import { distribution, workerHeap } from './benchmark-support';

interface Visit {
  cache: string;
  index: number;
  timing: { readyMs: number; resultMs: number };
  resources: {
    name: string;
    transferSize: number;
    encodedBodySize: number;
    decodedBodySize: number;
    duration: number;
  }[];
}

test('startup, phase costs, capacity, payloads and repeated execution (no speed gate)', async ({
  page,
  browser,
}, info) => {
  test.setTimeout(240_000);
  const repetitions = Number(process.env.M5B_REPETITIONS ?? '10');
  if (!Number.isInteger(repetitions) || repetitions < 3 || repetitions > 100)
    throw new Error('M5B_REPETITIONS must be 3..100');
  const visits: Visit[] = [];
  // Fresh HTTP-cache contexts, then reload each same context. Routing/interception
  // would disable HTTP caches; no synthetic throttling or request routing is used.
  for (let index = 0; index < 3; index++) {
    const context = await browser.newContext({
      baseURL: 'http://127.0.0.1:4173',
    });
    const visit = await context.newPage();
    await visit.addInitScript(() => {
      const state: { readyMs?: number; resultMs?: number } = {};
      (window as unknown as { visitTiming: typeof state }).visitTiming = state;
      const observer = new MutationObserver(() => {
        if (
          document.querySelector('[role="status"]')?.textContent === 'Ready' &&
          state.readyMs === undefined
        ) {
          state.readyMs = performance.now();
          (document.querySelector('button') as HTMLButtonElement).click();
        }
        if (document.querySelector('section[aria-label="Season result"]')) {
          state.resultMs = performance.now();
          observer.disconnect();
        }
      });
      observer.observe(document, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    });
    for (const cache of ['fresh-context-http-cache', 'same-context-reload']) {
      if (cache === 'fresh-context-http-cache') await visit.goto('/');
      else await visit.reload();
      await visit.getByRole('region', { name: 'Season result' }).waitFor();
      visits.push(
        await visit.evaluate(
          ({ cache, index }) => ({
            cache,
            index,
            timing: (
              window as unknown as {
                visitTiming: { readyMs: number; resultMs: number };
              }
            ).visitTiming,
            resources: (
              performance.getEntriesByType(
                'resource',
              ) as PerformanceResourceTiming[]
            ).map(
              ({
                name,
                transferSize,
                encodedBodySize,
                decodedBodySize,
                duration,
              }) => ({
                name,
                transferSize,
                encodedBodySize,
                decodedBodySize,
                duration,
              }),
            ),
          }),
          { cache, index },
        ),
      );
    }
    await context.close();
  }
  await page.goto('/__bench.html');
  const measurements = [];
  for (const [inputKind, base] of [
    ['small-observed', fixture],
    ['29-opponent-synthetic-capacity', largeFixture()],
  ] as const) {
    for (const detail of ['summary', 'events']) {
      const inputJson = JSON.stringify({ ...base, detail });
      const inputPath = resolve(
        artifacts,
        `m5b-input-${inputKind}-${detail}.json`,
      );
      writeFileSync(inputPath, inputJson);
      for (const output of ['summary', 'summaryBaseline', 'full'] as const) {
        const binary = resolve(
          process.cwd(),
          `target/release/examples/measure_boundary${process.platform === 'win32' ? '.exe' : ''}`,
        );
        const native = JSON.parse(
          execFileSync(
            binary,
            [
              inputPath,
              String(repetitions + 1),
              output === 'summary' ? 'summary' : 'full',
            ],
            { encoding: 'utf8' },
          ),
        );
        const worker = await session(page);
        const initialized = await worker.evaluate(async (instance) => {
          const response = await instance.send({
            type: 'initialize',
            requestId: 'init',
          });
          if (response.type !== 'ready')
            throw new Error(JSON.stringify(response));
          return {
            ...response,
            readyRoundTripMs: performance.now() - instance.createdAt,
          };
        });
        const before = await workerHeap(browser);
        const samples = [];
        for (let i = 0; i <= repetitions; i++) {
          samples.push(
            await worker.evaluate(
              async (instance, request) => {
                const start = performance.now();
                const response = await instance.send(request);
                const roundTripMs = performance.now() - start;
                if (response.type !== 'result')
                  throw new Error(JSON.stringify(response));
                const { resultJson, ...message } = response;
                return {
                  response: message,
                  roundTripMs,
                  messagingOverheadMs: Math.max(
                    0,
                    roundTripMs - response.timings.workerTotalMs,
                  ),
                  // UTF-8 application-payload estimate, not undocumented IPC wire bytes.
                  payloadBytes:
                    new TextEncoder().encode(JSON.stringify(message)).length +
                    (resultJson ? response.timings.resultJsonBytes : 0),
                };
              },
              {
                type: 'simulate' as const,
                requestId: String(i),
                inputJson,
                output,
              },
            ),
          );
        }
        const after = await workerHeap(browser);
        await worker.evaluate((instance) => instance.terminate());
        const warm = samples.slice(1);
        const summary = {
          nativeBoundaryMs: distribution(native.boundaryMs.slice(1)),
          roundTripMs: distribution(warm.map((s) => s.roundTripMs)),
          messagingOverheadMs: distribution(
            warm.map((s) => s.messagingOverheadMs),
          ),
          payloadBytes: distribution(warm.map((s) => s.payloadBytes)),
          phases: Object.fromEntries(
            [
              'inputParsingMs',
              'simulationMs',
              'serializationMs',
              'wasmCallMs',
              'resultProcessingMs',
              'wasmMemoryAfterBytes',
            ].map((field) => [
              field,
              distribution(
                warm.map(
                  (s) =>
                    s.response.timings[
                      field as keyof typeof s.response.timings
                    ],
                ),
              ),
            ]),
          ),
        };
        measurements.push({
          inputKind,
          opponents: base.opponents.length,
          profiles: base.profiles.length,
          detail,
          output,
          inputBytes: Buffer.byteLength(inputJson),
          initialized,
          before,
          after,
          native,
          first: samples[0],
          warm: summary,
          samples,
        });
      }
    }
  }
  const assets = readdirSync('apps/web/dist/assets').map((name) => {
    const bytes = readFileSync(resolve('apps/web/dist/assets', name));
    return { name, bytes: bytes.length, gzipBytes: gzipSync(bytes).length };
  });
  const startup = Object.fromEntries(
    ['fresh-context-http-cache', 'same-context-reload'].map((cache) => {
      const values = visits.filter((v) => v.cache === cache);
      return [
        cache,
        {
          readyMs: distribution(values.map((v) => v.timing.readyMs)),
          resultMs: distribution(values.map((v) => v.timing.resultMs)),
        },
      ];
    }),
  );
  const report = {
    schemaVersion: '2.0.0',
    project: info.project.name,
    browser: browser.version(),
    userAgent: await page.evaluate(() => navigator.userAgent),
    repetitions,
    startup,
    visits,
    measurements,
    assets,
    memoryApi: await page.evaluate(() => ({
      crossOriginIsolated,
      measureUserAgentSpecificMemory:
        'measureUserAgentSpecificMemory' in performance,
    })),
  };
  const path = resolve(artifacts, `m5b-${info.project.name}.json`);
  writeFileSync(path, JSON.stringify(report, null, 2));
  console.log(`M5B performance: ${path}`);
});
