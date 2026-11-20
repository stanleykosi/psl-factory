import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-24: the Assistant on the contract mock (PROPOSAL D-ASSISTANT-VIEW and D-CONVERSATION-MODEL, contract mock only).
// Every request goes to the local mock; no agent runs, nothing is sent to anyone.
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

const requests: string[] = [];
test.beforeEach(async ({ request, context, baseURL, page }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
  requests.length = 0;
  page.on('request', (r) => requests.push(r.url()));
});

const log = async (page: Page) => ((await (await page.request.get(`${MOCK}/__mock/assistant-log`)).json()) as { entries: { operation: string }[] }).entries;

async function ready(page: Page, path: string) {
  await page.goto(path);
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('.as__center')).toBeVisible();
}

/** Press "Start this invoice", check the prefilled drawer and start. */
async function startInvoice(page: Page) {
  await page.getByRole('button', { name: 'Start this invoice' }).click();
  const drawer = page.getByRole('dialog');
  await expect(drawer.getByRole('combobox', { name: 'Completed milestone' })).toContainText('Milestone 2 · beta signed 30 Oct');
  await expect(drawer.getByRole('combobox', { name: 'Project' })).toContainText('Harmattan Bank · mobile onboarding');
  return drawer;
}

const PAGES = [
  { name: '/assistant', path: '/assistant' },
  { name: 'CV-2404', path: '/assistant/CV-2404' },
  { name: 'CV-2401', path: '/assistant/CV-2401' },
  { name: 'CV-2403', path: '/assistant/CV-2403' },
  { name: 'CV-2405', path: '/assistant/CV-2405' },
  { name: 'CV-2401 after the start', path: '/assistant/CV-2401', started: true },
];

for (const width of [1440, 390]) {
  for (const entry of PAGES) {
    test(`${entry.name} at ${width}: axe clean, one h1, no sideways scroll, 44px targets on phones`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await ready(page, entry.path);
      if (entry.started) {
        const drawer = await startInvoice(page);
        await drawer.getByRole('button', { name: 'Start the invoice' }).click();
        await expect(page.getByText(/^Started INV-0415\./)).toBeVisible();
      }
      const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
      await expect(page.locator('h1')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      if (width < 720) {
        // every button, and every link that is not inside a sentence, is a 44px target
        for (const control of await page.locator('.as button:visible, .as a.as-row:visible, .as a.cmp-source:visible, .as a.psl-btn:visible').all()) {
          expect((await control.boundingBox())!.height, (await control.innerText()) || (await control.getAttribute('aria-label')) || '').toBeGreaterThanOrEqual(43.5);
        }
      }
    });
  }
}

test('the composer is labelled by agent, the Talk to chips are pressed buttons, and keyboard focus is visible', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await ready(page, '/assistant');
  await expect(page.getByRole('textbox', { name: 'Message Tola' })).toBeVisible();
  const chips = page.getByRole('group', { name: 'Talk to' }).getByRole('button');
  await expect(chips).toHaveCount(3);
  await expect(chips.first()).toHaveAttribute('aria-pressed', 'true');
  await chips.nth(1).click();
  await expect(page.getByRole('textbox', { name: 'Message Chidi' })).toBeVisible();
  await expect(chips.nth(1)).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('textbox', { name: 'Message Chidi' }).focus();
  const ring = await page.locator('.cmp-composer__box').evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(ring).not.toBe('none');
  await chips.first().focus();
  await page.keyboard.press('Tab');
  expect(await page.evaluate(() => getComputedStyle(document.activeElement!).outlineStyle)).not.toBe('none');
});

test('sending from the home posts one conversation and one message, then opens the thread', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await ready(page, '/assistant');
  await page.getByRole('textbox', { name: 'Message Tola' }).fill('Draft the Kora SOW');
  await page.getByRole('button', { name: 'Send' }).dblclick();
  await expect(page).toHaveURL(/\/assistant\/CV-N1$/);
  await expect(page.getByText('Sample answer from the contract mock. No agent ran.')).toBeVisible();
  expect((await log(page)).map((e) => e.operation)).toEqual(['E-CONVERSATION-NEW', 'E-MESSAGE']);
  await expect(page.getByRole('complementary', { name: 'Conversations' }).getByRole('link', { name: /^Draft the Kora SOW/ })).toBeVisible();
});

