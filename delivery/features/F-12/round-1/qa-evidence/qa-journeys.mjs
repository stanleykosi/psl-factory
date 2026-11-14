import { chromium } from '/Users/Hunchoo/psl-factory-worktrees/f-12/frontend/node_modules/playwright/index.mjs';
import { expect } from '/Users/Hunchoo/psl-factory-worktrees/f-12/frontend/node_modules/@playwright/test/index.mjs';
import AxeBuilder from '/Users/Hunchoo/psl-factory-worktrees/f-12/frontend/node_modules/@axe-core/playwright/dist/index.mjs';

const APP = 'http://localhost:4211';
const MOCK = 'http://127.0.0.1:4212';
const SHOTS = process.argv[2];
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const results = [];
const only = process.argv[3] ? process.argv[3].split(',') : null;

const browser = await chromium.launch();
async function ctx({ viewport = DESKTOP, scenario, persona, phone = false } = {}) {
  const c = await browser.newContext({ viewport, timezoneId: 'Africa/Lagos', ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  const cookies = [];
  if (scenario) cookies.push({ name: 'psl_mock_alerts', value: scenario, domain: 'localhost', path: '/' });
  if (persona) cookies.push({ name: 'psl_mock_persona', value: persona, domain: 'localhost', path: '/' });
  if (cookies.length) await c.addCookies(cookies);
  const page = await c.newPage();
  page.setDefaultTimeout(8000);
  return { c, page };
}
async function reset() {
  const r = await fetch(`${MOCK}/__mock/reset`, { method: 'POST' });
  if (r.status !== 204) throw new Error('reset ' + r.status);
}
async function run(name, fn) {
  if (only && !only.some((o) => name.startsWith(o))) return;
  const notes = [];
  try {
    await fn(notes);
    results.push(['PASS', name, notes.join(' | ')]);
  } catch (e) {
    results.push(['FAIL', name, (e.message || String(e)).split('\n').slice(0, 6).join(' ') + (notes.length ? ' || ' + notes.join(' | ') : '')]);
  }
}
const rows = (page) => page.getByRole('list', { name: 'Alerts' }).locator(':scope > li');
const sw = (page, name) => page.getByRole('switch', { name });
async function listLoaded(page) {
  await expect(page.getByRole('heading', { level: 1, name: 'Notifications' })).toBeVisible();
  await expect(page.locator('main').getByRole('status')).toHaveCount(0);
}
async function settingsLoaded(page) {
  await expect(page.getByRole('heading', { level: 1, name: 'How you’re alerted' })).toBeVisible();
  await expect(page.locator('main').getByRole('status')).toHaveCount(0);
}
async function axe(page, label, notes) {
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const v = r.violations.map((x) => `${x.id}:${x.nodes.length}`);
  notes.push(`axe ${label}: ${v.length ? v.join(',') : '0 violations'}`);
  if (v.length) throw new Error(`axe ${label}: ${v.join(',')}`);
}
const noHScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const shot = (page, n) => page.screenshot({ path: `${SHOTS}/${n}.png`, fullPage: true });

// ---------- LIST ----------
await run('L1 board list 1440', async (n) => {
  await reset();
  const { c, page } = await ctx();
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  await expect(page).toHaveTitle('Notifications · PSL Factory');
  await expect(rows(page).locator('.alerts-text')).toHaveText([
    'Invoice for Lagoon Health is waiting for your review', 'The UAT response for Lagoon Health is due tomorrow',
    'October payroll has 2 problems for HR', 'Milestone 1 invoice was verified']);
  await expect(rows(page).locator('.alerts-meta')).toHaveText([
    'Chidi · WhatsApp and email · 10:42', 'Tola · Email · 09:00 daily digest', 'Zainab · In app only (you are not HR)', 'Chidi · In app · yesterday']);
  await expect(page.locator('.alerts-count')).toHaveText('4 ALERTS');
  await expect(rows(page).locator('.psl-tag')).toHaveCount(1);
  const hrefs = await rows(page).locator('a').evaluateAll((as) => as.map((a) => a.getAttribute('href')));
  n.push('hrefs ' + hrefs.join(','));
  expect(hrefs).toEqual(['/work/W-1001', '/work/W-1002', '/work/W-1099', '/work/W-1006']);
  expect(await noHScroll(page)).toBe(true);
  await axe(page, 'list default 1440', n);
  await shot(page, 'list-1440');
  await c.close();
});

await run('L2 search/filter 1440, params only v7', async (n) => {
  await reset();
  const { c, page } = await ctx();
  const qs = [];
  page.on('request', (r) => { const u = new URL(r.url()); if (u.pathname === '/api/v1/notifications') qs.push(u.search); });
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  await page.getByRole('searchbox', { name: 'Search' }).fill('payroll');
  await expect(rows(page)).toHaveCount(1);
  await expect(page.locator('.alerts-count')).toHaveText('1 ALERT');
  await expect(page).toHaveURL(/q=payroll/);
  await page.getByRole('searchbox', { name: 'Search' }).fill('');
  await expect(rows(page)).toHaveCount(4);
  await page.getByRole('button', { name: 'Filter' }).click();
  const dlg = page.getByRole('dialog', { name: 'Filter' });
  await axe(page, 'filter open 1440', n);
  await dlg.getByRole('radio', { name: 'Chidi' }).check();
  await dlg.getByRole('button', { name: 'Show results' }).click();
  await expect(rows(page)).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Filter · 1' })).toBeVisible();
  await page.getByRole('button', { name: 'Filter · 1' }).click();
  await expect(dlg.getByText('1 unread')).toBeVisible();
  await dlg.getByRole('checkbox', { name: /Unread only/ }).check();
  await dlg.getByRole('button', { name: 'Show results' }).click();
  await expect(rows(page)).toHaveCount(1);
  await expect(page).toHaveURL(/agent=chidi/);
  await expect(page).toHaveURL(/unread=1/);
  // Esc discards a draft
  await page.getByRole('button', { name: 'Filter · 2' }).click();
  await dlg.getByRole('radio', { name: 'Tola' }).check();
  await page.keyboard.press('Escape');
  await expect(dlg).toHaveCount(0);
  await expect(page).toHaveURL(/agent=chidi/);
  await expect(page.getByRole('button', { name: 'Filter · 2' })).toBeFocused();
  await page.getByRole('searchbox', { name: 'Search' }).fill('nothing like this');
  await expect(page.getByRole('heading', { name: 'No alerts match' })).toBeVisible();
  await axe(page, 'no results 1440', n);
  await page.getByRole('button', { name: 'Clear search and filters' }).click();
  await expect(rows(page)).toHaveCount(4);
  await expect(page).toHaveURL(`${APP}/notifications`);
  const keys = new Set(qs.flatMap((s) => [...new URLSearchParams(s).keys()]));
  n.push('query keys sent: ' + [...keys].join(','));
  for (const k of keys) expect(['q', 'agent', 'unread', 'cursor']).toContain(k);
  const unreadVals = qs.map((s) => new URLSearchParams(s).get('unread')).filter(Boolean);
  expect(unreadVals.every((v) => v === 'true')).toBe(true);
  expect(qs.some((s) => new URLSearchParams(s).get('q') === '')).toBe(false);
  const storage = await page.evaluate(() => [localStorage.length, sessionStorage.length]);
  n.push('storage ' + storage.join('/'));
  expect(storage).toEqual([0, 0]);
  await c.close();
});

await run('L3 URL state: direct load with filters, unknown agent ignored', async (n) => {
  await reset();
  const { c, page } = await ctx();
  const qs = [];
  page.on('request', (r) => { const u = new URL(r.url()); if (u.pathname === '/api/v1/notifications') qs.push(u.search); });
  await page.goto(`${APP}/notifications?q=lagoon&agent=chidi`);
  await listLoaded(page);
  await expect(rows(page)).toHaveCount(1);
  await expect(page.getByRole('searchbox', { name: 'Search' })).toHaveValue('lagoon');
  await page.goto(`${APP}/notifications?agent=bogus&unread=yes`);
  await listLoaded(page);
  await expect(rows(page)).toHaveCount(4);
  await expect(page.getByRole('button', { name: 'Filter' })).toBeVisible();
  n.push('queries ' + qs.join(' ; '));
  expect(qs.at(-1)).toBe('');
  await c.close();
});

await run('L4 open unread alert -> POST read w/ CSRF -> /work, back shows read', async (n) => {
  await reset();
  const { c, page } = await ctx();
  const posts = [];
  page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/notifications/')) posts.push([r.url().replace(APP, ''), r.headers()['x-csrftoken']]); });
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  await rows(page).nth(0).locator('a').click();
  await expect(page).toHaveURL(/\/work\/W-1001$/);
  n.push('posts ' + JSON.stringify(posts));
  expect(posts).toEqual([['/api/v1/notifications/N-0001/read', 'mock-csrf-finance_lead']]);
  await page.goBack();
  await listLoaded(page);
  await expect(rows(page).locator('.psl-tag')).toHaveCount(0);
  await page.getByRole('button', { name: 'Filter' }).click();
  await expect(page.getByRole('dialog').getByText('0 unread')).toBeVisible();
  await page.keyboard.press('Escape');
  await rows(page).nth(3).locator('a').click();
  await expect(page).toHaveURL(/\/work\/W-1006$/);
  expect(posts.length).toBe(1);
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  await rows(page).nth(2).locator('a').click();
  await expect(page).toHaveURL(/\/work\/W-1099$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('You can’t open this work item');
  const main = await page.locator('main').textContent();
  expect(main).not.toMatch(/payroll/i);
  expect(posts.length).toBe(1);
  await c.close();
});

await run('L5 mark-read fails (500, then network) -> still navigates, NEW stays, no retry', async (n) => {
  for (const mode of ['500', 'abort']) {
    await reset();
    const { c, page } = await ctx();
    let posts = 0;
    await page.route('**/api/v1/notifications/*/read', (route) => {
      posts++;
      return mode === 'abort' ? route.abort() : route.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"x"}' });
    });
    await page.goto(`${APP}/notifications`);
    await listLoaded(page);
    await rows(page).nth(0).locator('a').click();
    await expect(page).toHaveURL(/\/work\/W-1001$/);
    await page.waitForTimeout(500);
    await page.goBack();
    await listLoaded(page);
    await expect(rows(page).nth(0).locator('.psl-tag')).toHaveText(/NEW$/);
    n.push(`${mode}: posts=${posts}`);
    expect(posts).toBe(1);
    await c.close();
  }
});

await run('L6 modifier click opens new tab without mark-read', async (n) => {
  await reset();
  const { c, page } = await ctx();
  let posts = 0;
  page.on('request', (r) => { if (r.method() === 'POST') posts++; });
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  const popup = c.waitForEvent('page');
  await rows(page).nth(0).locator('a').click({ modifiers: ['Meta'] });
  const p2 = await popup;
  await p2.waitForLoadState();
  n.push('new tab ' + p2.url().replace(APP, '') + ' posts=' + posts);
  expect(p2.url()).toContain('/work/W-1001');
  expect(posts).toBe(0);
  await expect(page).toHaveURL(/\/notifications$/);
  await c.close();
});

await run('L7 wrong user (pm persona) sees only own alerts in browser', async (n) => {
  await reset();
  const { c, page } = await ctx({ persona: 'pm' });
  const ids = [];
  page.on('response', async (r) => { if (new URL(r.url()).pathname === '/api/v1/notifications') { try { ids.push(...(await r.json()).items.map((i) => i.id)); } catch {} } });
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  const texts = await rows(page).locator('.alerts-text').allTextContents();
  n.push('pm ids ' + ids.join(',') + ' texts ' + texts.join(' / '));
  expect(ids.every((i) => i.startsWith('N-01'))).toBe(true);
  expect(texts.some((t) => t.includes('Lagoon Health is waiting'))).toBe(false);
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  const main = await page.locator('main').textContent();
  expect(main).toContain('+234 805 *** 1180');
  expect(main).not.toContain('4412');
  await c.close();
});

await run('L8 empty list 1440 + 390', async (n) => {
  for (const [vp, phone] of [[DESKTOP, false], [PHONE, true]]) {
    const { c, page } = await ctx({ scenario: 'empty', viewport: vp, phone });
    await page.goto(`${APP}/notifications`);
    await listLoaded(page);
    await expect(page.locator('.psl-empty h3')).toHaveText('No alerts yet.');
    await expect(page.getByRole('link', { name: 'Alert settings' })).toBeVisible();
    if (!phone) await expect(page.locator('.alerts-count')).toHaveText('0 ALERTS');
    expect(await noHScroll(page)).toBe(true);
    await axe(page, `empty ${vp.width}`, n);
    if (phone) await shot(page, 'empty-390');
    await c.close();
  }
});

await run('L9 list errors: 404, 403, 500, try again; last loaded after success', async (n) => {
  await reset();
  for (const code of ['404', '403']) {
    const { c, page } = await ctx();
    const h = (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': code } });
    await page.route('**/api/v1/notifications', h);
    await page.goto(`${APP}/notifications`);
    const card = page.locator('main').getByRole('alert');
    await expect(card).toContainText('ERROR · COULDN’T LOAD');
    await expect(card).toContainText('We couldn’t load your alerts. Your work is safe; nothing was changed.');
    n.push(`${code}: ` + (await card.innerText()).replace(/\n+/g, ' / '));
    await axe(page, `list error ${code}`, n);
    await page.unroute('**/api/v1/notifications', h);
    await card.getByRole('button', { name: 'Try again' }).click();
    await expect(rows(page)).toHaveCount(4);
    await c.close();
  }
  const { c, page } = await ctx();
  await page.route('**/api/v1/notifications', (r) => r.fulfill({ status: 503, contentType: 'text/html', body: '<html>bad gateway</html>' }));
  await page.goto(`${APP}/notifications`);
  const card = page.locator('main').getByRole('alert');
  await expect(card).toContainText('We couldn’t load your alerts.');
  n.push('503 html: ' + (await card.innerText()).replace(/\n+/g, ' / '));
  await page.unroute('**/api/v1/notifications');
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  await page.route('**/api/v1/notifications?*', (r) => r.abort());
  await page.getByRole('searchbox', { name: 'Search' }).fill('lagoon');
  await expect(card).toContainText(/Last loaded \d\d:\d\d\./);
  n.push('after-success: ' + (await card.innerText()).replace(/\n+/g, ' / '));
  await c.close();
});

await run('L10 401 list -> signed out with next incl search', async (n) => {
  const { c, page } = await ctx();
  await page.route('**/api/v1/notifications*', (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '401' } }));
  await page.goto(`${APP}/notifications?q=lagoon`);
  const href = await page.getByRole('link', { name: 'Sign in' }).getAttribute('href');
  n.push('href ' + href);
  expect(href).toBe('/accounts/login/?next=%2Fnotifications%3Fq%3Dlagoon');
  await c.close();
});

await run('L11 many: show more, failed show more', async (n) => {
  await reset();
  const { c, page } = await ctx({ scenario: 'many' });
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  await expect(rows(page)).toHaveCount(20);
  await page.route('**/api/v1/notifications?cursor=*', (r) => r.abort());
  await page.getByRole('button', { name: 'Show more' }).click();
  await expect(page.getByText('We couldn’t load more. Nothing was changed.')).toBeVisible();
  await expect(rows(page)).toHaveCount(20);
  await page.unroute('**/api/v1/notifications?cursor=*');
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(rows(page)).toHaveCount(25);
  await expect(page.getByRole('button', { name: 'Show more' })).toHaveCount(0);
  await expect(page.getByText('We couldn’t load more. Nothing was changed.')).toHaveCount(0);
  const ids = await rows(page).locator('a').evaluateAll((as) => as.map((a) => a.getAttribute('href')));
  n.push('unique hrefs ' + new Set(ids).size + '/25');
  await c.close();
});

await run('L12 bare (v4 backend): no invented fields, settings error card', async (n) => {
  await reset();
  const { c, page } = await ctx({ scenario: 'bare' });
  await page.goto(`${APP}/notifications?q=payroll&agent=chidi`);
  await listLoaded(page);
  await expect(rows(page)).toHaveCount(4);
  await expect(page).toHaveURL(`${APP}/notifications`);
  await expect(page.getByRole('search')).toHaveCount(0);
  const t = await page.locator('main').textContent();
  expect(t).not.toMatch(/ALERTS?|unread/);
  n.push('meta ' + (await rows(page).locator('.alerts-meta').allTextContents()).join(' / '));
  await rows(page).nth(0).locator('a').click();
  await expect(page).toHaveURL(/\/work\/W-1001$/);
  await page.goBack();
  await listLoaded(page);
  await expect(rows(page).nth(0).locator('.psl-tag')).toHaveText(/NEW$/);
  await page.goto(`${APP}/settings/alerts`);
  const card = page.locator('main').getByRole('alert');
  await expect(card).toContainText('We couldn’t load your alert settings. Your work is safe; nothing was changed.');
  await expect(card).toContainText('Reference not_found for support.');
  await expect(page.getByRole('button', { name: 'Save settings' })).toHaveCount(0);
  await expect(page.getByRole('switch')).toHaveCount(0);
  await axe(page, 'settings error', n);
  await c.close();
});

await run('L13 phone list 390: order, sheet, targets, open alert', async (n) => {
  await reset();
  const { c, page } = await ctx({ viewport: PHONE, phone: true });
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  await expect(page.getByRole('link', { name: '← Home' })).toHaveAttribute('href', '/');
  await expect(page.getByText('NOTIFICATIONS', { exact: true })).toHaveCount(0);
  await expect(page.locator('.alerts-count')).toHaveCount(0);
  const list = await page.getByRole('list', { name: 'Alerts' }).boundingBox();
  const set = await page.getByRole('link', { name: 'Alert settings' }).boundingBox();
  expect(set.y).toBeGreaterThan(list.y + list.height - 1);
  expect(await noHScroll(page)).toBe(true);
  const fb = await page.getByRole('button', { name: 'Filter' }).boundingBox();
  n.push(`filter btn ${fb.width}x${fb.height}`);
  expect(fb.width >= 44 && fb.height >= 44).toBe(true);
  await axe(page, 'list 390', n);
  await page.getByRole('button', { name: 'Filter' }).click();
  const sheet = page.getByRole('dialog', { name: 'Filter' });
  const sb = await sheet.boundingBox();
  n.push(`sheet y=${Math.round(sb.y)} h=${Math.round(sb.height)} bottom=${Math.round(sb.y + sb.height)}`);
  expect(Math.round(sb.y + sb.height)).toBeGreaterThanOrEqual(843);
  await axe(page, 'filter sheet 390', n);
  await shot(page, 'filter-sheet-390');
  await sheet.getByRole('radio', { name: 'Zainab' }).check();
  await sheet.getByRole('button', { name: 'Show results' }).click();
  await expect(rows(page)).toHaveCount(1);
  await page.goto(`${APP}/notifications`);
  await listLoaded(page);
  await rows(page).nth(0).locator('a').tap();
  await expect(page).toHaveURL(/\/work\/W-1001$/);
  await c.close();
});

// ---------- SETTINGS ----------
const puts = (page) => { const b = []; page.on('request', (r) => { if (r.method() === 'PUT') b.push({ csrf: r.headers()['x-csrftoken'], body: r.postDataJSON() }); }); return b; };

await run('S1 board settings 1440: content, save body, reload, second revision', async (n) => {
  await reset();
  const { c, page } = await ctx();
  const b = puts(page);
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await expect(page).toHaveTitle('Alert settings · PSL Factory');
  await expect(page.getByText('SETTINGS / ALERTS')).toBeVisible();
  await expect(page.getByLabel('Daily digest at')).toHaveValue('08:00');
  await expect(page.getByText('+234 803 *** 4412 · verified')).toBeVisible();
  await axe(page, 'settings 1440', n);
  const stuck = sw(page, 'Email, Work I started is stuck');
  await stuck.focus();
  await page.keyboard.press('Enter');
  await expect(stuck).toHaveAttribute('aria-checked', 'false');
  await page.getByLabel('Daily digest at').selectOption('09:00');
  await page.getByLabel('Quiet hours').selectOption('none');
  const save = page.getByRole('button', { name: 'Save settings' });
  await save.dblclick();
  await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
  await page.waitForTimeout(400);
  n.push('dblclick PUTs=' + b.length);
  expect(b.length).toBe(1);
  expect(b[0].csrf).toBe('mock-csrf-finance_lead');
  expect(b[0].body).toEqual({ channel: 'both', frequency: 'immediate', expected_revision: 3,
    events: [{ key: 'decision_waiting', whatsapp: true, email: true }, { key: 'info_requested', whatsapp: true, email: true },
      { key: 'work_stuck', whatsapp: true, email: false }, { key: 'work_verified', whatsapp: false, email: true },
      { key: 'everything_else', whatsapp: false, email: true }], digest_at: '09:00', quiet_hours: 'none' });
  expect(JSON.stringify(b[0].body)).not.toMatch(/4412|masked|label|timing/);
  await axe(page, 'saved 1440', n);
  // notice clears on next edit
  await sw(page, 'WhatsApp, Everything else').click();
  await expect(page.getByText('Your alert settings are saved.')).toHaveCount(0);
  await page.reload();
  await settingsLoaded(page);
  await expect(stuck).toHaveAttribute('aria-checked', 'false');
  await expect(sw(page, 'WhatsApp, Everything else')).toHaveAttribute('aria-checked', 'false');
  await expect(page.getByLabel('Daily digest at')).toHaveValue('09:00');
  await expect(page.getByLabel('Quiet hours')).toHaveValue('none');
  await save.click();
  await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
  n.push('2nd expected_revision=' + b[1].body.expected_revision);
  expect(b[1].body.expected_revision).toBe(4);
  // third save right away without reload must carry revision 5 (state replaced by PUT body)
  await save.click();
  await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
  await page.waitForTimeout(300);
  n.push('3rd expected_revision=' + b[2]?.body.expected_revision);
  expect(b[2].body.expected_revision).toBe(5);
  await c.close();
});

await run('S2 stale 409 -> re-read, edits dropped, focused callout; next save ok', async (n) => {
  await reset();
  const { c, page } = await ctx({ scenario: 'stale' });
  const b = puts(page);
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  const d = sw(page, 'WhatsApp, A decision is waiting for me');
  await d.click();
  await page.getByLabel('Daily digest at').selectOption('07:00');
  await page.getByRole('button', { name: 'Save settings' }).click();
  const callout = page.locator('main').getByRole('alert');
  await expect(callout).toHaveText('Someone changed these settings since you opened them. This is the latest version; make your changes again.');
  await expect(callout).toBeFocused();
  await expect(d).toHaveAttribute('aria-checked', 'true');
  await expect(sw(page, 'Email, Work I started is stuck')).toHaveAttribute('aria-checked', 'false');
  await expect(page.getByLabel('Daily digest at')).toHaveValue('08:00');
  await axe(page, 'stale 1440', n);
  await page.getByRole('button', { name: 'Save settings' }).click();
  await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
  n.push('revisions ' + b.map((x) => x.body.expected_revision).join(','));
  expect(b.map((x) => x.body.expected_revision)).toEqual([3, 4]);
  await c.close();
});

await run('S3 stale 409 whose re-read fails -> settings error card', async (n) => {
  await reset();
  const { c, page } = await ctx({ scenario: 'stale' });
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await page.route('**/api/v1/me/alert-preferences', (r) => r.request().method() === 'GET' ? r.abort() : r.continue());
  await sw(page, 'WhatsApp, A decision is waiting for me').click();
  await page.getByRole('button', { name: 'Save settings' }).click();
  const card = page.locator('main').getByRole('alert');
  await expect(card).toContainText('We couldn’t load your alert settings.');
  await expect(page.getByRole('button', { name: 'Save settings' })).toHaveCount(0);
  n.push((await card.innerText()).replace(/\n+/g, ' / '));
  await c.close();
});

await run('S4 invalid 422: sms echoed, message shown, edits kept', async (n) => {
  await reset();
  const { c, page } = await ctx({ scenario: 'invalid' });
  const b = puts(page);
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await sw(page, 'Email, Everything else').click();
  await page.getByRole('button', { name: 'Save settings' }).click();
  const callout = page.locator('main').getByRole('alert');
  await expect(callout).toHaveText('We couldn’t save your settings. Check these fields: channel.');
  await expect(callout).toBeFocused();
  await expect(sw(page, 'Email, Everything else')).toHaveAttribute('aria-checked', 'false');
  expect(b[0].body.channel).toBe('sms');
  await axe(page, 'invalid 1440', n);
  await c.close();
});

await run('S5 locked event: aria-disabled, no change, sent as read', async (n) => {
  await reset();
  const { c, page } = await ctx({ scenario: 'locked' });
  const b = puts(page);
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await expect(page.getByText('Only HR can receive payroll alerts outside the app')).toBeVisible();
  for (const nm of ['WhatsApp, Payroll problems', 'Email, Payroll problems']) {
    const l = sw(page, nm);
    await expect(l).toHaveAttribute('aria-disabled', 'true');
    await l.click({ force: true });
    await l.focus(); await page.keyboard.press('Space'); await page.keyboard.press('Enter');
    await expect(l).toHaveAttribute('aria-checked', 'false');
  }
  await page.getByRole('button', { name: 'Save settings' }).click();
  await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
  const ev = b[0].body.events.find((e) => e.key === 'payroll_problems');
  n.push('locked sent ' + JSON.stringify(ev));
  expect(ev).toEqual({ key: 'payroll_problems', whatsapp: false, email: false });
  await axe(page, 'locked 1440', n);
  await c.close();
});

await run('S6 save failures: 500, network, 403 csrf -> edits kept, no auto retry, manual retry works', async (n) => {
  await reset();
  const { c, page } = await ctx();
  let count = 0; let mode = '500';
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await page.route('**/api/v1/me/alert-preferences', async (r) => {
    if (r.request().method() !== 'PUT') return r.continue();
    count++;
    if (mode === '500') return r.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"The server had a problem."}' });
    if (mode === 'abort') return r.abort();
    if (mode === 'csrf') return r.continue({ headers: { ...r.request().headers(), 'x-csrftoken': 'mock-csrf-pm' } });
    return r.continue();
  });
  const d = sw(page, 'WhatsApp, A decision is waiting for me');
  await d.click();
  const save = page.getByRole('button', { name: 'Save settings' });
  const callout = page.locator('main').getByRole('alert');
  for (const m of ['500', 'abort', 'csrf']) {
    mode = m; const before = count;
    await save.click();
    await expect(callout).toContainText('We couldn’t save your settings. Nothing was changed.');
    await page.waitForTimeout(1200);
    n.push(`${m}: "${(await callout.innerText()).replace(/\n+/g, ' ')}" PUTs=${count - before}`);
    expect(count - before).toBe(1);
    await expect(d).toHaveAttribute('aria-checked', 'false');
    await expect(save).toBeEnabled();
  }
  await axe(page, 'save problem 1440', n);
  mode = 'ok';
  await save.click();
  await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
  await page.reload();
  await settingsLoaded(page);
  await expect(d).toHaveAttribute('aria-checked', 'false');
  await c.close();
});

