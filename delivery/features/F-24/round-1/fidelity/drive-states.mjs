// F-24 fidelity helper (test only). The fidelity tool scores one URL and cannot click, and the draft-started boards
// draw the thread after the start, so this drives the real page against the real mock and freezes the result: it
// resets the mock, opens CV-2401 with the persona cookie, presses "Start this invoice", checks the prefilled Start work
// drawer, presses the drawer's own start button, waits for the thread's re-read to show "Started INV-0415.", and saves the
// document to frozen/draft-started-<width>.html. The only DOM edits are for freezing (the scripts are removed, form
// values are copied into attributes and a <base> is added). No product or mock code is changed for this.
// The <base> points at serve-frozen.mjs (4772), which serves frozen/ and passes /_next assets through to the app (4770).
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4770, mock on 4771)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-24/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4770';
const MOCK = 'http://127.0.0.1:4771';
const FROZEN_BASE = 'http://localhost:4772/';

const WIDTHS = [
  { width: 1440, height: 1040 },
  { width: 390, height: 844 },
];

mkdirSync(join(here, 'frozen'), { recursive: true });
const browser = await chromium.launch({ args: ['--lang=en-GB'], env: { ...process.env, LANG: 'en_GB.UTF-8' } });
for (const viewport of WIDTHS) {
  const reset = await fetch(`${MOCK}/__mock/reset`, { method: 'POST' });
  if (reset.status !== 204) throw new Error(`mock reset failed: ${reset.status}`);
  const context = await browser.newContext({ viewport, timezoneId: 'Africa/Lagos', locale: 'en-GB' });
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: APP }]);
  const page = await context.newPage();
  await page.goto(`${APP}/assistant/CV-2401`);
  await page.getByRole('button', { name: 'Start this invoice' }).click();
  const drawer = page.getByRole('dialog');
  await drawer.getByRole('combobox', { name: 'Completed milestone' }).filter({ hasText: 'Milestone 2 · beta signed 30 Oct' }).waitFor();
  await drawer.getByRole('button', { name: 'Start the invoice' }).click();
  await page.getByText(/^Started INV-0415\./).waitFor();
  await page.waitForTimeout(500);
  const html = await page.evaluate((base) => {
    for (const el of document.querySelectorAll('input, textarea, select')) {
      if (el instanceof HTMLTextAreaElement) el.textContent = el.value;
      else if (el instanceof HTMLInputElement) el.setAttribute('value', el.value);
    }
    document.querySelectorAll('script, link[rel="preload"][as="script"], link[rel="modulepreload"]').forEach((el) => el.remove());
    const tag = document.createElement('base');
    tag.href = base;
    document.head.prepend(tag);
    return `<!doctype html>\n${document.documentElement.outerHTML}\n`;
  }, FROZEN_BASE);
  const out = join(here, 'frozen', `draft-started-${viewport.width}.html`);
  writeFileSync(out, html);
  console.log(`draft-started ${viewport.width}: ${out}`);
  await context.close();
}
await browser.close();
