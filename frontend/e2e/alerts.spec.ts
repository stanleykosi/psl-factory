import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// Alerts (SCR-15 list and settings) against the contract mock: 390 and 1440, axe WCAG 2.2 AA.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

async function scenario(context: BrowserContext, value: string) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies([{ name: 'psl_mock_alerts', value, url }]);
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

const rows = (page: Page) => page.getByRole('list', { name: 'Alerts' }).locator(':scope > li');
const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const sw = (page: Page, name: string) => page.getByRole('switch', { name });

async function listLoaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: 'Notifications' })).toBeVisible();
}
async function settingsLoaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: 'How you’re alerted' })).toBeVisible();
}

const BOARD_ROWS = [
  ['Invoice for Lagoon Health is waiting for your review', 'Chidi · WhatsApp and email · 10:42'],
  ['The UAT response for Lagoon Health is due tomorrow', 'Tola · Email · 09:00 daily digest'],
  ['October payroll has 2 problems for HR', 'Zainab · In app only (you are not HR)'],
  ['Milestone 1 invoice was verified', 'Chidi · In app · yesterday'],
];

async function expectBoardRows(page: Page) {
  await expect(rows(page)).toHaveCount(4);
  await expect(rows(page).locator('.alerts-text')).toHaveText(BOARD_ROWS.map((r) => r[0]));
  await expect(rows(page).locator('.alerts-meta')).toHaveText(BOARD_ROWS.map((r) => r[1]));
  const imgs = await rows(page).locator('img').evaluateAll((els) => els.map((el) => [el.getAttribute('src'), (el as HTMLImageElement).naturalWidth > 0]));
  expect(imgs).toEqual(['chidi', 'tola', 'zainab', 'chidi'].map((a) => [`/agents/${a}.png`, true]));
  await expect(rows(page).locator('.psl-tag')).toHaveCount(1);
  await expect(rows(page).nth(0).locator('.psl-tag')).toHaveText(/NEW$/);
  const looks = await rows(page).evaluateAll((els) =>
    els.map((li) => [getComputedStyle(li).backgroundColor, getComputedStyle(li.querySelector('.alerts-text')!).fontWeight]),
  );
  expect(looks.map((l) => l[1])).toEqual(['600', '400', '400', '400']);
  expect(looks[0][0]).not.toBe(looks[1][0]);
  expect(new Set(looks.slice(1).map((l) => l[0])).size).toBe(1);
}

test.describe('list at 1440 (SCR-15-desktop)', () => {
  test.use({ viewport: DESKTOP });

  test('board: header, toolbar, count and the four rows', async ({ page }) => {
    await page.goto('/notifications');
    await listLoaded(page);
    const main = page.locator('main');
    const order = await main.evaluate((el) => (el as HTMLElement).innerText);
    const marks = ['NOTIFICATIONS', 'Notifications', 'Alert settings', 'Filter', '4 ALERTS', BOARD_ROWS[0][0], BOARD_ROWS[3][1]];
    const at = marks.map((m) => order.indexOf(m));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    await expect(page.getByRole('searchbox', { name: 'Search' })).toHaveAttribute('placeholder', 'Search notifications');
    await expect(page.getByRole('button', { name: 'Filter' })).toHaveAttribute('aria-haspopup', 'dialog');
    await expect(page.getByRole('link', { name: 'Alert settings' })).toHaveAttribute('href', '/settings/alerts');
    await expectBoardRows(page);
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'alerts-list-1440');
    await expectNoAxeViolations(page);
  });

  test('focus rings on a row, Filter and the search box; tab order follows the page', async ({ page }) => {
    await page.goto('/notifications');
    await listLoaded(page);
    const order: string[] = [];
    for (let i = 0; i < 30 && order.length < 6; i++) {
      await page.keyboard.press('Tab');
      const name = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement;
        return el.closest('main') ? el.getAttribute('aria-label') ?? (el.textContent || el.id) : '';
      });
      if (name) order.push(name.slice(0, 20));
    }
    expect(order).toEqual(['Alert settings', 'alerts-q', 'Filter', 'Invoice for Lagoon H', 'The UAT response for', 'October payroll has ']);
    const ring = await page.evaluate(() => getComputedStyle(document.activeElement!).outlineStyle);
    expect(ring).toBe('solid');
  });
});