test('the started draft: the drawer is the normal one, one POST, the thread shows "Started INV-0415." with focus on it, and a reload keeps it', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await ready(page, '/assistant/CV-2401');
  const starts: unknown[] = [];
  page.on('request', (r) => r.method() === 'POST' && new URL(r.url()).pathname === '/api/v1/work' && starts.push(r.postDataJSON()));
  const drawer = await startInvoice(page);
  expect(starts).toEqual([]);
  await drawer.getByRole('button', { name: 'Start the invoice' }).click();
  const line = page.getByText(/^Started INV-0415\./);
  await expect(line).toBeVisible();
  await expect(drawer).toHaveCount(0);
  await expect(page).toHaveURL(/\/assistant\/CV-2401$/);
  expect(starts).toEqual([{ line: 'invoice', case_id: 'C-0102', case_revision: 3, intake: { project: 'P-0102', milestone: 'M-0202' }, idempotency_key: expect.any(String) }]);
  await expect(line).toBeFocused();
  await expect(page.getByRole('link', { name: 'Open the work item' })).toHaveAttribute('href', '/work/W-1401');
  await expect(page.getByRole('button', { name: 'Start this invoice' })).toHaveCount(0);
  await expect(page.getByRole('complementary', { name: 'Conversations' }).getByText('Started · INV-0415')).toBeVisible();
  await page.reload();
  await expect(page.getByText(/^Started INV-0415\./)).toBeVisible();
  expect((await log(page)).filter((e) => e.operation !== undefined)).toEqual([]);
});

test('a second tab that still shows the button gets the 409 through the drawer, then shows the started line', async ({ page, context }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await ready(page, '/assistant/CV-2401');
  const second = await context.newPage();
  await second.setViewportSize({ width: 1440, height: 900 });
  await ready(second, '/assistant/CV-2401');
  const drawerB = await startInvoice(second);
  await drawerB.getByRole('button', { name: 'Start the invoice' }).click();
  await expect(second.getByText(/^Started INV-0415\./)).toBeVisible();
  const drawerA = await startInvoice(page);
  await drawerA.getByRole('button', { name: 'Start the invoice' }).click();
  await expect(drawerA.getByText(/changed since you opened the form/)).toBeVisible();
  await drawerA.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByText(/^Started INV-0415\./)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start this invoice' })).toHaveCount(0);
});

test('CV-2405 is durable: a reload shows the advanced step, never step 3, and opening or reloading writes nothing', async ({ page, context }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await ready(page, '/assistant/CV-2405');
  await expect(page.getByText('WORKING · STEP 3 OF 5', { exact: true })).toBeVisible();
  // one poll, then a reload: the mock moves one step on each read
  await expect(page.getByText('WORKING · STEP 4 OF 5', { exact: true })).toBeVisible({ timeout: 8000 });
  await page.reload();
  await expect(page.getByText('WORKING · STEP 5 OF 5', { exact: true })).toBeVisible();
  const other = await context.newPage();
  await ready(other, '/assistant/CV-2405');
  await expect(other.getByText('WORKING · STEP 3 OF 5', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Sample answer from the contract mock. No agent ran.')).toBeVisible({ timeout: 8000 });
  await expect(page.getByText(/You can leave/)).toHaveCount(0);
  expect(await log(page)).toEqual([]);
});

for (const width of [1440, 390]) {
  test(`reduced motion at ${width}: no running animation on the step in progress or the working avatar`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.setViewportSize({ width, height: 900 });
    await ready(page, '/assistant/CV-2405');
    await expect(page.getByText(/WORKING/).first()).toBeVisible();
    expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBe(0);
  });
}

test('without reduced motion the step in progress pulses (so the check above is meaningful)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await ready(page, '/assistant/CV-2405');
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBeGreaterThan(0);
});

