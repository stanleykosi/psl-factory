import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const PAGE = '/finance/month-end?period=2026-10';
// F-79: SCR-36 Month-end against the contract mock's live GET /month-end, at 1440 and 390, axe WCAG 2.2 AA.
const BAD_PERIODS = ['/finance/month-end', '/finance/month-end?period=2026-13', '/finance/month-end?period=Oct', '/finance/month-end?period=2026-10&period=2026-11', '/finance/month-end?period='];

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.locator('main#main h1, main#main h3').first()).toBeVisible();
}

/** Cookies for the whole site (path /), so the browser also sends them to /api/v1. */
async function cookies(context: BrowserContext, values: Record<string, string>, baseURL: string) {
  await context.addCookies(Object.entries(values).map(([name, value]) => ({ name, value, url: `${baseURL}/` })));
}

async function openPage(page: Page, context: BrowserContext, baseURL: string, values: Record<string, string> = {}, path = PAGE) {
  await cookies(context, values, baseURL);
  await page.goto(path);
  await loaded(page);
}

/** Tabs forward until the target has keyboard focus, then returns its outline. */
async function tabTo(page: Page, target: Locator) {
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((el) => el === document.activeElement)) {
      return target.evaluate((el) => {
        const s = getComputedStyle(el);
        return { style: (s.outlineStyle !== 'none' ? s.outlineStyle : /rgb\(36, 89, 214\)|0px 0px 0px 2px inset/.test(s.boxShadow + s.borderTopColor + s.textDecorationColor) ? 'solid' : 'none'), width: (s.outlineStyle !== 'none' ? s.outlineWidth : '2px') };
      });
    }
  }
  throw new Error('target never received focus');
}

