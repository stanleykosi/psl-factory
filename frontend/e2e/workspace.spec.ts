import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

// F-17: the line workspace on the work item page (PROPOSAL D-LINE-WORKSPACE, contract mock only). Every request
// goes to the local mock; nothing is sent to anyone.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const PART_A = ['W-2001', 'W-2002', 'W-2003', 'W-2004', 'W-2005'];

test.use({ timezoneId: 'Africa/Lagos' });

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function openItem(page: Page, id: string) {
  await page.goto(`/work/${id}`);
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('.ws')).toBeAttached();
}

const ring = (target: Locator) =>
  target.evaluate((el) => {
    const s = getComputedStyle(el);
    return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2;
  });

/** Tabs forward until the target has keyboard focus. */
async function tabTo(page: Page, target: Locator) {
  for (let i = 1; i <= 80; i++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((el) => el === document.activeElement)) return i;
  }
  throw new Error('target never received focus');
}

const requests: string[] = [];

test.beforeEach(async ({ request, context, baseURL, page }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
  requests.length = 0;
  page.on('request', (r) => requests.push(r.url()));
});

for (const viewport of [DESKTOP, PHONE]) {
  for (const id of PART_A) {
    test(`${id} at ${viewport.width}: axe clean, one h1, no sideways scroll, 44px controls`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await openItem(page, id);
      await expectNoAxeViolations(page);
      await expect(page.locator('h1')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
      // buttons and button-styled links in the workspace (inline cite links in a sentence are WCAG 2.5.8's inline exception)
      for (const control of await page.locator('.ws button, .ws a.psl-btn').all()) {
        expect((await control.boundingBox())!.height, await control.innerText()).toBeGreaterThanOrEqual(44);
      }
    });
  }
}

test('at 390 the tables scroll inside their own frame, and the frame takes keyboard focus with a ring', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await openItem(page, 'W-2004');
  const frame = page.getByRole('region', { name: 'Table: Forecast · 6 months' });
  const sizes = await frame.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth, overflow: getComputedStyle(el).overflowX }));
  expect(sizes.overflow).toBe('auto');
  expect(sizes.scroll).toBeGreaterThan(sizes.client);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole('heading', { level: 1 }).click();
  await tabTo(page, frame);
  expect(await ring(frame)).toBe(true);
});

test('a cite link in the workspace shows a focus ring', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2001');
  const cite = page.locator('.ws').getByRole('link', { name: 'ISS-0233' });
  await page.getByRole('heading', { level: 1 }).click();
  await tabTo(page, cite);
  expect(await ring(cite)).toBe(true);
});

test('nothing in the workspace animates with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const id of PART_A) {
    await openItem(page, id);
    expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length), id).toBe(0);
  }
});

test('W-2002 paging and filters are drawn disabled and send nothing; every request went to the mock', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2002');
  await expect(page.getByText('4 of 64')).toBeVisible();
  const more = page.getByRole('button', { name: 'Show more' });
  await expect(more).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Status: Suggested by Tola' })).toBeDisabled();
  const before = requests.length;
  await more.click({ force: true });
  await page.waitForTimeout(300);
  expect(requests.slice(before).filter((u) => u.includes('/api/'))).toEqual([]);
  // the page's API calls go through the app's same-origin proxy to the mock; nothing leaves this machine
  for (const url of requests) expect(new URL(url).hostname, url).toMatch(/^(localhost|127\.0\.0\.1)$/);
});

test('W-2010 draws no workspace', async ({ page }) => {
  await page.goto('/work/W-2010');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.locator('.ws')).toHaveCount(0);
});
