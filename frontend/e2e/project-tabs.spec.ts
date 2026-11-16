import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// Project tabs (SCR-38 Milestones, SCR-11 Registers, SCR-29 Actions) against the contract mock: states at 390 and 1440,
// axe WCAG 2.2 AA, the URL and the requests the page makes.
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

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

async function expectTouchTargets(targets: Locator[]) {
  for (const target of targets) {
    const box = (await target.boundingBox())!;
    expect(box.width, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
    expect(box.height, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
  }
}

/** Requests the page makes for a tab read. */
function recordTabRequests(page: Page) {
  const urls: URL[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (/^\/api\/v1\/projects\/[^/]+\/(milestones|registers|actions)$/.test(url.pathname)) urls.push(url);
  });
  return urls;
}

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
    test.beforeEach(async ({ context }) => setCookies(context, { psl_mock_persona: 'pm' }));

    for (const id of ['P-0101', 'P-0102', 'P-0106']) {
      for (const tab of ['milestones', 'registers', 'actions']) {
        test(`${id} ${tab}: one h1, named table, no sideways scroll, no axe violations`, async ({ page }) => {
          await page.goto(`/projects/${id}/${tab}`);
          await loaded(page);
          await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
          await expect(page.getByRole('tablist', { name: 'Project' })).toBeVisible();
          if (id !== 'P-0106' && !phone) await expect(page.getByRole('table')).toHaveCount(1);
          if (id !== 'P-0106' && !phone) {
            await expect(page.locator('table caption')).toHaveText(tab === 'registers' ? 'Issues' : tab === 'milestones' ? 'Milestones' : 'Actions');
          }
          if (id === 'P-0106') await expect(page.getByRole('table')).toHaveCount(0);
          expect(await noHorizontalScroll(page)).toBe(true);
          await expectNoAxeViolations(page);
        });
      }
    }

    test('milestones: the board values; the changed state keeps INVOICE and PAID; no completion control', async ({ page, context }) => {
      await page.goto('/projects/P-0101/milestones');
      await loaded(page);
      await expect(page.getByText('Done 11 Nov · client UAT sign-off').first()).toBeVisible();
      await expect(page.getByText('INV-0398').first()).toBeVisible();
      await expect(page.getByText('Part paid · ₦500,000.00 owed').first()).toBeVisible();
      await expect(page.getByRole('link', { name: /complete/i })).toHaveCount(0);
      if (!phone) await expect(page.getByRole('columnheader')).toHaveText(['MILESTONE', 'CONTRACT AMOUNT', 'COMPLETION', 'INVOICE', 'PAID']);
      await setCookies(context, { psl_mock_milestones: 'changed' });
      await page.reload();
      await loaded(page);
      await expect(page.getByText('₦4,250,000.00 + the change · change amount Unknown').first()).toBeVisible();
      if (phone) await expect(page.getByRole('link', { name: 'CHANGED · CR-0031' })).toHaveAttribute('href', '/work/W-1005');
      else {
        await expect(page.getByRole('columnheader')).toHaveText(['MILESTONE', 'CONTRACT AMOUNT', 'COMPLETION', 'INVOICE', 'PAID', 'CHANGES']);
        await expect(page.getByRole('link', { name: 'CR-0031 · SMS reminders' })).toHaveAttribute('href', '/work/W-1005');
      }
      expect(await noHorizontalScroll(page)).toBe(true);
      await expectNoAxeViolations(page);
    });

    test('registers: the register and search live in the URL; requests follow; keyboard moves along the tabs', async ({ page }) => {
      const requests = recordTabRequests(page);
      await page.goto('/projects/P-0101/registers');
      await loaded(page);
      const registers = page.getByRole('tablist', { name: 'Register' }).getByRole('tab');
      await expect(registers).toHaveText(['Issues 3', 'Changes 2', 'Emergencies 0', 'RFPs 1']);
      await expect(page.getByRole('button', { name: /filter/i })).toHaveCount(0);
      expect(requests.map((u) => u.search)).toEqual(['?limit=20&register=issues']);

      await registers.nth(0).focus();
      await page.keyboard.press('End');
      await expect(registers.nth(3)).toBeFocused();
      await page.keyboard.press('Home');
      await expect(registers.nth(0)).toBeFocused();

      await registers.nth(1).click();
      await expect(page).toHaveURL(/\/projects\/P-0101\/registers\?register=changes$/);
      await expect(page.getByText('CR-0027').first()).toBeVisible();
      expect(requests.at(-1)!.searchParams.get('register')).toBe('changes');
      expect(requests.at(-1)!.searchParams.has('cursor')).toBe(false);
      await registers.nth(0).click();
      await expect(page).toHaveURL(/\/projects\/P-0101\/registers$/);

      await page.getByRole('searchbox', { name: 'Search' }).fill('android');
      await expect(page).toHaveURL(/registers\?q=android$/);
      await expect(page.getByText('ISS-0233').first()).toBeVisible();
      await expect(page.getByText('ISS-0229')).toHaveCount(0);
      expect(requests.at(-1)!.searchParams.get('q')).toBe('android');
      await page.getByRole('searchbox', { name: 'Search' }).fill('');
      await expect(page).toHaveURL(/registers$/);
      await expect(page.getByText('ISS-0229').first()).toBeVisible();
    });

    test('registers: empty register, no match with Clear search, and paging on P-0102', async ({ page }) => {
      await page.goto('/projects/P-0101/registers?register=emergencies');
      await loaded(page);
      await expect(page.getByText('No emergencies on this project yet.')).toBeVisible();
      await expectNoAxeViolations(page);
      await page.goto('/projects/P-0101/registers?q=zzz');
      await loaded(page);
      await expect(page.getByText('No issues match “zzz”.')).toBeVisible();
      await page.locator('.psl-empty').getByRole('button', { name: 'Clear search' }).click();
      await expect(page).toHaveURL(/registers$/);
      await expect(page.getByText('ISS-0233').first()).toBeVisible();

      const requests = recordTabRequests(page);
      await page.goto('/projects/P-0102/registers');
      await loaded(page);
      const more = page.getByRole('button', { name: 'Show more' });
      await expect(more).toBeVisible();
      await expect(page.getByText('20 showing')).toBeVisible();
      if (phone) await expectTouchTargets([more]);
      await more.click();
      await expect(page.getByText('ISS-1025').first()).toBeAttached();
      expect(requests.at(-1)!.searchParams.get('cursor')).toBe('o20');
      expect(page.url()).not.toContain('cursor');
      await expect(page.getByRole('button', { name: 'Show more' })).toHaveCount(0);
      await expect(page.locator(':focus')).not.toHaveCount(0);
      expect(await noHorizontalScroll(page)).toBe(true);
      await expectNoAxeViolations(page);
    });

    test('actions: header counts, search, footer', async ({ page }) => {
      await page.goto('/projects/P-0101/actions');
      await loaded(page);
      await expect(page.locator('.psl-resultcount')).toHaveText('9 ACTIONS · 3 OVERDUE · 1 WITHOUT OWNER');
      await expect(page.getByText('Actions come from confirmed minutes.')).toBeVisible({ visible: !phone });
      await expect(page.getByText('Assess the SMS reminders change').first()).toBeVisible();
      await expect(page.getByText('Unknown').first()).toBeVisible();
      await page.getByRole('searchbox', { name: 'Search' }).fill('sign');
      await expect(page).toHaveURL(/actions\?q=sign$/);
      await expect(page.getByText('Sign UAT plan').first()).toBeVisible();
      if (phone) {
        await expectTouchTargets([page.getByRole('searchbox', { name: 'Search' }), ...(await page.getByRole('tab').all())]);
      }
    });

    test('P-0103: the tab answers 403; the header stays and no fixture text shows', async ({ page }) => {
      await page.goto('/projects/P-0103/milestones');
      await loaded(page);
      await expect(page.getByRole('heading', { level: 2, name: 'No access to this tab' })).toBeVisible();
      await expect(page.getByRole('tablist', { name: 'Project' })).toBeVisible();
      await expect(page.getByText('Kick-off')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    test('a tab read that fails shows the error card and Try again sends one new request', async ({ page }) => {
      let fail = true;
      await page.route('**/api/v1/projects/P-0101/actions*', (route) =>
        fail ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"x"}' }) : route.continue(),
      );
      const requests = recordTabRequests(page);
      await page.goto('/projects/P-0101/actions');
      await expect(page.getByRole('main').getByRole('alert')).toContainText('We couldn’t load this tab. Your work is safe; nothing was changed.');
      expect(requests).toHaveLength(1);
      fail = false;
      await page.getByRole('button', { name: 'Try again' }).click();
      await expect(page.getByText('Send test accounts for UAT').first()).toBeVisible();
      expect(requests).toHaveLength(2);
    });
  });
}