test.describe('list at 390 (SCR-15-mobile)', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('board: back link, title, search and Filter icon, rows, then Alert settings; no eyebrow or count', async ({ page }) => {
    await page.goto('/notifications');
    await listLoaded(page);
    await expect(page.getByRole('link', { name: '← Home' })).toHaveAttribute('href', '/');
    await expect(page.getByRole('searchbox', { name: 'Search' })).toBeVisible();
    const filter = page.getByRole('button', { name: 'Filter' });
    await expect(filter).toBeVisible();
    expect(await filter.boundingBox()).toMatchObject({ width: 44, height: 44 });
    await expectBoardRows(page);
    const settings = page.getByRole('link', { name: 'Alert settings' });
    const listBox = (await page.getByRole('list', { name: 'Alerts' }).boundingBox())!;
    expect((await settings.boundingBox())!.y).toBeGreaterThan(listBox.y + listBox.height);
    await expect(page.getByText('NOTIFICATIONS', { exact: true })).toHaveCount(0);
    await expect(page.getByText(/ALERTS?$/)).toHaveCount(0);
    expect(await noHorizontalScroll(page)).toBe(true);
    for (const target of [page.getByRole('link', { name: '← Home' }), filter, rows(page).nth(0).locator('a')]) {
      expect((await target.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    await shot(page, 'alerts-list-390');
    await expectNoAxeViolations(page);
  });

  test('Filter opens as a bottom sheet', async ({ page }) => {
    await page.goto('/notifications');
    await listLoaded(page);
    await page.getByRole('button', { name: 'Filter' }).click();
    const sheet = page.getByRole('dialog', { name: 'Filter' });
    await expect(sheet).toHaveClass(/psl-sheet/);
    const box = (await sheet.boundingBox())!;
    expect(Math.round(box.y + box.height)).toBe(PHONE.height);
    await expectNoAxeViolations(page);
  });
});

test.describe('search, Filter and opening at 1440', () => {
  test.use({ viewport: DESKTOP });

  test('search and Filter send only q, agent, unread and cursor and show what is returned', async ({ page }) => {
    const sent: URL[] = [];
    page.on('request', (r) => {
      const url = new URL(r.url());
      if (url.pathname === '/api/v1/notifications') sent.push(url);
    });
    await page.goto('/notifications');
    await listLoaded(page);
    await page.getByRole('searchbox', { name: 'Search' }).fill('payroll');
    await expect(rows(page)).toHaveCount(1);
    await expect(page.locator('.alerts-count')).toHaveText('1 ALERT');
    expect(new URL(page.url()).searchParams.get('q')).toBe('payroll');

    await page.getByRole('searchbox', { name: 'Search' }).fill('');
    await expect(rows(page)).toHaveCount(4);
    await page.getByRole('button', { name: 'Filter' }).click();
    const dialog = page.getByRole('dialog', { name: 'Filter' });
    await expectNoAxeViolations(page);
    await dialog.getByRole('radio', { name: 'Chidi' }).check();
    await dialog.getByRole('button', { name: 'Show results' }).click();
    await expect(rows(page)).toHaveCount(2);
    await expect(page.getByRole('button', { name: 'Filter · 1' })).toBeVisible();

    await page.getByRole('button', { name: 'Filter · 1' }).click();
    await expect(dialog.getByText('1 unread')).toBeVisible();
    await dialog.getByRole('checkbox', { name: /Unread only/ }).check();
    await dialog.getByRole('button', { name: 'Show results' }).click();
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).locator('.psl-tag')).toHaveText(/NEW$/);

    await page.getByRole('searchbox', { name: 'Search' }).fill('nothing like this');
    await expect(page.getByRole('heading', { name: 'No alerts match' })).toBeVisible();
    await page.getByRole('button', { name: 'Clear search and filters' }).click();
    await expect(rows(page)).toHaveCount(4);

    const keys = new Set(sent.flatMap((u) => [...u.searchParams.keys()]));
    expect([...keys].every((k) => ['q', 'agent', 'unread', 'cursor'].includes(k))).toBe(true);
    expect(sent.some((u) => u.searchParams.get('unread') === 'true')).toBe(true);
  });

  test('opening an unread alert marks it read once and goes to its work; read and restricted rows only navigate', async ({ page }) => {
    const posts: { url: string; csrf: string | undefined }[] = [];
    page.on('request', (r) => {
      if (r.method() === 'POST') posts.push({ url: new URL(r.url()).pathname, csrf: r.headers()['x-csrftoken'] });
    });
    await page.goto('/notifications');
    await listLoaded(page);
    await rows(page).nth(0).locator('a').click();
    await expect(page).toHaveURL(/\/work\/W-1001$/);
    expect(posts).toEqual([{ url: '/api/v1/notifications/N-0001/read', csrf: 'mock-csrf-finance_lead' }]);

    await page.goBack();
    await listLoaded(page);
    await expect(rows(page)).toHaveCount(4);
    await expect(rows(page).locator('.psl-tag')).toHaveCount(0);
    await page.getByRole('button', { name: 'Filter' }).click();
    await expect(page.getByRole('dialog').getByText('0 unread')).toBeVisible();
    await page.keyboard.press('Escape');

    await rows(page).nth(3).locator('a').click();
    await expect(page).toHaveURL(/\/work\/W-1006$/);
    await page.goBack();
    await listLoaded(page);
    await rows(page).nth(2).locator('a').click();
    await expect(page).toHaveURL(/\/work\/W-1099$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('You can’t open this work item');
    expect(await page.locator('main').textContent()).not.toMatch(/payroll|W-1099/i);
    expect(posts).toHaveLength(1);
  });
});

test.describe('list states', () => {
  for (const [label, viewport] of [
    ['1440', DESKTOP],
    ['390', PHONE],
  ] as const) {
    test(`empty at ${label}: No alerts yet., the settings link stays`, async ({ page, context }) => {
      await page.setViewportSize(viewport);
      await scenario(context, 'empty');
      await page.goto('/notifications');
      await listLoaded(page);
      await expect(page.locator('.psl-empty h3')).toHaveText('No alerts yet.');
      await expect(page.getByRole('link', { name: 'Alert settings' })).toBeVisible();
      if (viewport === DESKTOP) await expect(page.locator('.alerts-count')).toHaveText('0 ALERTS');
      await expectNoAxeViolations(page);
    });

    test(`error at ${label}: the card, then Try again shows the rows`, async ({ page }) => {
      await page.setViewportSize(viewport);
      const fail = (route: import('@playwright/test').Route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '404' } });
      await page.route('**/api/v1/notifications', fail);
      await page.goto('/notifications');
      const card = page.locator('main').getByRole('alert');
      await expect(card).toContainText('ERROR · COULDN’T LOAD');
      await expect(card).toContainText('We couldn’t load your alerts. Your work is safe; nothing was changed.');
      await expect(card).toContainText('Reference not_found for support.');
      await expectNoAxeViolations(page);
      await page.unroute('**/api/v1/notifications', fail);
      await card.getByRole('button', { name: 'Try again' }).click();
      await expect(rows(page)).toHaveCount(4);
    });
  }

  test('loading: status and no rows; with reduced motion nothing animates', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    await page.route('**/api/v1/notifications*', async (route) => {
      await gate;
      await route.continue();
    });
    await page.goto('/notifications');
    await expect(page.getByRole('status')).toHaveText('Loading…');
    await expect(rows(page)).toHaveCount(0);
    expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBe(0);
    release();
    await expect(rows(page)).toHaveCount(4);
  });

  test('a failure after a success says when the list was last loaded', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto('/notifications');
    await listLoaded(page);
    await page.route('**/api/v1/notifications?*', (route) => route.abort());
    await page.getByRole('searchbox', { name: 'Search' }).fill('lagoon');
    await expect(page.locator('main').getByRole('alert')).toContainText(/Last loaded \d\d:\d\d\. Reference network_error for support\./);
  });

  test('many: Show more loads rows 21-25 and goes; a failed Show more keeps the 20 rows', async ({ page, context }) => {
    await page.setViewportSize(DESKTOP);
    await scenario(context, 'many');
    await page.goto('/notifications');
    await listLoaded(page);
    await expect(rows(page)).toHaveCount(20);
    const fail = (route: import('@playwright/test').Route) => route.abort();
    await page.route('**/api/v1/notifications?cursor=*', fail);
    await page.getByRole('button', { name: 'Show more' }).click();
    await expect(page.getByText('We couldn’t load more. Nothing was changed.')).toBeVisible();
    await expect(rows(page)).toHaveCount(20);
    await page.unroute('**/api/v1/notifications?cursor=*', fail);
    await page.getByRole('button', { name: 'Show more' }).click();
    await expect(rows(page)).toHaveCount(25);
    await expect(page.getByRole('button', { name: 'Show more' })).toHaveCount(0);
  });

  test('401 on the list shows signed out with next=/notifications', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.route('**/api/v1/notifications*', (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '401' } }));
    await page.goto('/notifications');
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/accounts/login/?next=%2Fnotifications');
  });
});