test('another person’s conversation and the reserved id show "We could not find that conversation." and nothing of it', async ({ page, context, baseURL }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  for (const id of ['CV-2401', 'CV-2499']) {
    await page.goto(`/assistant/${id}`);
    await expect(page.getByText('We could not find that conversation.')).toBeVisible();
    await expect(page.locator('main')).not.toContainText('Invoice · Harmattan Bank');
    await expect(page.locator('main')).not.toContainText('Create the invoice');
  }
  expect(await new AxeBuilder({ page }).withTags(TAGS).analyze().then((r) => r.violations)).toEqual([]);
});

test('Chidi only for finance_lead: ?agent=tola selects Chidi; the held microphone says "Not available yet" and sends nothing', async ({ page, context, baseURL }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  await ready(page, '/assistant?agent=tola');
  const chips = page.getByRole('group', { name: 'Talk to' }).getByRole('button');
  await expect(chips).toHaveCount(1);
  await expect(chips).toHaveAttribute('aria-pressed', 'true');
  const mic = page.getByRole('button', { name: 'Speak your request' });
  await expect(mic).toHaveAttribute('aria-disabled', 'true');
  expect((await mic.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await mic.focus();
  await expect(page.getByRole('tooltip')).toHaveText('Not available yet');
  await page.keyboard.press('Enter');
  expect(await log(page)).toEqual([]);
});

test('every request in this run went to the local mock', async ({ page }) => {
  await ready(page, '/assistant/CV-2401');
  for (const url of requests) expect(new URL(url).hostname, url).toMatch(/^(localhost|127\.0\.0\.1)$/);
});

test('desktop columns are the boards’: the list 240px and the agent panel 260px at 1440', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1040 });
  await ready(page, '/assistant/CV-2401');
  expect((await page.getByRole('complementary', { name: 'Conversations' }).boundingBox())!.width).toBe(240);
  expect((await page.getByRole('complementary', { name: 'Agent and context' }).boundingBox())!.width).toBe(260);
});

test('phone: the bar keeps "← Assistant" on one line with a one-line ellipsed title; the home composer is docked at the bottom', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page, '/assistant/CV-2405');
  const back = page.getByRole('link', { name: 'Back to Assistant' });
  expect((await back.boundingBox())!.height).toBeLessThanOrEqual(48);
  const note = page.locator('.shell-phonenote');
  expect((await note.boundingBox())!.height).toBeLessThanOrEqual(48);
  expect((await note.boundingBox())!.x).toBeGreaterThanOrEqual((await back.boundingBox())!.x + (await back.boundingBox())!.width);
  await ready(page, '/assistant');
  const composer = await page.locator('.as__composer').boundingBox();
  expect(composer!.y + composer!.height).toBeGreaterThan(844 - 4);
  await expect(page.getByRole('link', { name: 'Back to Home' })).toBeVisible();
  await expect(page.getByRole('button', { name: '5 earlier' })).toBeVisible();
});

test('phone: the draft button is never hidden under the docked composer when it takes focus; after the start the footer is "Open INV-0415"', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page, '/assistant/CV-2401');
  const button = page.getByRole('button', { name: 'Start this invoice' });
  await button.focus();
  const b = (await button.boundingBox())!;
  const c = (await page.locator('.as__composer').boundingBox())!;
  expect(b.y + b.height).toBeLessThanOrEqual(c.y + 1);
  const drawer = await startInvoice(page);
  await drawer.getByRole('button', { name: 'Start the invoice' }).click();
  const footer = page.getByRole('link', { name: 'Open INV-0415' });
  await expect(footer).toHaveAttribute('href', '/work/W-1401');
  expect((await footer.boundingBox())!.height).toBeGreaterThanOrEqual(50);
  // docked like the composer it replaces: its footer sits at the bottom of the viewport
  const dock = (await page.locator('.as__open').boundingBox())!;
  expect(dock.y + dock.height).toBeGreaterThan(844 - 4);
  await expect(page.getByRole('textbox')).toHaveCount(0);
});

