import { expect, test, type Page } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { historicalBatting, rate } from '../src/mlb/game/batting';
import { nativeResult } from './helpers';
import { DraftEngine, type Catalog } from '../src/mlb/draft/engine';
import type { WorkerResponse, WorkerRequest } from '../src/workers/protocol';
import {
  defaultBattingOrder,
  moveBatter,
} from '../src/mlb/draft/batting-order';
const fixture = JSON.parse(
  readFileSync('data/fixtures/mlb-game-2024-v1.json', 'utf8'),
);
const catalog: Catalog = JSON.parse(
  readFileSync('data/publications/mlb-draft-2024-v2.json', 'utf8'),
);
const engine = new DraftEngine(catalog);
// Preserve the immutable historical excerpt and v1 golden. Its same offered
// identities replay under the new catalog, with the new prices/budget/version.
fixture.draft = engine.replay(
  '20261027',
  fixture.draft.history.map((p: { playerId: string }) => p.playerId),
);
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
        engine.config.budget -
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

test('current game rejects legacy or modified catalog versions and budgets', async ({
  page,
}) => {
  const legacy = JSON.parse(
    readFileSync('data/publications/mlb-draft-2024-v1.json', 'utf8'),
  );
  for (const payload of [
    legacy,
    { ...catalog, defaultBudget: 90 },
    { ...catalog, pricingPolicy: 'unreviewed' },
  ]) {
    await page.route('**/assets/mlb-draft-2024-*.json', (route) =>
      route.fulfill({ json: payload }),
    );
    await page.goto('/');
    await page.getByRole('button', { name: 'Start your draft' }).click();
    await expect(page.getByRole('alert')).toContainText('digest/version');
    await expect(page.getByLabel('Player offers')).toHaveCount(0);
    await page.unroute('**/assets/mlb-draft-2024-*.json');
  }
});