test('bare: nothing a v4 backend lacks is shown; opening still works; settings shows the error card', async ({ page, context }) => {
  await page.setViewportSize(DESKTOP);
  await scenario(context, 'bare');
  await page.goto('/notifications');
  await listLoaded(page);
  await expect(rows(page).locator('.alerts-text')).toHaveText(BOARD_ROWS.map((r) => r[0]));
  await expect(rows(page).locator('.alerts-meta')).toHaveText(['Chidi · 10:42', /^Tola · \d\d:\d\d$/, /^Zainab · \d\d:\d\d$/, 'Chidi · yesterday']);
  await expect(page.getByRole('search')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Filter/ })).toHaveCount(0);
  expect(await page.locator('main').textContent()).not.toMatch(/ALERTS?|unread/);
  await rows(page).nth(0).locator('a').click();
  await expect(page).toHaveURL(/\/work\/W-1001$/);
  await page.goBack();
  await listLoaded(page);
  await expect(rows(page).nth(0).locator('.psl-tag')).toHaveText(/NEW$/);

  await page.goto('/settings/alerts');
  const card = page.locator('main').getByRole('alert');
  await expect(card).toContainText('We couldn’t load your alert settings. Your work is safe; nothing was changed.');
  await expect(card).toContainText('Reference not_found for support.');
  await expect(page.getByRole('table')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Save settings' })).toHaveCount(0);
});

