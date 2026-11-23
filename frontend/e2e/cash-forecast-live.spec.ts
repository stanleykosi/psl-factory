import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-103: the cash forecast on the live shapes (ids 4301 to 4308, served by mock/forecast-live.mjs). Read only.
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const SHOTS = process.env.F103_SHOTS;
const WRITES = /^(approve|return|reject|withdraw|post|record|match|leave unmatched|save|retry|cancel|resend)/i;

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Where it stands' }).or(page.locator('.ws-note').first())).toBeVisible();
};
const watch = (page: Page) => {
  const seen = { writes: [] as string[], urls: [] as string[] };
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (url.pathname.startsWith('/api/')) seen.urls.push(url.pathname);
    if (r.method() !== 'GET' && url.pathname.startsWith('/api/')) seen.writes.push(`${r.method()} ${url.pathname}`);
  });
  return seen;
};
const noWriteButtons = async (page: Page) => {
  const names = await page.locator('main#main').getByRole('button').allInnerTexts();
  expect(names.filter((n) => WRITES.test(n.trim()))).toEqual([]);
};

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4301 verified: header, six months, Unknown closing, receipt 9, no write', async ({ page }) => {
      const seen = watch(page);
      await page.goto('/work/4301');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('PSL Technologies Ltd')).toBeVisible();
      await expect(main.getByText('As of 20 Nov 2026')).toBeVisible();
      await expect(main.locator('table.ws-table').first().locator('tbody tr')).toHaveCount(6);
      await expect(main.locator('table.ws-table').first().getByText('Unknown')).toHaveCount(1);
      await expect(main.getByText(/Receipt 9/)).toBeVisible();
      await expect(main.getByText('Item inv-17 · Actual 5')).toBeVisible();
      await expect(main.getByText(/not set/i)).toHaveCount(0);
      await expect(main.getByText(/\d[MK]\b/)).toHaveCount(0);
      await noWriteButtons(page);
      expect(seen.writes).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4301-${viewport.width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4302 review: roles as words, no decide controls', async ({ page }) => {
      await page.goto('/work/4302');
      await loaded(page);
      await expect(page.getByText('Reviewed by Finance')).toBeVisible();
      await expect(page.getByText('Waiting for the finance review.')).toBeVisible();
      await expect(page.getByText(/not set/i)).toHaveCount(0);
      await noWriteButtons(page);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4302-${viewport.width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4303 investigating: stage, finding, no figures, no table, no delivery', async ({ page }) => {
      await page.goto('/work/4303');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('Chidi is reading the opening balances.')).toBeVisible();
      await expect(main.getByText('No forecast figures yet.')).toBeVisible();
      await expect(main.getByText('No actuals matched yet.')).toHaveCount(1);
      await expect(main.locator('table')).toHaveCount(0);
      await expect(main.getByRole('heading', { name: 'Delivery' })).toHaveCount(0);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4303-${viewport.width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4304 group: the disclosure as sent, read only, no staff or payroll request', async ({ page }) => {
      const seen = watch(page);
      await page.goto('/work/4304');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByRole('heading', { name: 'Rows shared with the group' })).toBeVisible();
      for (const t of ['Recipient 3', 'Recipient 4']) await expect(main.getByText(t)).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Available' })).toBeVisible();
      await expect(main.locator('input, select, [role=checkbox]')).toHaveCount(0);
      await expect(main.getByRole('heading', { name: 'Expected items' })).toHaveCount(0);
      expect(seen.urls.filter((u) => /payroll/i.test(u))).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4304-${viewport.width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4308 poisoned group: the payroll key text only, no staff name, no pay, nowhere in the page or storage', async ({ page }) => {
      const seen = watch(page);
      await page.goto('/work/4308');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('payroll-run-nov').first()).toBeVisible();
      const html = await page.content();
      expect(html).not.toMatch(/Ngozi|Nwosu|\b850,000\.00|\b850000\.00/);
      expect(page.url()).not.toMatch(/Ngozi|Nwosu/);
      const stored = await page.evaluate(() => JSON.stringify([{ ...localStorage }, { ...sessionStorage }]));
      expect(stored).not.toMatch(/Ngozi|Nwosu|850000/);
      expect(seen.urls.filter((u) => /payroll/i.test(u))).toEqual([]);
    });

    test('4305 uncertain: raw job status, outcome not known, restart rule, nothing resent, no recovery buttons', async ({ page }) => {
      await page.goto('/work/4305');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText(/Job 2 · sent/)).toBeVisible();
      await expect(main.getByText('Outcome not known')).toBeVisible();
      await expect(main.getByText('Restart allowed under rule 12')).toBeVisible();
      await expect(main.getByText(/Nothing has been resent from this page\./)).toBeVisible();
      await expect(main.getByText(/No receipt yet/)).toBeVisible();
      await expect(main.getByText('No proof on file')).toBeVisible();
      for (const name of [/retry/i, /cancel/i, /record what happened/i, /resend/i]) await expect(main.getByRole('button', { name })).toHaveCount(0);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4305-${viewport.width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4306 proof on file: a link to the proof route that is not requested until clicked', async ({ page }) => {
      const seen = watch(page);
      await page.goto('/work/4306');
      await loaded(page);
      const link = page.getByRole('link', { name: 'Proof on file' });
      await expect(link).toHaveAttribute('href', '/api/v1/work/4306/forecast/observations/8');
      expect(seen.urls.filter((u) => u.includes('/observations/'))).toEqual([]);
    });

    test('4307 and an unknown id are unavailable in the same words', async ({ page }) => {
      await page.goto('/work/4307');
      await expect(page.getByRole('heading', { name: 'This record is unavailable.' })).toBeVisible();
    });

    test('a failed forecast read keeps the header and says why (409)', async ({ page, context }) => {
      await context.addCookies([{ name: 'psl_mock_scenario', value: 'forecast:409', url: test.info().project.use.baseURL! }]);
      await page.goto('/work/4301');
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Cash forecast for PSL Technologies');
      await expect(page.getByText('This changed while you were reading it. Reload.')).toBeVisible();
      await expect(page.getByText('PSL Technologies Ltd')).toHaveCount(0);
    });

    test('actuals for a month: loaded once, rows, direction, Unknown, cut lists said so; no write; 404 keeps the forecast', async ({ page }) => {
      const seen = watch(page);
      await page.goto('/work/4301?month=2026-11');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('Actual 6 · Out')).toBeVisible();
      await expect(main.getByText('Actual 5 · In')).toBeVisible();
      await expect(main.getByText('Not verified')).toBeVisible();
      await expect(main.getByText('Showing the first rows only. The rest isn’t available here.')).toBeVisible();
      await expect(main.getByText(/show more/i)).toHaveCount(0);
      expect(seen.urls.filter((u) => u.endsWith('/actuals/2026-11'))).toHaveLength(1);
      await noWriteButtons(page);
      expect(seen.writes).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4301-actuals-${viewport.width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
      // choose another month with the control: no cut sentence for a month that is not cut, and the reversed match is marked
      await main.getByRole('combobox', { name: /Show actuals for/ }).click();
      await page.getByRole('option', { name: '2026-09' }).click();
      await expect(main.getByText('Reversed')).toBeVisible();
      await expect(main.getByText('Showing the first rows only. The rest isn’t available here.')).toHaveCount(0);
      await page.goto('/work/4301?month=2026-10');
      await expect(page.getByText('No actuals recorded for 2026-10.')).toBeVisible();
      await page.goto('/work/4301?month=2026-12');
      await expect(page.getByText('This record is unavailable.').first()).toBeVisible();
      await expect(page.getByText('PSL Technologies Ltd')).toBeVisible();
    });
  });
}
