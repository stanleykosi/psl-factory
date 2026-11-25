import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-102: the fixed asset schedule on the live shapes (ids 3901 to 3910, served by mock/assets-live.mjs). Read only.
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const SHOTS = process.env.F102_SHOTS;
const WRITES = /^(approve|return|reject|revoke|upload|correct|save|post|record|capture|attach)/i;

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Where it stands' })).toBeVisible();
};
const watch = (page: Page) => {
  const seen = { writes: [] as string[] };
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (r.method() !== 'GET' && url.pathname.startsWith('/api/')) seen.writes.push(`${r.method()} ${url.pathname}`);
  });
  return seen;
};
const checked = async (page: Page, name: string, width: number) => {
  const names = await page.locator('main#main').getByRole('button').allInnerTexts();
  expect(names.filter((n) => WRITES.test(n.trim()))).toEqual([]);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}-${width}.png`, fullPage: true });
  expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
};

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('3901 investigating: stage, finding, register, 64 assets, three unclear dates, nothing else', async ({ page }) => {
      const seen = watch(page);
      await page.goto('/work/3901');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('Chidi is reading the register and checking the dates.')).toBeVisible();
      await expect(main.getByText('PSL-Technologies').first()).toBeVisible();
      await expect(main.getByText('Sage-200')).toBeVisible();
      await expect(main.getByText('As of 31 Dec 2025')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Assets' }).locator('xpath=ancestor::section[1]').locator('tbody tr')).toHaveCount(64);
      for (const id of ['FA-007', 'FA-008', 'FA-009']) await expect(main.getByText(`${id} · Date unclear`)).toBeVisible();
      await expect(main.getByText('No review is open for you.')).toHaveCount(0);
      await expect(main.getByText('Approve, Return, Reject')).toBeVisible();
      await expect(main.getByRole('link', { name: 'Open proof' })).toHaveCount(0);
      await expect(main.getByRole('heading', { name: 'Depreciation schedule' })).toHaveCount(0);
      await expect(page.getByText(/not available|never reads asset values|MANAGEMENT ACCOUNTS/)).toHaveCount(0);
      expect(seen.writes).toEqual([]);
      await checked(page, '3901', viewport.width);
    });

    test('3902 unknown values: Unknown, Partial, no 0 for the missing', async ({ page }) => {
      await page.goto('/work/3902');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('Partial')).toBeVisible();
      await expect(main.getByText('Unknown').first()).toBeVisible();
      const closing = main.getByRole('heading', { name: 'Closing controls' }).locator('xpath=ancestor::section[1]');
      await expect(closing.getByText('Unknown')).toHaveCount(2);
      await checked(page, '3902', viewport.width);
    });

    test('3903 held: the reason, no totals', async ({ page }) => {
      await page.goto('/work/3903');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('The in-service date of one asset is unclear, so the charge is held.')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Schedule totals' })).toHaveCount(0);
      await expect(main.getByRole('columnheader', { name: 'Charge' })).toHaveCount(0);
      await checked(page, '3903', viewport.width);
    });

    test('3904 calculating: no schedule, no review beyond the one line', async ({ page }) => {
      await page.goto('/work/3904');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('The depreciation is being calculated.')).toBeVisible();
      await expect(main.getByText('No review is open for you.')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Depreciation schedule' })).toHaveCount(0);
      await checked(page, '3904', viewport.width);
    });

    test('3905 verified: schedule, totals, scope, Posted No, proof and note links', async ({ page }) => {
      await page.goto('/work/3905');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByRole('heading', { name: 'Depreciation schedule' })).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Schedule totals' })).toBeVisible();
      await expect(main.getByText('Posted to the ledger')).toBeVisible();
      await expect(main.getByText('Native source verified')).toBeVisible();
      await expect(main.getByText('Reviewed in-service date')).toBeVisible();
      const proofs = main.getByRole('link', { name: 'Open proof' });
      await expect(proofs).toHaveCount(3);
      await expect(proofs.first()).toHaveAttribute('href', '/api/v1/work/3905/assets/date-proofs/701');
      await expect(main.getByRole('link', { name: 'Open accounting note' })).toHaveAttribute('href', 'https://notes.example.test/accounting-note/8');
      const ok = await page.request.get('/api/v1/work/3905/assets/date-proofs/701');
      expect(ok.status()).toBe(200);
      expect((await page.request.get('/api/v1/work/3905/assets/date-proofs/999')).status()).toBe(404);
      await checked(page, '3905', viewport.width);
    });

    test('3906 ready without a note link: no accounting note and no placeholder', async ({ page }) => {
      await page.goto('/work/3906');
      await loaded(page);
      await expect(page.getByRole('link', { name: 'Open proof' })).toHaveCount(1);
      await expect(page.getByText(/accounting note/i)).toHaveCount(0);
    });

    test('3907 returned and 3908 empty', async ({ page }) => {
      await page.goto('/work/3907');
      await loaded(page);
      await expect(page.getByText('Returned for opening proof')).toBeVisible();
      await expect(page.getByText('No opening proof attached')).toBeVisible();
      await page.goto('/work/3908');
      await loaded(page);
      await expect(page.getByText('No register has been captured yet.')).toBeVisible();
      await expect(page.getByText('Waiting for the first register.')).toBeVisible();
      await checked(page, '3908', viewport.width);
    });

    test('3909 is unavailable and 3910 keeps the header with the same words', async ({ page }) => {
      await page.goto('/work/3909');
      await expect(page.getByText('This record is unavailable.')).toBeVisible();
      await page.goto('/work/3910');
      await expect(page.locator('main#main h1').first()).toBeVisible();
      await expect(page.getByText('This record is unavailable.')).toBeVisible();
    });

    test('a 503 on the panel keeps the header and offers Try again', async ({ page, context }) => {
      await context.addCookies([{ name: 'psl_mock_scenario', value: 'assets:503', domain: 'localhost', path: '/' }]);
      await page.goto('/work/3905');
      await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
      await expect(page.locator('main#main h1').first()).toBeVisible();
    });
  });
}
