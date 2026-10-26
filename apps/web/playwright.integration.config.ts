import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: '**/integration.spec.ts',
  outputDir: '../../target/m6b-test-results',
  workers: 1,
  timeout: 60_000,
  use: { baseURL: 'http://127.0.0.1:4273' },
  projects: [
    { name: 'chromium', use: devices['Desktop Chrome'] },
    { name: 'firefox', use: devices['Desktop Firefox'] },
    { name: 'webkit', use: devices['Desktop Safari'] },
    { name: 'edge', use: { ...devices['Desktop Edge'], channel: 'msedge' } },
  ],
  webServer: [
    {
      command: 'node scripts/serve-integration-api.mjs',
      cwd: '../..',
      url: 'http://127.0.0.1:4176/api/health',
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command:
        'npm run preview --workspace @draftory/web -- --port 4273 --strictPort',
      cwd: '../..',
      url: 'http://127.0.0.1:4273',
      env: { DRAFTORY_API_TARGET: 'http://127.0.0.1:4176' },
      reuseExistingServer: false,
    },
  ],
});
