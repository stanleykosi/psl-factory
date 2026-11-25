import { expect, test, type Page } from '@playwright/test';

// F-101: the income schedule (SCR-54 part 1) on the live work item, on the live shapes (mock/income-schedules-live.mjs).
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
const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4203: the schedule, the result and three buttons; Approve needs evidence and a note, then is sent once', async ({ page }) => {
      const sent = writes(page);
      const main = page.locator('main#main');
      await page.goto('/work/4203');
      await expect(main.getByRole('heading', { name: 'Income rows' })).toBeVisible();
      await expect(main.getByText('1,500,000.00 NGN')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'The result' })).toBeVisible();
      for (const name of ['Approve', 'Return', 'Reject']) await expect(main.getByRole('button', { name, exact: true })).toBeDisabled();
      await expect(main.getByRole('button', { name: 'Withdraw approval' })).toHaveCount(0);
      await expect(main.getByText('Choose the evidence this decision rests on.').first()).toBeVisible();
      await main.getByRole('combobox', { name: /Evidence/ }).click();
      await page.getByRole('option', { name: /^document/ }).click();
      await expect(main.getByText('Add a note.').first()).toBeVisible();
      await expect(main.getByRole('button', { name: 'Approve', exact: true })).toBeDisabled();
      expect(sent).toEqual([]);
      await main.getByLabel(/^Note/).fill('Checked against the ledger.');
      const approve = main.getByRole('button', { name: 'Approve', exact: true });
      if (label.startsWith('phone')) expect((await approve.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await approve.click();
      await expect(main.getByRole('button', { name: 'Withdraw approval' })).toBeVisible();
      await expect(main.getByRole('button', { name: 'Approve', exact: true })).toHaveCount(0);
      expect(sent).toEqual([{ path: '/api/v1/work/4203/reviews', body: { kind: 'schedule', expected_revision: 5, case_revision: 12, target_id: 9, verdict: 'approve', evidence_id: 61, note: 'Checked against the ledger.' } }]);
      expect(await noOverflow(page)).toBe(true);
    });

    test('4201 investigating: rows with an unknown amount, no result and no buttons', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4201');
      await expect(main.getByRole('heading', { name: 'Income rows' })).toBeVisible();
      await expect(main.getByText('Unknown', { exact: true })).toHaveCount(1);
      await expect(main.getByRole('heading', { name: 'The result' })).toHaveCount(0);
      await expect(main.getByRole('button', { name: /^(Approve|Return|Reject|Withdraw approval)$/ })).toHaveCount(0);
      expect(await noOverflow(page)).toBe(true);
    });

    test('4202 held: what is missing and the possible duplicates, read only', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4202');
      await expect(main.getByRole('heading', { name: 'Possible duplicates' })).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Still needed' })).toBeVisible();
      await expect(main.getByRole('button', { name: /Settle|Approve|Return|Reject/ })).toHaveCount(0);
    });

    test('4204 returned and 4205 verified: the rows, and only Withdraw approval', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4204');
      await expect(main.getByRole('heading', { name: 'Returned for correction' })).toBeVisible();
      await expect(main.getByRole('button', { name: /Correct|Approve|Return|Reject|Withdraw/ })).toHaveCount(0);
      await page.goto('/work/4205');
      await expect(main.getByRole('button', { name: 'Withdraw approval' })).toBeVisible();
      await expect(main.getByRole('button', { name: /^(Approve|Return|Reject)$/ })).toHaveCount(0);
    });

    test('4206: nobody is set to review; 4207: the inventory with no button; 4299: unavailable', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4206');
      await expect(main.getByText(/Nobody is set to review schedules yet/)).toBeVisible();
      await expect(main.getByRole('button', { name: /Approve|Return|Reject|Withdraw/ })).toHaveCount(0);
      await page.goto('/work/4207');
      await expect(main.getByText('Partial')).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Income rows' })).toHaveCount(0);
      await page.goto('/work/4299');
      await expect(page.getByText(/unavailable/i).first()).toBeVisible();
      await expect(page.getByText('Income schedule for Kora Logistics')).toHaveCount(0);
    });
  });
}