test.describe('settings at 1440 (SCR-15-desktop-settings)', () => {
  test.use({ viewport: DESKTOP });

  test('board: matrix, digest and quiet hours, number card and Save', async ({ page }) => {
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await expect(page.getByText('SETTINGS / ALERTS')).toBeVisible();
    const table = page.getByRole('table', { name: 'Alerts for each kind of work' });
    await expect(table.getByRole('columnheader')).toHaveText(['WHEN', 'WHATSAPP', 'EMAIL', 'TIMING']);
    const body = table.locator('tbody tr');
    await expect(body.locator('td:first-child')).toHaveText(['A decision is waiting for me', 'Information is requested from me', 'Work I started is stuck', 'Work I started is verified', 'Everything else']);
    await expect(body.locator('td:last-child')).toHaveText(['Straight away', 'Straight away', 'Straight away', 'In the daily digest', 'In the daily digest']);
    const states = await body.evaluateAll((trs) => trs.map((tr) => [...tr.querySelectorAll('[role=switch]')].map((s) => s.getAttribute('aria-checked')).join('/')));
    expect(states).toEqual(['true/true', 'true/true', 'true/true', 'false/true', 'false/true']);
    await expect(page.getByLabel('Daily digest at')).toHaveValue('08:00');
    await expect(page.getByLabel('Daily digest at').locator('option')).toHaveText(['07:00', '08:00', '09:00']);
    await expect(page.getByLabel('Quiet hours').locator('option:checked')).toHaveText('20:00 to 07:00, and weekends');
    await expect(page.getByText('WhatsApp number')).toBeVisible();
    await expect(page.getByText('+234 803 *** 4412 · verified')).toBeVisible();
    await expect(page.getByText('Alerts never include amounts or client details beyond the name.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save settings' })).toBeVisible();
    await expect(sw(page, 'WhatsApp, A decision is waiting for me')).toHaveAttribute('aria-checked', 'true');
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'alerts-settings-1440');
    await expectNoAxeViolations(page);
  });

  test('Space toggles a switch; save sends the contract body; a reload shows the saved values', async ({ page }) => {
    const bodies: unknown[] = [];
    page.on('request', (r) => {
      if (r.method() === 'PUT') bodies.push({ csrf: r.headers()['x-csrftoken'], body: r.postDataJSON() });
    });
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    const stuck = sw(page, 'Email, Work I started is stuck');
    await stuck.focus();
    const ring = await stuck.evaluate((el) => getComputedStyle(el).outlineStyle);
    await page.keyboard.press('Space');
    await expect(stuck).toHaveAttribute('aria-checked', 'false');
    expect(['solid', 'auto']).toContain(ring);
    await page.getByLabel('Daily digest at').selectOption('09:00');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
    await expectNoAxeViolations(page);
    expect(bodies).toEqual([
      {
        csrf: 'mock-csrf-finance_lead',
        body: {
          channel: 'both',
          frequency: 'immediate',
          expected_revision: 3,
          events: [
            { key: 'decision_waiting', whatsapp: true, email: true },
            { key: 'info_requested', whatsapp: true, email: true },
            { key: 'work_stuck', whatsapp: true, email: false },
            { key: 'work_verified', whatsapp: false, email: true },
            { key: 'everything_else', whatsapp: false, email: true },
          ],
          digest_at: '09:00',
          quiet_hours: '20-07-weekends',
        },
      },
    ]);
    await page.reload();
    await settingsLoaded(page);
    await expect(stuck).toHaveAttribute('aria-checked', 'false');
    await expect(page.getByLabel('Daily digest at')).toHaveValue('09:00');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
    expect((bodies[1] as { body: { expected_revision: number } }).body.expected_revision).toBe(4);
  });

  test('stale: the newer version replaces the edits and the callout is focused; the next save works', async ({ page, context }) => {
    await scenario(context, 'stale');
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    const decision = sw(page, 'WhatsApp, A decision is waiting for me');
    await decision.click();
    await expect(decision).toHaveAttribute('aria-checked', 'false');
    await page.getByRole('button', { name: 'Save settings' }).click();
    const callout = page.locator('main').getByRole('alert');
    await expect(callout).toHaveText('Someone changed these settings since you opened them. This is the latest version; make your changes again.');
    await expect(callout).toBeFocused();
    await expect(decision).toHaveAttribute('aria-checked', 'true');
    await expect(sw(page, 'Email, Work I started is stuck')).toHaveAttribute('aria-checked', 'false');
    await expectNoAxeViolations(page);
    const put = page.waitForRequest((r) => r.method() === 'PUT');
    await page.getByRole('button', { name: 'Save settings' }).click();
    expect((await put).postDataJSON().expected_revision).toBe(4);
    await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
  });

  test('invalid: channel goes back as read and the 422 message shows, focused; the edits stay', async ({ page, context }) => {
    await scenario(context, 'invalid');
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await sw(page, 'Email, Everything else').click();
    const put = page.waitForRequest((r) => r.method() === 'PUT');
    await page.getByRole('button', { name: 'Save settings' }).click();
    expect((await put).postDataJSON().channel).toBe('sms');
    const callout = page.locator('main').getByRole('alert');
    await expect(callout).toHaveText('We couldn’t save your settings. Check these fields: channel.');
    await expect(callout).toBeFocused();
    await expect(sw(page, 'Email, Everything else')).toHaveAttribute('aria-checked', 'false');
    await expectNoAxeViolations(page);
  });

  test('locked: the reason shows and the switches never change', async ({ page, context }) => {
    await scenario(context, 'locked');
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await expect(page.getByText('Only HR can receive payroll alerts outside the app')).toBeVisible();
    const locked = sw(page, 'Email, Payroll problems');
    await expect(locked).toHaveAttribute('aria-disabled', 'true');
    await locked.dispatchEvent('click');
    await locked.focus();
    await page.keyboard.press('Space');
    await expect(locked).toHaveAttribute('aria-checked', 'false');
    await expectNoAxeViolations(page);
  });

  test('401 on the save shows signed out with next=/settings/alerts', async ({ page }) => {
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await page.route('**/api/v1/me/alert-preferences', (route) =>
      route.request().method() === 'PUT' ? route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '401' } }) : route.continue(),
    );
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/accounts/login/?next=%2Fsettings%2Falerts');
  });
});

