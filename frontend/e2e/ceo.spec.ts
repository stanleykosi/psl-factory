import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// D-150: the CEO (Folake Bello) walked on the contract mock: My work in three queues, an item and its history,
// every project, the factory floor, alerts and Assistant. Sample data only; no pay amounts, no payment-exception decisions.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

test.beforeEach(async ({ request, context }: { request: import('@playwright/test').APIRequestContext; context: BrowserContext }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'ceo', url: test.info().project.use.baseURL! }]);
});

const tab = (page: Page, name: RegExp) => page.getByRole('tablist', { name: 'My work' }).getByRole('tab', { name });
const rowLinks = (page: Page) => page.locator('#my-work-panel').getByRole('link');

test('My work: five decisions, five waiting, four done, and search narrows them', async ({ page }) => {
  await page.goto('/my-work');
  await expect(page.getByText('Folake Bello · CEO')).toBeVisible();
  await expect(tab(page, /^Needs me/)).toBeVisible();
  for (const title of ['Kora Logistics · SOW v3', 'Harbour Bank · Mobile onboarding costing', 'Harmattan Bank · Emergency change for an incident', 'Lagoon Health · Escalate and communicate', 'PMO · Leadership report (November)']) {
    await expect(rowLinks(page).filter({ hasText: title }).first()).toBeVisible();
  }
  expect(await rowLinks(page).count()).toBeGreaterThanOrEqual(5);
  await tab(page, /^Waiting on others/).click();
  await expect(rowLinks(page).filter({ hasText: 'Ojo Foods · Ordering app plan' }).first()).toBeVisible();
  expect(await rowLinks(page).count()).toBeGreaterThanOrEqual(5);
  await tab(page, /^Done/).click();
  await expect(rowLinks(page).filter({ hasText: 'Lagoon Health · Discovery plan' }).first()).toBeVisible();
  expect(await rowLinks(page).count()).toBeGreaterThanOrEqual(4);
});

test('the Kora SOW v3 decision opens with the CEO at the last step, and its History tab lists the chain', async ({ page }) => {
  await page.goto('/my-work');
  await page.waitForLoadState('networkidle'); // the dev server hydrates after the rows draw; an early click on a row can be lost
  await rowLinks(page).filter({ hasText: 'Kora Logistics · SOW v3' }).first().click();
  await expect(page).toHaveURL(/\/work\/W-5001$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Kora Logistics · SOW v3' })).toBeVisible();
  await expect(page.getByText('CEO approval').first()).toBeVisible();
  await expect(page.getByText('You decide on statement of work v3.')).toBeVisible();
  await page.getByRole('tablist', { name: 'Work item' }).getByRole('tab', { name: /^History/ }).click();
  await expect(page.getByText(/Tola · planning agent/).first()).toBeVisible();
  await expect(page.getByText(/Kemi Adebayo · PMO Lead/).first()).toBeVisible();
  expect(await page.getByRole('table', { name: 'History, newest first' }).getByRole('row').count()).toBeGreaterThanOrEqual(6); // header + 5
});

test('the emergency change shows its cost as not known, never zero', async ({ page }) => {
  await page.goto('/work/W-5003');
  await expect(page.getByRole('heading', { level: 1, name: 'Harmattan Bank · Emergency change for an incident' })).toBeVisible();
  await expect(page.getByText('You decide whether the emergency change goes ahead. The cost is not known yet.')).toBeVisible();
  await expect(page.getByText(/₦\s?0(\.00)?\b/)).toHaveCount(0);
});

test('Projects: every project is listed and one opens', async ({ page }) => {
  await page.goto('/projects');
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible();
  await expect(page.locator('[data-project-link]').first()).toBeVisible();
  await page.getByRole('tab', { name: /All I can see/ }).click();
  await expect(page).toHaveURL(/\?status=all$/);
  await page.goto('/projects/P-0101');
  await expect(page.getByRole('tablist', { name: 'Project' })).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Lagoon Health');
});

test('Overview: the factory floor is populated', async ({ page }) => {
  await page.goto('/overview');
  await expect(page.getByRole('heading', { level: 1, name: 'Factory floor' })).toBeVisible();
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.locator('dl.overview__totals > div')).toHaveCount(4);
  await expect(page.locator('section[aria-label="Lines"] .overview__lines-of > .overview__row').first()).toBeVisible();
});

test('the Notifications page lists CEO alerts that open the items, and the bell counts the unread', async ({ page }) => {
  await page.goto('/notifications');
  await expect(page.getByRole('heading', { level: 1, name: 'Notifications' })).toBeVisible();
  for (const text of ['Kora Logistics SOW v3 needs your approval', 'The Harmattan Bank emergency change needs your decision', 'The Lagoon Health escalation is waiting for your decision', 'The November leadership report is ready for your review']) {
    await expect(page.getByText(text)).toBeVisible();
  }
  await expect(page.getByRole('link', { name: /Kora Logistics SOW v3 needs your approval/ }).first()).toHaveAttribute('href', '/work/W-5001');
  await expect(page.locator('nav.psl-nav').getByRole('button', { name: /^Alerts/ })).toContainText('4');
});

test('Assistant: five conversations, one opens in full, Zainab declines pay, and a new message gets a reply', async ({ page }) => {
  await page.goto('/assistant');
  for (const title of ['What is waiting for my decision?', 'Is the Kora Logistics SOW v3 ready for me to approve?', 'Which client invoices are still unpaid?', 'Can I see what the Delivery team is paid?', 'Which projects need me this week?']) {
    await expect(page.getByText(title).first()).toBeVisible();
  }
  await page.goto('/assistant/CV-2442');
  await expect(page.getByText('The PM and the PMO Lead have both approved it.', { exact: false })).toBeVisible();
  await expect(page.getByText('Read SOW v3 and its approval chain')).toBeVisible();
  await page.goto('/assistant/CV-2444');
  await expect(page.getByText(/has not been set up yet/).first()).toBeVisible();
  await expect(page.getByText(/₦|NGN/)).toHaveCount(0);
  await page.getByRole('textbox', { name: /^Message / }).fill('And what is waiting on others?');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(/I can show what waits for your decision/)).toBeVisible();
});
