import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// All exceptions (SCR-10) and Verified outputs (SCR-14) on the live work list against the contract mock, at 390 and 1440.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

test.use({ timezoneId: 'Africa/Lagos' });

const persona = (context: BrowserContext, value: string) =>
  context.addCookies([{ name: 'psl_mock_persona', value, url: test.info().project.use.baseURL! }]);
const noAxeViolations = async (page: Page) => {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
};
const loaded = (page: Page) => expect(page.getByText(/^Loading /)).toHaveCount(0);
const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });
const scrollWidth = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth);

for (const [label, viewport] of [['desktop 1440', DESKTOP], ['phone 390', PHONE]] as const) {
  test.describe(label, () => {
    test.use({ viewport });
    const phone = viewport.width < 720;

    test('exceptions: 8 rows, Show more adds the next page, coverage lines, no page-size control', async ({ page }) => {
      const lists: string[] = [];
      page.on('request', (request) => {
        if (request.url().includes('/api/v1/')) lists.push(`${request.method()} ${new URL(request.url()).pathname}${new URL(request.url()).search}`);
      });
      await page.goto('/exceptions');
      await loaded(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('All exceptions');
      await expect(page).toHaveTitle('All exceptions · PSL Factory');
      await expect(page.locator(phone ? '.exc-card' : 'tbody tr')).toHaveCount(8);
      await expect(page.getByText('8 shown so far')).toBeVisible();
      await expect(page.getByText('This list may be incomplete. Some work could not be checked yet.')).toBeVisible();
      await expect(page.getByRole('radio', { name: '50' })).toHaveCount(0);
      await shot(page, `exceptions-${viewport.width}`);
      await noAxeViolations(page);
      await page.getByRole('button', { name: 'Show more' }).click();
      await expect(page.locator(phone ? '.exc-card' : 'tbody tr')).toHaveCount(16);
      expect(await scrollWidth(page)).toBeLessThanOrEqual(viewport.width);
      expect(lists.filter((l) => l.includes('/api/v1/work?'))).toEqual(['GET /api/v1/work?queue=exceptions&page=1', 'GET /api/v1/work?queue=exceptions&page=2']);
      expect(lists.some((l) => l.includes('/api/v1/exceptions') || !l.startsWith('GET'))).toBe(false);
    });

    test('exceptions: persona none sees the empty state, pm sees the closed list', async ({ page, context }) => {
      await persona(context, 'none');
      await page.goto('/exceptions');
      await expect(page.getByRole('heading', { level: 2, name: 'No exceptions right now.' })).toBeVisible();
      await shot(page, `exceptions-${viewport.width}-empty`);
      await persona(context, 'pm');
      await page.goto('/exceptions');
      await expect(page.getByText('This list isn’t open to your role.')).toBeVisible();
    });

    test('verified: rows, Open output on a row with and without a file, empty state', async ({ page, context }) => {
      await page.goto('/verified');
      await loaded(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Verified outputs');
      await expect(page.locator(phone ? '.ver-card' : 'tbody tr')).toHaveCount(8);
      await expect(page.getByText(/Verified at/)).toHaveCount(0);
      await shot(page, `verified-${viewport.width}`);
      await noAxeViolations(page);
      expect(await scrollWidth(page)).toBeLessThanOrEqual(viewport.width);
      // The mock's id 413 has no output file (ids are listed in mock/live-work.mjs).
      await page.getByRole('button', { name: 'Show more' }).click();
      const none = page.locator(phone ? '.ver-card' : 'tbody tr').filter({ has: page.getByRole('link', { name: /INV-0386 / }) });
      await none.getByRole('button', { name: 'Open output' }).click();
      await expect(none.getByText('No output file is attached to this item yet. Open the item to see its records.')).toBeVisible();
      await persona(context, 'none');
      await page.goto('/verified');
      await expect(page.getByRole('heading', { level: 2, name: 'Nothing has been verified yet.' })).toBeVisible();
      await shot(page, `verified-${viewport.width}-empty`);
    });
  });
}
