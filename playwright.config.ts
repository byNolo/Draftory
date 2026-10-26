import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './apps/web/tests',
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
  },
  projects: [
    {
      name: 'deployment',
      use: { ...devices['Desktop Chrome'] },
      testMatch: '**/deployment.spec.ts',
    },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /(?:parity|delivery)\.spec\.ts/,
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      testMatch: /(?:parity|delivery)\.spec\.ts/,
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
      testMatch: /(?:parity|delivery)\.spec\.ts/,
    },
    {
      name: 'edge',
      use: { ...devices['Desktop Edge'], channel: 'msedge' },
      testMatch: /(?:parity|delivery)\.spec\.ts/,
    },
    {
      name: 'mobile-chromium',
      use: { ...devices['Pixel 7'] },
      testMatch: '**/parity.spec.ts',
    },
    {
      name: 'mobile-webkit',
      use: { ...devices['iPhone 13'] },
      testMatch: '**/parity.spec.ts',
    },
    ...(['chromium', 'firefox', 'webkit', 'edge'] as const).map((name) => ({
      name: `performance-${name}`,
      testMatch: '**/performance.spec.ts',
      use:
        name === 'edge'
          ? { ...devices['Desktop Edge'], channel: 'msedge' }
          : { browserName: name },
    })),
  ],
  webServer: {
    command: 'node scripts/serve-browser-tests.mjs',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
  },
});
