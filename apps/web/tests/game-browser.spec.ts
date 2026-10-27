import { expect, test, type Page } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { historicalBatting, rate } from '../src/mlb/game/batting';
import { nativeResult } from './helpers';
import { DraftEngine, type Catalog } from '../src/mlb/draft/engine';
import type { WorkerResponse, WorkerRequest } from '../src/workers/protocol';
const fixture = JSON.parse(
  readFileSync('data/fixtures/mlb-game-2024-v1.json', 'utf8'),
);
const catalog: Catalog = JSON.parse(
  readFileSync('data/publications/mlb-draft-2024-v1.json', 'utf8'),
);
const engine = new DraftEngine(catalog);
type Run = {
  request: Extract<WorkerRequest, { type: 'simulate' }>;
  response: Extract<WorkerResponse, { type: 'result' }>;
};
async function setup(page: Page) {
  // Small verified source excerpt in ordinary CI; real D1 is exercised with M6B_IMPORT_SQL.
  if (!process.env.M6B_IMPORT_SQL)
    await page.route('**/api/**', async (route) => {
      const url = new URL(route.request().url());
      let value: object;
      if (url.pathname.startsWith('/api/players/')) {
        const id = decodeURIComponent(url.pathname.split('/').at(-1)!);
        const player = fixture.players.find((p: { id: string }) => p.id === id);
        if (!player) {
          await route.fulfill({
            status: 404,
            json: {
              schemaVersion: '1.0.0',
              error: {
                code: 'fixtureOnly',
                message: 'Outside the verified test excerpt',
              },
            },
          });
          return;
        }
        value = { datasetId: catalog.datasetId, player };
      } else if (url.pathname === '/api/profiles/batch') {
        const ids = route.request().postDataJSON().profileIds as string[];
        value = {
          datasetId: catalog.datasetId,
          profiles: ids.map((id) =>
            fixture.profiles.find((p: { id: string }) => p.id === id),
          ),
        };
      } else value = { dataset: fixture.dataset };
      await route.fulfill({ json: { schemaVersion: '1.0.0', ...value } });
    });
  await page.addInitScript(() => {
    const runs: unknown[] = [];
    (window as unknown as { gameRuns: unknown[] }).gameRuns = runs;
    const original = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (
      message: unknown,
      ...args: unknown[]
    ) {
      const m = message as { type?: string; requestId?: string };
      if (m.type === 'simulate') {
        const listener = (event: MessageEvent) => {
          if (event.data.requestId === m.requestId) {
            runs.push({ request: message, response: event.data });
            this.removeEventListener('message', listener);
          }
        };
        this.addEventListener('message', listener);
      }
      return Reflect.apply(original, this, [message, ...args]);
    };
  });
  await page.goto('/?playtest=1');
  await page.getByText('Replay a draft seed', { exact: true }).click();
  await page.getByLabel('Draft seed', { exact: true }).fill('20261027');
  await page.getByRole('button', { name: 'Start your draft' }).click();
}
async function finish(page: Page) {
  for (let i = 0; i < 9; i++) {
    const id = fixture.draft.history[i].playerId;
    await page
      .getByRole('button', {
        name: `Draft ${engine.player(id).name}`,
        exact: true,
      })
      .click();
    await expect(page.getByTestId('game-budget')).toHaveText(
      String(
        90 -
          fixture.draft.history
            .slice(0, i + 1)
            .reduce((sum: number, p: { price: number }) => sum + p.price, 0),
      ),
    );
  }
  await expect(
    page.getByRole('heading', { name: 'Lineup locked.' }),
  ).toBeVisible();
  await expect(page.getByLabel('Your lineup')).toContainText('9 / 9');
  await page.getByText('Season seed and model notes', { exact: true }).click();
  await page.getByLabel('Season seed', { exact: true }).fill('20261025');
}
const runs = (page: Page) =>
  page.evaluate(() => (window as unknown as { gameRuns: Run[] }).gameRuns);

