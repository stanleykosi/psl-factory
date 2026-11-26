import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-115: the hypercare page (SCR-46) on the live work item, on the live shapes (mock/hypercare-live.mjs), at 1440 and 390: the four states,
// the pause and continue controls (one request per press), and the section-local failures.
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
  return { all: log, posts: () => log.filter((l) => l.method === 'POST') };
};
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const clean = async (page: Page) => {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
};
const HIDDEN = /Day \d|of 30|Log an observation|Log an issue|Record release|Ask Tola/;

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('5201 Setup needed: the line, the held check, no criteria list, nothing sent', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/5201');
      await expect(main.getByText('Hypercare criteria are not set.').first()).toBeVisible();
      await expect(main.getByText('Setup needed').first()).toBeVisible();
      await expect(main.getByText('An admin can draft them in Setup')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Checks' })).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Criteria' })).toHaveCount(0);
      await expect(main.getByText('None recorded').first()).toBeVisible();
      await expect(main.getByText(HIDDEN)).toHaveCount(0);
      expect(t.posts()).toEqual([]);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
    });

    test('5202 Evaluating: Not known results, one reading, and Pause sends one request', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/5202');
      await expect(main.getByRole('heading', { name: 'Criteria' })).toBeVisible();
      await expect(main.getByText('Tola is evaluating hypercare.')).toBeVisible();
      await expect(main.getByText('Not known').first()).toBeVisible();
      await expect(main.getByText('No reading yet')).toBeVisible();
      await expect(main.getByText('No open issues.')).toBeVisible();
      await expect(main.getByText('Window ends')).toBeVisible();
      await expect(main.getByText(HIDDEN)).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
      const pause = main.getByRole('button', { name: 'Pause background work' });
      expect((await pause.boundingBox())!.height).toBeGreaterThanOrEqual(label === 'phone 390' ? 44 : 32);
      await pause.dblclick();
      await expect(page.getByText(/Done\. This item is now:/).first()).toBeVisible();
      expect(t.posts()).toEqual([{ method: 'POST', path: '/api/v1/work/5202/background', body: { expected_revision: 8, enabled: false } }]);
      await expect(main.getByRole('button', { name: 'Resume' })).toBeVisible();
    });

    test('5203 Qualified: Verified, every criterion Met, nothing open', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/5203');
      await expect(main.getByText('Hypercare qualified.')).toBeVisible();
      await expect(main.getByText('Verified', { exact: true })).toBeVisible();
      await expect(main.getByText('No open issues.')).toBeVisible();
      await expect(main.getByText('Not known')).toHaveCount(0);
      await expect(main.getByText('Next', { exact: true })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
    });

    test('5204 Not met: the findings, the blocking issue in its own list, the next lines', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/5204');
      await expect(main.getByText('Engineering/error_rate fails the configured criterion')).toBeVisible();
      await expect(main.getByText('Not met').first()).toBeVisible();
      await expect(main.getByText('Blocks hypercare')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Open issues' })).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Metric readings' })).toBeVisible();
      await expect(main.getByText('Closure stays blocked until then.')).toBeVisible();
      expect(await noSideScroll(page)).toBe(true);
      await clean(page);
    });

    test('5205 paused: Continue sends enabled true', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/5205');
      await main.getByRole('button', { name: 'Continue background work' }).click();
      await expect(page.getByText(/Done\. This item is now:/).first()).toBeVisible();
      expect(t.posts()).toEqual([{ method: 'POST', path: '/api/v1/work/5205/background', body: { expected_revision: 8, enabled: true } }]);
    });

    test('5206, 5207 and 5208: unavailable, and the failing read alone', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/5206');
      await expect(page.getByText('This record is unavailable.').first()).toBeVisible();
      await page.goto('/work/5207');
      await expect(main.getByRole('heading', { name: 'Criteria' })).toBeVisible();
      await expect(main.getByText(/We couldn’t load this part of the page/)).toBeVisible();
      await page.goto('/work/5208');
      await expect(main.getByRole('heading', { name: 'Criteria' })).toBeVisible();
      await expect(main.getByText(/Open issues couldn’t be loaded/)).toBeVisible();
      await expect(main.getByText('Release and acceptance')).toBeVisible();
    });
  });
}
