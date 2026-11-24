import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Response } from '@playwright/test';

// Overview (SCR-06) against the contract mock (live GET /overview and GET /work/counts): flat and 3D floor at 1440, flat at 390, axe WCAG 2.2 AA.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const TITLES = ['Costing and commercial submission', 'RFP response and project handoff', 'Invoice preparation and delivery', 'Formal minutes and action handoff', 'A line added later'];

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

const main = (page: Page) => page.getByRole('main');
const rows = (page: Page) => page.locator('section[aria-label="Lines"] .overview__lines-of > .overview__row');
const tiles = (page: Page) => page.locator('dl.overview__totals > div');
const viewSwitch = (page: Page) => page.getByRole('radiogroup', { name: 'View' });
// A full-page capture briefly narrows the window, which (correctly) drops the 3D floor; the 3D shot is the viewport only.
const shot = (page: Page, name: string, fullPage = true) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

async function loaded(page: Page) {
  await expect(page.getByRole('heading', { level: 1, name: 'Factory floor' })).toBeVisible();
  await expect(page.getByText('Loading…')).toHaveCount(0);
}

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('default flat: four totals, floors and lines with squares, View switch, exceptions link', async ({ page }) => {
    const notFound: string[] = [];
    page.on('response', (r) => {
      if (r.status() >= 400) notFound.push(`${r.status()} ${r.url()}`);
    });
    await page.goto('/overview');
    await loaded(page);
    await expect(page).toHaveTitle('Overview · PSL Factory');
    await expect(main(page).getByText('FACTORY FLOOR · UPDATED 23 Nov 10:30 WAT')).toBeVisible();
    await expect(tiles(page)).toHaveText(['IN PROGRESS10', 'NEED A PERSON4', 'STOPPED1', 'VERIFIED THIS MONTH3Nov 2026']);
    await expect(main(page).getByText('Counted from all 15 items you can see')).toBeVisible();
    await expect(rows(page).locator('.overview__name')).toHaveText(TITLES);
    await expect(rows(page).locator('.psl-tag')).toHaveText(Array(5).fill('Not available yet'));
    await expect(page.getByRole('list', { name: 'Costing and commercial submission stations' }).getByRole('listitem')).toHaveCount(5);
    await expect(page.getByRole('link', { name: /Open work · Costing/ })).toHaveAttribute('href', '/my-work?line=commercial%2Fv1');
    await expect(page.getByRole('radio', { name: 'Flat' })).toHaveAttribute('aria-checked', 'true');
    await expect(main(page).getByRole('link', { name: 'See all exceptions' })).toHaveAttribute('href', '/exceptions');
    const avatar = page.locator('.overview__row--floor img.psl-avatar--tola').first();
    await expect(avatar).toBeVisible();
    expect(await avatar.evaluate((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth)).toBe(192);
    await expect(page.getByText(/can’t show the 3D floor/)).toHaveCount(0);
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'overview-1440');
    await page.waitForTimeout(1000);
    expect(notFound).toEqual([]);
    await expectNoAxeViolations(page);
  });

  test('limited counts read "at least N"; counts that fail leave the rows and say so', async ({ page, context }) => {
    await setCookies(context, { psl_mock_overview: 'limited' });
    await page.goto('/overview');
    await loaded(page);
    await expect(tiles(page).locator('dd')).toHaveText(['at least 10', 'at least 4', 'at least 1', 'at least 3']);
    await expect(main(page).getByText('Counted from the 50 most recent items you can see')).toBeVisible();
    await setCookies(context, { psl_mock_overview: 'no-counts' });
    await page.reload();
    await loaded(page);
    await expect(main(page).getByText('Totals are not available yet.')).toBeVisible();
    await expect(rows(page)).toHaveCount(5);
    await expect(page.locator('.overview__unknown')).toHaveCount(5);
    await expectNoAxeViolations(page);
  });

  test('empty lines: the empty message, no totals, no View switch, the exceptions link', async ({ page, context }) => {
    await setCookies(context, { psl_mock_overview: 'empty' });
    await page.goto('/overview');
    await loaded(page);
    await expect(tiles(page)).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'No lines to show yet.' })).toBeVisible();
    await expect(viewSwitch(page)).toHaveCount(0);
    await expect(main(page).getByRole('link', { name: 'See all exceptions' })).toBeVisible();
    await expectNoAxeViolations(page);
  });

  test('403 from /overview: the floor is not open to you, with the server message', async ({ page }) => {
    await page.route('**/api/v1/overview', (route) =>
      route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'Your role does not allow this.' }) }),
    );
    await page.goto('/overview');
    await expect(page.getByRole('heading', { name: 'The factory floor isn’t open to you.' })).toBeVisible();
    await expect(main(page).getByText('Your role does not allow this.')).toBeVisible();
    await expect(page.locator('dl')).toHaveCount(0);
    await expectNoAxeViolations(page);
  });

  test('no WebGL: no View switch, the device hint, every line and square', async ({ page }) => {
    await page.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, type: string, ...rest: unknown[]) {
        if (type === 'webgl' || type === 'webgl2') return null;
        return (original as (...a: unknown[]) => unknown).call(this, type, ...rest);
      } as typeof original;
    });
    await page.goto('/overview');
    await loaded(page);
    await expect(viewSwitch(page)).toHaveCount(0);
    await expect(page.getByText('This device can’t show the 3D floor, so it’s shown flat.')).toBeVisible();
    await expect(rows(page)).toHaveCount(5);
    await expect(page.locator('.overview__station')).toHaveCount(25);
    await expectNoAxeViolations(page);
  });

  test('reduced motion: flat with the motion hint and no 3D option', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/overview');
    await loaded(page);
    await expect(page.getByText('Motion is turned down on this device, so the floor is shown flat.')).toBeVisible();
    await expect(page.getByRole('radio', { name: '3D floor' })).toHaveCount(0);
    await expect(rows(page)).toHaveCount(5);
    await expectNoAxeViolations(page);
  });

  test('three.js loads only after 3D floor is chosen', async ({ page }) => {
    const scripts: Promise<string>[] = [];
    const collect = (response: Response) => {
      if (response.request().resourceType() === 'script') scripts.push(response.text().catch(() => ''));
    };
    page.on('response', collect);
    await page.goto('/overview');
    await loaded(page);
    await page.waitForLoadState('load');
    await page.waitForTimeout(500);
    const first = await Promise.all(scripts.splice(0));
    expect(first.length).toBeGreaterThan(0);
    expect(first.filter((text) => text.includes('__THREE__'))).toHaveLength(0);
    await page.getByRole('radio', { name: '3D floor' }).click();
    await expect(page.locator('canvas[role="img"]')).toBeVisible();
    const later = await Promise.all(scripts.splice(0));
    expect(later.some((text) => text.includes('__THREE__'))).toBe(true);
  });

  test('3D floor: a label per station for lines with counts, PERSON only where a person is needed, the strip links into the queue', async ({ page }) => {
    test.setTimeout(60_000);
    await page.goto('/overview');
    await loaded(page);
    await page.getByRole('radio', { name: '3D floor' }).click();
    await expect(page.getByRole('img', { name: /^3D factory floor: 5 lines/ })).toBeVisible();
    await expect(page.locator('.floor__line strong')).toHaveText(TITLES);
    // five lines, each with five stations (the line the sample does not reach is a known 0 here)
    await expect(page.locator('.floor__chip')).toHaveCount(25);
    await expect(page.locator('.floor__chip--person')).toHaveCount(3);
    const decision = page.getByRole('button', { name: '1 Decision PERSON. Costing and commercial submission · Decision · 1 item · needs a person' });
    await decision.hover();
    const strip = page.locator('.floor__strip');
    await expect(strip.locator('.floor__headline')).toContainText('Costing and commercial submission · Decision');
    await expect(strip.locator('.floor__headline')).toContainText('1 item, 2 need a person');
    await expect(strip.getByRole('link', { name: 'Open work' })).toHaveAttribute('href', '/my-work?line=commercial%2Fv1');
    await decision.click();
    await expect(strip.getByText('Pinned')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(strip.getByText('Pinned')).toHaveCount(0);
    await shot(page, 'overview-3d-1440', false);
    await expectNoAxeViolations(page);
    await page.getByRole('radio', { name: 'Flat' }).click();
    await expect(page.locator('canvas')).toHaveCount(0);
  });
});

test.describe('phone 390', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('flat only (SCR-06-mobile): summary line, line cards with name and tag, no sideways scroll', async ({ page }) => {
    await page.goto('/overview');
    await loaded(page);
    await expect(viewSwitch(page)).toHaveCount(0);
    await expect(page.locator('.overview__hint')).toHaveCount(0);
    await expect(page.locator('.overview__summary')).toHaveText('10 in progress · 4 need a person');
    await expect(main(page).getByText('FACTORY FLOOR · UPDATED 23 Nov 10:30 WAT')).toBeVisible();
    expect(await page.locator('.overview__sq').first().evaluate((el) => el.getBoundingClientRect().width)).toBe(18);
    for (const [i, name] of TITLES.entries()) {
      await expect(rows(page).nth(i).locator('.overview__name')).toHaveText(name);
      await expect(rows(page).nth(i).locator('.psl-tag')).toBeVisible();
    }
    expect(await noHorizontalScroll(page)).toBe(true);
    await expect(main(page).getByRole('link', { name: 'See all exceptions' })).toBeVisible();
    await shot(page, 'overview-390');
    await expectNoAxeViolations(page);
  });
});
