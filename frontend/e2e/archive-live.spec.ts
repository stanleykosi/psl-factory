import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-116: the archive page (SCR-47) on the live work item, on the live shapes (mock/archive-live.mjs), at 1440 and 390: working, verified,
// ready to start, uncertain with a lookup, and one request per press.
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
  return { posts: () => log.filter((l) => l.method === 'POST') };
};
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const clean = async (page: Page) => {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
};
const HIDDEN = /mark (each|found)|never purge|no approval|Ask Tola|step 3 of 4/i;

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('5302 working: the count, Copying rows, no Start, nothing sent', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/5302');
      await expect(main.getByText('Archiving in progress. 28 of 42 files copied.')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Archive index' })).toBeVisible();
      await expect(main.getByText(/Copying/).first()).toBeVisible();
      await expect(main.getByRole('button', { name: 'Start archive' })).toHaveCount(0);
      await expect(main.getByText(HIDDEN)).toHaveCount(0);
      expect(t.posts()).toEqual([]);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
    });

    test('5301 verified: the sentence, every group Archived, the next block, no Start', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/5301');
      await expect(main.getByText('Archived and verified: 42 files, each matched in the archive index.')).toBeVisible();
      await expect(main.getByText('Handover can start now that the archive is verified.')).toBeVisible();
      await expect(main.getByText('Archived', { exact: true })).toHaveCount(5);
      await expect(main.getByText(/Start the archive/)).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
    });

    test('5304 ready: the sources, Start sends one request with the checked ids', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/5304');
      await expect(main.getByRole('checkbox', { name: 'RFP response' })).toBeChecked();
      await expect(main.getByRole('checkbox', { name: 'Planning' })).not.toBeChecked();
      await clean(page);
      const start = main.getByRole('button', { name: 'Start archive' });
      expect((await start.boundingBox())!.height).toBeGreaterThanOrEqual(label === 'phone 390' ? 44 : 32);
      await start.dblclick();
      await expect(main.getByText(/Queued\./)).toBeVisible();
      expect(t.posts()).toEqual([{ method: 'POST', path: '/api/v1/work/5304/archive-files', body: { source_ids: [11, 12], expected_revision: 7, case_revision: 41 } }]);
    });

    test('5303 uncertain: Look up per file, no Copy again until a lookup finds a file missing', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/5303');
      await expect(main.getByText(/The archive store didn’t confirm 6 of 42 files/)).toBeVisible();
      await expect(main.getByText('Not confirmed · 6').first()).toBeVisible();
      await expect(main.getByRole('button', { name: 'Look up' })).toHaveCount(6);
      await expect(main.getByRole('button', { name: 'Copy again' })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
      await main.getByRole('button', { name: 'Look up' }).first().click();
      await expect(main.getByRole('button', { name: 'Copy again' })).toHaveCount(1);
      expect(t.posts()).toHaveLength(1);
    });
  });
}
