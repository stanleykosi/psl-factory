import { expect, test, type Page } from '@playwright/test';

// F-99: the costing sheet (SCR-27) on the live work item, on the live shapes (mock/costing-live.mjs).
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

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4700: inputs, figures, the rule and the approvals show; a price change is proposed', async ({ page }) => {
      const sent = writes(page);
      const main = page.locator('main#main');
      await page.goto('/work/4700');
      await expect(main.getByRole('heading', { name: 'Calculated figures' })).toBeVisible();
      await expect(main.getByText('25000000.00 NGN')).toBeVisible();
      await expect(main.getByText('Template rule (placeholder)')).toBeVisible();
      await expect(main.getByText('Chief executive')).toBeVisible();
      await main.getByRole('combobox', { name: 'What to adjust' }).click();
      await page.getByRole('option', { name: /^Engineering/ }).click();
      await main.getByLabel(/^Amount/).fill('-500000');
      await main.getByLabel(/^Reason/).fill('The plan shortened.');
      await main.getByRole('button', { name: 'Propose the change' }).click();
      await expect(main.getByText('Price change waiting for a decision')).toBeVisible();
      expect(sent.map((s) => s.path)).toEqual(['/api/v1/work/4700/bid-pricing']);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test('4701: the CEO step is approved and the page then shows all three approved; targets are 44px on a phone', async ({ page }) => {
      const sent = writes(page);
      const main = page.locator('main#main');
      await page.goto('/work/4701');
      const approve = main.getByRole('button', { name: 'Approve', exact: true });
      if (label.startsWith('phone')) expect((await approve.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await approve.click();
      await expect(main.getByRole('button', { name: 'Approve', exact: true })).toHaveCount(0);
      await expect(main.getByText('Approved', { exact: true })).toHaveCount(3);
      expect(sent.map((s) => s.body.role)).toEqual(['CEO']);
    });

    test('4703 held: why it is held and nothing to press; 4705: unknown figures read Unknown', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4703');
      await expect(main.getByText('The engineering estimate is missing.')).toBeVisible();
      await expect(main.getByRole('button', { name: /Approve|Return|Refuse|Propose/ })).toHaveCount(0);
      await page.goto('/work/4705');
      await expect(main.getByText('Unknown', { exact: true })).toHaveCount(2);
    });
  });
}