const main = (page: Page) => page.locator('main#main');
const cashCell = (page: Page) => page.locator('.monthend-cell').filter({ hasText: 'CASH RECEIVED' }).locator('.monthend-cell__value');
const monthEndReads = (reads: string[]) => reads.filter((u) => new URL(u).pathname === '/api/v1/month-end');

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('the board in order: counts with Stopped, cash, rows with labels, links to the returned paths', async ({ page, context, baseURL }) => {
    const reads: string[] = [];
    page.on('request', (r) => reads.push(r.url()));
    await openPage(page, context, baseURL!);
    const text = await main(page).innerText();
    const order = ['FINANCE / MONTH-END', 'Month-end · October 2026', 'UPDATED 10:42', 'DONE', 'WAITING', 'IN PROGRESS', 'STOPPED', 'CASH RECEIVED', '₦4.7M', 'Receivables snapshot', 'Bank statements', 'Management accounts', 'Income detail and schedules'];
    const positions = order.map((s) => text.indexOf(s));
    expect(positions.every((p) => p >= 0), JSON.stringify(positions)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    await expect(page.locator('.monthend-cell__value')).toHaveText(['2', '1', '3', '1', '₦4.7M']);
    const rows = page.locator('table tbody tr');
    await expect(rows).toHaveCount(4);
    await expect(rows.locator('td:nth-child(2) .psl-tag')).toHaveText(['Waiting for review', 'Waiting for the Access Bank statement', 'Agent preparing', 'Verified']);
    await expect(rows.nth(3).locator('.psl-tag')).toHaveClass('psl-tag psl-tag--done');
    await expect(rows.nth(0).locator('a')).toHaveAttribute('href', '/projects/00000000-0000-4000-8000-000000000101');
    await expect(page.getByText(/ of \d/)).toHaveCount(0);
    await expect(page.locator('.monthend-note, .monthend-bar, .monthend-aside')).toHaveCount(0);
    expect(monthEndReads(reads).map((u) => new URL(u).search)).toEqual(['?month=2026-10']);
    expect(reads.some((u) => u.includes('/api/v1/finance/'))).toBe(false);
    await expectNoAxeViolations(page);
  });

  test('Show more appends the next page and then goes away', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!);
    await page.getByRole('button', { name: 'Show more' }).click();
    await expect(page.locator('table tbody tr')).toHaveCount(6);
    await expect(page.getByRole('button', { name: 'Show more' })).toHaveCount(0);
    await expect(page.locator('.monthend-cell__value')).toHaveText(['2', '1', '3', '1', '₦4.7M']);
  });

  test('keyboard reaches a task link with a visible outline', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!);
    const outline = await tabTo(page, page.locator('table tbody tr a').first());
    expect(outline.style).toBe('solid');
    expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(2);
  });

  test('cash by project: an unavailable workspace reads Unknown, never 0', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!, { psl_mock_month_end: 'cash-unavailable' });
    await expect(cashCell(page)).toHaveText('By project');
    await expect(page.locator('.monthend-cash li').nth(1)).toContainText('Unknown');
    await expectNoAxeViolations(page);
    for (const variant of ['two-currency', 'more-cash', 'unnamed', 'zero']) {
      await openPage(page, context, baseURL!, { psl_mock_month_end: variant });
      await expectNoAxeViolations(page);
    }
    await expect(cashCell(page)).toHaveText('₦0.00');
  });
});

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('empty month', async ({ page, context, baseURL }) => {
      await openPage(page, context, baseURL!, { psl_mock_month_end: 'empty' });
      await expect(page.getByText('Nothing to close this month')).toBeVisible();
      expect((await page.locator('.monthend-empty').boundingBox())!.height).toBeLessThan(200);
      if (viewport === DESKTOP) await expect(page.locator('.monthend-cell__value')).toHaveText(['0', '0', '0', '0', '₦4.7M']);
      else await expect(page.locator('.monthend-summary')).toHaveText('0 done · 0 waiting');
      await expect(page.locator('table, .monthend-card')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    test('wrong user (pm) sees no access and nothing about the month', async ({ page, context, baseURL }) => {
      await openPage(page, context, baseURL!, { psl_mock_persona: 'pm' });
      await expect(page.getByRole('heading', { name: 'You can’t open this month-end checklist' })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Back to my queue' })).toHaveAttribute('href', '/my-work');
      expect(await main(page).innerText()).not.toMatch(/₦|Bank statements|Receivables|[0-9]/);
      await expectNoAxeViolations(page);
    });

    test('a 403 and a 404 month-end answer render the same main', async ({ page, context, baseURL }) => {
      const html: string[] = [];
      for (const scenario of ['403', '404']) {
        // Only the month-end read gets the scenario, so the frame's /me still succeeds.
        await page.unrouteAll();
        await page.route('**/api/v1/month-end*', (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': scenario } }));
        await openPage(page, context, baseURL!);
        await expect(page.getByRole('heading', { name: 'You can’t open this month-end checklist' })).toBeVisible();
        html.push(await main(page).innerHTML());
      }
      expect(html[1]).toBe(html[0]);
    });

    test('another month is not shown (mock 404)', async ({ page, context, baseURL }) => {
      await openPage(page, context, baseURL!, {}, '/finance/month-end?period=2026-09');
      await expect(page.getByRole('heading', { name: 'You can’t open this month-end checklist' })).toBeVisible();
    });

    test('a missing or malformed period is not found and sends no request', async ({ page }) => {
      const reads: string[] = [];
      page.on('request', (r) => reads.push(r.url()));
      for (const path of BAD_PERIODS) {
        await page.goto(path);
        await expect(page.getByText('This page doesn’t exist.')).toBeVisible();
      }
      expect(monthEndReads(reads)).toEqual([]);
      await expectNoAxeViolations(page);
    });

    test('the error card offers Try again', async ({ page, context, baseURL }) => {
      await cookies(context, { psl_mock_month_end: 'error' }, baseURL!);
      await page.goto(PAGE);
      await expect(page.getByText(/couldn’t load the month-end checklist/)).toBeVisible();
      await expect(page.getByRole('button', { name: /Try again/ })).toBeVisible();
      await expectNoAxeViolations(page);
    });
  });
}

test.describe('phone 390', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('the phone board: back link, summary and a card per returned task', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!);
    await expect(page.getByRole('link', { name: '← Finance' })).toBeVisible();
    expect(await page.getByRole('heading', { level: 1 }).innerText()).toBe('Month-end · Oct');
    await expect(page.locator('.monthend-summary')).toHaveText('2 done · 1 waiting');
    const cards = page.locator('.monthend-card');
    await expect(cards).toHaveCount(4);
    await expect(cards.locator('.psl-tag')).toHaveText(['Waiting for review', 'Waiting for the Access Bank statement', 'Agent preparing', 'Verified']);
    await expect(cards.locator('.monthend-card__where').first()).toContainText('Lagoon Health patient app');
    for (const hidden of ['.monthend-strip', 'table']) await expect(page.locator(hidden)).toBeHidden();
    await page.getByRole('button', { name: 'Show more' }).click();
    await expect(cards).toHaveCount(6);
    await expectNoAxeViolations(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const more = await page.getByRole('button', { name: 'Show more' }).count();
    expect(more).toBe(0);
  });

  test('the cash lines pass axe on a phone', async ({ page, context, baseURL }) => {
    for (const variant of ['cash-unavailable', 'two-currency', 'more-cash']) {
      await openPage(page, context, baseURL!, { psl_mock_month_end: variant });
      await expectNoAxeViolations(page);
    }
  });

  test('Show more is a 44px target', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!);
    expect((await page.getByRole('button', { name: 'Show more' }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
  });

  test('keyboard reaches the back link with a visible outline', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!);
    const outline = await tabTo(page, page.getByRole('link', { name: '← Finance' }));
    expect(outline.style).toBe('solid');
    expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(2);
  });

  test('← Finance goes back to My work through history', async ({ page }) => {
    await page.goto('/my-work');
    await loaded(page);
    await page.goto(PAGE);
    await loaded(page);
    await page.getByRole('link', { name: '← Finance' }).click();
    await expect(page).toHaveURL(/\/my-work$/);
  });
});
