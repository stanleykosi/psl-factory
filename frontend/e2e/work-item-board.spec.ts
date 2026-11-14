import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

// F-14: the SCR-02 board fixtures at 1440 and 390, signed in as each board's persona.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const PAGES: [string, string][] = [
  ['/work/W-1701', 'finance_lead'],
  ['/work/W-1702', 'pm'],
  ['/work/W-1703', 'pm'],
  ['/work/W-1704', 'pm'],
  ['/work/W-1705', 'finance_lead'],
  ['/work/W-1705/history', 'finance_lead'],
  ['/work/W-1706', 'finance_lead'],
  ['/work/W-1707', 'finance_lead'],
  ['/work/W-1708', 'pm'],
  ['/work/W-1709', 'pm'],
  ['/work/W-1710', 'finance_lead'],
  ['/work/W-1711', 'finance_lead'],
  ['/work/W-1099', 'finance_lead'],
];

test.use({ timezoneId: 'Africa/Lagos' });

async function loaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
}

async function go(page: Page, path: string, persona: string) {
  await page.context().addCookies([{ name: 'psl_mock_persona', value: persona, domain: 'localhost', path: '/' }]);
  await page.goto(path);
  await loaded(page);
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

/** Tabs forward until the target has keyboard focus, then returns its outline. */
async function tabTo(page: Page, target: Locator) {
  for (let i = 0; i < 80; i++) {
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
const ring = { style: 'solid', width: '2px' };

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    for (const [path, persona] of PAGES) {
      test(`${path} has no axe violations, no sideways scroll and one h1`, async ({ page }) => {
        await go(page, path, persona);
        await expect(page).toHaveTitle('Work item · PSL Factory');
        await expectNoAxeViolations(page);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
        await expect(page.locator('h1')).toHaveCount(1);
        const size = await page.locator('main h1').evaluate((el) => getComputedStyle(el).fontSize);
        const phoneSize = path.endsWith('/history') ? '20px' : path === '/work/W-1099' ? '24px' : '22px';
        expect(size).toBe(viewport === DESKTOP ? (path === '/work/W-1099' ? '33px' : '40px') : phoneSize);
        expect(await page.locator('main h1').evaluate((el) => el.classList.contains('shell-title'))).toBe(true);
      });
    }
  });
}

test.describe('phone back link (AC 4)', () => {
  test.use({ viewport: PHONE });

  for (const [path, label, href] of [
    ['/work/W-1701', 'Queue', '/my-work'],
    ['/work/W-1099', 'Queue', '/my-work'],
    ['/work/W-1705/history', 'Invoice', '/work/W-1705'],
    ['/work/W-1004/history', 'Work item', '/work/W-1004'],
  ] as const) {
    test(`${path}: "← ${label}" in the phone bar, none in main`, async ({ page }) => {
      await go(page, path, 'finance_lead');
      const back = page.locator('header.psl-phonebar').getByRole('link', { name: `Back to ${label}` });
      await expect(back).toHaveText(`← ${label}`);
      await expect(back).toHaveAttribute('href', href);
      await expect(page.locator('header.psl-phonebar').getByRole('button', { name: 'Menu' })).toHaveCount(0);
      await expect(page.locator('main').getByRole('link', { name: /^←/ })).toHaveCount(0);
    });
  }

  test('while the item loads the bar already shows "← Queue"', async ({ page }) => {
    await page.context().addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', domain: 'localhost', path: '/' }]);
    await page.route('**/api/v1/work/W-1701', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await route.continue();
    });
    await page.goto('/work/W-1701');
    await expect(page.getByRole('status')).toBeVisible();
    await expect(page.locator('header.psl-phonebar').getByRole('link', { name: 'Back to Queue' })).toBeVisible();
  });

  test('at 1440 the phone bar is not shown', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await go(page, '/work/W-1701', 'finance_lead');
    await expect(page.locator('header.psl-phonebar')).toBeHidden();
  });
});

test.describe('focus outlines (AC 20)', () => {
  test('desktop: tabs, panel link, filter and history controls', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await go(page, '/work/W-1705', 'finance_lead');
    expect(await tabTo(page, page.getByRole('link', { name: 'See in Verified outputs' }))).toEqual(ring);
    await go(page, '/work/W-1705/history', 'finance_lead');
    expect(await tabTo(page, page.getByRole('navigation', { name: 'Work item' }).getByRole('link', { name: 'Overview' }))).toEqual(ring);
    expect(await tabTo(page, page.getByRole('radio', { name: 'All 7' }))).toEqual(ring);
    expect(await tabTo(page, page.getByLabel('Rows per page'))).toEqual(ring);
  });

  test('phone: the disclosures show a ring and toggle', async ({ page }) => {
    await page.setViewportSize(PHONE);
    await go(page, '/work/W-1701', 'finance_lead');
    const steps = page.getByRole('button', { name: 'See his steps' });
    expect(await tabTo(page, steps)).toEqual(ring);
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: 'Hide his steps' })).toHaveAttribute('aria-expanded', 'true');
    await go(page, '/work/W-1706', 'finance_lead');
    const preview = page.getByRole('button', { name: 'Preview the invoice' });
    expect(await tabTo(page, preview)).toEqual(ring);
    await page.keyboard.press('Enter');
    await expect(page.getByRole('article', { name: 'Invoice preview' })).toBeVisible();
    await expectNoAxeViolations(page);
  });
});

test.describe('agent step motion (AC 20)', () => {
  for (const viewport of [DESKTOP, PHONE]) {
    test(`W-1703 at ${viewport.width}: no animation on the current step with reduced motion`, async ({ browser }) => {
      const context = await browser.newContext({ reducedMotion: 'reduce', viewport, timezoneId: 'Africa/Lagos' });
      await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', domain: 'localhost', path: '/' }]);
      const page = await context.newPage();
      await page.goto('/work/W-1703');
      await loaded(page);
      const box = page.locator('.psl-step--now .psl-step__box').first();
      expect(await box.evaluate((el) => getComputedStyle(el).animationName)).toBe('none');
      await context.close();
    });
  }
});

test.describe('history on the boards (AC 18)', () => {
  test('W-1705 at 1440: History 7, the filter counts, 7 rows and About history', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await go(page, '/work/W-1705/history', 'finance_lead');
    await expect(page.getByRole('navigation', { name: 'Work item' }).getByRole('link')).toHaveText(['Overview', 'History 7']);
    await expect(page.getByRole('radio')).toHaveText(['All 7', 'Decisions 2', 'Agent work 2', 'Evidence 1']);
    await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(7);
    await expect(page.getByRole('table').locator('tbody tr').first().locator('time')).toHaveText('12 Nov 16:40');
    await expect(page.getByRole('complementary', { name: 'About history' })).toBeVisible();
  });

  test('W-1705 at 390: HISTORY eyebrow, title and stacked entries', async ({ page }) => {
    await page.setViewportSize(PHONE);
    await go(page, '/work/W-1705/history', 'finance_lead');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('History · INV-0412');
    await expect(page.locator('main').getByText('HISTORY', { exact: true })).toBeVisible();
    // the phone board lists the five newest entries; "+ 2 earlier entries" shows the rest in place
    const cards = page.getByRole('list', { name: 'History, newest first' }).getByRole('listitem');
    await expect(cards).toHaveCount(5);
    await page.getByRole('button', { name: '+ 2 earlier entries' }).click();
    await expect(cards).toHaveCount(7);
  });
});

