import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test';

// F-17: the line workspace on the work item page (PROPOSAL D-LINE-WORKSPACE, contract mock only). Every request
// goes to the local mock; nothing is sent to anyone.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const PART_A = ['W-2001', 'W-2002', 'W-2003', 'W-2004', 'W-2005'];

test.use({ timezoneId: 'Africa/Lagos' });

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function openItem(page: Page, id: string) {
  await page.goto(`/work/${id}`);
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('.ws')).toBeAttached();
}

const ring = (target: Locator) =>
  target.evaluate((el) => {
    const s = getComputedStyle(el);
    return (s.outlineStyle !== 'none' ? s.outlineStyle : /rgb\(36, 89, 214\)|0px 0px 0px 2px inset/.test(s.boxShadow + s.borderTopColor + s.textDecorationColor) ? 'solid' : 'none') !== 'none' && parseFloat((s.outlineStyle !== 'none' ? s.outlineWidth : '2px')) >= 2;
  });

/** Tabs forward until the target has keyboard focus. */
async function tabTo(page: Page, target: Locator) {
  for (let i = 1; i <= 80; i++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((el) => el === document.activeElement)) return i;
  }
  throw new Error('target never received focus');
}

const requests: string[] = [];

test.beforeEach(async ({ request, context, baseURL, page }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
  requests.length = 0;
  page.on('request', (r) => requests.push(r.url()));
});

for (const viewport of [DESKTOP, PHONE]) {
  for (const id of PART_A) {
    test(`${id} at ${viewport.width}: axe clean, one h1, no sideways scroll, 44px controls`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await openItem(page, id);
      await expectNoAxeViolations(page);
      await expect(page.locator('h1')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
      // buttons and button-styled links in the workspace (inline cite links in a sentence are WCAG 2.5.8's inline exception)
      for (const control of await page.locator('.ws button, .ws a.psl-btn').all()) {
        expect((await control.boundingBox())!.height, await control.innerText()).toBeGreaterThanOrEqual(44);
      }
    });
  }
}

test('at 390 the tables scroll inside their own frame, and the frame takes keyboard focus with a ring', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await openItem(page, 'W-2004');
  const frame = page.getByRole('region', { name: 'Table: Forecast · 6 months' });
  const sizes = await frame.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth, overflow: getComputedStyle(el).overflowX }));
  expect(sizes.overflow).toBe('auto');
  expect(sizes.scroll).toBeGreaterThan(sizes.client);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole('heading', { level: 1 }).click();
  await tabTo(page, frame);
  expect(await ring(frame)).toBe(true);
});

test('a cite link in the workspace shows a focus ring', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2001');
  const cite = page.locator('.ws').getByRole('link', { name: 'ISS-0233' });
  await page.getByRole('heading', { level: 1 }).click();
  await tabTo(page, cite);
  expect(await ring(cite)).toBe(true);
});

test('nothing in the workspace animates with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const id of PART_A) {
    await openItem(page, id);
    expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length), id).toBe(0);
  }
});

test('W-2002 paging and filters are drawn disabled and send nothing; every request went to the mock', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2002');
  await expect(page.getByText('4 of 64')).toBeVisible();
  const more = page.getByRole('button', { name: 'Show more' });
  await expect(more).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Status: Suggested by Tola' })).toBeDisabled();
  const before = requests.length;
  await more.click({ force: true });
  await page.waitForTimeout(300);
  expect(requests.slice(before).filter((u) => u.includes('/api/'))).toEqual([]);
  // the page's API calls go through the app's same-origin proxy to the mock; nothing leaves this machine
  for (const url of requests) expect(new URL(url).hostname, url).toMatch(/^(localhost|127\.0\.0\.1)$/);
});

// ---------- Part B: steps and the write (mock only)
const log = async (request: APIRequestContext) =>
  (await (await request.get(`${MOCK}/__mock/workspace-log`)).json()) as { entries: { idempotency_key: string; step: string; status: number; replay: boolean; expected_revision: number }[]; sends: Record<string, number> };
const stepPosts = () => requests.filter((u) => /\/api\/v1\/work\/W-\d+\/steps$/.test(new URL(u).pathname));

