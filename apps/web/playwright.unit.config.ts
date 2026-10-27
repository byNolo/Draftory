import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  testMatch: ['**/data-client.spec.ts', '**/draft.spec.ts'],
  outputDir: '../../target/client-test-results',
  workers: 1,
});
