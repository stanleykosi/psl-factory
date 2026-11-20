import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-23: the minutes line on the F-17 workspace frame (PROPOSAL D-LINE-WORKSPACE, contract mock only). Every request goes
// to the local mock; nothing is sent to anyone, no delivery is real and the client template is a test template.
const WIDTHS = [1440, 390];
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const IDS = ['W-2301', 'W-2302', 'W-2303', 'W-2304', 'W-2305', 'W-2306', 'W-2307', 'W-2308'];

test.use({ timezoneId: 'Africa/Lagos' });

const requests: { method: string; url: string; body: string | null }[] = [];
const everything: string[] = [];
test.beforeEach(async ({ request, context, baseURL, page }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
  requests.length = 0;
  page.on('request', (r) => {
    requests.push({ method: r.method(), url: r.url(), body: r.postData() });
    everything.push(r.url());
  });
});

// the whole run, not one page: every request in every test went to the local app or the mock
test.afterEach(() => {
  for (const url of everything) expect(new URL(url).hostname, url).toMatch(/^(localhost|127\.0\.0\.1)$/);
});

const posts = (suffix: string) => requests.filter((r) => r.method === 'POST' && new URL(r.url).pathname.endsWith(suffix));

async function openItem(page: Page, id: string) {
  await page.goto(`/work/${id}`);
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('.ws')).toBeAttached();
}

for (const width of WIDTHS) {
  for (const id of IDS) {
    test(`${id} at ${width}: axe clean, one h1, no sideways scroll, 44px controls`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await openItem(page, id);
      const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
      await expect(page.locator('h1')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      // on a phone every control is 44px; a link in a sentence is the only exception, and these are not in sentences
      if (width === 390) {
        for (const control of await page.locator('.ws button:visible, .ws a.psl-btn, .ws .ws-links a, .ws input[type=checkbox]:visible').all()) {
          const box = (await control.boundingBox())!;
          const wrap = await control.evaluate((el) => (el.closest('label')?.getBoundingClientRect().height ?? el.getBoundingClientRect().height));
          expect(Math.max(box.height, wrap), await control.innerText().catch(() => 'checkbox')).toBeGreaterThanOrEqual(44);
        }
      }
    });
  }
}

test('W-2301: Confirm opens the form with focus on its heading, Escape closes it with no request, and the confirm sends one POST with the ticked set', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2301');
  const open = page.getByRole('button', { name: 'Confirm and create actions' });
  await open.click();
  const form = page.getByRole('form', { name: 'Confirm and create actions' });
  await expect(form.getByRole('heading', { name: 'Confirm and create actions' })).toBeFocused();
  await form.getByRole('radio', { name: 'Internal' }).focus();
  await page.keyboard.press('Escape');
  await expect(form).toHaveCount(0);
  await expect(open).toBeFocused();
  expect(posts('/steps')).toHaveLength(0);
  await page.getByRole('checkbox', { name: 'Select Assess the SMS reminders change' }).uncheck();
  await open.click();
  await page.getByRole('form').getByRole('button', { name: 'Confirm and create actions' }).click();
  await expect(page.getByText('Used the decisions and actions you confirmed')).toBeVisible();
  expect(posts('/steps')).toHaveLength(1);
  expect(JSON.parse(posts('/steps')[0].body!)).toMatchObject({ step: 'confirm_minutes', item_ids: ['D-1', 'D-2', 'A-1', 'A-2'], inputs: { audience: 'client' } });
});

test('W-2302: nothing to press, the working mark does not animate under reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2302');
  await expect(page.getByRole('link', { name: 'Ask Tola' })).toHaveAttribute('href', '/assistant');
  await expect(page.locator('.ws button')).toHaveCount(0);
  const animations = await page.evaluate(() => [...document.querySelectorAll('.ws *')].filter((el) => getComputedStyle(el).animationName !== 'none').length);
  expect(animations).toBe(0);
  expect(posts('/steps')).toHaveLength(0);
});

test('W-2303: Send for review posts once and the page shows the review', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2303');
  await page.getByRole('button', { name: 'Send for review' }).click();
  await expect(page.getByRole('link', { name: 'Approve and send' })).toBeVisible();
  expect(posts('/steps')).toHaveLength(1);
});

