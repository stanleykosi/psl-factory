import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// All exceptions (SCR-10) against the contract mock: default, empty, no-access, signed-out and error at 390 and 1440.
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

/** The h1 reads "All exceptions" on desktop and "Exceptions · N" on phones (SCR-10-mobile). */
async function loaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: /^(All exceptions|Exceptions( · \d+)?)$/ })).toBeVisible();
}

/** The scenario header on the list request only, so /me still loads and the page itself answers the status. */
async function scenarioOnList(page: Page, status: string) {
  await page.route('**/api/v1/exceptions*', (route) =>
    route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': status } }),
  );
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

const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });
const scrollWidth = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth);
const FOOTER = 'The factory never resends after an unknown outcome until it has checked for a receipt. Nothing here is lost; each item resumes where it stopped.';

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('default list: header, search bar, columns, 20 rows in order, paging bar, footer; Show more gives 25', async ({ page }) => {
    await page.goto('/exceptions');
    await loaded(page);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('All exceptions');
    await expect(page.getByRole('searchbox', { name: 'Search' })).toHaveAttribute('placeholder', 'Search exceptions');
    await expect(page.getByRole('button', { name: 'Filter' })).toBeVisible();
    await expect(page.getByText('25 OPEN')).toBeVisible();
    await expect(page).toHaveTitle('All exceptions · PSL Factory');
    await expect(page.getByText(/^Everyone’s work that can’t move on by itself, across every line you can see/)).toBeVisible();
    const table = page.getByRole('table', { name: 'Exceptions, in the order the factory reports them' });
    await expect(table.getByRole('columnheader')).toHaveText(['WHAT HAPPENED', 'WORK', 'WHAT’S BEING DONE', 'WHO ACTS']);
    const rows = table.locator('tbody tr');
    await expect(rows).toHaveCount(20);
    await expect(rows.first().locator('.psl-tag')).toHaveText('SEND UNCERTAIN');
    await expect(rows.first().locator('time')).toHaveText('since 11:02');
    await expect(rows.first().getByRole('link')).toHaveAttribute('href', '/work/W-1005');
    await expect(rows.first().getByRole('link')).toHaveCSS('text-decoration-line', 'none');
    await expect(rows.first().getByRole('link')).toHaveCSS('color', 'rgb(31, 36, 39)');
    await expect(rows.first().locator('.exc-ref')).toHaveText('INV-0405');
    await expect(page.getByText('Showing 20')).toBeVisible();
    await expect(page.getByRole('radio', { name: '20' })).toHaveAttribute('aria-checked', 'true');
    await expect(page.getByText('As of 14 Nov 11:05')).toBeVisible();
    await expect(page.getByText(FOOTER)).toBeVisible();
    await shot(page, 'exceptions-desktop-default');
    await expectNoAxeViolations(page);

    const ring = { style: 'solid', width: '2px' };
    expect(await tabTo(page, rows.first().getByRole('link'))).toEqual(ring);
    const more = page.getByRole('button', { name: 'Show more' });
    expect(await tabTo(page, more)).toEqual(ring);
    await page.keyboard.press('Enter');
    await expect(rows).toHaveCount(25);
    await expect(more).toHaveCount(0);
    await expect(page.getByText('Showing 25')).toBeVisible();
    expect(await scrollWidth(page)).toBeLessThanOrEqual(DESKTOP.width);
  });

  test('search and Filter narrow the list through the API; the narrowed empty state clears both', async ({ page }) => {
    await page.goto('/exceptions');
    await loaded(page);
    const rows = page.getByRole('table').locator('tbody tr');
    await page.getByRole('searchbox', { name: 'Search' }).fill('Kora');
    await expect(rows).toHaveCount(3);
    await expect(page.getByText('3 OPEN')).toBeVisible();
    await page.getByRole('button', { name: 'Filter' }).click();
    const dialog = page.getByRole('dialog', { name: 'Filter' });
    await expect(dialog).toBeVisible();
    await expectNoAxeViolations(page);
    await dialog.getByRole('radio', { name: 'Follow-up needed' }).check();
    await dialog.getByRole('button', { name: 'Show results' }).click();
    await expect(rows).toHaveCount(1);
    await expect(rows.first().locator('.psl-tag')).toHaveText('FOLLOW-UP NEEDED');
    await expect(page.getByText('1 OPEN')).toBeVisible();
    await page.getByRole('searchbox', { name: 'Search' }).fill('Sable');
    await expect(page.getByRole('heading', { level: 2, name: 'No exceptions match your search and filter.' })).toBeVisible();
    await page.getByRole('button', { name: 'Clear search and filter' }).click();
    await expect(rows).toHaveCount(20);
    await expect(page.getByText('25 OPEN')).toBeVisible();
  });

  test('rows open their own work item', async ({ page }) => {
    await page.goto('/exceptions');
    await loaded(page);
    await page.getByRole('link', { name: 'Kora Logistics · Milestone 1 invoice' }).click();
    await expect(page).toHaveURL(/\/work\/W-1005$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Kora Logistics · Milestone 1 invoice');
    await expect(page.getByRole('link', { name: 'See all exceptions' })).toHaveAttribute('href', '/exceptions');

    await page.goto('/exceptions');
    await loaded(page);
    await page.getByRole('link', { name: 'Northwind Clinics · Weekly client update' }).click();
    await expect(page).toHaveURL(/\/work\/W-1503$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Northwind Clinics · Weekly client update');
    await expect(page.getByRole('link', { name: 'See all exceptions' })).toBeVisible();
    await expectNoAxeViolations(page);
  });

  test('the work item link shows only for exception states', async ({ page }) => {
    for (const [id, shown] of [
      ['W-1005', 1],
      ['W-1003', 0],
      ['W-1006', 0],
    ] as const) {
      await page.goto(`/work/${id}`);
      await expect(page.getByRole('status')).toHaveCount(0);
      await expect(page.locator('main#main h1')).toBeVisible();
      await expect(page.getByRole('link', { name: 'See all exceptions' })).toHaveCount(shown);
    }
  });

  test('signed out (cookie 401) shows the sign-in link back to /exceptions', async ({ page, context }) => {
    await setCookies(context, { psl_mock_scenario: '401' });
    await page.goto('/exceptions');
    await expect(page.getByText('You’re signed out.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/accounts/login/?next=%2Fexceptions');
  });

  test('a 401 on the list itself shows the signed-out state inside the page', async ({ page }) => {
    await scenarioOnList(page, '401');
    await page.goto('/exceptions');
    await loaded(page);
    await expect(page.getByText('You’re signed out.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/accounts/login/?next=%2Fexceptions');
  });

  test('a 503 shows the error card; Try again loads the list', async ({ page }) => {
    let fail = true;
    await page.route('**/api/v1/exceptions*', (route) =>
      fail ? route.fulfill({ status: 503, contentType: 'application/json', body: '{"code":"unavailable","message":"Down."}' }) : route.continue(),
    );
    await page.goto('/exceptions');
    await loaded(page);
    await expect(page.getByText('ERROR · COULDN’T LOAD')).toBeVisible();
    await expect(page.getByText('We couldn’t load the exceptions. Your work is safe; nothing was changed.')).toBeVisible();
    await expect(page.getByText('Reference unavailable for support.')).toBeVisible();
    await expectNoAxeViolations(page);
    fail = false;
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(20);
  });
});

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('empty (cookie psl_mock_exceptions=empty)', async ({ page, context }) => {
      await setCookies(context, { psl_mock_exceptions: 'empty' });
      await page.goto('/exceptions');
      await loaded(page);
      await expect(page.getByRole('heading', { level: 2, name: 'No exceptions.' })).toBeVisible();
      await expect(page.getByText('Everything is moving or verified.')).toBeVisible();
      await expect(page.getByText('As of 14 Nov 11:05')).toBeVisible();
      await expect(page.getByRole('table')).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Show more' })).toHaveCount(0);
      await expect(page.getByText(FOOTER)).toHaveCount(0);
      await shot(page, `exceptions-${viewport.width}-empty`);
      await expectNoAxeViolations(page);
      expect(await scrollWidth(page)).toBeLessThanOrEqual(viewport.width);
    });

    for (const [how, setup] of [
      ['persona pm', (page: Page, context: BrowserContext) => setCookies(context, { psl_mock_persona: 'pm' }).then(() => page)],
      ['a 404', (page: Page) => scenarioOnList(page, '404').then(() => page)],
    ] as const) {
      test(`no access for ${how}: no rows, count or As of`, async ({ page, context }) => {
        await setup(page, context);
        await page.goto('/exceptions');
        await loaded(page);
        await expect(page.getByRole('heading', { level: 2, name: 'This list is for Leads' })).toBeVisible();
        await expect(page.getByText('Your own exceptions appear in My work, under Needs me.')).toBeVisible();
        await expect(page.getByRole('link', { name: 'Go to My work' })).toHaveAttribute('href', '/my-work');
        const main = (await page.locator('main').textContent()) ?? '';
        expect(main).not.toMatch(/shown|As of|Kora Logistics|W-1005/);
        await shot(page, `exceptions-${viewport.width}-noaccess-${how.replace(/\s/g, '-')}`);
        await expectNoAxeViolations(page);
        expect(await scrollWidth(page)).toBeLessThanOrEqual(viewport.width);
      });
    }
  });
}

