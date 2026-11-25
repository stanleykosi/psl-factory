import { expect, test, type Page } from '@playwright/test';

// F-97: the engagement (SCR-41) and planning (SCR-42) panels on the live work item, on the live shapes (mock/engagement-live.mjs).
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const writes = (page: Page) => {
  const sent: { path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/api/')) sent.push({ path: new URL(r.url()).pathname, body: JSON.parse(r.postData() ?? '{}') });
  });
  return sent;
};
const choose = async (page: Page, label: string, option: RegExp) => {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
};

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4650: confirm the PM, record the details, register, and the page shows the registered engagement', async ({ page }) => {
      const sent = writes(page);
      const main = page.locator('main#main');
      await page.goto('/work/4650');
      await expect(main.getByText('Route A · converted from a won bid')).toBeVisible();
      await expect(main.getByText('Engagement steps')).toBeVisible();
      await choose(page, 'Project manager', /^Amaka Obi/);
      await choose(page, 'Role', /^PMO Lead/);
      await choose(page, 'Source for this choice', /^Engagement source/);
      await main.getByRole('button', { name: 'Confirm the project manager' }).click();
      await expect(main.getByRole('button', { name: 'Record the details' })).toBeVisible();
      await choose(page, 'Source you checked', /^Product input/);
      await choose(page, 'Plan', /^RFP outcome/);
      await main.getByRole('checkbox').check();
      await main.getByRole('button', { name: 'Record the details' }).click();
      await expect(main.getByRole('button', { name: 'Register the engagement' })).toBeVisible();
      await main.getByLabel(/Official project identifier/).fill('PSL-2026-014');
      await choose(page, 'Role', /^Head of PMO/);
      await choose(page, 'Source for the registration', /^Engagement source/);
      await main.getByRole('button', { name: 'Register the engagement' }).click();
      await expect(main.getByText('Receipt recorded')).toBeVisible();
      await expect(main.getByRole('link', { name: 'Project planning' })).toHaveAttribute('href', '/work/4655');
      expect(sent.map((s) => s.body.action)).toEqual(['assign', 'details', 'register']);
      expect(sent.every((s) => s.path === '/api/v1/work/4650/engagement')).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test('4650: a button with nothing chosen sends nothing and says what is missing; the targets are 44px on a phone', async ({ page }) => {
      const sent = writes(page);
      const main = page.locator('main#main');
      await page.goto('/work/4650');
      const button = main.getByRole('button', { name: 'Confirm the project manager' });
      await button.click();
      await expect(main.getByText('Choose the project manager.')).toBeVisible();
      expect(sent).toEqual([]);
      if (label.startsWith('phone')) expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    });

    test('4654 held: the finding shows and nothing can be pressed; 4653 registered: no forms', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4654');
      await expect(main.getByText('The prior identity or planning handoff needs current-source review')).toBeVisible();
      await expect(main.getByRole('button', { name: /Confirm|Record the details|Register|Check again/ })).toHaveCount(0);
      await page.goto('/work/4653');
      await expect(main.getByRole('link', { name: 'Kora Logistics · fleet tracker' })).toBeVisible();
      await expect(main.getByRole('combobox')).toHaveCount(0);
    });

    test('4655 planning: every department with its status; unknown effort reads Unknown; 4656 says the packet is not available', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4655');
      for (const name of ['Engineering', 'QA', 'Security', 'Product', 'Infrastructure']) await expect(main.getByText(name, { exact: true }).first()).toBeVisible();
      await expect(main.getByText('Changed from costing')).toBeVisible();
      await expect(main.getByText('Effort unknown')).toBeVisible();
      await expect(main.getByText('Nobody set to receive it')).toBeVisible();
      await expect(main.getByRole('button')).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.goto('/work/4656');
      await expect(main.getByText('The planning packet isn’t available to you here.')).toBeVisible();
    });
  });
}
