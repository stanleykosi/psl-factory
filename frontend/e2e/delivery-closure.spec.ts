import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-118: Closure (SCR-49) on the live work item, on the live shapes (mock/closure-live.mjs), at 1440 and 390. Sample data only.
// The closure document version and decision proof are not served by any read, so Close and Return are held; the replace-the-report
// write is the one closure write a browser can complete here.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const track = (page: Page) => {
  const log: { method: string; path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/')) log.push({ method: r.method(), path: new URL(r.url()).pathname, body: r.method() === 'POST' ? JSON.parse(r.postData() ?? '{}') : {} });
  });
  return { all: log, writes: () => log.filter((l) => l.method === 'POST') };
};
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const clean = async (page: Page) => {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
};
const GONE = /Tola|read-only|Support contract|moves to Closed|debts? (are |is )?confirmed/i;

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('6201: not yet; eight checks, the held finding as next, no Finance block, no Tola', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/6201');
      await expect(main.getByText('Closure · Not yet').first()).toBeVisible();
      await expect(main.getByText('Next: No retrospective saved')).toBeVisible();
      await expect(main.getByText('Before closure')).toBeVisible();
      for (const title of ['Current project scope', 'Go-live acceptance', 'Release stability', 'Project archive', 'Support handover', 'Finance notification coverage', 'PM closure report']) await expect(main.getByText(title).first()).toBeVisible();
      await expect(main.getByRole('link', { name: 'Write the retrospective' })).toBeVisible();
      await expect(main.getByText('Finance confirmation: milestone notifications')).toHaveCount(0);
      await expect(main.getByText(GONE)).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
    });

    test('6204: Close and Return are shown from the task and held with a reason; the Finance form is held without a served proof; nothing is sent', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/6204');
      await expect(main.getByText('Closure · Waiting for your decision').first()).toBeVisible();
      await expect(main.getByRole('button', { name: 'Close the project' })).toBeDisabled();
      await expect(main.getByRole('button', { name: 'Return with a note' })).toBeDisabled();
      await expect(main.getByText('The closure report isn’t ready to decide yet').first()).toBeVisible();
      await expect(main.getByText('Finance confirmation: milestone notifications')).toBeVisible();
      await expect(main.getByText('Milestone 31')).toBeVisible();
      await expect(main.getByText('No Finance evidence available to attach')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Confirm milestone notifications' })).toBeDisabled();
      await expect(main.getByText(GONE)).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
      expect(t.writes()).toEqual([]);
    });

    test('6203: awaiting the Head of PMO, no decision control, the Finance finding is the reason', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/6203');
      await expect(main.getByText('Closure · Awaiting Head of PMO').first()).toBeVisible();
      await expect(main.getByText('Next: The Head of PMO decides on closure.')).toBeVisible();
      await expect(main.getByRole('button', { name: /Close the project|Return with a note/ })).toHaveCount(0);
      await expect(main.getByText('Receipt missing for milestone 3').first()).toBeVisible();
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
    });

    test('6205: returned with who, when and why; replacing the report sends one request and leaves the returned state', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/6205');
      await expect(main.getByText('Ada Okafor returned closure on 24 Nov: “Add the client’s sign-off on the hypercare summary to the report.”')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Replace the report' })).toBeDisabled();
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
      await main.getByLabel('Report', { exact: true }).fill('The corrected report');
      await main.getByLabel('Where it comes from').fill('PM archive');
      await main.getByLabel('Why it is replaced').fill('The sign-off was missing');
      await main.getByRole('button', { name: 'Replace the report' }).dblclick();
      await expect(main.getByText('Closure · Awaiting Head of PMO').first()).toBeVisible();
      expect(t.writes()).toHaveLength(1);
      expect(t.writes()[0]).toMatchObject({ path: '/api/v1/work/6205/closure-report', body: { expected_revision: 8, case_revision: 41, previous_evidence_id: 107, report_text: 'The corrected report', source_reference: 'PM archive', reason: 'The sign-off was missing' } });
      await expect(main.getByRole('button', { name: 'Replace the report' })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('6206: closed; what is still open with an unknown amount as "Amount not recorded", the date and the limited note', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/6206');
      await expect(main.getByText('Closed', { exact: true }).first()).toBeVisible();
      await expect(main.getByText('Still open after closure')).toBeVisible();
      await expect(main.getByText('₦1,250,000.00')).toBeVisible();
      await expect(main.getByText('Amount not recorded')).toBeVisible();
      await expect(main.getByText('As of 20 Nov 2026 · List is limited; more may exist.')).toBeVisible();
      await expect(main.getByText(GONE)).toHaveCount(0);
      await expect(main.getByRole('button', { name: /Close the project|Return|Replace|Confirm/ })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
    });

    test('6207 and 6208: no open invoices says so; no visible debt draws nothing', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/6207');
      await expect(main.getByText('No open invoices recorded as of 20 Nov 2026.')).toBeVisible();
      await page.goto('/work/6208');
      await expect(main.getByText('Closed', { exact: true }).first()).toBeVisible();
      await expect(main.getByText('Still open after closure')).toHaveCount(0);
      await expect(main.getByText(/No open invoices/)).toHaveCount(0);
    });

    test('6209: not yours reads exactly that', async ({ page }) => {
      await page.goto('/work/6209');
      await expect(page.locator('main#main').getByText('This record is unavailable.').first()).toBeVisible();
    });
  });
}
