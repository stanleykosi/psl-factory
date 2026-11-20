import { expect, test } from '@playwright/test';

// F-52: the shared header's History link is a 44 by 44 target at 390 and unchanged on desktop. Measured on two lines
// (the income schedule W-2702 and the leadership report W-3202); persona is the mock's default finance lead / ceo as each line needs.
const LINES = [
  { id: 'W-2702', persona: 'finance_lead' },
  { id: 'W-3202', persona: 'ceo' },
];

for (const { id, persona } of LINES) {
  test.describe(`${id} History link`, () => {
    test.beforeEach(async ({ context }) => {
      await context.addCookies([{ name: 'psl_mock_persona', value: persona, url: test.info().project.use.baseURL! }]);
    });

    test('is at least 44 by 44 at 390', async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(`/work/${id}`);
      const link = page.getByRole('link', { name: 'History' });
      await expect(link).toBeVisible();
      const box = await link.evaluate((el) => el.getBoundingClientRect().toJSON());
      expect(box.width).toBeGreaterThanOrEqual(44);
      expect(box.height).toBeGreaterThanOrEqual(44);
    });

    test('is unchanged on desktop (under 44 high)', async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(`/work/${id}`);
      const link = page.getByRole('link', { name: 'History' });
      await expect(link).toBeVisible();
      const box = await link.evaluate((el) => el.getBoundingClientRect().toJSON());
      expect(box.height).toBeLessThan(44);
    });
  });
}