const PART_B: [string, (page: Page) => Promise<unknown>][] = [
  ['W-2006 form open', async (page) => {
    await openItem(page, 'W-2006');
    await page.getByRole('button', { name: 'Save and accept' }).click();
    await expect(page.getByRole('form', { name: 'Save and accept' })).toBeVisible();
  }],
  ['W-2006 422', async (page) => {
    await openItem(page, 'W-2006');
    await page.getByRole('button', { name: 'Check my answer' }).click();
    const form = page.getByRole('form', { name: 'Check my answer' });
    await form.getByLabel('Your answer').fill('Officers approve.');
    await form.getByRole('button', { name: 'Check my answer' }).click();
    await expect(form.getByText('Say how approvals are recorded.', { exact: true })).toBeVisible();
  }],
  ['W-2007 409', async (page) => {
    await openItem(page, 'W-2007');
    await page.getByRole('button', { name: 'Edit your update' }).click();
    const form = page.getByRole('form', { name: 'Edit your update' });
    await form.getByLabel('Your update').fill('Login fix verified.');
    await form.getByRole('button', { name: 'Edit your update' }).click();
    await expect(page.getByText('This changed while you were working. Showing version 5.')).toBeVisible();
  }],
  ['W-2008 uncertain', async (page) => {
    await openItem(page, 'W-2008');
    await page.getByRole('button', { name: 'Approve and send' }).click();
    await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
  }],
  ['W-2009 decision step', (page) => openItem(page, 'W-2009')],
];

for (const viewport of [DESKTOP, PHONE]) {
  for (const [name, reach] of PART_B) {
    test(`${name} at ${viewport.width}: axe clean, no sideways scroll, 44px controls`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await reach(page);
      await expectNoAxeViolations(page);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
      for (const control of await page.locator('.ws button:visible, .ws a.psl-btn:visible, .ws .ws-checkwrap:visible').all()) {
        expect((await control.boundingBox())!.height, await control.innerText()).toBeGreaterThanOrEqual(44);
      }
    });
  }
}

test('the form heading takes focus on open; Escape closes it and focus returns to the step', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2006');
  const control = page.getByRole('button', { name: 'Save and accept' });
  await control.click();
  await expect(page.getByRole('heading', { name: 'Save and accept' })).toBeFocused();
  await page.getByRole('form', { name: 'Save and accept' }).getByLabel('Short title (optional)').fill('x');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('form')).toHaveCount(0);
  await expect(control).toBeFocused();
  expect(await ring(control)).toBe(true);
  expect(stepPosts()).toEqual([]);
});

test('W-2001: a double click sends once (one send for that key on the mock), and the returned message is announced', async ({ page, request }) => {
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2001');
  await page.getByRole('button', { name: 'Approve and send' }).dblclick();
  await expect(page.getByRole('status').filter({ hasText: 'Lagoon Health received v2: emailed 12 Nov 15:10 to 2 contacts, both deliveries confirmed. Verified.' })).toBeVisible();
  const recorded = await log(request);
  expect(recorded.entries).toHaveLength(1);
  expect(recorded.sends[recorded.entries[0].idempotency_key]).toBe(1);
  expect(stepPosts()).toHaveLength(1);
});