await run('S7 401 on settings read and on save -> signed out next=/settings/alerts', async (n) => {
  const { c, page } = await ctx();
  await page.route('**/api/v1/me/alert-preferences', (r) => r.continue({ headers: { ...r.request().headers(), 'x-mock-scenario': '401' } }));
  await page.goto(`${APP}/settings/alerts`);
  const href1 = await page.getByRole('link', { name: 'Sign in' }).getAttribute('href');
  await page.unroute('**/api/v1/me/alert-preferences');
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await page.route('**/api/v1/me/alert-preferences', (r) => r.request().method() === 'PUT' ? r.continue({ headers: { ...r.request().headers(), 'x-mock-scenario': '401' } }) : r.continue());
  await page.getByRole('button', { name: 'Save settings' }).click();
  const href2 = await page.getByRole('link', { name: 'Sign in' }).getAttribute('href');
  n.push(`read ${href1}; save ${href2}`);
  expect(href1).toBe('/accounts/login/?next=%2Fsettings%2Falerts');
  expect(href2).toBe('/accounts/login/?next=%2Fsettings%2Falerts');
  await c.close();
});

await run('S8 settings 200 without events -> missing_events card', async (n) => {
  const { c, page } = await ctx();
  await page.route('**/api/v1/me/alert-preferences', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"channel":"both","frequency":"immediate","revision":1}' }));
  await page.goto(`${APP}/settings/alerts`);
  const card = page.locator('main').getByRole('alert');
  await expect(card).toContainText('Reference missing_events for support.');
  await expect(page.getByRole('button', { name: 'Save settings' })).toHaveCount(0);
  await card.getByRole('button', { name: 'Try again' }).click();
  await expect(card).toContainText('missing_events');
  await page.unroute('**/api/v1/me/alert-preferences');
  await card.getByRole('button', { name: 'Try again' }).click();
  await settingsLoaded(page);
  n.push('try again recovers');
  await c.close();
});

