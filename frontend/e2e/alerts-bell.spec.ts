import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// The alert bell and its drawer (F-15, F-61) against the contract mock in the live 1.24.0 shapes, scenario board unless
// said: 1440 and 390, axe WCAG 2.2 AA. Visual reference: concept 3 of design/concepts/alerts-bell-concepts.html.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const NEED = ['Invoice ready for review', 'Project plan to sign off', 'Invoice review'];
const INFO = ['Assistant reply', 'Milestone 2 is complete', 'Reminder: month-end close'];
const PROJECT = /\/projects\/6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f$/;

test.use({ timezoneId: 'Africa/Lagos' });

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

async function cookies(context: BrowserContext, values: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(values).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`) });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const bar = (page: Page) => page.locator('nav.psl-nav');
const bell = (page: Page) => bar(page).getByRole('button', { name: /^Alerts/ });
const phoneBell = (page: Page) => page.locator('.shell-phone').getByRole('button', { name: /^Alerts/ });
const dialog = (page: Page) => page.getByRole('dialog', { name: 'Alerts' });
const opens = (page: Page) => dialog(page).getByRole('link', { name: /^Open:/ });
const box = async (l: Locator) => (await l.boundingBox())!;
/** Waits for the slide-in to end, so boxes are measured where the drawer rests. */
const still = (l: Locator) => l.evaluate((el) => Promise.all(el.getAnimations().map((a) => a.finished)).then(() => undefined));

/** Counts the alerts list reads and the mark-read POSTs the page sends. */
function track(page: Page) {
  const seen = { lists: 0, posts: [] as { path: string; csrf?: string; body: string }[] };
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (url.pathname === '/api/v1/notifications' && r.method() === 'GET') seen.lists += 1;
    if (r.method() === 'POST' && url.pathname.startsWith('/api/v1/notifications/')) seen.posts.push({ path: url.pathname, csrf: r.headers()['x-csrftoken'], body: r.postData() ?? '' });
  });
  return seen;
}

async function ready(page: Page, path = '/my-work') {
  await page.goto(path);
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.locator('main#main > *').first()).toBeVisible();
}

async function badgeReads(page: Page, text: string, trigger = bell(page)) {
  await expect(trigger.locator('.shell-bellbadge')).toHaveText(text);
}

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('the bell sits right of the links and left of the name; badge 5, chip "3 need you", Start work last', async ({ page }) => {
    await ready(page);
    await badgeReads(page, '5');
    await expect(bell(page)).toHaveAccessibleName('Alerts, 5 unread, 3 need you');
    await expect(bell(page)).toHaveAttribute('aria-expanded', 'false');
    const chip = bar(page).locator('.shell-bellchip');
    await expect(chip).toHaveText('3 need you');
    const [links, b, c, who, start, badge] = await Promise.all(
      [bar(page).locator('.psl-nav__links'), bell(page), chip, bar(page).locator('.psl-nav__who'), bar(page).getByRole('button', { name: 'Start work' }), bell(page).locator('.shell-bellbadge')].map(box),
    );
    expect(links.x + links.width).toBeLessThan(b.x);
    expect(c.x).toBeCloseTo(b.x + b.width, 0);
    expect(c.height).toBe(24);
    expect(c.x + c.width).toBeLessThan(who.x);
    expect(who.x + who.width).toBeLessThan(start.x);
    expect(badge.height).toBeGreaterThanOrEqual(17);
    // As concept 3 draws it: -2px top and -3px right of the bell's padding box (inside its 2px border).
    expect(badge.y - (b.y + 2)).toBeCloseTo(-2, 0);
    expect(b.x + b.width - 2 - (badge.x + badge.width)).toBeCloseTo(-3, 0);
    const look = await chip.evaluate((el) => {
      const s = getComputedStyle(el);
      return [s.backgroundColor, s.color, s.fontSize];
    });
    expect(look).toEqual(['rgb(200, 64, 28)', 'rgb(255, 255, 255)', '12px']);
    expect(await bell(page).locator('.shell-bellbadge').evaluate((el) => getComputedStyle(el).backgroundColor)).toBe('rgb(200, 64, 28)');
    await shot(page, 'bell-1440-closed');
    await expectNoAxeViolations(page);
  });

  test('Tab goes links, bell, name menu, Start work, with Start work last in the bar', async ({ page }) => {
    await ready(page);
    await bar(page).getByRole('link', { name: 'Setup' }).focus();
    await page.keyboard.press('Tab');
    await expect(bell(page)).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(bar(page).getByRole('button', { name: /^Account menu: / })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(bar(page).getByRole('button', { name: 'Start work' })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(bar(page).getByRole('button', { name: 'More ways to start' })).toBeFocused();
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement!.closest('nav.psl-nav'))).toBeNull();
  });

  test('the drawer: 500px at the right, full height, groups, rows, footer; focus inside; axe clean', async ({ page }) => {
    await ready(page);
    await bell(page).click();
    const d = dialog(page);
    await expect(d).toBeVisible();
    await expect(bell(page)).toHaveAttribute('aria-expanded', 'true');
    const bellLook = await bell(page).evaluate((el) => [getComputedStyle(el).borderTopColor, getComputedStyle(el).borderTopWidth, getComputedStyle(el).backgroundColor]);
    expect(bellLook).toEqual(['rgb(255, 255, 255)', '2px', 'rgb(53, 61, 65)']);
    // The shared Drawer takes focus on its panel; Tab then reaches Close first.
    await expect(d).toBeFocused();
    await expect(opens(page)).toHaveCount(5);
    await still(d);
    const panel = await box(d);
    expect(Math.abs(panel.width - 500)).toBeLessThanOrEqual(1);
    expect(panel.x + panel.width).toBe(1440);
    expect(panel.y).toBe(0);
    expect(panel.y + panel.height).toBe(900);

    const text = await d.evaluate((el) => (el as HTMLElement).innerText);
    const marks = ['Alerts', 'NEEDS YOU', ...NEED, 'FOR INFORMATION', ...INFO, 'See all alerts', 'Alert settings'];
    const at = marks.map((m) => text.indexOf(m));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    await expect(d.locator('.alerts-grp')).toHaveText(['Needs you, 3', 'For information, 3']);
    expect(await d.locator('.alerts-grp--need').evaluate((el) => getComputedStyle(el).backgroundColor)).toBe('rgb(251, 227, 217)');
    await expect(d.locator('.alerts-meta').first()).toHaveText(/^Chidi · (\d\d:\d\d|yesterday)$/);
    await expect(d.locator('.psl-tag')).toHaveCount(0);
    const fills = await opens(page).evaluateAll((els) => els.map((el) => getComputedStyle(el).backgroundColor));
    expect(fills).toEqual([...Array(3).fill('rgb(36, 89, 214)'), ...Array(2).fill('rgb(255, 255, 255)')]);
    const weights = await d.locator('.alerts-text').evaluateAll((els) => els.map((el) => getComputedStyle(el).fontWeight));
    expect(weights).toEqual(['600', '600', '600', '600', '400', '600']);
    const foot = [await box(d.getByRole('link', { name: /^See all alerts/ })), await box(d.getByRole('link', { name: 'Alert settings' }))];
    expect(foot[0].x).toBeLessThan(foot[1].x);
    expect(foot[1].y + foot[1].height).toBeGreaterThan(850);
    await expect(page.getByRole('button', { name: /sign out/i })).toHaveCount(0);
    await shot(page, 'bell-1440-open');
    await expectNoAxeViolations(page);
  });

  test('focus stays inside; Escape, Close and the scrim close it and focus returns to the bell', async ({ page }) => {
    await ready(page);
    await bell(page).click();
    await expect(dialog(page)).toBeVisible();
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press('Tab');
      expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true);
    }
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press('Shift+Tab');
      expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true);
    }
    expect(await page.evaluate(() => document.querySelector('main')!.inert)).toBe(true);
    const before = await page.evaluate(() => window.scrollY);
    await page.mouse.wheel(0, 600);
    expect(await page.evaluate(() => window.scrollY)).toBe(before);

    await page.keyboard.press('Escape');
    await expect(dialog(page)).toHaveCount(0);
    await expect(bell(page)).toBeFocused();
    await expect(bell(page)).toHaveAttribute('aria-expanded', 'false');

    await bell(page).click();
    await dialog(page).getByRole('button', { name: 'Close' }).click();
    await expect(dialog(page)).toHaveCount(0);
    await expect(bell(page)).toBeFocused();

    await bell(page).click();
    await page.mouse.click(200, 500);
    await expect(dialog(page)).toHaveCount(0);
    await expect(bell(page)).toBeFocused();
  });

  test('the footer links go to /notifications and /settings/alerts and close the drawer', async ({ page }) => {
    await ready(page);
    await bell(page).click();
    await dialog(page).getByRole('link', { name: /^See all alerts/ }).click();
    await expect(page).toHaveURL(/\/notifications$/);
    await expect(dialog(page)).toHaveCount(0);
    await bell(page).click();
    await dialog(page).getByRole('link', { name: 'Alert settings' }).click();
    await expect(page).toHaveURL(/\/settings\/alerts$/);
    await expect(dialog(page)).toHaveCount(0);
  });

  test('Open on an unread alert: one POST of {} with the CSRF token, then the work; back shows badge 4 and "2 need you"', async ({ page }) => {
    const seen = track(page);
    await ready(page);
    await badgeReads(page, '5');
    await bell(page).click();
    await opens(page).first().dblclick();
    await expect(page).toHaveURL(/\/work\/4103$/);
    await expect(dialog(page)).toHaveCount(0);
    expect(seen.posts).toEqual([{ path: `/api/v1/notifications/${'a1'.padEnd(64, '0')}/read`, csrf: 'mock-csrf-finance_lead', body: '{}' }]);
    await page.goBack();
    await expect(page).toHaveURL(/\/my-work$/);
    await badgeReads(page, '4');
    await expect(bar(page).locator('.shell-bellchip')).toHaveText('2 need you');
  });

  test('Open on a read alert sends no POST; a failed POST still opens the work, once', async ({ page }) => {
    const seen = track(page);
    await ready(page);
    await bell(page).click();
    await opens(page).nth(4).click();
    await expect(page).toHaveURL(PROJECT);
    expect(seen.posts).toHaveLength(0);

    await page.route('**/api/v1/notifications/*/read', (route) => route.fulfill({ status: 500, json: { code: 'server_error', message: 'Down.' } }));
    await ready(page);
    await bell(page).click();
    await opens(page).first().click();
    await expect(page).toHaveURL(/\/work\/4103$/);
    expect(seen.posts).toHaveLength(1);
  });

  test('one read per page load and one per opening; nothing more over 70 s idle or after marking read', async ({ page }) => {
    await page.clock.install();
    const seen = track(page);
    await ready(page);
    await badgeReads(page, '5');
    expect(seen.lists).toBe(1);
    await bell(page).click();
    await expect(opens(page)).toHaveCount(5);
    expect(seen.lists).toBe(2);
    await page.keyboard.press('Escape');
    await page.clock.fastForward(70_000);
    await page.waitForTimeout(300);
    expect(seen.lists).toBe(2);
  });

  test('with reduced motion nothing animates in the drawer', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await ready(page);
    await bell(page).click();
    expect(await dialog(page).evaluate((el) => [getComputedStyle(el).animationName, getComputedStyle(el).transitionDuration])).toEqual(['none', '0s']);
  });

  test('many: the badge is the server total (40), the drawer lists page 1 only, and See all alerts says 40 unread', async ({ page, context }) => {
    await cookies(context, { psl_mock_alerts: 'many' });
    await ready(page);
    await expect(bell(page)).toHaveAccessibleName('Alerts, 40 unread, 5 need you');
    await bell(page).click();
    await expect(dialog(page).locator('.alerts-row')).toHaveCount(25);
    await expect(dialog(page).getByRole('link', { name: 'See all alerts (40 unread)' })).toBeVisible();
    await expect(dialog(page).getByText('Load more')).toHaveCount(0);
  });

  test('empty: "No alerts" with the summary and the footer links; no badge or chip', async ({ page, context }) => {
    await cookies(context, { psl_mock_alerts: 'empty' });
    await ready(page);
    await expect(bell(page)).toHaveAccessibleName('Alerts');
    await expect(bell(page).locator('.shell-bellbadge')).toHaveCount(0);
    await bell(page).click();
    await expect(dialog(page)).toContainText('No alerts');
    await expect(dialog(page).locator('.alerts-summary')).toContainText('0 need you, 0 new updates, 0 older unread');
    await expect(dialog(page).getByRole('link', { name: /^See all alerts/ })).toBeVisible();
    await expectNoAxeViolations(page);
  });

  test('loading: the skeleton with "Loading…" and no badge', async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    await page.route('**/api/v1/notifications', async (route) => {
      await gate;
      await route.continue();
    });
    await page.goto('/my-work');
    await expect(bell(page)).toBeVisible();
    await expect(bell(page).locator('.shell-bellbadge')).toHaveCount(0);
    await bell(page).click();
    await expect(dialog(page).getByRole('status')).toHaveText('Loading…');
    release();
    await expect(opens(page)).toHaveCount(5);
  });

  test('a failure: the error card and no badge; Try again reads once and shows the list', async ({ page }) => {
    const seen = track(page);
    const fail = (route: import('@playwright/test').Route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '404' } });
    await page.route('**/api/v1/notifications', fail);
    await ready(page);
    await expect(bell(page)).toHaveAccessibleName('Alerts');
    await bell(page).click();
    const card = dialog(page).getByRole('alert');
        await expect(card).toContainText('We couldn’t load your alerts. Your work is safe; nothing was changed.');
    await expect(card).toContainText('Reference not_found for support.');
    await page.unroute('**/api/v1/notifications', fail);
    const before = seen.lists;
    await dialog(page).getByRole('button', { name: 'Try again' }).click();
    await expect(opens(page)).toHaveCount(5);
    expect(seen.lists).toBe(before + 1);
    await badgeReads(page, '5');
  });

  test('a 401: signed out with Sign in back to this page, and no further reads; a 403 says the account can’t use PSL Factory', async ({ page }) => {
    const seen = track(page);
    const as = (code: string) => (route: import('@playwright/test').Route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': code } });
    await page.route('**/api/v1/notifications', as('401'));
    await ready(page);
    await bell(page).click();
    await expect(dialog(page)).toContainText('You’re signed out.');
    await expect(dialog(page).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in?next=%2Fmy-work');
    await page.keyboard.press('Escape');
    await bell(page).click();
    await expect(dialog(page)).toContainText('You’re signed out.');
    expect(seen.lists).toBe(1);

    await page.unroute('**/api/v1/notifications');
    await page.route('**/api/v1/notifications', as('403'));
    await ready(page);
    await bell(page).click();
    await expect(dialog(page)).toContainText('Your account can’t use PSL Factory.');
  });

  test('/me signed out: no bell and no alerts read', async ({ page, context }) => {
    const seen = track(page);
    await cookies(context, { psl_mock_scenario: '401' });
    await page.goto('/my-work');
    await expect(page.getByText('You’re signed out.')).toBeVisible();
    await expect(page.getByRole('button', { name: /^Alerts/ })).toHaveCount(0);
    expect(seen.lists).toBe(0);
  });

  test('a person sees only their own alerts: switching persona changes the list and the counts', async ({ page, context }) => {
    await ready(page);
    await badgeReads(page, '5');
    await bell(page).click();
    await expect(opens(page)).toHaveCount(5);
    await page.keyboard.press('Escape');
    await cookies(context, { psl_mock_persona: 'pm' });
    await ready(page);
    await expect(bell(page)).not.toHaveAccessibleName('Alerts, 5 unread, 3 need you');
    await bell(page).click();
    await expect(dialog(page).locator('.alerts-text').first()).toHaveText('The project plan for Kestrel Logistics needs your sign-off');
    await expect(dialog(page).getByText(NEED[0])).toHaveCount(0);
  });
});

test.describe('bar widths', () => {
  for (const width of [720, 900, 1079, 1080]) {
    for (const path of ['/', '/projects', '/notifications']) {
      test(`at ${width}px on ${path} the bar fits: links, bell, name and Start work on one line`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await ready(page, path);
        await expect(bell(page).locator('.shell-bellbadge')).toHaveText('5');
        await expect(bar(page).locator('.shell-bellchip')).toBeVisible({ visible: width >= 1080 });
        expect(await noHorizontalScroll(page)).toBe(true);
        const inner = await page.locator('.psl-nav__in').evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
        expect(inner.scroll).toBeLessThanOrEqual(inner.client);
        const boxes = await Promise.all([bar(page).locator('.psl-nav__links'), bell(page), bar(page).locator('.psl-nav__who'), bar(page).getByRole('button', { name: 'Start work' })].map(box));
        for (let i = 1; i < boxes.length; i++) expect(boxes[i - 1].x + boxes[i - 1].width).toBeLessThanOrEqual(boxes[i].x);
        expect(new Set(boxes.map((b) => Math.round(b.y + b.height / 2))).size).toBe(1);
        const who = await bar(page).locator('.psl-nav__who').evaluate((el) => el.scrollWidth <= el.clientWidth);
        expect(who).toBe(true);
        // the bar keeps its 28px gutter at the right
        expect(boxes[3].x + boxes[3].width).toBeLessThanOrEqual(width - 28);
      });
    }
  }
});

test.describe('phone 390', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('Menu, PSL FACTORY, bell (44x44), + Start; Tab goes Menu, bell, + Start', async ({ page }) => {
    await ready(page);
    const header = page.locator('header.psl-phonebar');
    const parts = [header.getByRole('button', { name: 'Menu' }), header.getByText('PSL FACTORY'), phoneBell(page), page.locator('.shell-phone').getByRole('button', { name: 'Start work' })];
    const boxes = await Promise.all(parts.map(box));
    for (let i = 1; i < boxes.length; i++) expect(boxes[i - 1].x + boxes[i - 1].width).toBeLessThanOrEqual(boxes[i].x);
    expect(boxes[2].width).toBeGreaterThanOrEqual(44);
    expect(boxes[2].height).toBeGreaterThanOrEqual(44);
    await expect(phoneBell(page)).toHaveAccessibleName('Alerts, 5 unread, 3 need you');
    await expect(page.locator('.shell-phone .shell-bellchip')).toHaveCount(0);
    await parts[0].focus();
    await page.keyboard.press('Tab');
    await expect(phoneBell(page)).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(parts[3]).toBeFocused();
    await shot(page, 'bell-390-closed');
  });

  test('on a sub-page with a back link: ← label, bell, + Start', async ({ page }) => {
    await ready(page, '/frame-fixtures/phone-back');
    const header = page.locator('header.psl-phonebar');
    const back = header.getByRole('link', { name: 'Back to Queue' });
    await expect(back).toBeVisible();
    await expect(header.getByRole('button', { name: 'Menu' })).toHaveCount(0);
    const [b, bellBox, start] = await Promise.all([back, phoneBell(page), page.locator('.shell-phone').getByRole('button', { name: 'Start work' })].map(box));
    expect(b.x + b.width).toBeLessThanOrEqual(bellBox.x);
    expect(bellBox.x + bellBox.width).toBeLessThanOrEqual(start.x);
    expect(bellBox.width).toBeGreaterThanOrEqual(44);
    expect(bellBox.height).toBeGreaterThanOrEqual(44);
  });

  test('the sheet: 36px from the top, grab bar, Close 44px, tabs; Needs you first; arrows switch; Escape back to the bell; axe clean', async ({ page }) => {
    await ready(page);
    await phoneBell(page).click();
    const d = dialog(page);
    await expect(d).toBeVisible();
    await expect(d).toBeFocused();
    await still(d);
    const panel = await box(d);
    expect(panel.y).toBe(0);
    expect(panel.y + panel.height).toBe(844);
    expect(panel.width).toBe(390);
    await expect(d.locator('.psl-sheet__grab')).toBeVisible();
    const close = await box(d.getByRole('button', { name: 'Close' }));
    expect(close.width).toBeGreaterThanOrEqual(44);
    expect(close.height).toBeGreaterThanOrEqual(44);
    const tabs = d.getByRole('tab');
    await expect(tabs).toHaveText(['Needs you 3', 'For information']);
    for (const t of await tabs.all()) expect((await box(t)).height).toBeGreaterThanOrEqual(44);
    await expect(tabs.first()).toHaveAttribute('aria-selected', 'true');
    await expect(d.locator('.alerts-text')).toHaveText(NEED);
    for (const o of await opens(page).all()) {
      const ob = await box(o);
      expect(ob.height).toBeGreaterThanOrEqual(44);
      expect(ob.width).toBeGreaterThanOrEqual(60);
    }
    // the footer links are 44px targets on the phone, side by side (QA-2, D-92c)
    const foot = [await box(d.getByRole('link', { name: /^See all alerts/ })), await box(d.getByRole('link', { name: 'Alert settings' }))];
    for (const f of foot) expect(f.height).toBeGreaterThanOrEqual(44);
    expect(Math.abs(foot[0].y - foot[1].y)).toBeLessThanOrEqual(1);
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'bell-390-open');
    await expectNoAxeViolations(page);

    await tabs.first().focus();
    await page.keyboard.press('ArrowRight');
    await expect(tabs.nth(1)).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(tabs.nth(1)).toHaveAttribute('aria-selected', 'true');
    await expect(d.locator('.alerts-text')).toHaveText(INFO);
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('Enter');
    await expect(d.locator('.alerts-text')).toHaveText(NEED);
    await tabs.nth(1).click();
    await expect(d.locator('.alerts-text')).toHaveText(INFO);

    await page.keyboard.press('Escape');
    await expect(d).toHaveCount(0);
    await expect(phoneBell(page)).toBeFocused();
  });

  test('with no needs-you alert the sheet opens on For information and Needs you is one tap away', async ({ page, context }) => {
    await cookies(context, { psl_mock_persona: 'pm' });
    await ready(page);
    await phoneBell(page).click();
    await expect(dialog(page).getByRole('tab', { name: 'For information' })).toHaveAttribute('aria-selected', 'true');
    await expect(dialog(page).getByRole('tab', { name: 'Needs you' })).toBeVisible();
  });

  test('with reduced motion the sheet appears without animation', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await ready(page);
    await phoneBell(page).click();
    expect(await dialog(page).evaluate((el) => [getComputedStyle(el).animationName, getComputedStyle(el).transitionDuration])).toEqual(['none', '0s']);
  });
});

test.describe('phone bar at narrow widths', () => {
  test.use({ hasTouch: true, isMobile: true });
  for (const width of [320, 360, 375, 390]) {
    test(`${width}px: the wordmark ends 8px or more before the bell; bell 44px; Menu, bell and + Start in order; no horizontal scroll`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await ready(page);
      const header = page.locator('header.psl-phonebar');
      const [menu, brand, bellBox, start] = await Promise.all(
        [header.getByRole('button', { name: 'Menu' }), header.locator('.psl-brand'), phoneBell(page), page.locator('.shell-phone').getByRole('button', { name: 'Start work' })].map(box),
      );
      expect(menu.x + menu.width).toBeLessThanOrEqual(brand.x);
      expect(brand.x + brand.width + 8).toBeLessThanOrEqual(bellBox.x);
      expect(bellBox.x + bellBox.width).toBeLessThanOrEqual(start.x);
      expect(start.x + start.width).toBeLessThanOrEqual(width);
      expect([bellBox.width, bellBox.height, menu.width, menu.height].every((n) => n >= 44)).toBe(true);
      expect(await noHorizontalScroll(page)).toBe(true);
    });
  }

  test('Open from the sheet: focus is on the bell of the page it opens', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await ready(page);
    await phoneBell(page).click();
    await opens(page).first().click();
    await expect(page).toHaveURL(/\/work\//);
    await expect(dialog(page)).toHaveCount(0);
    await expect(phoneBell(page)).toBeFocused();
  });

  test('Alert settings: focus is on the bell of the settings page', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await ready(page);
    await phoneBell(page).click();
    await dialog(page).getByRole('link', { name: 'Alert settings' }).click();
    await expect(page).toHaveURL(/\/settings\/alerts/);
    await expect(phoneBell(page)).toBeFocused();
  });
});

test.describe('top bar across 720 to 1440', () => {
  for (const width of [720, 760, 900, 1079, 1080, 1440]) {
    test(`${width}px: nothing overlaps or is cut; 8px or more between the bell and the name${width >= 760 ? '; links keep 4px padding' : ''}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await ready(page);
      const parts = [bar(page).locator('.psl-brand'), bar(page).locator('.psl-nav__links'), bell(page), bar(page).locator('.psl-nav__who'), bar(page).getByRole('button', { name: 'Start work' })];
      const boxes = await Promise.all(parts.map(box));
      for (let i = 1; i < boxes.length; i++) expect(boxes[i - 1].x + boxes[i - 1].width).toBeLessThanOrEqual(boxes[i].x);
      // the bell's own 2px border counts as part of the bell, so the gap is measured from its box
      expect(boxes[3].x - (boxes[2].x + boxes[2].width)).toBeGreaterThanOrEqual(8);
      expect(boxes[4].x + boxes[4].width).toBeLessThanOrEqual(width - 28);
      expect(await bar(page).locator('.psl-nav__who').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
      expect(await noHorizontalScroll(page)).toBe(true);
      const pad = await bar(page).locator('.psl-navlink').first().evaluate((el) => getComputedStyle(el).paddingLeft);
      if (width >= 760 && width < 1080) expect(pad).toBe('4px');
    });
  }
});