test('W-2304: Open the minutes reads one document and shows the test template tag; the work page sends nothing to steps, claim or decision', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2304');
  await page.getByRole('button', { name: 'Open the minutes' }).click();
  await expect(page.getByRole('heading', { name: 'Weekly sync minutes · Lagoon Health' })).toBeVisible();
  await expect(page.locator('.ws').getByText('Test template')).toBeVisible();
  expect(requests.filter((r) => new URL(r.url).pathname.startsWith('/api/v1/documents/'))).toHaveLength(1);
  await expect(page.getByRole('link', { name: 'Approve and send' })).toHaveAttribute('href', '/work/W-2304/decide?task=T-2304');
  await expect(page.getByRole('link', { name: 'Return with a note' })).toHaveAttribute('href', '/work/W-2304/decide?task=T-2304');
  expect(requests.filter((r) => r.method === 'POST')).toEqual([]);
});

for (const width of WIDTHS) {
  test(`Return needs a note at ${width}: blank and over-long are refused before any request, a valid note sends one return`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await openItem(page, 'W-2304');
    await page.getByRole('link', { name: 'Return with a note' }).click();
    await expect(page).toHaveURL(/\/work\/W-2304\/decide\?task=T-2304/);
    const note = page.getByLabel(/^Note/);
    await expect(note).toBeVisible();
    const ret = page.getByRole('button', { name: 'Return', exact: true });
    await expect(page.getByRole('button', { name: /^Approve v1/ })).toBeEnabled();
    await ret.click();
    expect(posts('/decision')).toHaveLength(0);
    await note.fill('x'.repeat(2001));
    await ret.click();
    expect(posts('/decision')).toHaveLength(0);
    await note.fill('Fix the third action before it goes.');
    await ret.click();
    await expect.poll(() => posts('/decision').length).toBe(1);
    expect(JSON.parse(posts('/decision')[0].body!)).toMatchObject({ verdict: 'return', note: 'Fix the third action before it goes.' });
  });
}

for (const width of [1440, 390, 320]) {
  test(`W-2305 at ${width}: after an uncertain approve the decision links stay disabled, before and after a reload, and reconcile is the only action`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await openItem(page, 'W-2305');
    await page.getByRole('link', { name: 'Approve and send' }).click();
    await expect(page).toHaveURL(/\/decide\?task=T-2305/);
    const approve = page.getByRole('button', { name: /^Approve v1/ });
    await expect(approve).toBeEnabled();
    await approve.click();
    await expect.poll(() => posts('/decision').length).toBe(1);
    // QA-3-1: the decision page says the result is not confirmed, and claims no approval or next step
    await expect(page.getByText(/We couldn’t confirm your decision\./)).toBeVisible();
    await expect(page.getByText(/is approved|YOU APPROVED|Next step\./)).toHaveCount(0);
    await openItem(page, 'W-2305');
    for (const reload of [false, true]) {
      if (reload) {
        await page.reload();
        await expect(page.locator('.ws')).toBeAttached();
      }
      for (const name of ['Approve and send', 'Return with a note']) {
        await expect(page.getByRole('link', { name })).toHaveCount(0);
        const control = page.locator('.ws').getByRole('button', { name });
        await expect(control).toHaveAttribute('aria-disabled', 'true');
        await control.click({ force: true });
      }
      await expect(page).toHaveURL(/\/work\/W-2305$/);
      await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
    }
    expect(posts('/decision')).toHaveLength(1);
    expect(posts('/steps')).toHaveLength(0);
    await page.getByRole('radio', { name: /It didn’t arrive/ }).click();
    await page.getByRole('button', { name: 'Record and continue' }).click();
    await expect.poll(() => posts('/actions').length).toBe(1);
    expect(posts('/decision')).toHaveLength(1);
    expect(posts('/steps')).toHaveLength(0);
  });
}

test('W-2307 and W-2308: no request leaves the page by itself', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const id of ['W-2307', 'W-2308']) await openItem(page, id);
  expect(requests.filter((r) => r.method === 'POST')).toEqual([]);
});