test('complete playable flow: historical cards, roster, compact native parity, repeat and reset', async ({
  page,
}, info) => {
  const requests: string[] = [];
  page.on('request', (r) => requests.push(new URL(r.url()).pathname));
  await setup(page);
  const first = page.getByRole('article').filter({
    has: page.getByRole('heading', { name: 'Will Smith', exact: true }),
  });
  const p = fixture.players[0],
    s = historicalBatting(p, engine.player(p.id), 2024);
  await expect(first).toContainText(rate(s.avg));
  await expect(first).toContainText(rate(s.obp));
  await expect(first).toContainText(rate(s.slg));
  expect(
    requests.some((p) => p.endsWith('.wasm') || p.includes('DeveloperHarness')),
  ).toBe(false);
  expect(requests.some((p) => p.startsWith('/api/profiles'))).toBe(false);
  mkdirSync('target/m7c', { recursive: true });
  await page.screenshot({
    path: `target/m7c/offers-${info.project.name}.png`,
    fullPage: true,
  });
  await finish(page);
  await page
    .getByRole('button', { name: 'Simulate 162-game season', exact: true })
    .click();
  const results = page.getByRole('region', {
    name: 'Simulated season results',
    exact: true,
  });
  await expect(results).toContainText('81–81');
  await expect(results.getByRole('row')).toHaveCount(11);
  const [firstRun] = await runs(page);
  const native = nativeResult(JSON.parse(firstRun.request.inputJson));
  expect(firstRun.request.output).toBe('batting');
  expect(firstRun.response.batting).toEqual({
    schemaVersion: '1.0.0',
    teamId: native.team.teamId,
    totals: native.team.totals,
    batters: native.team.batters,
  });
  expect(firstRun.response).not.toHaveProperty('resultJson');
  expect(firstRun.response.timings.resultJsonBytes).toBeLessThan(6000);
  for (const row of native.team.batters) {
    const player = engine.player(row.batterId.replace('draft:2024:', ''));
    await expect(
      results.getByRole('row').filter({ hasText: player.name }),
    ).toContainText(String(row.stats.plateAppearances));
  }
  const batchCount = requests.filter((p) => p === '/api/profiles/batch').length;
  await page.getByRole('button', { name: 'Replay this season seed' }).click();
  await expect.poll(async () => (await runs(page)).length).toBe(2);
  const second = (await runs(page))[1];
  expect(second.response.batting).toEqual(firstRun.response.batting);
  expect(second.response.summary).toEqual(firstRun.response.summary);
  expect(requests.filter((p) => p === '/api/profiles/batch').length).toBe(
    batchCount,
  );
  await page
    .getByRole('button', { name: 'Play another season', exact: true })
    .click();
  await expect.poll(async () => (await runs(page)).length).toBe(3);
  const third = (await runs(page))[2];
  expect(third.response.summary.seed).not.toBe(firstRun.response.summary.seed);
  await page.getByText('Local playtest tools', { exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export session JSON' }).click();
  const file = await download;
  const path = await file.path();
  const exported = JSON.parse(readFileSync(path!, 'utf8'));
  writeFileSync(
    `target/m7c/session-${info.project.name}.json`,
    JSON.stringify(exported, null, 2),
  );
  expect(exported.draft).toEqual(fixture.draft);
  expect(exported.result.batting).toEqual(third.response.batting);
  writeFileSync(
    `target/m7c/game-${info.project.name}.json`,
    JSON.stringify({ runs: await runs(page), requestPaths: requests }, null, 2),
  );
  await page.screenshot({
    path: `target/m7c/results-${info.project.name}.png`,
    fullPage: true,
  });
  await page
    .getByRole('button', { name: 'Start a new draft', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Who’s your C?' }),
  ).toBeVisible();
  await expect(page.getByTestId('game-budget')).toHaveText('90');
  await expect(results).toHaveCount(0);
  await expect(page.getByLabel('Your lineup')).toContainText('0 / 9');
  if (process.env.M6B_IMPORT_SQL) {
    await expect(
      page.getByLabel('Player offers').getByRole('button').first(),
    ).toBeEnabled();
    await expect(page.getByRole('alert')).toHaveCount(0);
  }
});

test('mobile keyboard flow, loading, retry after API/WASM failures and cancellation', async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await page.route('**/api/players/**', (route) =>
    route.fulfill({
      status: 503,
      json: {
        schemaVersion: '1.0.0',
        error: { code: 'unavailable', message: 'Temporary player-data outage' },
      },
    }),
  );
  await page.reload();
  await page.getByText('Replay a draft seed', { exact: true }).click();
  await page.getByLabel('Draft seed', { exact: true }).fill('20261027');
  await page.getByRole('button', { name: 'Start your draft' }).click();
  await expect(page.getByRole('alert')).toContainText(
    'Temporary player-data outage',
  );
  await expect(
    page.getByRole('button', { name: 'Draft Will Smith', exact: true }),
  ).toBeDisabled();
  await page.unroute('**/api/players/**');
  await page.getByRole('button', { name: 'Retry player statistics' }).click();
  const pick = page.getByRole('button', {
    name: 'Draft Will Smith',
    exact: true,
  });
  await expect(pick).toBeEnabled();
  await page.keyboard.press('Tab');
  await pick.focus();
  await expect(pick).toBeFocused();
  expect(
    await pick.evaluate((el) => getComputedStyle(el).outlineStyle),
  ).not.toBe('none');
  expect((await pick.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await page.screenshot({
    path: `target/m7c/mobile-offers-${info.project.name}.png`,
    fullPage: true,
  });
  await pick.press('Enter');
  await expect(
    page.getByRole('heading', { name: 'Who’s your SS?' }),
  ).toBeFocused();
  for (let i = 1; i < 9; i++)
    await page
      .getByRole('button', {
        name: `Draft ${engine.player(fixture.draft.history[i].playerId).name}`,
        exact: true,
      })
      .click();
  await page.route('**/api/profiles/batch', (route) =>
    route.fulfill({
      status: 503,
      json: {
        schemaVersion: '1.0.0',
        error: {
          code: 'unavailable',
          message: 'Profiles temporarily unavailable',
        },
      },
    }),
  );
  await page
    .getByRole('button', { name: 'Simulate 162-game season', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText(
    'Profiles temporarily unavailable',
  );
  await expect(page.getByLabel('Your lineup')).toContainText('9 / 9');
  await page.unroute('**/api/profiles/batch');
  await page.route('**/*.wasm', (route) => route.abort());
  await page
    .getByRole('button', { name: 'Simulate 162-game season', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText('Your lineup is saved');
  await page.unroute('**/*.wasm');
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/*.wasm', async (route) => {
    await gate;
    await route.continue().catch(() => {});
  });
  await page
    .getByRole('button', { name: 'Simulate 162-game season', exact: true })
    .click();
  await expect(page.getByRole('status')).toContainText('Preparing');
  await expect(
    page.getByRole('button', { name: 'Start a new draft' }),
  ).toBeDisabled();
  await page.getByRole('button', { name: 'Cancel season' }).click();
  release();
  await expect(page.getByRole('status')).toContainText('cancelled');
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.unroute('**/*.wasm');
  await page
    .getByRole('button', { name: 'Simulate 162-game season', exact: true })
    .click();
  await expect(
    page.getByRole('region', { name: 'Simulated season results', exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `target/m7c/mobile-results-${info.project.name}.png`,
    fullPage: true,
  });
});
