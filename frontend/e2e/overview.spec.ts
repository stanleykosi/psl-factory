import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page, type Response } from '@playwright/test';

// Overview (SCR-06) against the contract mock: flat and 3D floor at 1440, flat at 390, axe WCAG 2.2 AA.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const LINES = ['Pre-sale', 'Planning', 'Release', 'Closing', 'Invoices', 'Month-end', 'Cash and BU', 'Payroll'];
const NOTES = ['1 WAITING', '1 STOPPED', '1 UNCERTAIN', 'ON TRACK', '2 WAITING', 'ON TRACK', 'ON TRACK', '2 PROBLEMS'];

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
const rows = (page: Page) => page.locator('section[aria-label="Lines"] [role="list"] > .overview__row');
const tiles = (page: Page) => page.locator('dl.overview__totals > div');
const viewSwitch = (page: Page) => page.getByRole('radiogroup', { name: 'View' });
// A full-page capture briefly narrows the window, which (correctly) drops the 3D floor; the 3D shot is the viewport only.
const shot = (page: Page, name: string, fullPage = true) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

async function loaded(page: Page) {
  await expect(page.getByRole('heading', { level: 1, name: 'Factory floor' })).toBeVisible();
  await expect(page.getByRole('status')).toHaveCount(0);
}

/** Tabs until the target has focus, then reads its outline. */
async function keyboardRing(page: Page, target: Locator) {
  for (let i = 0; i < 80; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press('Tab');
  }
  await expect(target).toBeFocused();
  return target.evaluate((el) => {
    const s = getComputedStyle(el);
    return { style: s.outlineStyle, width: s.outlineWidth };
  });
}

