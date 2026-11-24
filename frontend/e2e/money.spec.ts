import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// F-71 Money tab (SCR-12), on the live money read, against the contract mock at 390 and 1440, axe WCAG 2.2 AA. Every request the page makes
// goes to the app's /api/v1, which the app proxies to the mock (MOCK_PORT); nothing reaches a real backend.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const panel = (page: Page) => page.getByRole('tabpanel', { name: 'Money' });
const rows = (page: Page) => panel(page).locator('tbody tr');
const cards = (page: Page) => panel(page).locator('.money__card');

/** Records every request the page makes to an API path. */
function apiCalls(page: Page) {
  const seen: URL[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/')) seen.push(url);
  });
  return seen;
}

async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.locator('.psl-loading')).toHaveCount(0);
}

async function expectTouchTargets(targets: Locator[]) {
  for (const target of targets) {
    const box = (await target.boundingBox())!;
    expect(box.height, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
    expect(box.width, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
  }
}

test.beforeEach(async ({ context }) => {
  await setCookies(context, { psl_mock_persona: 'finance_lead' });
});

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;
  const w = viewport.width;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    test('P-0101 rows from data: stages in the order sent, amounts with the currency code, invoices, paid and owed, the time', async ({ page }) => {
      const calls = apiCalls(page);
      await page.goto('/projects/P-0101/money');
      await loaded(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Lagoon Health · patient app');
      if (phone) {
        await expect(cards(page)).toHaveCount(5);
        await expect(cards(page).locator('.money__stage')).toHaveText(['1 · Kick-off', '2 · UAT sign-off', '3 · Go-live', 'Hypercare', 'INV-0420 outside any stage']);
        await expect(cards(page).nth(2)).toContainText('The reviewed stage terms do not state an amount.');
        const hint = panel(page).getByText('Tap an amount to see where it comes from');
        await expect(hint).toBeVisible();
        await expect(page.getByRole('complementary')).toHaveCount(0);
        await expectTouchTargets([...(await cards(page).locator('a').all())]);
      } else {
        await expect(rows(page)).toHaveCount(5);
        await expect(panel(page).locator('tfoot')).toHaveCount(0);
        await expect(rows(page).locator('td:nth-child(1)')).toHaveText(['1 · Kick-off', '2 · UAT sign-off', '3 · Go-live', 'Hypercare', 'INV-0420 outside any stage']);
        await expect(rows(page).locator('td:nth-child(2)')).toHaveText(['NGN 3,000,000.00', 'NGN 4,250,000.00', 'UnknownThe reviewed stage terms do not state an amount.', 'NGN 500,000.00', 'USD 1,000.00']);
        await expect(rows(page).nth(0).locator('td:nth-child(3) .money__block')).toHaveText(['INV-0398 · Delivered', 'INV-0399 · Issued']);
        await expect(rows(page).nth(1).locator('td:nth-child(4)')).toHaveText('Paid Unknown · Owed Unknown');
        await expect(page.getByRole('complementary', { name: 'Choose an amount to see where it comes from.' })).toBeVisible();
      }
      await expect(panel(page).locator('.money__asof')).toHaveText('As of 12 Nov 16:40');
      const text = await panel(page).innerText();
      expect(text).not.toMatch(/total|outstanding|balance|part paid|not paid/i);
      expect(await noHorizontalScroll(page)).toBe(true);
      const port = new URL(page.url()).port;
      expect(calls.map((u) => `${u.host}${u.pathname}`)).toContain(`localhost:${port}/api/v1/projects/00000000-0000-4000-8000-000000000101/money`);
      expect(calls.every((u) => u.host === new URL(page.url()).host)).toBe(true);
      await shot(page, `money-default-${w}`);
      await expectNoAxeViolations(page);
    });

    test('deep link ?figure=kickoff lists its sources in order; a reload keeps it', async ({ page }) => {
      await page.goto('/projects/P-0101/money?figure=kickoff');
      await loaded(page);
      const surface = phone ? page.getByRole('dialog', { name: 'Kick-off' }) : page.getByRole('complementary', { name: 'Kick-off' });
      await expect(surface).toBeVisible();
      await expect(surface.locator('ol > li')).toHaveCount(2);
      await expect(surface.locator('ol > li').first()).toContainText('Statement of work SOW-0198 v2 · Signed SOW');
      await expect(surface.locator('ol a')).toHaveCount(0);
      if (!phone) await shot(page, `money-figure-${w}`);
      await page.reload();
      await loaded(page);
      await expect(surface).toBeVisible();
      await expect(surface.locator('ol > li')).toHaveCount(2);
      if (phone) await shot(page, `money-sheet-${w}`);
      await expectNoAxeViolations(page);
    });

    test('limited, empty, unknown figure and no-money-access pass axe with no sideways scroll', async ({ page }) => {
      for (const path of ['/projects/P-0102/money', '/projects/P-0106/money', '/projects/P-0101/money?figure=nope', '/projects/P-0107/money', '/projects/P-0108/money']) {
        await page.goto(path);
        await loaded(page);
        if (path.includes('P-0102')) await expect(page.getByText('Some figures may be incomplete.')).toBeVisible();
        if (path.includes('P-0106')) await expect(panel(page).getByRole('heading', { level: 2, name: 'No contract stages yet' })).toBeVisible();
        if (path.includes('nope')) await expect(page.getByText('That figure isn’t available.')).toBeVisible();
        if (/P-010[78]/.test(path)) {
          await expect(panel(page).getByText('You can’t see this project’s money.')).toBeVisible();
          const text = await page.locator('body').innerText();
          for (const word of ['Kick-off', 'NGN', 'Your role does not allow this', 'We could not find that record']) expect(text).not.toContain(word);
        }
        expect(await noHorizontalScroll(page), path).toBe(true);
        await expectNoAxeViolations(page);
        if (path.includes('nope') && phone) await page.keyboard.press('Escape');
      }
    });

    test('pm on P-0104 and P-0099: the project is refused and no money is read', async ({ page, context }) => {
      const calls = apiCalls(page);
      await setCookies(context, { psl_mock_persona: 'pm' });
      for (const id of ['P-0104', 'P-0099']) {
        await page.goto(`/projects/${id}/money`);
        await loaded(page);
        await expect(page.getByText('You can’t open this project')).toBeVisible();
        expect(await page.locator('body').innerText()).not.toContain('NGN');
      }
      expect(calls.filter((u) => /\/money$/.test(u.pathname))).toEqual([]);
    });

    test('a failed money read shows the error card and Try again makes exactly one more money request', async ({ page }) => {
      let fail = true;
      await page.route('**/api/v1/projects/00000000-0000-4000-8000-000000000101/money*', (route) =>
        fail ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"x"}' }) : route.continue(),
      );
      const calls = apiCalls(page);
      await page.goto('/projects/P-0101/money');
      await expect(page.getByRole('main').getByRole('alert')).toContainText('We couldn’t load this project’s money.');
      fail = false;
      const before = calls.filter((u) => u.pathname.endsWith('/money')).length;
      await page.getByRole('button', { name: 'Try again' }).click();
      await expect(rows(page).or(cards(page)).first()).toBeVisible();
      expect(calls.filter((u) => u.pathname.endsWith('/money')).length).toBe(before + 1);
    });

    if (!phone) {
      test('press Hypercare: the URL is replaced, the aside shows its sources, focus and aria-current stay, it is announced', async ({ page }) => {
        await page.goto('/projects/P-0101/money?figure=kickoff');
        await loaded(page);
        const entries = await page.evaluate(() => window.history.length);
        const link = rows(page).nth(3).getByRole('link', { name: 'NGN 500,000.00' });
        await link.click();
        await expect(page).toHaveURL(/\/projects\/P-0101\/money\?figure=hypercare$/);
        expect(await page.evaluate(() => window.history.length)).toBe(entries);
        await expect(page.getByRole('complementary', { name: 'Hypercare' }).locator('ol > li')).toHaveCount(1);
        await expect(link).toBeFocused();
        await expect(link).toHaveAttribute('aria-current', 'true');
        await expect(panel(page).locator('[aria-live="polite"]')).toHaveText('Showing where Hypercare comes from');
        await expectNoAxeViolations(page);
      });
    } else {
      test('press Kick-off: a bottom sheet with its sources; Esc and Close drop figure and return focus', async ({ page }) => {
        await page.goto('/projects/P-0101/money');
        await loaded(page);
        const amount = cards(page).nth(0).getByRole('link', { name: 'NGN 3,000,000.00' });
        await amount.click();
        const sheet = page.getByRole('dialog', { name: 'Kick-off' });
        await expect(sheet).toBeVisible();
        await expect(page).toHaveURL(/\?figure=kickoff$/);
        await expectNoAxeViolations(page);
        await page.keyboard.press('Escape');
        await expect(sheet).toHaveCount(0);
        await expect(page).toHaveURL(/\/projects\/P-0101\/money$/);
        await expect(amount).toBeFocused();
        await amount.click();
        await expect(sheet).toBeVisible();
        await sheet.getByRole('button', { name: 'Close' }).click();
        await expect(sheet).toHaveCount(0);
        await expect(amount).toBeFocused();
      });
    }
  });
}
