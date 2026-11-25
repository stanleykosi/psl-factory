import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-90: releasing an invoice from the live work item (mock/invoice-release-live.mjs, ids 4140 to 4144).
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const SHOTS = process.env.F90_SHOTS;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
};
/** Every write the page makes, as "METHOD path body". */
const writes = (page: Page) => {
  const sent: string[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/api/')) sent.push(`${r.method()} ${new URL(r.url()).pathname} ${r.postData() ?? ''}`);
  });
  return sent;
};
const scenario = (page: Page, value: string) => page.context().addCookies([{ name: 'psl_mock_scenario', value, url: `http://localhost:${process.env.E2E_PORT ?? 3101}` }]);
const RELEASE = 'POST /api/v1/work/4140/actions {"action":"release_invoice","expected_revision":9}';

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4140 offers the release; the dialog sends nothing until confirmed; one exact POST; the page moves to Verified without a second one', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4140');
      await loaded(page);
      const main = page.locator('main#main');
      const invoice = main.getByRole('heading', { name: 'Invoice' }).locator('xpath=ancestor::section[1]');
      await expect(invoice).toContainText('INV-0412');
      await expect(invoice).toContainText('NGN 1250000.00');
      await expect(invoice).toContainText('Not issued yet');
      await expect(invoice).toContainText('No delivery recorded');
      await expect(invoice.getByText('Unknown')).toHaveCount(2);
      expect(sent).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4140-${viewport.width}.png`, fullPage: true });
      await main.getByRole('button', { name: 'Release invoice' }).click();
      const dialog = page.getByRole('alertdialog', { name: 'Release this invoice?' });
      await expect(dialog).toBeVisible();
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4140-dialog-${viewport.width}.png` });
      expect(sent).toEqual([]);
      await dialog.getByRole('button', { name: 'Keep it' }).click();
      await expect(dialog).toHaveCount(0);
      expect(sent).toEqual([]);
      await main.getByRole('button', { name: 'Release invoice' }).click();
      await dialog.getByRole('button', { name: 'Release invoice' }).dblclick();
      await expect(page.getByRole('status').filter({ hasText: 'Release requested.' })).toContainText('Release requested. The invoice is being sent; this page will update.');
      await expect(main.locator('.work-state')).toHaveText('Processing');
      await expect(main.getByRole('button', { name: 'Release invoice' })).toHaveCount(0);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4140-requested-${viewport.width}.png`, fullPage: true });
      await expect(main.locator('.work-state')).toHaveText('Verified', { timeout: 30_000 });
      await expect(invoice).not.toContainText('Not issued yet');
      await expect(invoice).not.toContainText('No delivery recorded');
      expect(sent).toEqual([RELEASE]);
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4143 does not offer it: no button, no controls row, no words about it; the invoice reads Unknown, never 0', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4143');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByRole('button', { name: /release/i })).toHaveCount(0);
      await expect(main.locator('.work-controls')).toHaveCount(0);
      await expect(main).not.toContainText(/release/i);
      const invoice = main.getByRole('heading', { name: 'Invoice' }).locator('xpath=ancestor::section[1]');
      await expect(invoice.getByText('Unknown')).toHaveCount(2);
      await expect(invoice).not.toContainText(/\b0\.00\b/);
      expect(sent).toEqual([]);
    });

    test('4141: the 202 leaves it offered at the same revision, so it stays disabled and no second POST is sent', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4141');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Release invoice' }).click();
      await page.getByRole('alertdialog').getByRole('button', { name: 'Release invoice' }).click();
      await expect(main.getByText('Release requested. Waiting for the server.')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Release invoice' })).toBeDisabled();
      await page.waitForTimeout(11_000);
      expect(sent).toHaveLength(1);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4141-${viewport.width}.png`, fullPage: true });
    });

    test('a dropped connection locks the release; a reload keeps it locked; no second POST', async ({ page }) => {
      const sent = writes(page);
      await scenario(page, 'wdrop');
      await page.goto('/work/4140');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Release invoice' }).click();
      await page.getByRole('alertdialog').getByRole('button', { name: 'Release invoice' }).click();
      await expect(main.getByRole('alert')).toContainText('We couldn’t confirm that this happened. Check the page before trying again.');
      await expect(main.getByRole('button', { name: 'Release invoice' })).toBeDisabled();
      await expect(main.locator('.psl-reason', { hasText: 'Check the page before trying again.' })).toBeVisible();
      await expect(main.getByRole('button', { name: /try again|retry/i })).toHaveCount(0);
      await page.context().clearCookies({ name: 'psl_mock_scenario' });
      await page.reload();
      await loaded(page);
      await expect(main.getByRole('button', { name: 'Release invoice' })).toBeDisabled();
      await expect(main.locator('.psl-reason', { hasText: 'Check the page before trying again.' })).toBeVisible();
      await page.waitForTimeout(6_000);
      expect(sent).toEqual([RELEASE]);
    });

    test('4144: after an unknown release, Check what happened sends a reconcile, never a release', async ({ page }) => {
      const sent = writes(page);
      await scenario(page, 'w500');
      await page.goto('/work/4144');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Release invoice' }).click();
      await page.getByRole('alertdialog').getByRole('button', { name: 'Release invoice' }).click();
      await expect(main.getByRole('alert')).toContainText('We couldn’t confirm that this happened.');
      await page.context().clearCookies({ name: 'psl_mock_scenario' });
      const check = main.getByRole('button', { name: 'Check what happened' });
      await expect(check).toBeEnabled();
      await check.click();
      await expect.poll(() => sent.length).toBe(2);
      expect(sent[1]).toBe('POST /api/v1/work/4144/actions {"action":"reconcile","expected_revision":9}');
      expect(sent.filter((s) => s.includes('release_invoice'))).toHaveLength(1);
    });

    test('4142 (no version): the button is disabled with its reason and nothing is sent', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4142');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByRole('button', { name: 'Release invoice' })).toBeDisabled();
      await expect(main.getByText('We don’t have this item’s current version yet. Reload and try again.')).toBeVisible();
      await main.getByRole('button', { name: 'Release invoice' }).click({ force: true });
      await expect(page.getByRole('alertdialog')).toHaveCount(0);
      expect(sent).toEqual([]);
    });

    test('a 409 re-reads: "This changed..." and the button is gone; a 422 shows the server words only', async ({ page }) => {
      const sent = writes(page);
      await scenario(page, 'w409');
      await page.goto('/work/4140');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Release invoice' }).click();
      await page.getByRole('alertdialog').getByRole('button', { name: 'Release invoice' }).click();
      await expect(main.getByRole('alert')).toContainText('This changed while you were working. Showing the latest version.');
      await expect(main.getByRole('button', { name: 'Release invoice' })).toHaveCount(0);
      expect(sent).toHaveLength(1);
      await page.context().clearCookies({ name: 'psl_mock_scenario' });
      await scenario(page, 'w422');
      await page.goto('/work/4141');
      await loaded(page);
      await main.getByRole('button', { name: 'Release invoice' }).click();
      await page.getByRole('alertdialog').getByRole('button', { name: 'Release invoice' }).click();
      await expect(main.getByRole('alert')).toContainText('A release setting is missing. Ask the Finance Lead to set it.');
      expect(sent).toHaveLength(2);
    });

    test('the controls row, dialog and invoice block do not overlap and the row stacks on the phone', async ({ page }) => {
      await page.goto('/work/4140');
      await loaded(page);
      const main = page.locator('main#main');
      const button = main.getByRole('button', { name: 'Release invoice' });
      const box = (await button.boundingBox())!;
      const invoice = (await main.getByRole('heading', { name: 'Invoice' }).locator('xpath=ancestor::section[1]').boundingBox())!;
      expect(box.y + box.height).toBeLessThanOrEqual(invoice.y + 1);
      if (viewport.width === 390) {
        expect(box.height).toBeGreaterThanOrEqual(44);
        expect(box.x + box.width).toBeLessThanOrEqual(390);
      }
      await button.click();
      const dialog = (await page.getByRole('alertdialog').boundingBox())!;
      expect(dialog.x).toBeGreaterThanOrEqual(0);
      expect(dialog.x + dialog.width).toBeLessThanOrEqual(viewport.width);
    });
  });
}