test.describe('settings at 390 (SCR-15-mobile-settings)', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('phone: back link, four cards, quiet hours line and the pinned Save; no digest select or number', async ({ page, context }) => {
    await scenario(context, 'phone');
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await expect(page.getByRole('link', { name: '← Notifications' })).toHaveAttribute('href', '/notifications');
    const cards = page.locator('.alerts-eventcard');
    await expect(cards.locator('.alerts-eventlabel')).toHaveText(['A decision is waiting for me', 'Information is requested from me', 'Work I started is stuck', 'Work I started is verified']);
    await expect(cards.locator('.alerts-timing')).toHaveText(['Straight away', 'Straight away', 'Straight away', 'Daily digest']);
    await expect(cards.nth(3).getByRole('switch')).toHaveCount(2);
    await expect(sw(page, 'WhatsApp, Work I started is verified')).toHaveAttribute('aria-checked', 'false');
    await expect(page.getByText('Quiet hours 20:00 to 07:00 and weekends')).toBeVisible();
    await expect(page.getByLabel('Daily digest at')).toHaveCount(0);
    await expect(page.getByText('WhatsApp number')).toHaveCount(0);
    const save = page.getByRole('button', { name: 'Save settings' });
    const box = (await save.boundingBox())!;
    expect(Math.round(box.y + box.height + 18)).toBe(PHONE.height);
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'alerts-settings-390');
    await expectNoAxeViolations(page);
  });

  test('board on the phone: a fifth card, and the save has no digest_at or quiet_hours', async ({ page }) => {
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await expect(page.locator('.alerts-eventcard')).toHaveCount(5);
    const put = page.waitForRequest((r) => r.method() === 'PUT');
    await page.getByRole('button', { name: 'Save settings' }).click();
    const body = (await put).postDataJSON();
    expect(body).not.toHaveProperty('digest_at');
    expect(body).not.toHaveProperty('quiet_hours');
    await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
    await expectNoAxeViolations(page);
  });

  for (const [name, setup] of [
    ['stale', 'stale'],
    ['invalid', 'invalid'],
  ] as const) {
    test(`${name} at 390 has no axe violations`, async ({ page, context }) => {
      await scenario(context, setup);
      await page.goto('/settings/alerts');
      await settingsLoaded(page);
      await page.getByRole('button', { name: 'Save settings' }).click();
      await expect(page.locator('main').getByRole('alert')).toBeFocused();
      await expectNoAxeViolations(page);
    });
  }
});

test('direct loads render the headings (message targets, PMO-0-3)', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto('/notifications');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Notifications');
  await expect(page).toHaveTitle('Notifications · PSL Factory');
  await page.goto('/settings/alerts');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('How you’re alerted');
  await expect(page).toHaveTitle('Alert settings · PSL Factory');
});

test('the switch focus ring and the Save focus ring are visible', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto('/settings/alerts');
  await settingsLoaded(page);
  const rings: Record<string, string> = {};
  const targets: [string, Locator][] = [
    ['switch', sw(page, 'WhatsApp, A decision is waiting for me')],
    ['select', page.getByLabel('Daily digest at')],
    ['save', page.getByRole('button', { name: 'Save settings' })],
  ];
  for (const [name, target] of targets) {
    for (let i = 0; i < 40; i++) {
      if (await target.evaluate((el) => el === document.activeElement)) break;
      await page.keyboard.press('Tab');
    }
    await expect(target).toBeFocused();
    rings[name] = await target.evaluate((el) => `${getComputedStyle(el).outlineStyle} ${getComputedStyle(el).outlineWidth}`);
  }
  expect(rings).toEqual({ switch: 'solid 2px', select: 'solid 2px', save: 'solid 2px' });
});
