import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-87a: the work item's own controls on the live shapes (mock/work-live.mjs): check what happened, resume, cancel, background.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const SHOTS = process.env.F87_SHOTS;

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

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4120 shows one button and no choice; pressing it sends one exact body and shows what the re-read says', async ({ page }) => {
      const sent = writes(page);
      await scenario(page, 'ready');
      await page.goto('/work/4120');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByRole('group', { name: 'Controls' }).getByRole('button')).toHaveCount(1);
      await expect(main.getByRole('radio')).toHaveCount(0);
      expect(sent).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4120-${viewport.width}.png`, fullPage: true });
      await main.getByRole('button', { name: 'Check what happened' }).click();
      await expect(main.getByRole('status')).toContainText('Checked. This item is now: Ready to continue.');
      await expect(main.locator('.work-state')).toHaveText('Ready to continue');
      expect(sent).toEqual(['POST /api/v1/work/4120/actions {"action":"reconcile","expected_revision":5}']);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4120-done-${viewport.width}.png`, fullPage: true });
    });

    test('4111 has no controls row, no heading and no empty gap', async ({ page }) => {
      await page.goto('/work/4111');
      await loaded(page);
      await expect(page.getByRole('group', { name: 'Controls' })).toHaveCount(0);
      await expect(page.locator('.work-controls')).toHaveCount(0);
    });

    test('4121 resume sends the control body; cancel asks first and sends only on "Cancel this work"', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4121');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByRole('button', { name: 'Resume' })).toBeVisible();
      await main.getByRole('button', { name: 'Cancel' }).click();
      const dialog = page.getByRole('alertdialog', { name: 'Cancel this work?' });
      await expect(dialog).toBeVisible();
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4121-dialog-${viewport.width}.png` });
      expect(sent).toEqual([]);
      await dialog.getByRole('button', { name: 'Keep it' }).click();
      await expect(dialog).toHaveCount(0);
      expect(sent).toEqual([]);
      await main.getByRole('button', { name: 'Cancel' }).click();
      await dialog.getByRole('button', { name: 'Cancel this work' }).click();
      await expect(main.locator('.work-state')).toHaveText('Cancelled');
      expect(sent).toEqual(['POST /api/v1/work/4121/control {"action":"cancel","expected_revision":3}']);
    });

    test('4121 resume', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4121');
      await loaded(page);
      await page.locator('main#main').getByRole('button', { name: 'Resume' }).click();
      await expect(page.locator('main#main .work-state')).toHaveText('Ready to continue');
      expect(sent).toEqual(['POST /api/v1/work/4121/control {"action":"resume","expected_revision":3}']);
    });

    test('4122 pause and continue carry no action', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4122');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Pause background work' }).click();
      await expect(main.getByRole('status')).toBeVisible();
      await main.getByRole('button', { name: 'Continue background work' }).click();
      await expect.poll(() => sent.length).toBe(2);
      expect(sent).toEqual(['POST /api/v1/work/4122/background {"expected_revision":7,"enabled":false}', 'POST /api/v1/work/4122/background {"expected_revision":7,"enabled":true}']);
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4110 (no version) draws disabled buttons with the reason and sends nothing', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4110');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByRole('button', { name: 'Check what happened' })).toBeDisabled();
      await expect(main.getByText('We don’t have this item’s current version yet. Reload and try again.')).toHaveCount(2);
      expect(sent).toEqual([]);
    });

    test('a 409 shows the latest version and the next press carries the new revision', async ({ page }) => {
      const sent = writes(page);
      await scenario(page, 'w409');
      await page.goto('/work/4121');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Resume' }).click();
      await expect(main.getByRole('alert')).toContainText('This changed while you were working. Showing the latest version.');
      await page.context().clearCookies({ name: 'psl_mock_scenario' });
      await main.getByRole('button', { name: 'Resume' }).click();
      await expect.poll(() => sent.length).toBe(2);
      expect(sent[1]).toContain('"expected_revision":5');
    });

    test('a dropped connection on Resume locks it and the page sends nothing more', async ({ page }) => {
      const sent = writes(page);
      await scenario(page, 'wdrop');
      await page.goto('/work/4121');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Resume' }).click();
      await expect(main.getByRole('alert')).toContainText('We couldn’t confirm that this happened. Check the page before trying again.');
      await expect(main.locator('.work-state')).toHaveText('Ready to continue');
      expect(sent).toHaveLength(1);
    });
  });
}