test('W-2007: queued is announced as Waiting; the 409 re-bases the next press on version 5 with a new key', async ({ page, request }) => {
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2007');
  await page.getByRole('button', { name: 'Ask Tola to reassemble' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Waiting: Tola reassembles the report after the 16:00 records sync.' })).toBeVisible();
  await request.post(`${MOCK}/__mock/reset`);
  await page.reload();
  await expect(page.locator('.ws')).toBeAttached();
  await page.getByRole('button', { name: 'Edit your update' }).click();
  const form = page.getByRole('form', { name: 'Edit your update' });
  await form.getByLabel('Your update').fill('Login fix verified.');
  await form.getByRole('button', { name: 'Edit your update' }).click();
  await expect(page.locator('.ws-notice').filter({ hasText: 'This changed while you were working. Showing version 5.' })).toBeVisible();
  await expect(form.getByLabel('Your update')).toHaveValue('Login fix verified.');
  await page.waitForTimeout(1000);
  expect((await log(request)).entries).toHaveLength(1);
  await form.getByRole('button', { name: 'Edit your update' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Done: Edit your update.' })).toBeVisible();
  const [stale, done] = (await log(request)).entries;
  expect([stale.status, stale.expected_revision]).toEqual([409, 4]);
  expect([done.status, done.expected_revision]).toEqual([200, 5]);
  expect(done.idempotency_key).not.toBe(stale.idempotency_key);
});

test('W-2008 on a phone: after an uncertain send, Record and continue is tappable', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  await page.setViewportSize(PHONE);
  await openItem(page, 'W-2008');
  await page.getByRole('button', { name: 'Approve and send' }).click();
  await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
  await page.getByRole('radio', { name: /It didn’t arrive/ }).check();
  const answered = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/v1/work/W-2008/actions');
  await page.getByRole('button', { name: 'Record and continue' }).click();
  expect((await answered).status()).toBe(200);
});

async function pressApprove(page: Page) {
  await page.getByRole('button', { name: 'Approve and send' }).click();
  await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
  await page.getByRole('radio', { name: /It didn’t arrive/ }).check();
}

async function recordAtBottom(page: Page) {
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const answered = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/v1/work/W-2008/actions');
  await page.getByRole('button', { name: 'Record and continue' }).click();
  expect((await answered).status()).toBe(200);
}

for (const size of [PHONE, { width: 320, height: 640 }]) {
  test(`W-2008 at ${size.width}: scrolled to the bottom after an uncertain send, Record and continue is tappable`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
    await page.setViewportSize(size);
    await openItem(page, 'W-2008');
    await pressApprove(page);
    await recordAtBottom(page);
  });

  test(`W-2008 at ${size.width}: after a reload while uncertain every step is off, sends nothing, and Record and continue is tappable`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
    await page.setViewportSize(size);
    await openItem(page, 'W-2008');
    await page.getByRole('button', { name: 'Approve and send' }).click();
    await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
    for (const b of await page.locator('.ws-steps button').all()) await expect(b).toHaveAttribute('aria-disabled', 'true');
    const before = stepPosts().length;
    await page.getByRole('button', { name: 'Approve and send' }).click({ force: true });
    await page.waitForTimeout(300);
    expect(stepPosts()).toHaveLength(before);
    await page.getByRole('radio', { name: /It didn’t arrive/ }).check();
    await recordAtBottom(page);
  });
}

test('W-2008: effect uncertain turns every step off; the reconcile answer goes once to E-WORK-ACTION and nothing to steps', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2008');
  await page.getByRole('button', { name: 'Approve and send' }).click();
  await expect(page.locator('.ws-notice').filter({ hasText: 'Delivery to Lagoon Health couldn’t be confirmed.' })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
  for (const b of await page.locator('.ws-steps button').all()) await expect(b).toHaveAttribute('aria-disabled', 'true');
  await page.getByRole('button', { name: 'Approve and send' }).click({ force: true });
  await page.getByRole('radio', { name: /It didn’t arrive/ }).check();
  const answered = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/v1/work/W-2008/actions');
  await page.getByRole('button', { name: 'Record and continue' }).click();
  expect((await answered).status()).toBe(200);
  expect(requests.filter((u) => new URL(u).pathname === '/api/v1/work/W-2008/actions')).toHaveLength(1);
  expect(stepPosts()).toHaveLength(1);
});

test('W-2008 at 390: after the press the uncertain callout is on screen, clear of the pinned bar (QA-5-3)', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  await page.setViewportSize(PHONE);
  await openItem(page, 'W-2008');
  await page.getByRole('button', { name: 'Approve and send' }).click();
  const callout = page.locator('.ws-notice').filter({ hasText: 'Delivery to Lagoon Health couldn’t be confirmed.' });
  await expect(callout).toBeVisible();
  await expect.poll(async () => (await callout.boundingBox())!.y + (await callout.boundingBox())!.height).toBeLessThanOrEqual(PHONE.height);
  expect((await callout.boundingBox())!.y).toBeGreaterThanOrEqual(0);
});

test('W-2009: the decision step is a link to the decision page; following it opens the page and the workspace sent nothing', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openItem(page, 'W-2009');
  const link = page.locator('.ws').getByRole('link', { name: 'Open the decision' });
  await expect(link).toHaveAttribute('href', '/work/W-2009/decide?task=T-2009');
  // what the workspace sent before the decision page (which claims and decides itself, F-16) opened
  const before = [...requests];
  await link.click();
  await expect(page).toHaveURL(/\/work\/W-2009\/decide\?task=T-2009$/);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.getByRole('button', { name: /Approve/ }).first()).toBeVisible();
  expect(before.filter((u) => /\/(steps|claim|decision)$/.test(new URL(u).pathname))).toEqual([]);
});

test('nothing in the step form animates with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openItem(page, 'W-2006');
  await page.getByRole('button', { name: 'Save and accept' }).click();
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBe(0);
});

test('W-2010 draws no workspace', async ({ page }) => {
  await page.goto('/work/W-2010');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.locator('.ws')).toHaveCount(0);
});
