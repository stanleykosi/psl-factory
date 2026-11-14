import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const PAGE = '/finance/month-end?period=2026-10';
const BAD_PERIODS = ['/finance/month-end', '/finance/month-end?period=2026-13', '/finance/month-end?period=Oct', '/finance/month-end?period=2026-10&period=2026-11', '/finance/month-end?period='];

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
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
        return { style: s.outlineStyle, width: s.outlineWidth };
      });
    }
  }
  throw new Error('target never received focus');
}

const main = (page: Page) => page.locator('main#main');
const cashCell = (page: Page) => page.locator('.monthend-cell').filter({ hasText: 'CASH RECEIVED' }).locator('.monthend-cell__value');
const hrefs = (page: Page) => main(page).locator('a:visible').evaluateAll((links) => links.map((a) => a.getAttribute('href')));

async function noDebugText(page: Page) {
  const text = await page.locator('body').innerText();
  expect(text).not.toContain('SAMPLE DATA');
  expect(text).not.toMatch(/W-16\d\d|action_needed|\b[A-Z]{2,4}-\d{4}\b/);
}

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('the board in order, links to work items, restricted row without a link', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!);
    const text = await main(page).innerText();
    const order = [
      'FINANCE / MONTH-END',
      'Month-end · October 2026',
      'FROM RECORDS YOU CAN SEE · UPDATED 10:42',
      'DONE',
      '2 of 7',
      'WAITING',
      'IN PROGRESS',
      'CASH RECEIVED',
      '₦4.7M + Unknown',
      'Bank statements',
      'Management accounts',
      'Income detail and schedules',
      'Fixed asset schedule',
      'Cash forecast',
      'Business-unit totals',
      'Payroll',
      'Chidi',
      'Import the missing statement',
    ];
    const positions = order.map((s) => text.indexOf(s));
    expect(positions.every((p) => p >= 0), JSON.stringify(positions)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    await expect(page.locator('.monthend-cell__value')).toHaveText(['2 of 7', '3', '2', '₦4.7M + Unknown']);
    await expect(cashCell(page)).toHaveAccessibleDescription('Known so far ₦4,712,500.00; the rest is not known yet.');

    const rows = page.locator('table tbody tr');
    await expect(rows).toHaveCount(7);
    await expect(rows.locator('td:nth-child(3) .psl-tag')).toHaveText(['WAITING', 'NEEDS FINANCE DECISION', 'DONE', 'WAITING', 'DONE', 'WAITING', 'WAITING ON HR']);
    await expect(rows.nth(1).locator('.psl-tag')).toHaveClass('psl-tag psl-tag--person');
    await expect(rows.nth(2).locator('.psl-tag')).toHaveClass('psl-tag psl-tag--done');
    await expect(rows.nth(6).locator('.psl-tag')).toHaveClass('psl-tag psl-tag--waiting');
    await expect(rows.nth(0)).toContainText('Access Bank statement missing');
    await expect(rows.nth(0)).toContainText('2 of 3 accounts imported');

    const payroll = rows.nth(6);
    await expect(payroll.locator('strong')).toHaveText('Payroll');
    await expect(payroll).toContainText('HR only');
    await expect(payroll.locator('a')).toHaveCount(0);

    await expect(page.locator('.monthend-note img')).toHaveAttribute('src', '/agents/chidi.png');
    await expect(page.locator('.monthend-note img')).toHaveAttribute('alt', '');
    expect(await hrefs(page)).toEqual([
      ...['W-1601', 'W-1602', 'W-1603', 'W-1604', 'W-1605', 'W-1606'].map((id) => `/work/${id}`),
      '/work/W-1601',
    ]);
    await expect(page.getByRole('link', { name: 'Import the missing statement' })).toHaveAttribute('href', '/work/W-1601');
    const all = await page.locator('a').evaluateAll((links) => links.map((a) => a.getAttribute('href') ?? ''));
    expect(all.filter((h) => /SCR-|\.dc\.html|claude\.ai/.test(h))).toEqual([]);
    await expect(page.getByText('← Finance')).toBeHidden();
    await noDebugText(page);
    await expectNoAxeViolations(page);
  });

  test('keyboard reaches every Open link and the action with a visible outline', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!);
    const targets = [...(await page.getByRole('link', { name: 'Open' }).all()), page.getByRole('link', { name: 'Import the missing statement' })];
    expect(targets).toHaveLength(7);
    for (const target of targets) {
      const outline = await tabTo(page, target);
      expect(outline.style).toBe('solid');
      expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(2);
    }
  });

  test('unknown and known cash, never 0', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!, { psl_mock_month_end: 'unknown' });
    await expect(cashCell(page)).toHaveText('Unknown');
    await expect(cashCell(page)).toHaveAccessibleDescription('Not known yet.');
    await expectNoAxeViolations(page);

    await openPage(page, context, baseURL!, { psl_mock_month_end: 'known' });
    await expect(cashCell(page)).toHaveText('₦4.7M');
    await expect(cashCell(page)).toHaveAccessibleDescription('₦4,712,500.00');
    const cell = page.locator('.monthend-cell').filter({ hasText: 'CASH RECEIVED' });
    expect(await cell.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe('rgb(255, 255, 255)');
    await expect(page.locator('.monthend-note')).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Import the missing statement' })).toHaveCount(0);
    for (const value of await page.locator('.monthend-cell__value').allInnerTexts()) expect(value).not.toMatch(/^$|^0$|₦0/);
  });

  test('a pure v4 body (contract)', async ({ page, context, baseURL }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await openPage(page, context, baseURL!, { psl_mock_month_end: 'contract' });
    expect(errors).toEqual([]);
    await expect(page.locator('.monthend-asof')).toHaveCount(0);
    await expect(page.locator('.monthend-cell__value')).toHaveText(['Unknown', 'Unknown', 'Unknown', 'Unknown']);
    const rows = page.locator('table tbody tr');
    await expect(rows.locator('td:first-child')).toHaveText(['Bank statements', 'Management accounts', 'Income detail and schedules', 'Fixed asset schedule', 'Cash forecast', 'Business-unit totals', 'Payroll']);
    await expect(rows.locator('.psl-tag')).toHaveText(['WAITING', 'ACTION NEEDED', 'VERIFIED', 'WAITING', 'VERIFIED', 'WAITING', 'WAITING']);
    await expect(rows.locator('a')).toHaveCount(6);
    await expect(rows.nth(6).locator('td').nth(3)).toHaveText('');
    await expect(page.locator('.monthend-note')).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Import the missing statement' })).toHaveCount(0);
    await expectNoAxeViolations(page);
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
      await expect(page.getByText('No month-end tasks you can see for October 2026.')).toBeVisible();
      if (viewport === DESKTOP) await expect(page.locator('.monthend-cell__value')).toHaveText(['0 of 0', '0', '0', 'Unknown']);
      else await expect(page.locator('.monthend-summary')).toHaveText('0 of 0 done · 0 waiting');
      await expect(page.locator('table, .monthend-card, .monthend-note, .monthend-bar')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    test('wrong user (pm) sees no access and nothing about the month', async ({ page, context, baseURL }) => {
      await openPage(page, context, baseURL!, { psl_mock_persona: 'pm' });
      await expect(page.getByRole('heading', { name: 'You can’t open this month-end checklist' })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Back to my queue' })).toHaveAttribute('href', '/my-work');
      expect(await main(page).innerText()).not.toMatch(/₦|Bank statements|Payroll|[0-9]/);
      await expectNoAxeViolations(page);
    });

    test('a person with no sections (none) gets the frame state and nothing about the month', async ({ page, context, baseURL }) => {
      // The frame (F-01) stops at "No sections are open to your role yet." before any page renders; the mock
      // would answer this persona's month-end read with 403.
      await openPage(page, context, baseURL!, { psl_mock_persona: 'none' });
      await expect(page.getByText('No sections are open to your role yet.')).toBeVisible();
      expect(await main(page).innerText()).not.toMatch(/₦|Bank statements|Payroll|[0-9]/);
      await expectNoAxeViolations(page);
    });

    test('a 403 and a 404 month-end answer render the same main', async ({ page, context, baseURL }) => {
      const html: string[] = [];
      for (const scenario of ['403', '404']) {
        // Only the month-end read gets the scenario, so the frame's /me still succeeds.
        await page.unrouteAll();
        await page.route('**/api/v1/finance/month-end*', (route) =>
          route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': scenario } }),
        );
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
      page.on('request', (r) => {
        if (r.url().includes('/api/v1/finance/month-end')) reads.push(r.url());
      });
      for (const path of BAD_PERIODS) {
        await page.goto(path);
        await expect(page.getByText('This page doesn’t exist.')).toBeVisible();
      }
      expect(reads).toEqual([]);
      await expectNoAxeViolations(page);
    });

    test('no sample tag and no debug identifiers', async ({ page, context, baseURL }) => {
      await openPage(page, context, baseURL!);
      await noDebugText(page);
    });
  });
}

test.describe('phone 390', () => {
  test.use({ viewport: PHONE });

  test('the phone board: back link, summary, six cards and the pinned action', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!, { psl_mock_month_end: 'board-phone' });
    await expect(page.getByRole('link', { name: '← Finance' })).toBeVisible();
    expect(await page.getByRole('heading', { level: 1 }).innerText()).toBe('Month-end · Oct');
    await expect(page.locator('.monthend-summary')).toHaveText('2 of 7 done · 3 waiting');
    const cards = page.locator('.monthend-card');
    await expect(cards).toHaveCount(6);
    await expect(cards.locator('strong')).toHaveText(['Bank statements', 'Management accounts', 'Income detail and schedules', 'Fixed asset schedule', 'Cash forecast', 'Business-unit totals']);
    await expect(cards.locator('.psl-tag')).toHaveText(['WAITING', 'NEEDS FINANCE DECISION', 'DONE', 'WAITING', 'DONE', 'WAITING']);
    await expect(cards.locator('.monthend-card__where').first()).toHaveText('2 of 3 accounts imported');
    for (const hidden of ['.monthend-strip', 'table', '.monthend-note']) await expect(page.locator(hidden)).toBeHidden();
    await expect(page.getByRole('link', { name: 'Open' })).toHaveCount(0);
    const action = page.getByRole('link', { name: 'Import the missing statement' });
    await expect(action).toHaveAttribute('href', '/work/W-1601');
    const box = (await action.boundingBox())!;
    expect(box.y + box.height).toBeGreaterThan(PHONE.height - 40);
    expect(await page.locator('.monthend-bar').evaluate((el) => getComputedStyle(el).position)).toBe('sticky');
    expect(await hrefs(page)).toEqual(['/my-work', '/work/W-1601']);
    await expectNoAxeViolations(page);
  });

  test('default data: every returned task is a card, the restricted one without a link', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!);
    await expect(page.locator('.monthend-card')).toHaveCount(7);
    await expect(page.locator('.monthend-card').last()).toContainText('Payroll');
    await expect(page.locator('.monthend-card a')).toHaveCount(0);
    await expectNoAxeViolations(page);
  });

  test('unknown and contract scenarios pass axe', async ({ page, context, baseURL }) => {
    for (const scenario of ['unknown', 'contract']) {
      await openPage(page, context, baseURL!, { psl_mock_month_end: scenario });
      await expectNoAxeViolations(page);
    }
  });

  test('keyboard reaches the back link and the action with a visible outline', async ({ page, context, baseURL }) => {
    await openPage(page, context, baseURL!, { psl_mock_month_end: 'board-phone' });
    for (const target of [page.getByRole('link', { name: '← Finance' }), page.getByRole('link', { name: 'Import the missing statement' }).last()]) {
      const outline = await tabTo(page, target);
      expect(outline.style).toBe('solid');
      expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(2);
    }
  });

  test('← Finance goes back to My work through history', async ({ page }) => {
    await page.goto('/my-work');
    await loaded(page);
    await page.goto(PAGE);
    await loaded(page);
    await page.getByRole('link', { name: '← Finance' }).click();
    await expect(page).toHaveURL(/\/my-work$/);
  });

  test('← Finance opened in a fresh tab follows its href', async ({ page }) => {
    await page.goto('/my-work');
    await loaded(page);
    const [fresh] = await Promise.all([page.waitForEvent('popup'), page.evaluate((url) => window.open(url), PAGE)]);
    await loaded(fresh);
    expect(await fresh.evaluate(() => window.history.length)).toBe(1);
    await expect(fresh.getByRole('link', { name: '← Finance' })).toHaveAttribute('href', '/my-work');
    await fresh.getByRole('link', { name: '← Finance' }).click();
    await expect(fresh).toHaveURL(/\/my-work$/);
  });
});
