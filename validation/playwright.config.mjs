import { defineConfig } from '@playwright/test';
const mode = process.env.FIXTURE_MODE || 'buggy';
const evidence = process.env.RESEARCH_EVIDENCE_DIR || '../research/evidence';
export default defineConfig({
  testDir: './tests', workers: 1, retries: 0, timeout: 15000,
  outputDir: `${evidence}/playwright-${mode}/artifacts`,
  reporter: [['list'], ['json', {outputFile: `${evidence}/playwright-${mode}/results.json`}], ['junit', {outputFile: `${evidence}/playwright-${mode}/junit.xml`}]],
  use: { baseURL: 'http://127.0.0.1:18871', browserName: 'chromium', trace: 'on', screenshot: 'on', headless: true },
  webServer: {command: `.venv/bin/python fixture.py --mode ${mode} --port 18871`, url: 'http://127.0.0.1:18871/health', reuseExistingServer: false, timeout: 10000}
});