await run('S9 phone settings 390 (phone scenario): cards, quiet line, pinned save, body', async (n) => {
  await reset();
  const { c, page } = await ctx({ scenario: 'phone', viewport: PHONE, phone: true });
  const b = puts(page);
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await expect(page.getByRole('link', { name: '← Notifications' })).toHaveAttribute('href', '/notifications');
  await expect(page.locator('.alerts-eventcard')).toHaveCount(4);
  await expect(page.getByText('Quiet hours 20:00 to 07:00 and weekends')).toBeVisible();
  await expect(page.getByLabel('Daily digest at')).toHaveCount(0);
  await expect(page.getByText('WhatsApp number')).toHaveCount(0);
  expect(await noHScroll(page)).toBe(true);
  const save = page.getByRole('button', { name: 'Save settings' });
  const sb = await save.boundingBox();
  n.push(`save y=${Math.round(sb.y)} h=${Math.round(sb.height)}`);
  expect(sb.y + sb.height).toBeLessThanOrEqual(844);
  expect(sb.y).toBeGreaterThan(700);
  const swb = await sw(page, 'Email, Work I started is stuck').boundingBox();
  n.push(`switch box ${Math.round(swb.width)}x${Math.round(swb.height)}`);
  await axe(page, 'settings 390', n);
  await shot(page, 'settings-phone-390');
  await sw(page, 'Email, Work I started is stuck').tap();
  await save.tap();
  await expect(page.getByRole('status')).toHaveText('Your alert settings are saved.');
  n.push('phone body keys ' + Object.keys(b[0].body).join(','));
  expect(b[0].body.digest_at).toBeUndefined();
  expect(b[0].body.quiet_hours).toBeUndefined();
  expect(b[0].body.events.length).toBe(4);
  await axe(page, 'saved 390', n);
  await c.close();
});

