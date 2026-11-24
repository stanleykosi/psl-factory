import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Route } from '@playwright/test';

// Alerts (SCR-15 list and settings, F-61) against the contract mock in the live 1.24.0 shapes: 390 and 1440, axe WCAG 2.2 AA.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const A1 = 'a1'.padEnd(64, '0');

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

async function expectClearOfSaveBar(page: Page) {
  const callout = await page.locator('main .psl-callout').first().boundingBox();
  const bar = await page.locator('.alerts-footer').boundingBox();
  expect(callout!.y + callout!.height).toBeLessThanOrEqual(bar!.y);
}

const rows = (page: Page) => page.locator('.alerts-list > li');
const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const sw = (page: Page, name: string) => page.getByRole('switch', { name, exact: true });
const asStatus = (code: string) => (route: Route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': code } });

async function listLoaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: 'Notifications' })).toBeVisible();
}
async function settingsLoaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: 'How you’re alerted' })).toBeVisible();
}

const TITLES = ['Invoice ready for review', 'Project plan to sign off', 'Invoice review', 'Assistant reply', 'Milestone 2 is complete', 'Reminder: month-end close'];

async function expectBoardRows(page: Page) {
  await expect(rows(page)).toHaveCount(6);
  await expect(rows(page).locator('.alerts-text')).toHaveText(TITLES);
  await expect(page.locator('.alerts-grp')).toHaveText(['Needs you, 3', 'For information, 3']);
  // agent, avatar and time only where the alert has them: five rows have an agent, three have neither agent nor time
  await expect(rows(page).locator('.alerts-meta')).toHaveCount(4);
  await expect(rows(page).locator('.alerts-meta').first()).toHaveText(/^Chidi · (\d\d:\d\d|yesterday)$/);
  const imgs = await rows(page).locator('img').evaluateAll((els) => els.map((el) => [el.getAttribute('src'), (el as HTMLImageElement).naturalWidth > 0]));
  expect(imgs).toEqual(['chidi', 'tola', 'tola', 'zainab'].map((a) => [`/agents/${a}.png`, true]));
  await expect(page.locator('.alerts-summary')).toHaveText(/^Today, \d{1,2} [A-Z][a-z]{2}: 3 need you, \d+ new updates?, \d+ older unread\.$/);
  await expect(page.locator('.alerts-asof')).toHaveText(/^As of \d\d:\d\d WAT\. 6 loaded, 5 unread\.$/);
  await expect(page.locator('.alerts-list a')).toHaveCount(5);
  await expect(page.locator('.alerts-list a').nth(0)).toHaveAttribute('href', '/work/4103');
  await expect(page.locator('.alerts-list a[href*="/accounts/"]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Mark as read/ })).toHaveCount(1);
  await expect(rows(page).locator('.psl-tag')).toHaveCount(5);
}

async function expectNoToolbar(page: Page) {
  await expect(page.getByRole('searchbox')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Filter' })).toHaveCount(0);
  await expect(page.getByText(/\d+ ALERTS?\b/)).toHaveCount(0);
}

test.describe('list at 1440 (SCR-15-desktop)', () => {
  test.use({ viewport: DESKTOP });

  test('board: header, summary, both groups, six rows, as-of line; no search, filter or total', async ({ page }) => {
    await page.goto('/notifications');
    await listLoaded(page);
    const order = await page.locator('main').evaluate((el) => (el as HTMLElement).innerText);
    const marks = ['NOTIFICATIONS', 'Alert settings', 'Today,', 'NEEDS YOU', TITLES[0], 'FOR INFORMATION', TITLES[3], 'As of'];
    const at = marks.map((m) => order.indexOf(m));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    await expect(page.getByRole('link', { name: 'Alert settings' })).toHaveAttribute('href', '/settings/alerts');
    await expectBoardRows(page);
    await expectNoToolbar(page);
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'alerts-list-1440');
    await expectNoAxeViolations(page);
  });

  test('focus ring on a row; tab order follows the page', async ({ page }) => {
    await page.goto('/notifications');
    await listLoaded(page);
    const order: string[] = [];
    for (let i = 0; i < 30 && order.length < 3; i++) {
      await page.keyboard.press('Tab');
      const name = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement;
        return el.closest('main') ? (el.textContent ?? '') : '';
      });
      if (name) order.push(name.slice(0, 20));
    }
    expect(order[0]).toBe('Alert settings');
    expect(order[1]).toContain('Invoice ready for r');
    const ring = await page.evaluate(() => (getComputedStyle(document.activeElement!).outlineStyle !== 'none' ? getComputedStyle(document.activeElement!).outlineStyle : /rgb\(36, 89, 214\)|0px 0px 0px 2px inset/.test(getComputedStyle(document.activeElement!).boxShadow + getComputedStyle(document.activeElement!).borderTopColor + getComputedStyle(document.activeElement!).textDecorationColor) ? 'solid' : 'none'));
    expect(ring).toBe('solid');
  });
});