/** Station screen-reader texts per line, as read from the flat list. */
const stationTexts = (page: Page) =>
  page.locator('section[aria-label="Lines"] ol').evaluateAll((ols) =>
    ols.map((ol) => [...ol.querySelectorAll('.overview__sr')].map((sr) => sr.textContent)),
  );

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('default flat: four totals, eight lines with counts, View switch, exceptions link', async ({ page }) => {
    const notFound: string[] = [];
    page.on('response', (r) => {
      if (r.status() >= 400) notFound.push(`${r.status()} ${r.url()}`);
    });
    await page.goto('/overview');
    await loaded(page);
    await expect(page).toHaveTitle('Overview · PSL Factory');
    await expect(main(page).getByText('FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT')).toBeVisible();
    await expect(tiles(page)).toHaveText(['IN PROGRESS18', 'NEED A PERSON5', 'STOPPED3', 'VERIFIED THIS MONTH28']);
    await expect(rows(page).locator('.overview__name')).toHaveText(LINES);
    await expect(rows(page).locator('.psl-tag')).toHaveText(NOTES);
    await expect(page.getByRole('list', { name: 'Invoices stations' }).getByRole('listitem')).toHaveCount(7);
    await expect(page.getByRole('radio', { name: 'Flat' })).toHaveAttribute('aria-checked', 'true');
    await expect(main(page).getByRole('link', { name: 'See all exceptions' })).toHaveAttribute('href', '/exceptions');
    await expect(rows(page).first().locator('.overview__sub')).toHaveText('RFP · commercial');
    // The mascot avatars are static files that load (no broken image).
    const avatar = rows(page).first().getByRole('img', { name: 'Tola · PMO agent' });
    await expect(avatar).toBeVisible();
    expect(await avatar.evaluate((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth)).toBe(192);
    // A normal desktop browser with WebGL gets the 3D option and no "can't show" hint.
    await expect(page.getByText(/can’t show the 3D floor/)).toHaveCount(0);
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'overview-1440');
    // The link to /exceptions is not prefetched (that route is another feature's), so nothing on the page fails to load.
    await page.waitForTimeout(1000);
    expect(notFound).toEqual([]);
    await expectNoAxeViolations(page);
  });

  test('keyboard: Tab reaches the View switch with a 2px ring, arrows move the selection, the link is reachable', async ({ page }) => {
    await page.goto('/overview');
    await loaded(page);
    const flat = page.getByRole('radio', { name: 'Flat' });
    const floor = page.getByRole('radio', { name: '3D floor' });
    expect(await keyboardRing(page, flat)).toEqual({ style: 'solid', width: '2px' });
    await page.keyboard.press('ArrowRight');
    await expect(floor).toBeFocused();
    await expect(floor).toHaveAttribute('aria-checked', 'true');
    expect(await floor.evaluate((el) => getComputedStyle(el).outlineStyle + ' ' + getComputedStyle(el).outlineWidth)).toBe('solid 2px');
    await page.keyboard.press('ArrowLeft');
    await expect(flat).toBeFocused();
    await expect(flat).toHaveAttribute('aria-checked', 'true');
    const link = main(page).getByRole('link', { name: 'See all exceptions' });
    expect(await keyboardRing(page, link)).toMatchObject({ style: 'solid' });
  });

  test('empty lines: four 0 tiles, the empty message, no View switch, the exceptions link', async ({ page, context }) => {
    await setCookies(context, { psl_mock_overview: 'empty' });
    await page.goto('/overview');
    await loaded(page);
    await expect(tiles(page).locator('dd')).toHaveText(['0', '0', '0', '0']);
    await expect(page.getByRole('heading', { name: 'No lines to show yet.' })).toBeVisible();
    await expect(viewSwitch(page)).toHaveCount(0);
    await expect(main(page).getByRole('link', { name: 'See all exceptions' })).toBeVisible();
    await expectNoAxeViolations(page);
  });

  test('all-zero lines: every square empty, no numerals, tags verbatim', async ({ page, context }) => {
    await setCookies(context, { psl_mock_overview: 'zero' });
    await page.goto('/overview');
    await loaded(page);
    await expect(rows(page)).toHaveCount(8);
    await expect(page.locator('.overview__station:not(.overview__station--empty)')).toHaveCount(0);
    expect((await page.locator('.overview__sq').allTextContents()).join('')).toBe('');
    await expect(rows(page).locator('.psl-tag')).toHaveText(NOTES);
  });

  test('a line status (proposed field, mock variant) gives the board tag tones', async ({ page, context }) => {
    await setCookies(context, { psl_mock_overview: 'status' });
    await page.goto('/overview');
    await loaded(page);
    const tones = await rows(page).locator('.psl-tag').evaluateAll((tags) => tags.map((t) => t.className.replace('psl-tag ', '')));
    expect(tones).toEqual(['psl-tag--waiting', 'psl-tag--person', 'psl-tag--person', 'psl-tag--done', 'psl-tag--waiting', 'psl-tag--done', 'psl-tag--done', 'psl-tag--person']);
    await expectNoAxeViolations(page);
  });

  test('403 from E-OVERVIEW: the floor is not open, with the server message', async ({ page }) => {
    await page.route('**/api/v1/overview', (route) =>
      route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'Your role does not allow this.' }) }),
    );
    await page.goto('/overview');
    await expect(page.getByRole('heading', { name: 'The factory floor isn’t open to your role.' })).toBeVisible();
    await expect(main(page).getByText('Your role does not allow this.')).toBeVisible();
    await expect(page.locator('dl')).toHaveCount(0);
    await expectNoAxeViolations(page);
  });

  test('no WebGL: no View switch, the device hint, every line and count', async ({ page }) => {
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
    await expect(rows(page)).toHaveCount(8);
    const texts = await stationTexts(page);
    expect(texts[4]).toEqual(['Milestone: 3 items', 'Draft: 0 items', 'Check: 1 item', 'Approve: 1 item, needs a person', 'Send: 0 items', 'Receipt: 0 items', 'Match: 1 item']);
    expect(texts.flat()).toHaveLength(40);
    await expectNoAxeViolations(page);
  });

  test('reduced motion: flat with the motion hint and no 3D option', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/overview');
    await loaded(page);
    await expect(page.getByText('Motion is turned down on this device, so the floor is shown flat.')).toBeVisible();
    await expect(page.getByRole('radio', { name: '3D floor' })).toHaveCount(0);
    await expect(rows(page)).toHaveCount(8);
    await shot(page, 'overview-1440-reduced-motion');
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

  test('3D floor: same figures, renders on demand, moves only when a poll changes a count', async ({ page, context }) => {
    await page.clock.install();
    await page.addInitScript(() => {
      const w = window as unknown as { __raf: number };
      w.__raf = 0;
      const raf = window.requestAnimationFrame.bind(window);
      window.requestAnimationFrame = (cb) => {
        w.__raf += 1;
        return raf(cb);
      };
    });
    const rafCount = () => page.evaluate(() => (window as unknown as { __raf: number }).__raf);
    await page.goto('/overview');
    await loaded(page);
    await page.getByRole('radio', { name: '3D floor' }).click();
    const canvas = page.getByRole('img', { name: /^3D factory floor: 8 lines/ });
    await expect(canvas).toBeVisible();
    // The stage follows concept 3 (D-01): clamp(460px, 50vw, 640px), so 640px at 1440.
    expect(await canvas.boundingBox()).toMatchObject({ height: 640 });
    expect(await canvas.evaluate((el) => Boolean((el as HTMLCanvasElement).getContext('webgl2') ?? (el as HTMLCanvasElement).getContext('webgl')))).toBe(true);
    await expect(rows(page)).toHaveCount(8);
    await expect(tiles(page)).toHaveCount(4);

    await page.waitForTimeout(1000);
    const settled = await rafCount();
    await page.waitForTimeout(2000);
    expect(await rafCount()).toBe(settled);
    expect(await noHorizontalScroll(page)).toBe(true);
    await expectNoAxeViolations(page);

    await setCookies(context, { psl_mock_overview: 'changed' });
    await page.clock.fastForward(15_000);
    await expect(page.locator('.overview__eyebrow')).toHaveText('FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT');
    await expect.poll(async () => (await stationTexts(page))[0][0]).toBe('Brief: 2 items');
    expect((await stationTexts(page))[4][0]).toBe('Milestone: 1 item');
    expect((await stationTexts(page))[7][2]).toBe('Approve: 1 item');
    await expect(tiles(page).locator('dd')).toHaveText(['19', '4', '3', '29']);
    expect(await rafCount()).toBeGreaterThan(settled);
    await page.waitForTimeout(1000);
    const after = await rafCount();
    await page.waitForTimeout(1000);
    expect(await rafCount()).toBe(after);
    await shot(page, 'overview-3d-1440', false);
    await expect(canvas).toBeVisible();
  });
  test('3D floor (tilted board): a label per station, hover and focus readout, lift settles, reset', async ({ page }) => {
    // Waits for the lift to settle plus an axe pass over 40 overlay buttons; software WebGL is slow on a busy machine.
    test.setTimeout(60_000);
    await page.addInitScript(() => {
      const w = window as unknown as { __raf: number };
      w.__raf = 0;
      const raf = window.requestAnimationFrame.bind(window);
      window.requestAnimationFrame = (cb) => {
        w.__raf += 1;
        return raf(cb);
      };
    });
    const rafCount = () => page.evaluate(() => (window as unknown as { __raf: number }).__raf);
    await page.goto('/overview');
    await loaded(page);
    await page.getByRole('radio', { name: '3D floor' }).click();
    await expect(page.getByRole('img', { name: /^3D factory floor: 8 lines/ })).toBeVisible();
    const chips = page.locator('.floor__chip');
    await expect(chips).toHaveCount(40);
    await expect(page.locator('.floor__line strong')).toHaveText(LINES);
    const readout = page.locator('.floor__readout');
    await expect(readout).toHaveText('Point at, tap or tab to a station to read it. Drag sideways to turn the board.');

    const approve = page.getByRole('button', { name: '1 Approve PERSON. Invoices · Approve · 1 item · needs a person' });
    await expect(approve).toHaveText('1 Approve PERSON');
    await approve.hover();
    await expect(readout).toHaveText('Invoices · Approve · 1 item · needs a person');
    // The lift and the lean ease in, then frames stop.
    await page.waitForTimeout(2500);
    const settled = await rafCount();
    await page.waitForTimeout(1000);
    expect(await rafCount()).toBe(settled);

    await page.getByRole('button', { name: 'Reset view' }).click();
    await expect(readout).toHaveText('Point at, tap or tab to a station to read it. Drag sideways to turn the board.');
    await page.getByRole('button', { name: '1 Brief. Pre-sale · Brief · 1 item · no person needed' }).focus();
    await expect(readout).toHaveText('Pre-sale · Brief · 1 item · no person needed');
    await shot(page, 'overview-3d-board-1440', false);
    await expectNoAxeViolations(page);

    await page.getByRole('radio', { name: 'Flat' }).click();
    await expect(page.locator('canvas')).toHaveCount(0);
    await expect(chips).toHaveCount(0);
  });
});

test.describe('phone 390', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('flat only (SCR-06-mobile): summary line, line cards with name and tag, no sideways scroll', async ({ page }) => {
    await page.goto('/overview');
    await loaded(page);
    await expect(viewSwitch(page)).toHaveCount(0);
    await expect(page.locator('.overview__hint')).toHaveCount(0);
    await expect(page.locator('.overview__summary')).toHaveText('18 in progress · 5 need a person');
    await expect(main(page).getByText('FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT')).toBeVisible();
    expect(await page.locator('.overview__sq').first().evaluate((el) => el.getBoundingClientRect().width)).toBe(18);
    for (const [i, name] of LINES.entries()) {
      await expect(rows(page).nth(i).locator('.overview__name')).toHaveText(name);
      await expect(rows(page).nth(i).locator('.overview__name')).toBeVisible();
      await expect(rows(page).nth(i).locator('.psl-tag')).toBeVisible();
    }
    expect(await noHorizontalScroll(page)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await expect(main(page).getByRole('link', { name: 'See all exceptions' })).toBeVisible();
    await shot(page, 'overview-390');
    await expectNoAxeViolations(page);
  });
});
