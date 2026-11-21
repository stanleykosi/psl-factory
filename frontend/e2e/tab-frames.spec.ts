import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// D-170: a tab click keeps the page's frame. The h1 is tagged before the click and must still carry the tag after it,
// which only holds when the same element stays mounted (the frame is a layout, not rebuilt per tab).
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

/** The visible h1 of the page (a phone page draws a second, hidden one in some views). */
const heading = (page: Page) => page.locator('main#main h1:visible').first();

async function tag(page: Page) {
  await expect(heading(page)).toBeVisible();
  await heading(page).evaluate((el) => el.setAttribute('data-kept', 'yes'));
}

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  test.describe(label, () => {
    test.use({ viewport, ...(viewport === PHONE ? { hasTouch: true, isMobile: true } : {}) });

    test('project: Journey to Milestones keeps the same h1 and tab bar', async ({ page, context }) => {
      await setCookies(context, { psl_mock_persona: 'pm' });
      await page.goto('/projects/P-0101');
      await tag(page);
      const tabs = page.getByRole('tablist', { name: 'Project' });
      await tabs.getByRole('tab', { name: /^Milestones/ }).click();
      await expect(page).toHaveURL(/\/projects\/P-0101\/milestones$/);
      await expect(tabs.getByRole('tab', { name: /^Milestones/ })).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('main#main h1[data-kept="yes"]:visible').first()).toBeVisible();
    });

    test('work item: Overview to History keeps the same h1 and tab bar', async ({ page, context }) => {
      await setCookies(context, { psl_mock_persona: 'finance_lead' });
      await page.goto('/work/W-1004');
      await tag(page);
      const tabs = page.getByRole('tablist', { name: 'Work item' });
      await tabs.getByRole('tab', { name: /^History/ }).click();
      await expect(page).toHaveURL(/\/work\/W-1004\/history$/);
      await expect(tabs.getByRole('tab', { name: /^History/ })).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('main#main h1[data-kept="yes"]:visible').first()).toBeVisible();
    });
  });
}

test.describe('setup, desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('Rules to Delegation keeps the same h1 and tab bar, and the Rules count stays', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'admin' });
    await page.goto('/setup/rules');
    await tag(page);
    const tabs = page.getByRole('tablist', { name: 'Setup' });
    const rules = tabs.getByRole('tab', { name: /^Rules/ });
    const label = await rules.textContent();
    await tabs.getByRole('tab', { name: 'Delegation' }).click();
    await expect(page).toHaveURL(/\/setup\/delegation$/);
    await expect(tabs.getByRole('tab', { name: 'Delegation' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('main#main h1[data-kept="yes"]:visible').first()).toBeVisible();
    await expect(rules).toHaveText(label!);
  });
});
