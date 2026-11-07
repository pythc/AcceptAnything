import { defineConfig } from '../../../validation/node_modules/@playwright/test/index.mjs';
export default defineConfig({
  testDir: '.', testMatch: ['browser.spec.mjs', 'candidate.spec.mjs'], workers: 1, retries: 0, timeout: 120000,
  outputDir: process.env.ACCEPTANCE_REPORT + '/artifacts',
  reporter: [['json', {outputFile: process.env.ACCEPTANCE_REPORT + '/results.json'}]],
  use: {baseURL: process.env.ACCEPTANCE_URL, browserName: 'chromium', headless: true, trace: 'on', screenshot: 'on', actionTimeout: 20000}
});
