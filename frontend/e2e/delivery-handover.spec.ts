import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

// F-117: Handover to Support (SCR-48) on the live work item, on the live shapes (mock/handover-live.mjs), at 1440 and 390.
// Sample data only: nothing is ever sent to Support.
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
const choose = async (main: Locator, label: RegExp | string, option: RegExp) => {
  await main.getByRole('combobox', { name: label }).click();
  await main.page().getByRole('option', { name: option }).click();
};
const GONE = /Tola|Review needed|Open question for PSL|ATTACHED|Replaced|TEST TEMPLATE/;

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('6101: waiting to be published; a double click publishes once and the page says Queued', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/6101');
      await expect(main.getByText('Waiting to be published')).toBeVisible();
      await expect(main.getByText('Publishing sends it to Support. Then you record whether they received it or found gaps.')).toBeVisible();
      await expect(main.getByText(GONE)).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
      await main.getByRole('button', { name: 'Publish to Support' }).dblclick();
      await expect(main.getByText('Queued for Support')).toBeVisible();
      expect(t.writes()).toHaveLength(1);
      expect(t.writes()[0]).toMatchObject({ path: '/api/v1/work/6101/support-publication', body: { expected_revision: 8, case_revision: 41, version_id: 9101 } });
      await expect(main.getByRole('button', { name: 'Publish to Support' })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('6103: the record form, then one request and the reply on the page', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/6103');
      await expect(main.getByRole('heading', { name: 'Record Support’s reply' })).toBeVisible();
      await expect(main.getByText('Recording as Support lead')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Record reply' })).toBeDisabled();
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
      await main.getByLabel('Who replied').fill('Femi Ojo');
      await choose(main, 'How they replied', /^Email$/);
      await main.getByLabel('When they replied').fill('2026-11-25T11:00');
      await main.getByRole('radio', { name: 'Gaps found' }).click();
      await main.getByLabel('Gaps', { exact: true }).fill('First gap\n\nSecond gap');
      await main.getByLabel('Note', { exact: true }).fill('Two things are missing');
      await choose(main, 'Proof', /signature v1/);
      await main.getByRole('button', { name: 'Record reply' }).dblclick();
      await expect(main.getByText('Support found 2 gaps').first()).toBeVisible();
      expect(t.writes()).toHaveLength(1);
      expect(t.writes()[0].body).toMatchObject({ receipt_id: 8101, previous_id: null, status: 'gaps', gaps: ['First gap', 'Second gap'], role: 'Support lead', evidence_id: 7301 });
      await expect(main.getByText('1. First gap')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Record Support’s reply' })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('6104 and 6105: the gaps as numbered Open rows; received shows none', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/6104');
      await expect(main.getByText('Support listed 2 gaps on 25 Nov')).toBeVisible();
      await expect(main.getByText('2. Runbook misses the nightly export restart')).toBeVisible();
      await expect(main.getByText('Open')).toHaveCount(2);
      await expect(main.getByText(GONE)).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
      await page.goto('/work/6105');
      await expect(main.getByText('Support received it').first()).toBeVisible();
      await expect(main.getByText(/Support listed/)).toHaveCount(0);
      await expect(main.getByText('Open')).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('6106: uncertain; Check what happened sends one reconcile and there is no Publish', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/6106');
      await expect(main.getByText(/We couldn’t confirm whether Support got it/)).toBeVisible();
      await expect(main.getByRole('button', { name: /Publish/ })).toHaveCount(0);
      await main.getByRole('button', { name: 'Check what happened' }).dblclick();
      await expect(main.getByRole('button', { name: 'Check what happened' })).toHaveCount(0);
      expect(t.writes().map((w) => [w.path, w.body])).toEqual([['/api/v1/work/6106/actions', { expected_revision: 8, action: 'reconcile' }]]);
    });

    test('6107: the recipient sees the document and acknowledges once', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/6107');
      await expect(main.getByText('Support handover · version 1')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Support’s own acknowledgement' })).toBeVisible();
      await expect(main.getByText(GONE)).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
      await main.getByRole('radio', { name: 'Received' }).click();
      await main.getByLabel('Acknowledgement note').fill('Got it');
      await choose(main, 'Acknowledgement proof', /support_acknowledgement v1/);
      await main.getByRole('button', { name: 'Acknowledge' }).click();
      await expect(main.getByText('Acknowledged by Support: Received')).toBeVisible();
      expect(t.writes()).toHaveLength(1);
    });

    test('6108: not yours reads exactly that', async ({ page }) => {
      await page.goto('/work/6108');
      await expect(page.locator('main#main').getByText('This record is unavailable.').first()).toBeVisible();
    });
  });
}
