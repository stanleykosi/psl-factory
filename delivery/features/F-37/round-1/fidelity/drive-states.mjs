// F-37 fidelity helper (test only; the F-27 pattern). The fidelity tool scores one URL and cannot click, and the register and
// record boards draw a form filled in, so this drives the real pages against the real mock and freezes the result. Each state:
// reset the mock, open the page with persona pm, use only the real controls (tick R-07, press Edit answer or Write my own, type the values), copy each input's current value into its
// attribute, remove the scripts, add <base href> and save frozen/<board>-<width>.html. Nothing else in the DOM is edited, and
// no product or mock code is changed for this. The <base> points at serve-frozen.mjs on 4994 (the mock is stopped by then),
// which serves frozen/ and passes /_next assets through to the app on 4995.
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4995, mock on 4994)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-37/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4995';
const MOCK = 'http://127.0.0.1:4994';
const FROZEN_BASE = 'http://localhost:4994/';

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
  // a click elsewhere would close an open Drawer (its scrim), so none is made; the filled values are already committed by Tab or change
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

async function open(page) {
  await page.goto(`${APP}/work/W-3402`);
  await page.getByRole('button', { name: 'Edit answer' }).waitFor();
  await page.getByRole('checkbox', { name: /R-07/ }).first().check();
}
async function edit(page, phone) {
  await open(page);
  await page.getByRole('button', { name: 'Edit answer' }).click();
  const scope = phone ? page.getByRole('dialog') : page.locator('form[aria-labelledby]');
  const answer = scope.getByLabel(/Your answer/);
  await answer.waitFor();
  await answer.fill('Loan officers approve applications up to a set limit; above it a second approver signs, and every approval is logged.');
  await answer.press('Tab');
}
async function reject(page, phone) {
  await open(page);
  await page.getByRole('button', { name: 'Write my own' }).click();
  const scope = phone ? page.getByRole('dialog') : page.locator('form[aria-labelledby]');
  await scope.getByLabel(/Your answer/).waitFor();
}

async function review(page) {
  await open(page);
}

for (const width of [1440, 390]) {
  const v = width === 390 ? 'mobile' : 'desktop';
  await freeze(`SCR-26-${v}-review`, width, review);
  await freeze(`SCR-26-${v}-edit`, width, edit);
  await freeze(`SCR-26-${v}-reject`, width, reject);
}
await browser.close();