test.describe('list at 390 (SCR-15-mobile)', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('board: back link, title, rows, then Alert settings; no eyebrow, search, Filter or count', async ({ page }) => {
    await page.goto('/notifications');
    await listLoaded(page);
    await expect(page.getByRole('link', { name: '← Home' })).toHaveAttribute('href', '/');
    await expectBoardRows(page);
    await expectNoToolbar(page);
    const settings = page.getByRole('link', { name: 'Alert settings' });
    const last = (await rows(page).last().boundingBox())!;
    expect((await settings.boundingBox())!.y).toBeGreaterThan(last.y + last.height);
    await expect(page.getByText('NOTIFICATIONS', { exact: true })).toHaveCount(0);
    expect(await noHorizontalScroll(page)).toBe(true);
    for (const target of [page.getByRole('link', { name: '← Home' }), rows(page).nth(0).locator('a'), page.getByRole('button', { name: /^Mark as read/ })]) {
      expect((await target.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    await shot(page, 'alerts-list-390');
    await expectNoAxeViolations(page);
  });
});

test.describe('opening at 1440', () => {
  test.use({ viewport: DESKTOP });

  test('an unread alert sends one POST of {} with the CSRF token, then goes to its work; the bell drops by one', async ({ page }) => {
    const posts: { path: string; csrf?: string; body: string }[] = [];
    page.on('request', (r) => {
      if (r.method() === 'POST' && new URL(r.url()).pathname.startsWith('/api/v1/notifications/')) posts.push({ path: new URL(r.url()).pathname, csrf: r.headers()['x-csrftoken'], body: r.postData() ?? '' });
    });
    await page.goto('/notifications');
    await listLoaded(page);
    await rows(page).nth(0).locator('a').dblclick();
    await expect(page).toHaveURL(/\/work\/4103$/);
    expect(posts).toEqual([{ path: `/api/v1/notifications/${A1}/read`, csrf: 'mock-csrf-finance_lead', body: '{}' }]);
    await page.goBack();
    await listLoaded(page);
    await expect(page.locator('nav.psl-nav .shell-bellbadge')).toHaveText('4');
  });

  test('a row with no link has Mark as read, which marks it in place', async ({ page }) => {
    await page.goto('/notifications');
    await listLoaded(page);
    await page.getByRole('button', { name: /^Mark as read/ }).click();
    await expect(page.getByRole('button', { name: /^Mark as read/ })).toHaveCount(0);
    await expect(page.locator('.alerts-asof')).toHaveText(/6 loaded, 4 unread/);
    await expect(page).toHaveURL(/\/notifications$/);
  });

  test('a read alert only navigates', async ({ page }) => {
    const posts: string[] = [];
    page.on('request', (r) => r.method() === 'POST' && posts.push(r.url()));
    await page.goto('/notifications');
    await listLoaded(page);
    await rows(page).nth(4).locator('a').click();
    await expect(page).toHaveURL(/\/projects\//);
    expect(posts.filter((u) => u.includes('/notifications/'))).toEqual([]);
  });

  test('a failed mark-read leaves the row unread and says so; the work still opens', async ({ page }) => {
    await page.route('**/api/v1/notifications/*/read', (route) => route.fulfill({ status: 500, json: { code: 'server_error', message: 'Down.' } }));
    await page.goto('/notifications');
    await listLoaded(page);
    await rows(page).nth(0).locator('a').click();
    await expect(page).toHaveURL(/\/work\/4103$/);
  });
});

test.describe('list states', () => {
  for (const [label, viewport] of [['1440', DESKTOP], ['390', PHONE]] as const) {
    test.describe(`at ${label}`, () => {
      test.use({ viewport });

      test('empty: "No alerts", the summary and the settings link', async ({ page, context }) => {
        await scenario(context, 'empty');
        await page.goto('/notifications');
        await listLoaded(page);
        await expect(page.getByText('No alerts', { exact: true })).toBeVisible();
        await expect(page.locator('.alerts-summary')).toContainText('0 need you');
        await expect(page.getByRole('link', { name: 'Alert settings' })).toBeVisible();
        await expectNoAxeViolations(page);
      });

      test('error: the card, then Try again shows the rows', async ({ page }) => {
        const fail = asStatus('404');
        await page.route('**/api/v1/notifications?page=1', fail);
        await page.goto('/notifications');
        const card = page.getByRole('alert').filter({ hasText: 'We couldn’t load your alerts' });
        await expect(card).toContainText('We couldn’t load your alerts.');
        await expect(card).toContainText('Reference not_found for support.');
        await expectNoAxeViolations(page);
        await page.unroute('**/api/v1/notifications?page=1', fail);
        await page.getByRole('button', { name: 'Try again' }).click();
        await expect(rows(page)).toHaveCount(6);
      });
    });
  }

  test.use({ viewport: DESKTOP });

  test('loading: status and no rows; with reduced motion nothing animates', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    await page.route('**/api/v1/notifications?page=1', async (route) => {
      await gate;
      await route.continue();
    });
    await page.goto('/notifications');
    await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toBeVisible();
    await expect(rows(page)).toHaveCount(0);
    release();
    await expect(rows(page)).toHaveCount(6);
  });

  test('401 on the list shows signed out with next=/notifications', async ({ page }) => {
    await page.route('**/api/v1/notifications?page=1', asStatus('401'));
    await page.goto('/notifications');
    await expect(page.getByRole('link', { name: 'Sign in' }).first()).toHaveAttribute('href', '/sign-in?next=%2Fnotifications');
  });

  test('many: Load more loads 25, then 10, and goes; a failed page keeps the rows and offers retry', async ({ page, context }) => {
    await scenario(context, 'many');
    const requests: string[] = [];
    page.on('request', (r) => new URL(r.url()).pathname === '/api/v1/notifications' && r.method() === 'GET' && requests.push(new URL(r.url()).search));
    await page.goto('/notifications');
    await listLoaded(page);
    await expect(rows(page)).toHaveCount(25);
    await expect(page.locator('.alerts-asof')).toHaveText(/25 loaded, 40 unread/);
    const failing = (route: Route) => route.abort();
    await page.route('**/api/v1/notifications?page=2', failing);
    await page.getByRole('button', { name: 'Load more' }).click();
    await expect(page.getByText('Couldn’t load more alerts. Try again.')).toBeVisible();
    await expect(rows(page)).toHaveCount(25);
    await page.unroute('**/api/v1/notifications?page=2', failing);
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(rows(page)).toHaveCount(50);
    await page.getByRole('button', { name: 'Load more' }).click();
    await expect(rows(page)).toHaveCount(60);
    await expect(page.getByRole('button', { name: 'Load more' })).toHaveCount(0);
    expect(requests.filter((s) => s.includes('page=3'))).toEqual(['?page=3']);
    expect(await noHorizontalScroll(page)).toBe(true);
  });
});

test.describe('settings at 1440 (SCR-15-desktop-settings)', () => {
  test.use({ viewport: DESKTOP });

  test('board: two switches with Ready and Not ready yet, the receipts, Save; nothing else', async ({ page }) => {
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await expect(page.locator('.alerts-eyebrow')).toHaveText('SETTINGS / ALERTS');
    await expect(page.getByRole('switch')).toHaveCount(2);
    await expect(sw(page, 'Email')).toHaveAttribute('aria-checked', 'true');
    await expect(sw(page, 'WhatsApp')).toHaveAttribute('aria-checked', 'false');
    await expect(page.locator('.alerts-channelstate')).toHaveText(['Ready', 'Not ready yet']);
    await expect(page.locator('.alerts-receipt')).toHaveCount(4);
    await expect(page.locator('.alerts-receiptstate')).toHaveText(['Delivered', 'Not confirmed', 'Queued', 'Held']);
    await expect(page.getByRole('table')).toHaveCount(0);
    await expect(page.getByRole('combobox')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Save settings' })).toBeDisabled();
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'alerts-settings-1440');
    await expectNoAxeViolations(page);
  });

  test('Space toggles a switch; save sends exactly the three fields, shows Saved, and the next save uses the returned revision', async ({ page }) => {
    const bodies: unknown[] = [];
    page.on('request', (r) => r.method() === 'POST' && new URL(r.url()).pathname === '/api/v1/me/alert-preferences' && bodies.push(r.postDataJSON()));
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    const whatsapp = sw(page, 'WhatsApp');
    await whatsapp.focus();
    await page.keyboard.press('Space');
    await expect(whatsapp).toHaveAttribute('aria-checked', 'true');
    await expect(page.locator('#alerts-state-whatsapp')).toHaveText('Not ready yet: you will not receive anything on this channel until it is set up');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();
    await expect(page.locator('.alerts-receipt')).toHaveCount(4);
    await sw(page, 'Email').click();
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect.poll(() => bodies.length).toBe(2);
    expect(bodies).toEqual([
      { revision: 3, email_requested: true, whatsapp_requested: true },
      { revision: 4, email_requested: false, whatsapp_requested: true },
    ]);
    await page.reload();
    await settingsLoaded(page);
    await expect(sw(page, 'Email')).toHaveAttribute('aria-checked', 'false');
    await expect(sw(page, 'WhatsApp')).toHaveAttribute('aria-checked', 'true');
  });

  test('stale: the notice shows, nothing retries, and Reload brings the newer version', async ({ page, context }) => {
    await scenario(context, 'stale');
    let saves = 0;
    page.on('request', (r) => r.method() === 'POST' && new URL(r.url()).pathname === '/api/v1/me/alert-preferences' && (saves += 1));
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await sw(page, 'WhatsApp').click();
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByText('These settings changed elsewhere. Reload to see the latest.')).toBeVisible();
    expect(saves).toBe(1);
    await expectNoAxeViolations(page);
    await page.getByRole('button', { name: 'Reload' }).click();
    await expect(sw(page, 'Email')).toHaveAttribute('aria-checked', 'false');
    await expect(sw(page, 'WhatsApp')).toHaveAttribute('aria-checked', 'false');
    await expect(page.getByText(/changed elsewhere/)).toHaveCount(0);
    expect(saves).toBe(1);
  });

  test('invalid: the server message shows and the edit stays', async ({ page, context }) => {
    await scenario(context, 'invalid');
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await sw(page, 'WhatsApp').click();
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.locator('main .psl-callout')).toContainText('Check the settings and try again.');
    await expect(sw(page, 'WhatsApp')).toHaveAttribute('aria-checked', 'true');
  });

  test('401 on the save shows signed out with next=/settings/alerts', async ({ page }) => {
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await page.route('**/api/v1/me/alert-preferences', (route) => (route.request().method() === 'POST' ? asStatus('401')(route) : route.continue()));
    await sw(page, 'WhatsApp').click();
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByRole('link', { name: 'Sign in' }).first()).toHaveAttribute('href', '/sign-in?next=%2Fsettings%2Falerts');
  });

  test('the switch focus ring and the Save focus ring are visible (keyboard focus)', async ({ page }) => {
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    // A focus ring is a 2px outline, or the design system's inset 2px ring in the focus colour.
    const ring = (el: Element) => (getComputedStyle(el).outlineStyle !== 'none' ? `${getComputedStyle(el).outlineStyle} ${getComputedStyle(el).outlineWidth}` : /rgb\(36, 89, 214\)|0px 0px 0px 2px inset/.test(getComputedStyle(el).boxShadow + getComputedStyle(el).borderTopColor + getComputedStyle(el).textDecorationColor) ? 'solid 2px' : 'none');
    const reach = async (target: ReturnType<typeof sw>) => {
      for (let i = 0; i < 40; i++) {
        if (await target.evaluate((el) => el === document.activeElement)) break;
        await page.keyboard.press('Tab');
      }
      await expect(target).toBeFocused();
    };
    const whatsapp = sw(page, 'WhatsApp');
    await reach(whatsapp);
    const rings: Record<string, string> = { switch: await whatsapp.evaluate(ring) };
    await page.keyboard.press('Space');
    const save = page.getByRole('button', { name: 'Save settings' });
    await reach(save);
    rings.save = await save.evaluate(ring);
    expect(rings).toEqual({ switch: 'solid 2px', save: 'solid 2px' });
  });
});

