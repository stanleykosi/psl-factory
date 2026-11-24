import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-55: the HR stand-in persona (D-142) walked end to end on the contract mock: My work in three queues, two work
// items and their history, alerts, Assistant, and the stand-in line to start. Sample data only; no pay amounts.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

async function asHr(context: BrowserContext) {
  await context.addCookies([{ name: 'psl_mock_persona', value: 'hr', url: test.info().project.use.baseURL! }]);
}

test.beforeEach(async ({ request, context }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await asHr(context);
});

const tab = (page: Page, name: RegExp) => page.getByRole('tablist', { name: 'My work' }).getByRole('tab', { name });
const rowLinks = (page: Page) => page.locator('#my-work-panel').getByRole('link');

test('My work has rows in all three queues, and search narrows them', async ({ page }) => {
  await page.goto('/my-work');
  await expect(tab(page, /^Needs me/)).toBeVisible();
  await expect(rowLinks(page).filter({ hasText: 'November staff list · confirm for payroll' }).first()).toBeVisible();
  expect(await rowLinks(page).count()).toBeGreaterThanOrEqual(3);
  await tab(page, /^Waiting on others/).click();
  await expect(rowLinks(page).filter({ hasText: 'Payroll correction' }).first()).toBeVisible();
  expect(await rowLinks(page).count()).toBeGreaterThanOrEqual(3);
  await tab(page, /^Done/).click();
  await expect(rowLinks(page).filter({ hasText: 'Leaver record' }).first()).toBeVisible();
  expect(await rowLinks(page).count()).toBeGreaterThanOrEqual(2);
});

for (const [id, title, agentStep, next] of [
  ['W-4601', 'November staff list · confirm for payroll', 'Found 2 staff with no business unit', 'Next, HR confirms the November staff list. Zainab then sends it to Finance for payroll matching.'],
  ['W-4605', 'Payroll correction · HR Lead decision', 'Wrote the correction for the HR Lead to decide', 'The HR Lead decides whether to correct the October matching. Amounts are not shown here.'],
]) {
  test(`${id} opens with its track, agent and next step, and a History tab`, async ({ page }) => {
    await page.goto(`/work/${id}`);
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
    await expect(page.getByText('Zainab').first()).toBeVisible();
    await expect(page.getByText(agentStep)).toBeVisible();
    await expect(page.getByText(next)).toBeVisible();
    await page.getByRole('tablist', { name: 'Work item' }).getByRole('tab', { name: /^History/ }).click();
    await expect(page.getByText('Restricted').first()).toBeVisible();
    await expect(page.getByText(/Zainab · HR agent/).first()).toBeVisible();
    await expect(page.getByText(/Amaka Obi · HR/).first()).toBeVisible();
    expect(await page.getByRole('table', { name: 'History, newest first' }).getByRole('row').count()).toBeGreaterThanOrEqual(6); // header + 5
  });
}

test('the Notifications page lists HR alerts that open HR items', async ({ page }) => {
  await page.goto('/notifications');
  await expect(page.getByRole('heading', { level: 1, name: 'Notifications' })).toBeVisible();
  await expect(page.getByText('Your November staff list is ready to confirm')).toBeVisible();
  await expect(page.getByText('Finance asked for Segun Alade’s last working day')).toBeVisible();
  const link = page.getByRole('link', { name: /Your November staff list is ready to confirm/ }).first();
  await expect(link).toHaveAttribute('href', '/work/W-4601');
});

test('the bell shows the unread HR alerts', async ({ page }) => {
  await page.goto('/my-work');
  await expect(page.locator('nav.psl-nav').getByRole('button', { name: /^Alerts/ })).toContainText('3');
});

test('Assistant: two conversations open in full, the salary one is declined, and a new message gets a reply', async ({ page }) => {
  await page.goto('/assistant');
  await expect(page.getByText('Is the November staff list ready for Finance?').first()).toBeVisible();
  for (const title of ['Fix the two staff with no business unit', 'Why did Finance ask about a leaver?', 'A staff member’s salary', 'Who joined or left in November?']) {
    await expect(page.getByText(title).first()).toBeVisible();
  }
  await page.goto('/assistant/CV-2421');
  await expect(page.getByText('Two people, Ifeoma Nwosu and Sani Garba, have no business unit', { exact: false })).toBeVisible();
  await expect(page.getByText('Compared it with the October list')).toBeVisible();
  await page.goto('/assistant/CV-2424');
  await expect(page.getByText(/has not been set up yet/).first()).toBeVisible();
  await expect(page.getByText(/₦|NGN/)).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Message Zainab' }).fill('Who left in October?');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(/I do not show pay amounts/)).toBeVisible();
});

// F-86: the drawer lists live lines; the HR staff list has no live form yet (LC-Q3), so it opens the chooser and offers the full form's link.
test('hr opens Start work: a line without a live form is unavailable, with a link to its full form, and starts nothing', async ({ page }) => {
  await page.goto('/my-work');
  await expect(tab(page, /^Needs me/)).toBeVisible();
  await page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Choose a line' });
  await expect(dialog.getByText('Payroll', { exact: true })).toBeVisible();
  await expect(dialog.getByRole('link', { name: 'Open in the full form' }).first()).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
});

test('hr is refused Projects, Exceptions and Setup', async ({ page }) => {
  for (const [path, words] of [['/projects', 'This section isn’t open to your role.'], ['/setup', 'This section isn’t open to your role.'], ['/exceptions', 'This list is for Leads']]) {
    await page.goto(path);
    await expect(page.getByText(words), path).toBeVisible();
    await expect(page.getByRole('link', { name: 'Go to My work' }), path).toBeVisible();
  }
});

test.describe('HR Lead (stand-in)', () => {
  test.beforeEach(async ({ context }) => {
    await context.addCookies([{ name: 'psl_mock_persona', value: 'hr_lead', url: test.info().project.use.baseURL! }]);
  });

  test('sees the decisions as Needs me, opens one and its history, and is refused Setup', async ({ page }) => {
    await page.goto('/my-work');
    await expect(page.getByText('Ngozi Adeyemi · HR Lead')).toBeVisible();
    const panel = page.locator('#my-work-panel');
    for (const title of ['Payroll correction · HR Lead decision', 'Staff record change · Chinedu Eze moves to Delivery', 'Business unit moves · confirm before payroll matching']) {
      await expect(panel.getByRole('link', { name: new RegExp(title) }).first()).toBeVisible();
    }
    await page.goto('/work/W-4612');
    await expect(page.getByRole('link', { name: 'Open the decision' })).toBeVisible();
    await page.getByRole('tablist', { name: 'Work item' }).getByRole('tab', { name: /^History/ }).click();
    await expect(page.getByText('Restricted').first()).toBeVisible();
    await expect(page.getByText(/Zainab · HR agent/).first()).toBeVisible();
    await page.goto('/setup');
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
  });

  test('Assistant lists three conversations and Zainab declines a salary', async ({ page }) => {
    await page.goto('/assistant/CV-2433');
    await expect(page.getByText(/has not been set up yet/).first()).toBeVisible();
    await page.goto('/assistant');
    await expect(page.getByText('What is waiting for my decision?').first()).toBeVisible();
    await expect(page.getByText('Are the business unit moves safe to confirm?').first()).toBeVisible();
  });
});
