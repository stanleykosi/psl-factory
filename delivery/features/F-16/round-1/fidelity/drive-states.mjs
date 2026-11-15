// F-16 fidelity helper (test only). The fidelity tool scores one URL and cannot click, and the done and stale
// decision views exist only after a decide, so this drives them through the real page against the mock and
// freezes the result: for each state and width it resets the mock, opens the decision with the persona cookie,
// clicks Approve v2, waits for the state's heading, removes the scripts and saves the rendered document to
// frozen/<state>-<width>.html. No product or mock code is changed for this.
//
// The saved page's <base> points at serve-frozen.mjs (4603), which serves frozen/ and passes /_next assets through
// to the app, so the page's CSS and fonts load from the same origin (the app sends fonts without CORS headers).
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4601, mock on 4602)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-16/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4601';
const MOCK = 'http://127.0.0.1:4602';
const FROZEN_BASE = 'http://localhost:4603/';

const STATES = [
  { state: 'done', url: '/work/W-1901/decide?task=T-1901', ready: 'Invoice v2 for Lagoon Health is approved', settled: 'Chidi will issue it' },
  { state: 'stale', url: '/work/W-1902/decide?task=T-1902', ready: 'A newer version arrived while you were reading.', settled: 'Review version 3' },
];
const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
];

mkdirSync(join(here, 'frozen'), { recursive: true });
const browser = await chromium.launch();
for (const { state, url, ready, settled } of STATES) {
  for (const viewport of WIDTHS) {
    const reset = await fetch(`${MOCK}/__mock/reset`, { method: 'POST' });
    if (reset.status !== 204) throw new Error(`mock reset failed: ${reset.status}`);
    const context = await browser.newContext({ viewport, timezoneId: 'Africa/Lagos' });
    await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: APP }]);
    const page = await context.newPage();
    await page.goto(APP + url);
    const approve = page.getByRole('button', { name: 'Approve v2' });
    await approve.waitFor();
    await page.waitForFunction(() => {
      const b = [...document.querySelectorAll('button')].find((el) => el.textContent === 'Approve v2');
      return b && !b.disabled;
    });
    await approve.click();
    await page.getByText(ready, { exact: true }).waitFor();
    await page.getByText(settled).first().waitFor();
    await page.waitForTimeout(300);
    const html = await page.evaluate((base) => {
      document.querySelectorAll('script, link[rel="preload"][as="script"], link[rel="modulepreload"]').forEach((el) => el.remove());
      const tag = document.createElement('base');
      tag.href = base;
      document.head.prepend(tag);
      return `<!doctype html>\n${document.documentElement.outerHTML}\n`;
    }, FROZEN_BASE);
    const out = join(here, 'frozen', `${state}-${viewport.width}.html`);
    writeFileSync(out, html);
    console.log(`${state} ${viewport.width}: ${out}`);
    await context.close();
  }
}
await browser.close();
