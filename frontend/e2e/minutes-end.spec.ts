import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-28: the minutes line's two end states on the F-17 workspace frame (PROPOSAL D-LINE-WORKSPACE, contract mock only).
// Every request goes to the local mock; nothing is sent, filed or created, no delivery is real and the client template
// is a test template.
const WIDTHS = [1440, 390];
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const IDS = ['W-2310', 'W-2311', 'W-2312', 'W-2313', 'W-2314'];

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
    test(`${id} at ${width}: axe clean, one h1, no sideways scroll, visible focus, 44px phone controls`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.setViewportSize({ width, height: 900 });
      await openItem(page, id);
      const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
      await expect(page.locator('h1')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      if (id !== 'W-2314') await expect(page.locator('.ws table').first().getByRole('columnheader')).toHaveText(id === 'W-2313' ? ['Action', 'Owner', 'Due', 'State', 'Steps'] : ['Action', 'Owner', 'Due', 'State']);
      // no tag or button label wraps onto a second line
      const wrapped = await page.evaluate(() =>
        [...document.querySelectorAll('.ws .psl-tag, .ws button, .ws a.psl-btn')]
          .filter((el) => {
            const range = document.createRange();
            range.selectNodeContents(el);
            return new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size > 1;
          })
          .map((el) => el.textContent),
      );
      expect(wrapped).toEqual([]);
      const animations = await page.evaluate(() => [...document.querySelectorAll('.ws *')].filter((el) => getComputedStyle(el).animationName !== 'none').length);
      expect(animations).toBe(0);
      const link = page.locator('.ws .ws-links a').first();
      if (await link.count()) {
        await link.focus();
        const outline = await link.evaluate((el) => getComputedStyle(el).outlineStyle + getComputedStyle(el).boxShadow);
        expect(outline).not.toMatch(/^none(none)?$/);
      }
      if (width === 390) {
        // UI-1-2: the actions table shows every cell, no sideways scroll inside its frame, DUE and STATE labelled
        const frame = page.locator('.ws .ws-tablewrap').first();
        expect(await frame.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
        const labels = await page.locator('.ws .ws-table--stack tbody tr:first-child td').evaluateAll((tds) => tds.map((td) => getComputedStyle(td, '::before').content));
        expect(labels.slice(0, 4)).toEqual(['"Action"', '"Owner"', '"Due"', '"State"']);
        for (const control of await page.locator('.ws button:visible, .ws .ws-links a').all()) {
          const box = (await control.boundingBox())!;
          expect(box.height, await control.innerText()).toBeGreaterThanOrEqual(44);
        }
      }
      expect(requests.filter((r) => r.method !== 'GET')).toEqual([]);
    });
  }
}

test('W-2310 and W-2311: Open actions goes to the project Actions tab', async ({ page }) => {
  for (const id of ['W-2310', 'W-2311']) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openItem(page, id);
    await expect(page.getByRole('link', { name: 'Open actions' })).toHaveAttribute('href', '/projects/C-0211/actions');
  }
});

test('W-2312 at 1440 and 390: reconcile is the only action; one press is one POST to /actions and none to steps, claim or decision', async ({ page }) => {
  for (const width of WIDTHS) {
    requests.length = 0;
    await page.setViewportSize({ width, height: 900 });
    await openItem(page, 'W-2312');
    await expect(page.locator('.ws').getByText('Uncertain', { exact: true })).toBeVisible();
    await expect(page.getByRole('radiogroup', { name: 'Confirm what happened' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('radiogroup', { name: 'Confirm what happened' })).toBeVisible();
    await page.getByRole('radio', { name: /I can’t tell yet/ }).click();
    await page.getByRole('button', { name: 'Record and continue' }).click();
    await expect.poll(() => posts('/actions').length).toBe(1);
    for (const suffix of ['/steps', '/claim', '/decision']) expect(posts(suffix)).toHaveLength(0);
    expect(requests.filter((r) => r.method === 'POST')).toHaveLength(1);
    await expect(page.getByRole('link', { name: 'Open actions' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open the minutes' })).toBeVisible();
  }
});

test('W-2312: Open the minutes reads exactly one document', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2312');
  await page.getByRole('button', { name: 'Open the minutes' }).click();
  await expect(page.locator('.ws').getByText('Test template')).toBeVisible();
  expect(requests.filter((r) => new URL(r.url).pathname.startsWith('/api/v1/documents/')).map((r) => new URL(r.url).pathname)).toEqual(['/api/v1/documents/D-2304/versions/1']);
});

for (const width of WIDTHS) {
  test(`reaching internal at ${width}: choosing Internal on W-2301 and confirming ends on the filed view; Client ends on the drafted view`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await openItem(page, 'W-2301');
    await page.getByRole('button', { name: 'Confirm and create actions' }).click();
    await page.getByRole('form', { name: 'Confirm and create actions' }).getByRole('radio', { name: 'Internal' }).click();
    await page.getByRole('form').getByRole('button', { name: 'Confirm and create actions' }).click();
    await expect(page.getByText('Filed · Internal').first()).toBeVisible();
    expect(posts('/steps')).toHaveLength(1);
    expect(JSON.parse(posts('/steps')[0].body!)).toMatchObject({ step: 'confirm_minutes', inputs: { audience: 'internal' } });
    expect(posts('/decision')).toHaveLength(0);
    await page.request.post(`${MOCK}/__mock/reset`);
    requests.length = 0;
    await openItem(page, 'W-2301');
    await page.getByRole('button', { name: 'Confirm and create actions' }).click();
    await page.getByRole('form').getByRole('button', { name: 'Confirm and create actions' }).click();
    await expect(page.getByText('Used the decisions and actions you confirmed')).toBeVisible();
  });

  test(`reaching published at ${width}: approving W-2309 on the decide page ends on the published view with F-16 requests only`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await openItem(page, 'W-2309');
    await page.getByRole('link', { name: 'Approve and send' }).click();
    await expect(page).toHaveURL(/\/work\/W-2309\/decide\?task=T-2309/);
    const approve = page.getByRole('button', { name: /^Approve v1/ });
    await expect(approve).toBeEnabled();
    await approve.click();
    await expect.poll(() => posts('/decision').length).toBe(1);
    expect(posts('/claim').length).toBeLessThanOrEqual(1);
    expect(posts('/steps')).toHaveLength(0);
    requests.length = 0;
    await openItem(page, 'W-2309');
    await expect(page.getByText('Published · Received').first()).toBeVisible();
    await expect(page.locator('.ws').getByText('Sent to')).toBeVisible();
    expect(requests.filter((r) => r.method !== 'GET')).toEqual([]);
  });
}

test('W-2313: Assign owner posts one step with the chosen owner; W-2311 has no such control', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openItem(page, 'W-2313');
  await page.getByRole('button', { name: 'Assign owner' }).click();
  const form = page.getByRole('form', { name: 'Assign owner' });
  await form.getByRole('combobox', { name: /Owner/ }).click();
  await page.getByRole('option', { name: /Tunde Bello/ }).click();
  await form.getByRole('button', { name: 'Assign owner' }).click();
  await expect.poll(() => posts('/steps').length).toBe(1);
  expect(JSON.parse(posts('/steps')[0].body!)).toMatchObject({ step: 'assign_owner', item_ids: ['A-2'], inputs: { owner: 'U-TUNDE' } });
  await openItem(page, 'W-2311');
  await expect(page.getByRole('button', { name: 'Assign owner' })).toHaveCount(0);
});