// F-48: the "can't" state.
test('CV-2404: the cant pose at 1440 (side panel) and 390 (inline card, 44px controls), still, with no write', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await ready(page, '/assistant/CV-2404');
  await expect(page.getByRole('complementary', { name: 'Agent and context' }).getByAltText('Zainab pose')).toHaveAttribute('src', '/agents/zainab-cant.png');
  await expect(page.getByAltText('Zainab, can’t do this')).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page, '/assistant/CV-2404');
  const card = page.getByAltText('Zainab, can’t do this');
  await expect(card).toHaveAttribute('src', '/agents/zainab-cant.png');
  expect(await card.evaluate((el) => getComputedStyle(el).animationName + getComputedStyle(el).transitionDuration)).toMatch(/^none0s$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect((await log(page)).filter((e) => /post|send|start/i.test(e.operation))).toEqual([]);
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations).toEqual([]);
});

test('the conversation list loads the next page as it is scrolled to the end, without reloading the rows shown (D-138)', async ({ page }) => {
  const all = Array.from({ length: 25 }, (_, i) => ({
    conversation_id: `CV-S${i}`,
    title: `Scroll chat ${i}`,
    agent: 'tola',
    status: 'idle',
    updated_at: '2026-11-13T09:00:00Z',
  }));
  const listCalls: string[] = [];
  await page.route('**/api/v1/assistant/conversations?*', async (route) => {
    const url = new URL(route.request().url());
    listCalls.push(url.search);
    const limit = Number(url.searchParams.get('limit') ?? 10);
    const offset = Number(/^o:(\d+)$/.exec(url.searchParams.get('cursor') ?? '')?.[1] ?? 0);
    const body = { items: all.slice(offset, offset + limit), as_of: '2026-11-14T10:00:00Z', ...(offset + limit < all.length ? { next_cursor: `o:${offset + limit}` } : {}) };
    await route.fulfill({ json: body });
  });
  await page.setViewportSize({ width: 1440, height: 500 });
  await ready(page, '/assistant');
  const links = page.locator('.as-row');
  await expect(links).toHaveCount(10);
  await expect(page.getByRole('radiogroup', { name: 'Rows per page' })).toHaveCount(0);
  const first = await links.first().elementHandle();
  await links.last().scrollIntoViewIfNeeded();
  await expect(links).toHaveCount(20);
  await links.last().scrollIntoViewIfNeeded();
  await expect(links).toHaveCount(25);
  expect(listCalls.filter((c) => c.includes('cursor='))).toHaveLength(2);
  // the first row is the very same element: nothing already shown was reloaded
  expect(await first!.evaluate((el) => el.isConnected)).toBe(true);
  expect(await links.first().evaluate((el, h) => el === h, first)).toBe(true);
});

test('desktop: only the thread scrolls; both side footers and the composer keep their place (D-140)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 520 });
  await ready(page, '/assistant/CV-2404');
  const scroller = page.locator('.as__scroll');
  const pieces = [page.locator('.as__note'), page.locator('.as__cannot'), page.locator('.as__composer'), page.locator('.as__talk'), page.locator('.as__new')];
  const place = async () => Promise.all(pieces.map(async (p) => (await p.boundingBox())!));
  // the thread is longer than its window, so it has something to scroll, and it opens at the latest message
  const m = await scroller.evaluate((el) => ({ over: el.scrollHeight > el.clientHeight, atEnd: Math.abs(el.scrollHeight - el.clientHeight - el.scrollTop) < 2 }));
  expect(m.over).toBe(true);
  expect(m.atEnd).toBe(true);
  const before = await place();
  await scroller.evaluate((el) => (el.scrollTop = 0));
  await expect.poll(() => scroller.evaluate((el) => el.scrollTop)).toBe(0);
  const after = await place();
  after.forEach((box, i) => {
    expect(Math.abs(box.x - before[i].x)).toBeLessThanOrEqual(1);
    expect(Math.abs(box.y - before[i].y)).toBeLessThanOrEqual(1);
  });
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight)).toBe(true);
  // both footers sit inside the window
  for (const box of before.slice(0, 3)) expect(box.y + box.height).toBeLessThanOrEqual(520);
});
