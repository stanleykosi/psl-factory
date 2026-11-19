// F-45 fidelity helper (test only; the F-34/F-31 pattern, spec Conflicts 2 and 15). The fidelity tool scores one URL and cannot
// click, and the observe boards draw the form open with "Found" chosen and the proof uploaded, so this drives the real page
// against the real mock and freezes the result. Each width: reset the mock, open /work/W-4202 as persona finance_lead, use
// only the real controls (press "Record observation", choose Found, upload a 310 KB qb-screenshot-je7741.png through the real
// file input; on the phone the Drawer is open), copy each input's value into its attribute, remove the scripts, add
// <base href> and save frozen/<board>-<width>.html. The observation is never submitted: the workspace log has no step after.
// serve-frozen.mjs serves frozen/ on 4956 and passes /_next assets through to the app on 4955.
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4955, mock on 4954)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-45/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4955';
const MOCK = 'http://127.0.0.1:4954';
const FROZEN_BASE = 'http://localhost:4956/';
const png = { name: 'qb-screenshot-je7741.png', mimeType: 'image/png', buffer: Buffer.alloc(310 * 1024, 7) };

mkdirSync(join(here, 'frozen'), { recursive: true });
const browser = await chromium.launch({ args: ['--lang=en-GB'], env: { ...process.env, LANG: 'en_GB.UTF-8' } });

async function freeze(name, width, steps) {
  const reset = await fetch(`${MOCK}/__mock/reset`, { method: 'POST' });
  if (reset.status !== 204) throw new Error(`mock reset failed: ${reset.status}`);
  const phone = width < 500;
  const context = await browser.newContext({ viewport: { width, height: phone ? 844 : 900 }, timezoneId: 'Africa/Lagos', locale: 'en-GB', ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: APP }]);
  const page = await context.newPage();
  await steps(page, phone);
  await page.waitForTimeout(400);
  const html = await page.evaluate((base) => {
    for (const el of document.querySelectorAll('input, textarea')) {
      if (el instanceof HTMLTextAreaElement) el.textContent = el.value;
      else if (el instanceof HTMLInputElement && el.type === 'checkbox') el.toggleAttribute('checked', el.checked);
      else if (el instanceof HTMLInputElement && el.type !== 'file') el.setAttribute('value', el.value);
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

async function observe(page, phone) {
  await page.goto(`${APP}/work/W-4202`);
  await page.getByRole('button', { name: 'Record observation' }).waitFor();
  await page.getByRole('button', { name: 'Record observation' }).click();
  const scope = phone ? page.getByRole('dialog', { name: 'Record observation' }) : page.locator('.ws form');
  await scope.getByRole('combobox', { name: /What you found/ }).click();
  await page.getByRole('option', { name: 'Found', exact: true }).click();
  await scope.locator('input[type="file"]').setInputFiles(png);
  await scope.getByText('qb-screenshot-je7741.png · 310 KB').waitFor();
  await page.mouse.move(0, 0);
}

for (const width of [1440, 390]) {
  const v = width === 390 ? 'mobile' : 'desktop';
  await freeze(`SCR-58-${v}-observe`, width, observe);
}
const log = await (await fetch(`${MOCK}/__mock/workspace-log`)).json();
if (log.entries.length !== 0) throw new Error('the drive sent a step');
console.log('workspace log: no step sent');
await browser.close();
