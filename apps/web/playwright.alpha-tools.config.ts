import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  testMatch: '**/alpha-tools.spec.ts',
  outputDir: '../../target/alpha-tools-test-results',
  workers: 1,
});
