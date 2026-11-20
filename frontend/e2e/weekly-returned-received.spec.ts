import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-22: the weekly client report returned to the PM or received by the client (PROPOSAL D-LINE-WORKSPACE, contract
// mock only). Every request goes to the local mock; nothing is sent to anyone and no delivery is real.
const WIDTHS = [1440, 390];
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const IDS = ['W-2209', 'W-2210', 'W-2211', 'W-2212', 'W-2213', 'W-2214'];

test.use({ timezoneId: 'Africa/Lagos' });

const requests: { method: string; url: string }[] = [];
const everything: string[] = [];
test.beforeEach(async ({ request, context, baseURL, page }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
  requests.length = 0;
  page.on('request', (r) => {
    requests.push({ method: r.method(), url: r.url() });
    everything.push(r.url());
  });
});

// the whole run, not one page: every request in every test above went to the local app or the mock
test.afterEach(() => {
  for (const url of everything) expect(new URL(url).hostname, url).toMatch(/^(localhost|127\.0\.0\.1)$/);
});

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
      for (const control of await page.locator('.ws button, .ws a.psl-btn').all()) {
        expect((await control.boundingBox())!.height, await control.innerText()).toBeGreaterThanOrEqual(44);
      }
    });
  }
}

test('W-2209: Edit opens the form with focus on its heading; Escape closes it and returns focus to the button', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2209');
  const open = page.getByRole('button', { name: 'Edit your update' });
  await open.click();
  const form = page.getByRole('form', { name: 'Edit your update' });
  await expect(form.getByRole('heading', { name: 'Edit your update' })).toBeFocused();
  await expect(form.getByLabel('Risks (optional)', { exact: true })).toHaveValue('Login fails on older Android phones (high)');
  await form.getByLabel('Risks (optional)', { exact: true }).focus();
  await page.keyboard.press('Escape');
  await expect(form).toHaveCount(0);
  await expect(open).toBeFocused();
});

test('W-2209: Send posts once to the mock and the page reloads to the assembling state', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2209');
  await page.getByRole('button', { name: 'Edit your update' }).click();
  await page.getByRole('form').getByRole('button', { name: 'Edit your update' }).click();
  await expect(page.getByText('Assembling the weekly report')).toBeVisible();
  expect(requests.filter((r) => r.method === 'POST' && new URL(r.url).pathname.endsWith('/steps'))).toHaveLength(1);
});

test('W-2211 and W-2214 send nothing and offer no button', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const id of ['W-2211', 'W-2214']) {
    await openItem(page, id);
    await expect(page.locator('.ws button')).toHaveCount(0);
  }
  expect(requests.filter((r) => r.method === 'POST')).toEqual([]);
});

test('W-2212: reconcile is the only action; no step is posted and a reload keeps it', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2212');
  await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
  expect(requests.filter((r) => r.method === 'POST' && new URL(r.url).pathname.endsWith('/steps'))).toEqual([]);
});

test('the returned primary button is blue (action), not green, and the Next head is plain', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2209');
  const button = page.getByRole('button', { name: 'Edit your update' });
  const token = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--action').trim());
  const bg = await button.evaluate((el) => getComputedStyle(el).backgroundColor);
  const probe = await page.evaluate((t) => {
    const d = document.createElement('div');
    d.style.backgroundColor = t;
    document.body.append(d);
    const c = getComputedStyle(d).backgroundColor;
    d.remove();
    return c;
  }, token);
  expect(bg).toBe(probe);
  const head = page.locator('.ws-decide--next .psl-panel__head');
  await expect(head).toHaveText('Next');
  expect(await head.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe('rgba(0, 0, 0, 0)');
});
