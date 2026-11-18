// F-34 fidelity helper (test only; the F-31 pattern). The fidelity tool scores one URL and cannot click, and the record boards
// draw the form open and filled, so this drives the real page against the real mock and freezes the result. Each state: reset
// the mock, open /work/W-3102 with persona pm, use only the real controls (press "Record release", type the date, upload the
// deployment log through the real file input), copy each input's current value into its attribute, remove the scripts, add
// <base href> and save frozen/<board>-<width>.html. The record is never submitted. serve-frozen.mjs serves frozen/ on 4960
// (the mock is stopped by then) and passes /_next assets through to the app on 4961.
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4961, mock on 4960)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-34/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4961';
const MOCK = 'http://127.0.0.1:4960';
const FROZEN_BASE = 'http://localhost:4960/';
const pdf = (name) => ({ name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 sample deployment log\n'.repeat(60)) });

mkdirSync(join(here, 'frozen'), { recursive: true });
const browser = await chromium.launch({ args: ['--lang=en-GB'], env: { ...process.env, LANG: 'en_GB.UTF-8' } });

async function freeze(name, width, steps) {
  const reset = await fetch(`${MOCK}/__mock/reset`, { method: 'POST' });
  if (reset.status !== 204) throw new Error(`mock reset failed: ${reset.status}`);
  const phone = width < 500;
  const context = await browser.newContext({ viewport: { width, height: phone ? 844 : 900 }, timezoneId: 'Africa/Lagos', locale: 'en-GB', ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: APP }]);
  const page = await context.newPage();
  await steps(page, phone);
  await page.waitForTimeout(400);
  const html = await page.evaluate((base) => {
    for (const el of document.querySelectorAll('input, textarea')) {
      if (el instanceof HTMLTextAreaElement) el.textContent = el.value;
      else if (el instanceof HTMLInputElement && el.type === 'checkbox') el.toggleAttribute('checked', el.checked);
      else el.setAttribute('value', el.value);
    }
    document.querySelectorAll('script, link[rel="preload"][as="script"], link[rel="modulepreload"]').forEach((el) => el.remove());
    const tag = document.createElement('base');
    tag.href = base;
    document.head.prepend(tag);
    return `<!doctype html>\n${document.documentElement.outerHTML}\n`;
  }, FROZEN_BASE);
  const out = join(here, 'frozen', `${name}-${width}.html`);
  writeFileSync(out, html);
  console.log(`${name} ${width}: ${out}`);
  await context.close();
}

async function record(page) {
  await page.goto(`${APP}/work/W-3102`);
  await page.getByRole('button', { name: 'Record release' }).waitFor();
  await page.getByRole('button', { name: 'Record release' }).click();
  const form = page.locator('form[aria-labelledby]');
  await form.locator('input[type="file"]').setInputFiles(pdf('release-1.0.0-log.pdf'));
  await form.getByText(/Add another file/).first().waitFor();
  await form.getByLabel(/Released on/).fill('2026-04-01T22:00');
  await form.getByLabel(/Released on/).press('Tab');
}

for (const width of [1440, 390]) {
  const v = width === 390 ? 'mobile' : 'desktop';
  await freeze(`SCR-46-${v}-record`, width, record);
}
const log = await (await fetch(`${MOCK}/__mock/workspace-log`)).json();
if (log.entries.length !== 0) throw new Error('the drive sent a step');
await browser.close();
