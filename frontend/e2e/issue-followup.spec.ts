import { expect, test, type Page } from '@playwright/test';

// F-111: the issue follow-up panel (SCR-30 part 1), read only, on the mock's fixtures 5101 to 5107.
const BANNED = /FIX IN TESTING|FOLLOW-UP VERIFIED|recorded by PM|Tola/;
const WRITES = /^(Post update|Record reply|Set owner|Message owner|Refresh|Restart|Raise an escalation)/;

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pmo_lead', url: test.info().project.use.baseURL! }]);
});

async function open(page: Page, id: number) {
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && !r.url().includes('/__mock/')) writes.push(`${r.method()} ${r.url()}`);
  });
  await page.goto(`/work/${id}`);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  return writes;
}

async function noWriteControls(page: Page) {
  for (const b of await page.getByRole('button').all()) expect((await b.textContent()) ?? '').not.toMatch(WRITES);
  await expect(page.locator('body')).not.toContainText(BANNED);
}

test('5101 shows the issue, owner, age and the blocked milestone', async ({ page }) => {
  const writes = await open(page, 5101);
  await expect(page.getByText('ISS-0233')).toBeVisible();
  await expect(page.getByText('High', { exact: true })).toBeVisible();
  await expect(page.getByText('In Progress', { exact: true })).toBeVisible();
  await expect(page.getByText('Engineering', { exact: true })).toBeVisible();
  await expect(page.getByText('3 days')).toBeVisible();
  await expect(page.getByText('Go-live', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'What has happened' })).toBeVisible();
  await expect(page.getByText('Owner acknowledged')).toBeVisible();
  await noWriteControls(page);
  expect(writes).toEqual([]);
});

test('5102 overdue shows the banner, the chasing rows and the timing', async ({ page }) => {
  await open(page, 5102);
  await expect(page.getByText('No response since 09 Nov')).toBeVisible();
  await expect(page.getByText('No receipt yet')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('Time unknown');
  await expect(page.getByText('Reminder due')).toBeVisible();
  await expect(page.getByText('Escalate by')).toBeVisible();
  await expect(page.getByText('PMO lead', { exact: true })).toBeVisible();
  await noWriteControls(page);
});

test('5103 no owner shows the banner and no zero or placeholder', async ({ page }) => {
  await open(page, 5103);
  await expect(page.getByText('This issue has no owner.')).toBeVisible();
  await expect(page.getByText('Not recorded').first()).toBeVisible();
  await expect(page.locator('body')).not.toContainText(/0 days|Unassigned|Reminder due/);
  await expect(page.getByText('No message has been sent to the owner.')).toBeVisible();
  await noWriteControls(page);
});

test('5104 verified leads with the finding and a planned UAT that is not a link', async ({ page }) => {
  await open(page, 5104);
  await expect(page.getByText('The fix was confirmed by Engineering on 22 Nov.')).toBeVisible();
  await expect(page.getByText('UAT (planned)')).toBeVisible();
  await expect(page.getByRole('link', { name: /UAT/ })).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText('Closed');
  await noWriteControls(page);
});

test('5105 messages 403 leaves the rest of the page', async ({ page }) => {
  await open(page, 5105);
  await expect(page.getByText('Chasing is not available to you')).toBeVisible();
  await expect(page.getByText('ISS-0233')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'What has happened' })).toBeVisible();
});

test('5106 is unavailable', async ({ page }) => {
  await page.goto('/work/5106');
  await expect(page.getByRole('heading', { name: 'This record is unavailable.' })).toBeVisible();
});

test('5107 detail 503 shows the facts and a message in place of the timeline', async ({ page }) => {
  await open(page, 5107);
  await expect(page.getByText('ISS-0233')).toBeVisible();
  await expect(page.getByText(/Reload the page to try again/)).toBeVisible();
});
