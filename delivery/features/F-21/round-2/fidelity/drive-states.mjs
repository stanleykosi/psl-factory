// F-21 fidelity helper (test only). The fidelity tool scores one URL and cannot click, and the default and invalid
// boards draw the four-part form open and filled, so this drives the real page against the real mock and freezes the
// result: it resets the mock, opens the page with the persona cookie, opens "Send to Tola to assemble" with the real
// control, types the board's four parts, chooses the board's cited records through the real pickers, (invalid:) presses
// Send and takes the mock's real 422, copies each input's current value into its attribute, removes the scripts, adds
// <base href> and saves the document to frozen/<variant>-<width>.html. No product or mock code is changed for this.
// The <base> points at serve-frozen.mjs (4743), which serves frozen/ and passes /_next assets through to the app (4741).
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4741, mock on 4742)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-21/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4741';
const MOCK = 'http://127.0.0.1:4742';
const FROZEN_BASE = 'http://localhost:4743/';

const PARTS = {
  Status: "Milestone 2 is complete: Lagoon Health signed UAT on 11 Nov. Work on milestone 3 (go-live) has started.",
  Risks: 'Login fails on some older Android phones (high). A fix is in testing; go-live waits on it.',
  Timeline: 'Go-live remains planned for 4 Dec, subject to the login fix and test accounts from your team.',
  'Next steps': 'Your team: send test accounts by 13 Nov. Ours: finish the login fix and assess the SMS reminders change.',
};
const CITES = {
  Status: ['Milestone 2 · UAT signed 11 Nov', 'UAT walkthrough · 11 Nov'],
  Risks: ['ISS-0233 Login fails on older Android phones · High'],
  Timeline: ['Weekly sync with Lagoon Health · 10 Nov'],
  'Next steps': ['Client to send test accounts · due 13 Nov', 'CR-0031 Add SMS reminders · being assessed'],
};

async function cite(page, part) {
  await page.getByRole('combobox', { name: `Cites for ${part.toLowerCase()} (optional)` }).click();
  for (const label of CITES[part]) await page.getByRole('option', { name: label }).click();
  await page.keyboard.press('Escape');
}

const VARIANTS = [
  {
    variant: 'default',
    url: '/work/W-2201',
    steps: async (page) => {
      await page.getByRole('button', { name: 'Send to Tola to assemble' }).click();
      for (const [part, text] of Object.entries(PARTS)) {
        await page.getByLabel(`${part} (optional)`, { exact: true }).fill(text);
        await cite(page, part);
      }
    },
  },
  {
    variant: 'invalid',
    url: '/work/W-2202',
    steps: async (page) => {
      await page.getByRole('button', { name: 'Send to Tola to assemble' }).click();
      await page.getByRole('button', { name: 'Send to Tola to assemble' }).last().click();
      await page.getByText('Cite at least one record: no record cited yet.').first().waitFor();
    },
  },
];

const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
];

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
