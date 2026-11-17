// F-27 fidelity helper (test only). The fidelity tool scores one URL and cannot click, and SCR-13-desktop-delegation
// draws the "Add a delegation" panel filled in, so this drives the real page against the real mock and freezes the
// result: it resets the mock, opens /setup/delegation with the persona cookie, chooses From Kemi Adebayo and To Femi Ade
// through the real Selects, types Dates 18 Nov 2026 to 25 Nov 2026 and Reason "Annual leave" into the real fields,
// copies each input's current value into its attribute, removes the scripts, adds <base href> and saves the document to
// frozen/default-1440.html. Nothing else in the DOM is edited, and no product or mock code is changed for this.
// The <base> points at serve-frozen.mjs (4803), which serves frozen/ and passes /_next assets through to the app (4801).
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4801, mock on 4802)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-27/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4801';
const MOCK = 'http://127.0.0.1:4802';
const FROZEN_BASE = 'http://localhost:4803/';

mkdirSync(join(here, 'frozen'), { recursive: true });
const browser = await chromium.launch({ args: ['--lang=en-GB'], env: { ...process.env, LANG: 'en_GB.UTF-8' } });
const reset = await fetch(`${MOCK}/__mock/reset`, { method: 'POST' });
if (reset.status !== 204) throw new Error(`mock reset failed: ${reset.status}`);
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, timezoneId: 'Africa/Lagos', locale: 'en-GB' });
await context.addCookies([{ name: 'psl_mock_persona', value: 'admin', url: APP }]);
const page = await context.newPage();
await page.goto(`${APP}/setup/delegation`);
const panel = page.getByRole('complementary', { name: 'Add a delegation' });
await panel.waitFor();
await panel.getByRole('combobox', { name: 'From' }).click();
await page.getByRole('option', { name: 'Kemi Adebayo · PMO Lead' }).click();
await panel.getByRole('combobox', { name: 'To' }).click();
await page.getByRole('option', { name: 'Femi Ade · PMO Lead' }).click();
for (const [label, text] of [['Starts', '18 Nov 2026'], ['Ends', '25 Nov 2026']]) {
  await panel.getByLabel(label).fill(text);
  await panel.getByLabel(label).press('Tab');
}
await panel.getByLabel('Reason').fill('Annual leave');
await page.mouse.click(5, 300);
await page.waitForTimeout(300);
const html = await page.evaluate((base) => {
  for (const el of document.querySelectorAll('input, textarea')) {
    if (el instanceof HTMLTextAreaElement) el.textContent = el.value;
    else el.setAttribute('value', el.value);
  }
  document.querySelectorAll('script, link[rel="preload"][as="script"], link[rel="modulepreload"]').forEach((el) => el.remove());
  const tag = document.createElement('base');
  tag.href = base;
  document.head.prepend(tag);
  return `<!doctype html>\n${document.documentElement.outerHTML}\n`;
}, FROZEN_BASE);
const out = join(here, 'frozen', 'default-1440.html');
writeFileSync(out, html);
console.log(`default 1440: ${out}`);
await browser.close();