await run('S10 phone settings 390 board: 5 cards, stale and invalid at 390', async (n) => {
  await reset();
  let { c, page } = await ctx({ viewport: PHONE, phone: true });
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await expect(page.locator('.alerts-eventcard')).toHaveCount(5);
  await expect(page.locator('.alerts-eventcard').nth(4)).toContainText('Everything else');
  await c.close();
  ({ c, page } = await ctx({ scenario: 'stale', viewport: PHONE, phone: true }));
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await sw(page, 'WhatsApp, A decision is waiting for me').tap();
  await page.getByRole('button', { name: 'Save settings' }).tap();
  await expect(page.locator('main').getByRole('alert')).toContainText('Someone changed these settings');
  const cb = await page.locator('main').getByRole('alert').boundingBox();
  n.push(`stale callout 390 y=${Math.round(cb.y)} h=${Math.round(cb.height)} vis=${cb.y >= 0 && cb.y + cb.height <= 844}`);
  await axe(page, 'stale 390', n);
  await c.close();
  ({ c, page } = await ctx({ scenario: 'invalid', viewport: PHONE, phone: true }));
  await page.goto(`${APP}/settings/alerts`);
  await settingsLoaded(page);
  await page.getByRole('button', { name: 'Save settings' }).tap();
  const al = page.locator('main').getByRole('alert');
  await expect(al).toHaveText('We couldn’t save your settings. Check these fields: channel.');
  const ab = await al.boundingBox();
  const fb = await page.getByRole('button', { name: 'Save settings' }).boundingBox();
  n.push(`invalid callout 390 y=${Math.round(ab.y)}-${Math.round(ab.y + ab.height)} footer y=${Math.round(fb.y)} obscured=${ab.y + ab.height > fb.y - 12 && ab.y < fb.y + fb.height}`);
  await axe(page, 'invalid 390', n);
  await shot(page, 'invalid-390');
  await c.close();
});

await run('S11 signed-out direct /work/W-1001 returns via next', async (n) => {
  const { c, page } = await ctx();
  await page.route('**/api/v1/**', (r) => r.continue({ headers: { ...r.request().headers(), 'x-mock-scenario': '401' } }));
  await page.goto(`${APP}/work/W-1001`);
  const href = await page.getByRole('link', { name: 'Sign in' }).first().getAttribute('href');
  n.push('href ' + href);
  expect(href).toContain('next=%2Fwork%2FW-1001');
  await c.close();
});

await reset();
await browser.close();
for (const r of results) console.log(r.join(' :: '));
