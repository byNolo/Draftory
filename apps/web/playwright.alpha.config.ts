import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: [
    '**/alpha.spec.ts',
    '**/game-browser.spec.ts',
    '**/integration.spec.ts',
  ],
  outputDir: '../../target/alpha-test-results',
  workers: 1,
  timeout: 60_000,
  use: { baseURL: 'http://127.0.0.1:4180' },
  projects: [
    { name: 'chromium', use: devices['Desktop Chrome'] },
    { name: 'firefox', use: devices['Desktop Firefox'] },
    { name: 'webkit', use: devices['Desktop Safari'] },
    {
      name: 'mobile-chromium',
      use: devices['Pixel 7'],
      testMatch: '**/game-browser.spec.ts',
    },
    {
      name: 'mobile-webkit',
      use: devices['iPhone 13'],
      testMatch: '**/game-browser.spec.ts',
    },
    { name: 'edge', use: { ...devices['Desktop Edge'], channel: 'msedge' } },
  ],
  webServer: {
    command: 'node scripts/serve-integration-api.mjs',
    cwd: '../..',
    env: { DRAFTORY_ALPHA_TEST: '1' },
    url: 'http://127.0.0.1:4180/api/health',
    timeout: process.env.M6B_IMPORT_SQL ? 300_000 : 120_000,
    reuseExistingServer: false,
  },
});
