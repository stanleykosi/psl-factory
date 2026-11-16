// F-23 fidelity helper (test only). The fidelity tool scores one URL and cannot click, and the default desktop board draws
// the confirm form's audience on screen, so this drives the real page against the real mock and freezes the result: it
// resets the mock, opens /work/W-2301 with the persona cookie, presses "Confirm and create actions" with the real control
// (which opens the form and its audience), copies each input's current value into its attribute, removes the scripts, adds
// <base href> and saves the document to frozen/default-<width>.html. No product or mock code is changed for this.
// The <base> points at serve-frozen.mjs (4763), which serves frozen/ and passes /_next assets through to the app (4761).
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4761, mock on 4762)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-23/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4761';
const MOCK = 'http://127.0.0.1:4762';
const FROZEN_BASE = 'http://localhost:4763/';

const VARIANTS = [
  {
    variant: 'default',
    url: '/work/W-2301',
    steps: async (page) => {
      await page.getByRole('button', { name: 'Confirm and create actions' }).click();
      await page.getByRole('form', { name: 'Confirm and create actions' }).waitFor();
    },
  },
];

const WIDTHS = [{ width: 1440, height: 900 }];

mkdirSync(join(here, 'frozen'), { recursive: true });
const browser = await chromium.launch({ args: ['--lang=en-GB'], env: { ...process.env, LANG: 'en_GB.UTF-8' } });
for (const { variant, url, steps } of VARIANTS) {
  for (const viewport of WIDTHS) {
    const reset = await fetch(`${MOCK}/__mock/reset`, { method: 'POST' });
    if (reset.status !== 204) throw new Error(`mock reset failed: ${reset.status}`);
    const context = await browser.newContext({ viewport, timezoneId: 'Africa/Lagos', locale: 'en-GB' });
    await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: APP }]);
    const page = await context.newPage();
    await page.goto(APP + url);
    await page.locator('main#main h1').first().waitFor();
    await steps(page);
    await page.waitForTimeout(300);
    const html = await page.evaluate((base) => {
      for (const el of document.querySelectorAll('input, textarea, select')) {
        if (el instanceof HTMLInputElement && (el.type === 'radio' || el.type === 'checkbox')) {
          if (el.checked) el.setAttribute('checked', '');
          else el.removeAttribute('checked');
        } else if (el instanceof HTMLSelectElement) {
          for (const o of el.options) {
            if (o.selected) o.setAttribute('selected', '');
            else o.removeAttribute('selected');
          }
        } else if (el instanceof HTMLTextAreaElement) {
          el.textContent = el.value;
        } else {
          el.setAttribute('value', el.value);
        }
      }
      document.querySelectorAll('script, link[rel="preload"][as="script"], link[rel="modulepreload"]').forEach((el) => el.remove());
      const tag = document.createElement('base');
      tag.href = base;
      document.head.prepend(tag);
      return `<!doctype html>\n${document.documentElement.outerHTML}\n`;
    }, FROZEN_BASE);
    const out = join(here, 'frozen', `${variant}-${viewport.width}.html`);
    writeFileSync(out, html);
    console.log(`${variant} ${viewport.width}: ${out}`);
    await context.close();
  }
}
await browser.close();