test.describe('settings at 390 (SCR-15-mobile-settings)', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('phone: back link, two switches, receipts and the pinned Save', async ({ page }) => {
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await expect(page.getByRole('link', { name: '← Notifications' })).toHaveAttribute('href', '/notifications');
    await expect(page.getByRole('switch')).toHaveCount(2);
    for (const s of await page.getByRole('switch').all()) expect((await s.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(page.locator('.alerts-receipt')).toHaveCount(4);
    const save = page.getByRole('button', { name: 'Save settings' });
    const box = (await save.boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(844);
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(await noHorizontalScroll(page)).toBe(true);
    await shot(page, 'alerts-settings-390');
    await expectNoAxeViolations(page);
  });

  for (const setup of ['stale', 'invalid'] as const) {
    test(`${setup} at 390 shows the notice clear of the pinned Save bar, with no axe violations`, async ({ page, context }) => {
      await scenario(context, setup);
      await page.goto('/settings/alerts');
      await settingsLoaded(page);
      await sw(page, 'WhatsApp').click();
      await page.getByRole('button', { name: 'Save settings' }).click();
      await expect(page.locator('main .psl-callout[tabindex="-1"]')).toBeFocused();
      await expectClearOfSaveBar(page);
      await expectNoAxeViolations(page);
    });
  }

  test('a failed save at 390 shows the whole message above the pinned Save bar', async ({ page }) => {
    await page.goto('/settings/alerts');
    await settingsLoaded(page);
    await page.route('**/api/v1/me/alert-preferences', (route) =>
      route.request().method() === 'POST' ? route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ code: 'server_error', message: 'Try again in a moment.' }) }) : route.fallback(),
    );
    await sw(page, 'WhatsApp').click();
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.locator('main').getByRole('alert')).toContainText('We couldn’t save your settings. Nothing was changed.');
    await expectClearOfSaveBar(page);
  });
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
