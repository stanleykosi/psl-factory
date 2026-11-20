import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-21: the weekly client report line on the workspace frame (PROPOSAL D-LINE-WORKSPACE, contract mock only).
// Every request goes to the local mock; nothing is sent to anyone and no real template or recipient exists.
const WIDTHS = [1440, 390];
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const IDS = ['W-2201', 'W-2202', 'W-2203', 'W-2204', 'W-2205', 'W-2206', 'W-2207', 'W-2208'];

test.use({ timezoneId: 'Africa/Lagos' });

const requests: string[] = [];
test.beforeEach(async ({ request, context, baseURL, page }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
  requests.length = 0;
  page.on('request', (r) => requests.push(r.url()));
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

test('the four-part form opens with focus on its heading, picks cites, closes on Escape with focus back on the step', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2201');
  const open = page.getByRole('button', { name: 'Send to Tola to assemble' });
  await open.click();
  const form = page.getByRole('form', { name: 'Send to Tola to assemble' });
  await expect(form.getByRole('heading', { name: 'Send to Tola to assemble' })).toBeFocused();
  await form.getByRole('combobox', { name: 'Cites for timeline (optional)' }).click();
  await page.getByRole('option', { name: 'Weekly sync with Lagoon Health · 10 Nov' }).click();
  // Escape closes the list only; the form and the chosen cite stay
  await page.keyboard.press('Escape');
  await expect(form).toBeVisible();
  await expect(form.getByRole('combobox', { name: 'Cites for timeline (optional)' })).toContainText('Weekly sync with Lagoon Health');
  await form.getByLabel('Timeline (optional)', { exact: true }).focus();
  await page.keyboard.press('Escape');
  await expect(form).toHaveCount(0);
  await expect(open).toBeFocused();
});

test('W-2202: Send takes the mock 422, each message sits under its part, focus on the first, nothing client-side', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2202');
  await page.getByRole('button', { name: 'Send to Tola to assemble' }).click();
  await page.getByRole('form').getByRole('button', { name: 'Send to Tola to assemble' }).click();
  const form = page.getByRole('form', { name: 'Send to Tola to assemble' });
  await expect(form.getByLabel('Risks (optional)', { exact: true })).toBeFocused();
  await expect(form.getByLabel('Risks (optional)', { exact: true })).toHaveAttribute('aria-invalid', 'true');
  await expect(form.getByRole('combobox', { name: 'Cites for next steps (optional)' })).toHaveAttribute('aria-invalid', 'true');
  await expect(form.getByText("Two parts can't be sent yet. Every part needs words and at least one record from 5–11 Nov.")).toHaveCount(1);
});

test('W-2201 send reaches the assembling state; the disabled step sends nothing; the pulse stops with reduced motion', async ({ page, request }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openItem(page, 'W-2201');
  await page.getByRole('button', { name: 'Send to Tola to assemble' }).click();
  await page.getByRole('form').getByRole('button', { name: 'Send to Tola to assemble' }).click();
  await expect(page.getByText('Assembling the weekly report')).toBeVisible();
  await expect(page.getByText('TEST TEMPLATE')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send for PMO Lead review' })).toHaveAttribute('aria-disabled', 'true');
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBe(0);
  const log = (await (await request.get(`${MOCK}/__mock/workspace-log`)).json()) as { entries: unknown[] };
  expect(log.entries).toHaveLength(1);
  await page.getByRole('button', { name: 'Send for PMO Lead review' }).click({ force: true });
  await page.waitForTimeout(300);
  expect(((await (await request.get(`${MOCK}/__mock/workspace-log`)).json()) as { entries: unknown[] }).entries).toHaveLength(1);
});

test('W-2204 approve: a double click is one send on the mock, done shows the live line (mock evidence only)', async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2204');
  const approve = page.getByRole('button', { name: 'Approve and send' });
  await approve.dblclick();
  await expect(page.getByRole('status').filter({ hasText: 'Lagoon Health received v1' })).toBeVisible();
  const log = (await (await request.get(`${MOCK}/__mock/workspace-log`)).json()) as { sends: Record<string, number> };
  expect(Object.values(log.sends)).toEqual([1]);
});

for (const width of [1440, 390, 320]) {
  test(`W-2205 at ${width}: uncertain send locks every step, only reconcile posts, "Record and continue" stays tappable`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 800 });
    await openItem(page, 'W-2205');
    await page.getByRole('button', { name: 'Approve and send' }).click();
    await expect(page.getByRole('group', { name: 'Confirm what happened' })).toBeVisible();
    for (const b of await page.locator('.ws-steps button').all()) await expect(b).toHaveAttribute('aria-disabled', 'true');
    await page.getByRole('button', { name: 'Approve and send' }).click({ force: true });
    await page.reload();
    await expect(page.locator('.ws')).toBeAttached();
    await page.getByRole('button', { name: 'Approve and send' }).click({ force: true });
    await page.waitForTimeout(300);
    const log = (await (await request.get(`${MOCK}/__mock/workspace-log`)).json()) as { entries: unknown[] };
    expect(log.entries).toHaveLength(1);
    const record = page.getByRole('button', { name: 'Record and continue' });
    await page.getByRole('radio', { name: /It didn’t arrive/ }).check({ force: true });
    await record.scrollIntoViewIfNeeded();
    const box = (await record.boundingBox())!;
    const hit = await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.closest('button')?.textContent, { x: box.x + box.width / 2, y: box.y + box.height / 2 });
    expect(hit).toContain('Record and continue');
  });
}

test('W-2208: the decision step is a link to the F-16 page and sends nothing', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2208');
  const link = page.getByRole('link', { name: 'Approve and send' });
  await expect(link).toHaveAttribute('href', '/work/W-2208/decide?task=T-2208');
  const before = requests.length;
  await link.click();
  await expect(page).toHaveURL(/\/work\/W-2208\/decide\?task=T-2208/);
  expect(requests.slice(before).filter((u) => new URL(u).pathname.endsWith('/steps'))).toEqual([]);
});

test('every request in this run went to the local mock', async ({ page }) => {
  await openItem(page, 'W-2201');
  for (const url of requests) expect(new URL(url).hostname, url).toMatch(/^(localhost|127\.0\.0\.1)$/);
});
