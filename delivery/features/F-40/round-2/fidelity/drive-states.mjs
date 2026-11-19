// F-40 fidelity helper (test only; the F-27 and F-31 pattern). The fidelity tool scores one URL and cannot click, and the record
// boards draw a form filled in, so this drives the real page against the real mock and freezes the result. Each state: reset the
// mock, open /work/W-3703 with persona pm, use only the real controls (choose Gaps found, type the two gaps, set 10 Apr 2026 11:00,
// upload support-reply-10apr.pdf (40 KB) through the real file input, tick the confirmation), copy each input's current value
// into its attribute, remove the scripts, add <base href> and save frozen/SCR-48-<width>-record.html. Nothing else in the DOM is
// edited, and no product or mock code is changed for this. The <base> points at serve-frozen.mjs on 4974 (the mock is stopped by
// then), which serves frozen/ and passes /_next assets through to the app on 4975.
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4975, mock on 4974)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-40/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4975';
const MOCK = 'http://127.0.0.1:4974';
const FROZEN_BASE = 'http://localhost:4974/';
const pdf = (name) => ({ name, mimeType: 'application/pdf', buffer: Buffer.alloc(40 * 1024, '%PDF-1.4 sample reply\n') });

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
      else if (el instanceof HTMLInputElement && (el.type === 'checkbox' || el.type === 'radio')) el.toggleAttribute('checked', el.checked);
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
  await page.goto(`${APP}/work/W-3703`);
  const panel = page.getByRole('region', { name: 'Record Support’s reply' });
  await panel.getByRole('radio', { name: 'Gaps found' }).waitFor({ state: 'attached' });
  await panel.getByLabel('When they replied').fill('2026-04-10T11:00');
  await panel.getByRole('radio', { name: 'Gaps found' }).check({ force: true });
  await panel.getByLabel('Gaps', { exact: true }).fill('No contact for the credit bureau outage\nRunbook misses the nightly export restart');
  await panel.locator('input[type="file"]').setInputFiles(pdf('support-reply-10apr.pdf'));
  await panel.getByText(/Uploaded/).first().waitFor();
  await panel.getByRole('checkbox', { name: 'I confirm this response is genuine.' }).check();
}

for (const width of [1440, 390]) {
  const v = width === 390 ? 'mobile' : 'desktop';
  await freeze(`SCR-48-${v}-record`, width, record);
}
await browser.close();
