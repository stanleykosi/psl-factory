import { expect, test, type Page } from '@playwright/test';

// D-155: the live demo of the mock. These two specs need the dev server the dev script starts (MOCK_DEMO and
// NEXT_PUBLIC_MOCK_DEMO on): the demo bar does not exist in a production build. Run them with E2E_DEMO=1.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.skip(process.env.E2E_DEMO !== '1', 'needs the dev server with the demo bar (E2E_DEMO=1)');
test.describe.configure({ timeout: 240_000 });

test.beforeEach(async ({ request, context, baseURL }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies(
    [['psl_mock_persona', 'pm'], ['psl_mock_demo', 'on'], ['psl_mock_speed', 'fast']].map(([name, value]) => ({ name, value, url: baseURL! })),
  );
});

async function switchRole(page: Page, role: string) {
  await page.getByRole('complementary', { name: 'Demo controls' }).getByRole('button', { name: 'Demo' }).click();
  await page.getByRole('combobox', { name: 'Role' }).click();
  await page.getByRole('option', { name: role }).click();
  await page.waitForLoadState('load');
}

test('a line run: pm starts an invoice, the steps tick, the Finance Lead decides from the demo bar, and it ends in Done', async ({ page }) => {
  await page.goto('/my-work');
  await page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Project' }).click();
  await dialog.getByRole('option', { name: 'Lagoon Health · patient app' }).click();
  await dialog.getByRole('combobox', { name: 'Completed milestone' }).click();
  await dialog.getByRole('option', { name: /Milestone 3/ }).click();
  await dialog.getByRole('button', { name: 'Start the invoice' }).click();
  await expect(page).toHaveURL(/\/work\/W-9001$/);

  // the first station is the agent's: its steps appear one after the other
  await expect(page.getByText('Read what “Draft invoice” needs')).toBeVisible();
  await expect(page.getByText('Worked on “Draft invoice”')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Checked the result of “Draft invoice”')).toBeVisible({ timeout: 30_000 });

  // then it waits for a person, who is not the starter
  await expect(page.getByText('A Finance Lead decides “Finance review”.').first()).toBeVisible({ timeout: 30_000 });
  await page.goto('/my-work?queue=waiting_on_others');
  await expect(page.getByRole('link', { name: /Invoice preparation and delivery · Demo 1/ })).toBeVisible();

  await switchRole(page, 'Finance Lead');
  await page.goto('/my-work');
  await page.getByRole('link', { name: /Invoice preparation and delivery · Demo 1/ }).click();
  await page.getByRole('link', { name: 'Open the decision' }).click();
  const approve = page.getByRole('button', { name: /^Approve / });
  await expect(approve).toBeEnabled();
  await approve.click();

  // the remaining stations run, and the item ends verified, in Done, for the starter
  await switchRole(page, 'PM');
  await expect.poll(async () => {
    await page.goto('/my-work?queue=done');
    return page.getByRole('link', { name: /Invoice preparation and delivery · Demo 1/ }).count();
  }, { timeout: 120_000, intervals: [5_000] }).toBe(1);
  await page.getByRole('link', { name: /Invoice preparation and delivery · Demo 1/ }).click();
  await expect(page.getByText('Done. Every step is in the history.').first()).toBeVisible();
});

test('an assistant run: the steps appear one at a time, then the answer, its sources and the card', async ({ page }) => {
  await page.goto('/assistant');
  await page.getByRole('textbox', { name: 'Message Tola' }).fill('How are my projects doing?');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page).toHaveURL(/\/assistant\/CV-N1$/);
  await expect(page.getByText('Read your request')).toBeVisible();
  await expect(page.getByText('Looked up the projects and milestones you can see')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Sample answer from Tola in the live demo.')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Sample project plan')).toBeVisible();
  await expect(page.getByText('Sample status note')).toBeVisible();
});