test('custom batting order: keyboard, pointer/touch, native parity, result identity and session resets', async ({
  page,
}, info) => {
  test.setTimeout(90_000);
  await setup(page);
  await finish(page);
  const original = defaultBattingOrder(fixture.draft);
  const list = page.getByRole('list', { name: 'Batting order', exact: true });
  const ids = () =>
    list
      .locator('li')
      .evaluateAll((rows) =>
        rows.map((r) => (r as HTMLElement).dataset.battingPlayer),
      );
  expect(await ids()).toEqual(original);
  const assignments = await page
    .getByLabel('Your lineup', { exact: true })
    .textContent();
  const name = engine.player(original[2]).name;
  const up = page.getByRole('button', { name: `Move ${name} up`, exact: true });
  await up.focus();
  await up.press('Enter');
  expect(await ids()).toEqual(moveBatter(original, original[2], 1));
  await expect(up).toBeFocused();
  await expect(page.getByRole('status')).toContainText(`${name} now bats 2`);
  await page
    .getByRole('button', { name: `Move ${name} down`, exact: true })
    .click();
  expect(await ids()).toEqual(original);

  const source = list
    .locator('li')
    .nth(2)
    .getByRole('button', { name: /^Reorder / });
  const target = list.locator('li').nth(1);
  await source.scrollIntoViewIfNeeded();
  const a = (await source.boundingBox())!,
    b = (await target.boundingBox())!;
  if (info.project.name === 'mobile-chromium') {
    // Real browser touch input via the existing Playwright/CDP tooling.
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Input.dispatchTouchEvent', {
      type: 'touchStart',
      touchPoints: [{ x: a.x + a.width / 2, y: a.y + a.height / 2 }],
    });
    await cdp.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ x: a.x + a.width / 2, y: b.y + b.height / 2 }],
    });
    await cdp.send('Input.dispatchTouchEvent', {
      type: 'touchEnd',
      touchPoints: [],
    });
    await cdp.detach();
  } else {
    await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
    await page.mouse.down();
    await page.mouse.move(a.x + a.width / 2, b.y + b.height / 2, { steps: 8 });
    await page.mouse.up();
  }
  expect(await ids()).toEqual(moveBatter(original, original[2], 1));
  await page
    .getByRole('button', { name: 'Reset batting order', exact: true })
    .click();
  expect(await ids()).toEqual(original);
  const handle = page.getByRole('button', {
    name: `Reorder ${engine.player(original[8]).name}`,
    exact: true,
  });
  await handle.focus();
  await handle.press('ArrowUp');
  const chosen = moveBatter(original, original[8], 7);
  expect(await ids()).toEqual(chosen);
  await expect(handle).toBeFocused();
  expect(
    await page.getByLabel('Your lineup', { exact: true }).textContent(),
  ).toBe(assignments);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  for (const button of await list.getByRole('button').all()) {
    const box = (await button.boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
  mkdirSync('target/m8c1', { recursive: true });
  await page.screenshot({
    path: `target/m8c1/order-${info.project.name}.png`,
    fullPage: true,
  });
  await page
    .getByRole('button', { name: 'Simulate 162-game season', exact: true })
    .click();
  const result = page.getByRole('region', {
    name: 'Simulated season results',
    exact: true,
  });
  await expect(result).toBeVisible();
  const first = (await runs(page))[0];
  const input = JSON.parse(first.request.inputJson);
  expect(input.userTeam.lineup.map((p: { id: string }) => p.id)).toEqual(
    chosen.map((id) => `draft:2024:${id}`),
  );
  const native = nativeResult(input);
  expect(first.response.batting!.batters).toEqual(native.team.batters);
  const rows = result.locator('tbody tr');
  for (let i = 0; i < chosen.length; i++) {
    const id = chosen[i],
      player = engine.player(id);
    const position = fixture.draft.history.find(
      (p: { playerId: string }) => p.playerId === id,
    ).position;
    const stats = native.team.batters.find(
      (p: { batterId: string }) => p.batterId === `draft:2024:${id}`,
    ).stats;
    await expect(rows.nth(i).getByRole('rowheader')).toContainText(
      `${i + 1}. ${player.name}`,
    );
    await expect(rows.nth(i).getByRole('rowheader')).toContainText(position);
    await expect(rows.nth(i).getByRole('cell').first()).toHaveText(
      String(stats.plateAppearances),
    );
  }
  await page
    .getByRole('button', { name: 'Replay this season seed', exact: true })
    .click();
  await expect.poll(async () => (await runs(page)).length).toBe(2);
  expect((await runs(page))[1].response.batting).toEqual(
    first.response.batting,
  );
  expect((await runs(page))[1].response.summary).toEqual(
    first.response.summary,
  );
  await page
    .getByRole('button', { name: 'Play another season', exact: true })
    .click();
  await expect.poll(async () => (await runs(page)).length).toBe(3);
  const third = (await runs(page))[2];
  expect(JSON.parse(third.request.inputJson).userTeam.lineup).toEqual(
    input.userTeam.lineup,
  );
  expect(third.response.summary.seed).not.toBe(first.response.summary.seed);
  await page
    .getByRole('button', { name: 'Edit batting order', exact: true })
    .click();
  expect(await ids()).toEqual(chosen);
  const reset = page.getByRole('button', {
    name: 'Reset batting order',
    exact: true,
  });
  if (info.project.name.startsWith('mobile-')) await reset.tap();
  else await reset.click();
  expect(await ids()).toEqual(original);
  await page
    .getByRole('button', { name: 'Start a new draft', exact: true })
    .click();
  await expect(list).toHaveCount(0);
  await expect(
    page.getByRole('heading', { name: 'Who’s your C?', exact: true }),
  ).toBeFocused();
  const exportButton = page.getByRole('button', {
    name: 'Export session JSON',
  });
  if (!(await exportButton.isVisible()))
    await page.getByText('Local playtest tools', { exact: true }).click();
  await expect(exportButton).toBeVisible();
  const download = page.waitForEvent('download');
  await exportButton.click();
  const exported = JSON.parse(
    readFileSync((await (await download).path())!, 'utf8'),
  );
  expect(exported.battingOrder).toEqual([]);
  expect(exported.draft.history).toEqual([]);
  // Replay the same picks in a new draft to isolate reset from roster changes.
  await page.reload();
  await setup(page);
  await finish(page);
  expect(await ids()).toEqual(original);
});

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
  await expect(first.locator('.price strong')).toHaveText(
    String(engine.player(p.id).price),
  );
  await expect(first).toContainText('historical PA');
  await expect(
    page.getByText('credits left / 65', { exact: true }),
  ).toBeVisible();
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
  await expect(page.getByLabel('Your lineup', { exact: true })).toContainText(
    `${engine.config.budget - fixture.draft.remainingBudget} credits`,
  );
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
    await expect(
      results.getByRole('row').filter({ hasText: player.name }),
    ).toContainText(`${engine.player(player.id).price} credits`);
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
  await expect(page.getByTestId('game-budget')).toHaveText(
    String(engine.config.budget),
  );
  await expect(results).toHaveCount(0);
  await expect(page.getByLabel('Your lineup')).toContainText('0 / 9');
  if (process.env.M6B_IMPORT_SQL) {
    await expect(
      page.getByLabel('Player offers').getByRole('button').first(),
    ).toBeEnabled();
    await expect(page.getByRole('alert')).toHaveCount(0);
  }
});

test('a missing WASM asset offers an explicit reload that returns to the latest start screen', async ({
  page,
}) => {
  await setup(page);
  await finish(page);
  await page.route('**/*.wasm', (route) =>
    route.fulfill({
      status: 404,
      contentType: 'text/html',
      body: 'Missing versioned asset',
    }),
  );
  await page
    .getByRole('button', { name: 'Simulate 162-game season', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText(
    'Reloading clears this draft',
  );
  await page.unroute('**/*.wasm');
  await page
    .getByRole('button', { name: 'Reload latest app', exact: true })
    .click();
  await expect(
    page.getByRole('button', { name: 'Start your draft' }),
  ).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
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
    page.getByRole('button', { name: 'Reset batting order', exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole('button', { name: 'Start a new draft' }),
  ).toBeDisabled();
  await page.getByRole('button', { name: 'Cancel season' }).click();
  release();
  await expect(page.getByRole('status')).toContainText('cancelled');
  await expect(
    page.getByRole('button', { name: 'Reset batting order', exact: true }),
  ).toBeEnabled();
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
