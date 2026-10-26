import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './apps/web/tests',
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    ...devices['Desktop Chrome'],
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : {}),
  },
  projects: [
    { name: 'chromium', testMatch: '**/parity.spec.ts' },
    { name: 'performance', testMatch: '**/performance.spec.ts' },
  ],
  webServer: {
    command:
      'npm run preview --workspace @draftory/web -- --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
  },
});
