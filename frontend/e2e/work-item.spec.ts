import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const PAGES = ['/work/W-1001', '/work/W-1003', '/work/W-1004/history', '/work/W-1099'];

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
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

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    for (const path of PAGES) {
      test(`${path} has no axe violations and no sideways page scroll`, async ({ page }) => {
        await page.goto(path);
        await loaded(page);
        await expect(page).toHaveTitle('Work item · PSL Factory');
        await page.screenshot({ path: test.info().outputPath(`${path.replace(/\//g, '_')}.png`), fullPage: true });
        await expectNoAxeViolations(page);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
      });
    }
  });
}

test('W-1004 shows the A-WORKITEM facts', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto('/work/W-1004');
  await loaded(page);
  await expect(page.getByRole('list', { name: 'Facts' }).getByRole('listitem')).toHaveText([
    'DRAFTEDEarned12 Nov 10:58',
    'REVIEWEDEarned12 Nov 16:12',
    'APPROVEDEarned12 Nov 16:40',
    'SENT—Not yet',
    'RECEIPT RECORDEDUnknown',
    'VERIFIED—Not yet',
  ]);
  await expect(page.getByText('Paid is a separate Finance fact and is not part of this line.')).toBeVisible();
});

test('W-1099 shows the no-access board and nothing about the item', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto('/work/W-1099');
  await loaded(page);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('You can’t open this work item');
  await expect(page.getByRole('link', { name: 'Back to my queue' })).toHaveAttribute('href', '/my-work');
  expect(await page.locator('main').textContent()).not.toContain('W-1099');
});

test('at 390px the stations are a vertical list with the status on the right', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto('/work/W-1001');
  await loaded(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  const region = page.getByRole('region', { name: 'Stations' });
  const track = await region.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
  expect(track.scroll).toBeLessThanOrEqual(track.client);
  const rows = await region.getByRole('listitem').evaluateAll((items) =>
    items.map((li) => {
      const box = li.getBoundingClientRect();
      const [number, name, status] = Array.from(li.children).map((child) => child.getBoundingClientRect());
      return { top: box.top, left: box.left, width: box.width, number, name, status };
    }),
  );
  expect(rows.length).toBeGreaterThan(1);
  for (const [i, row] of rows.entries()) {
    if (i > 0) expect(row.top).toBeGreaterThan(rows[i - 1].top);
    expect(row.left).toBe(rows[0].left);
    expect(row.width).toBe(rows[0].width);
    expect(row.status.left).toBeGreaterThan(row.name.left);
    expect(Math.abs(row.status.top - row.name.top)).toBeLessThan(row.name.height);
  }
});

for (const width of [760, 900, 1079]) {
  test(`at ${width}px the stations are a vertical list with nothing clipped`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/work/W-1005');
    await loaded(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    const region = page.getByRole('region', { name: 'Stations' });
    const track = await region.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth, right: el.getBoundingClientRect().right }));
    expect(track.scroll).toBeLessThanOrEqual(track.client);
    const rows = await region.getByRole('listitem').evaluateAll((items) => items.map((li) => li.getBoundingClientRect().toJSON()));
    expect(rows).toHaveLength(7);
    for (const [i, row] of rows.entries()) {
      if (i > 0) expect(row.top).toBeGreaterThanOrEqual(rows[i - 1].bottom - 1);
      expect(row.left).toBe(rows[0].left);
      expect(row.right).toBeLessThanOrEqual(track.right);
    }
  });
}

for (const width of [1080, 1440]) {
  test(`at ${width}px the stations are a row with all 7 visible`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/work/W-1005');
    await loaded(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    const region = page.getByRole('region', { name: 'Stations' });
    const track = await region.evaluate((el) => {
      const box = el.getBoundingClientRect();
      return { scroll: el.scrollWidth, client: el.clientWidth, left: box.left, right: box.right };
    });
    expect(track.scroll).toBeLessThanOrEqual(track.client);
    const rows = await region.getByRole('listitem').evaluateAll((items) => items.map((li) => li.getBoundingClientRect().toJSON()));
    expect(rows).toHaveLength(7);
    for (const [i, row] of rows.entries()) {
      if (i > 0) expect(row.left).toBeGreaterThan(rows[i - 1].left);
      expect(row.top).toBe(rows[0].top);
      expect(row.left).toBeGreaterThanOrEqual(track.left);
      expect(row.right).toBeLessThanOrEqual(track.right);
    }
  });
}

for (const [width, background, color] of [
  [1440, 'rgb(138, 90, 0)', 'rgb(255, 255, 255)'],
  [1080, 'rgb(138, 90, 0)', 'rgb(255, 255, 255)'],
  [1079, 'rgb(255, 241, 214)', 'rgb(110, 71, 0)'],
  [390, 'rgb(255, 241, 214)', 'rgb(110, 71, 0)'],
] as const) {
  test(`at ${width}px the effect-uncertain station is ${width >= 1080 ? 'solid amber with white text' : 'a pale amber row'}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/work/W-1005');
    await loaded(page);
    const deliver = page.getByRole('region', { name: 'Stations' }).locator('li[aria-current="step"]');
    await expect(deliver).toContainText('Deliver');
    expect(await deliver.evaluate((el) => [getComputedStyle(el).backgroundColor, getComputedStyle(el).color])).toEqual([background, color]);
  });
}

test.describe('agent step motion', () => {
  test.use({ viewport: DESKTOP });

  test('the current step pulses only when motion is allowed', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.goto('/work/W-1003');
    await loaded(page);
    const box = page.locator('.psl-step--now .psl-step__box');
    expect(await box.evaluate((el) => getComputedStyle(el).animationName)).toBe('psl-pulse');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    expect(await box.evaluate((el) => getComputedStyle(el).animationName)).toBe('none');
  });

  test('with reduced motion the current step does not animate', async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: 'reduce', viewport: DESKTOP });
    const page = await context.newPage();
    await page.goto('/work/W-1003');
    await loaded(page);
    expect(await page.locator('.psl-step--now .psl-step__box').evaluate((el) => getComputedStyle(el).animationName)).toBe('none');
    await context.close();
  });
});

test('history: 10 rows, Show more appends to 12, then no Show more; focus rings on tabs, filter and Show more', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto('/work/W-1004/history');
  await loaded(page);
  const rows = page.getByRole('table').locator('tbody tr');
  await expect(rows).toHaveCount(12);

  const ring = { style: 'solid', width: '2px' };
  expect(await tabTo(page, page.getByRole('navigation', { name: 'Work item' }).getByRole('link', { name: 'Overview' }))).toEqual(ring);
  expect(await tabTo(page, page.getByRole('radio', { name: 'All' }))).toEqual(ring);
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('radio', { name: 'Decisions' })).toBeFocused();
  await expect(page.getByRole('radio', { name: 'Decisions' })).toHaveAttribute('aria-checked', 'true');
  await expect(rows).toHaveCount(4);
  await page.getByRole('radio', { name: 'All' }).click();

  await page.getByLabel('Rows per page').selectOption('10');
  await expect(rows).toHaveCount(10);
  const more = page.getByRole('button', { name: 'Show more' });
  await expect(more).toBeVisible();
  await page.getByLabel('Rows per page').focus();
  expect(await tabTo(page, more)).toEqual(ring);
  await page.keyboard.press('Enter');
  await expect(rows).toHaveCount(12);
  await expect(more).toHaveCount(0);
  await expect(rows.first().locator('time')).toHaveText('12 Nov 16:40');
  await expectNoAxeViolations(page);
});
