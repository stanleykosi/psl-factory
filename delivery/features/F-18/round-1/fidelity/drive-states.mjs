// F-18 fidelity helper (test only). The fidelity tool scores one URL and cannot click, and the boards draw the
// forms already filled, so this drives them through the real page against the mock and freezes the result: for
// each variant and width it resets the mock, opens the page with the persona cookie, chooses the options through
// the real controls, types the board's values, uploads a file with the board's proof file name and size, copies
// each input's current value into its attribute, removes the scripts, adds <base href> and saves the document to
// frozen/<variant>-<width>.html. No product or mock code is changed for this.
//
// The saved page's <base> points at serve-frozen.mjs (4623), which serves frozen/ and passes /_next assets through
// to the app, so the page's CSS and fonts load from the same origin.
//
// Usage: node drive-states.mjs [playwright index.mjs]   (app on 4621, mock on 4622)
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const playwright = process.argv[2] ?? '/Users/Hunchoo/psl-factory-worktrees/f-18/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(playwright);
const APP = 'http://localhost:4621';
const MOCK = 'http://127.0.0.1:4622';
const FROZEN_BASE = 'http://localhost:4623/';

const pdf = (name, kb) => ({ name, mimeType: 'application/pdf', buffer: Buffer.alloc(kb * 1024, 37) });

/** Each variant: the page, then the steps the person takes, in the board's values. */
const VARIANTS = [
  {
    variant: 'team-input',
    url: '/work/W-2101/respond?task=T-2101',
    steps: async (page) => {
      await page.getByRole('radio', { name: 'Security, missing' }).click();
      await page.getByLabel('Estimate (person-days)').fill('18');
      await page.getByLabel('What they gave').fill('Security estimate and data-protection notes');
      await page.locator('input[type="file"]').setInputFiles({ ...pdf('security-estimate-tamarind.xlsx', 64), mimeType: 'application/vnd.ms-excel' });
      await page.getByText('Uploaded · 64 KB').waitFor();
      await page.getByLabel('Received').fill('2026-11-12T15:10');
      await page.getByRole('checkbox', { name: 'I confirm this input came from the team named above.' }).check();
    },
  },
  {
    variant: 'rfp-outcome',
    url: '/work/W-2103/outcome',
    steps: async (page) => {
      await page.getByRole('radio', { name: 'Won', exact: true }).click();
      await page.getByLabel('When you learned it').fill('2026-12-04T11:00');
      await page.getByLabel('Awarded amount').fill('₦40,951,000.00');
      await proof(page, 'tamarind-award-letter.pdf', 310);
    },
  },
  {
    variant: 'rfp-outcome-lost',
    url: '/work/W-2103/outcome',
    steps: async (page) => {
      await page.getByRole('radio', { name: 'Lost', exact: true }).click();
      await page.getByLabel('When you learned it').fill('2026-12-04T11:00');
      await page.getByRole('radio', { name: 'Price', exact: true }).click();
      await page
        .getByLabel('Lessons (what we’d do differently)')
        .fill('Our total was 18% above the winning bid; they wanted go-live in 10 weeks, we said 14. They rated our audit-trail answer highest.');
      await proof(page, 'tamarind-regret-letter.pdf', 96);
    },
  },
  {
    variant: 'rfp-outcome-pending',
    url: '/work/W-2103/outcome',
    steps: async (page) => {
      await page.getByRole('radio', { name: 'Pending', exact: true }).click();
      await page.getByLabel('When you learned it').fill('2026-12-01T15:20');
      await page.getByLabel('Expected decision date').fill('2026-12-12');
      await page.getByLabel('Remind me on').fill('2026-12-12T09:00');
      await proof(page, 'tamarind-email-decision-delayed.pdf', 42);
    },
  },
  {
    variant: 'rfp-outcome-unknown',
    url: '/work/W-2103/outcome',
    steps: async (page) => {
      await page.getByRole('radio', { name: 'Unknown', exact: true }).click();
      await page.getByLabel('Last contact with the client').fill('2026-11-26T15:42');
      await page.getByLabel('Remind me on').fill('2026-12-10T09:00');
      // The board draws no file (Conflicts 7): proof stays required, so the person adds the submission email.
      await proof(page, 'tamarind-submission-email.pdf', 42);
    },
  },
];

async function proof(page, name, kb) {
  await page.locator('input[type="file"]').setInputFiles(pdf(name, kb));
  await page.getByText(`Uploaded · ${kb} KB`).waitFor();
}

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
    // The relationship owner, as the boards draw it, wherever the select is shown.
    const role = page.getByLabel('You are recording as');
    if (await role.count()) await role.selectOption('relationship_owner');
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
