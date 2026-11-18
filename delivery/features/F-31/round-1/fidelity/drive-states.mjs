// F-31 fidelity helper (test only; the F-27 pattern). The fidelity tool scores one URL and cannot click, and the register and
// record boards draw a form filled in, so this drives the real pages against the real mock and freezes the result. Each state:
// reset the mock, open the page with persona pm, use only the real controls (press "Register engagement" or QA's
// "Record input", upload the file through the real file input, type the values), copy each input's current value into its
// attribute, remove the scripts, add <base href> and save frozen/<board>-<width>.html. Nothing else in the DOM is edited, and
// no product or mock code is changed for this. The <base> points at serve-frozen.mjs on 4860 (the mock is stopped by then),
// which serves frozen/ and passes /_next assets through to the app on 4861.
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4861, mock on 4860)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-31/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4861';
const MOCK = 'http://127.0.0.1:4860';
const FROZEN_BASE = 'http://localhost:4860/';
const pdf = (name) => ({ name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 sample plan\n'.repeat(60)) });

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

async function register(page, phone) {
  await page.goto(`${APP}/work/W-2602`);
  await page.getByRole('button', { name: 'Register engagement' }).waitFor();
  await page.getByRole('button', { name: 'Register engagement' }).click();
  const scope = phone ? page.getByRole('dialog') : page.locator('form[aria-labelledby]');
  await scope.locator('input[type="file"]').setInputFiles(pdf('kickoff-plan-v1.pdf'));
  await scope.getByText(/Add another file/).first().waitFor();
  await scope.getByLabel(/Start date/).fill('15 Jan 2027');
  await scope.getByLabel(/Start date/).press('Tab');
  await scope.getByLabel(/Client project contact/).fill('Ngozi Bello · Head of Lending Operations');
  await scope.getByLabel(/Client project contact/).press('Tab');
}

async function record(page, phone) {
  await page.goto(`${APP}/work/W-2603`);
  await page.getByRole('button', { name: 'Record input' }).first().waitFor();
  await page.locator('tr').filter({ has: page.locator('td', { hasText: /^QA$/ }) }).getByRole('button', { name: 'Record input' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel(/What they gave/).waitFor();
  await dialog.getByLabel('Who gave it').selectOption({ label: 'QA · QA lead, PSL' });
  await dialog.getByLabel(/Estimate/).fill('45');
  await dialog.getByLabel(/What they gave/).fill('Test plan and QA effort for the loan app');
  await dialog.locator('input[type="file"]').setInputFiles(pdf('qa-plan.pdf'));
  await dialog.getByText(/Uploaded/).first().waitFor();
  await dialog.getByLabel(/Received/).fill('2026-12-11T16:05');
  await dialog.getByRole('checkbox').check();
}

for (const width of [1440, 390]) {
  const v = width === 390 ? 'mobile' : 'desktop';
  await freeze(`SCR-41-${v}-register`, width, register);
  await freeze(`SCR-42-${v}-record`, width, record);
}
await browser.close();
