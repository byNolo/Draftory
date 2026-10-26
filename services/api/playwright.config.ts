import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  outputDir: '../../target/api-test-results',
  workers: 1,
  retries: 0,
  timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:4174' },
  webServer: {
    command: 'node scripts/serve-api-tests.mjs',
    cwd: '../..',
    url: 'http://127.0.0.1:4174/api/health',
    timeout: 90_000,
    reuseExistingServer: false,
  },
});