test.describe('phone 390', () => {
  test.use({ viewport: PHONE });

  test('rows are cards with no sideways scroll; Show more is at least 44px tall', async ({ page }) => {
    await page.goto('/exceptions');
    await loaded(page);
    await expect(page.getByRole('table')).toHaveCount(0);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Exceptions · 25');
    await expect(page.getByRole('link', { name: '← Queue' })).toHaveAttribute('href', '/my-work');
    await expect(page.getByRole('searchbox', { name: 'Search' })).toBeVisible();
    expect((await page.getByRole('button', { name: 'Filter' }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
    const cards = page.getByRole('list', { name: 'Exceptions, in the order the factory reports them' }).getByRole('listitem');
    await expect(cards).toHaveCount(20);
    const first = cards.first();
    await expect(first.locator('.psl-tag')).toHaveText('SEND UNCERTAIN');
    await expect(first.getByRole('link')).toHaveText('Kora Logistics · Milestone 1 invoice');
    await expect(first).toContainText('Chidi is checking for a delivery receipt by reference. Nothing resent.');
    expect(await scrollWidth(page)).toBeLessThanOrEqual(390);
    const more = page.getByRole('button', { name: 'Show more' });
    expect((await more.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await shot(page, 'exceptions-390-default');
    await expectNoAxeViolations(page);
    const ring = { style: 'solid', width: '2px' };
    expect(await tabTo(page, first.getByRole('link'))).toEqual(ring);
    // The title link covers the whole card: a tap on the card's text opens the item.
    await more.click();
    await expect(cards).toHaveCount(25);
    await expect(more).toHaveCount(0);
    expect(await scrollWidth(page)).toBeLessThanOrEqual(390);
  });

  test('tapping a card anywhere opens its work item', async ({ page }) => {
    await page.goto('/exceptions');
    await loaded(page);
    // A real tap on the card's text: the title link's overlay takes it (Playwright's own click refuses a covered target).
    const box = (await page.getByText('Waiting for an update template for this client.').boundingBox())!;
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await expect(page).toHaveURL(/\/work\/W-1503$/);
  });

  test('Try again is at least 44px tall', async ({ page }) => {
    await page.route('**/api/v1/exceptions*', (route) => route.abort());
    await page.goto('/exceptions');
    await loaded(page);
    const retry = page.getByRole('button', { name: 'Try again' });
    await expect(retry).toBeVisible();
    expect((await retry.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await scrollWidth(page)).toBeLessThanOrEqual(390);
    await expectNoAxeViolations(page);
  });
});
