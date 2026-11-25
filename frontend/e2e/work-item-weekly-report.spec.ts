import { expect, test, type Page } from '@playwright/test';

// F-89: review (approve, return, refuse) and correct on the weekly report panel, on the live shapes (mock/work-live.mjs).
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.getByText('Recipients')).toBeVisible();
};
const writes = (page: Page) => {
  const sent: { path: string; body: unknown }[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/api/')) sent.push({ path: new URL(r.url()).pathname, body: JSON.parse(r.postData() ?? '{}') });
  });
  return sent;
};
const scenario = (page: Page, value: string) => page.context().addCookies([{ name: 'psl_mock_scenario', value, url: `http://localhost:${process.env.E2E_PORT ?? 3101}` }]);

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4130 shows the text, the note and three buttons; 4131 two; 4133 none', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4130');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('Build is <b>on track</b>.', { exact: false })).toBeVisible();
      await expect(main.getByText('Note from the review')).toBeVisible();
      for (const name of ['Approve and send', 'Return with a note', 'Refuse']) await expect(main.getByRole('button', { name })).toBeVisible();
      expect(sent).toEqual([]);
      await page.goto('/work/4131');
      await loaded(page);
      await expect(main.getByRole('button', { name: 'Refuse' })).toHaveCount(0);
      await expect(main.getByRole('button', { name: 'Return with a note' })).toBeVisible();
      await page.goto('/work/4133');
      await loaded(page);
      await expect(main.getByText('Your review')).toHaveCount(0);
      await expect(main.getByText('The report:', { exact: false })).toHaveCount(0);
      await expect(main.getByRole('button', { name: 'Edit your update' })).toHaveCount(0);
    });

    test('4136 and 4137 hold Approve; 4134 has no review buttons', async ({ page }) => {
      const main = page.locator('main#main');
      for (const id of [4136, 4137]) {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(main.getByRole('button', { name: 'Approve and send' })).toHaveCount(0);
        await expect(main.getByRole('button', { name: 'Refuse' })).toBeVisible();
        await expect(main.getByText(/can’t be approved from this page/)).toBeVisible();
      }
      await page.goto('/work/4134');
      await loaded(page);
      await expect(main.getByRole('button', { name: 'Return with a note' })).toHaveCount(0);
    });

    test('Approve sends one exact body and tells the result from the re-read', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4130');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Approve and send' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Recorded.' })).toContainText('This item is now: Waiting');
      expect(sent).toEqual([{ path: '/api/v1/work/4130/reviews', body: { kind: 'document', expected_revision: 6, case_revision: 12, version_id: 9101, verdict: 'approve', note: '' } }]);
      await expect(main.getByRole('button', { name: 'Approve and send' })).toHaveCount(0);
      await expect(main.getByText('No receipt yet')).toBeVisible();
    });

    test('Return and Refuse need a note, then send it', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4130');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Return with a note' }).click();
      await expect(main.getByText('Write a note first.')).toBeVisible();
      expect(sent).toEqual([]);
      await main.getByLabel('Note').fill('The dates are wrong.');
      await main.getByRole('button', { name: 'Refuse' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Recorded.' })).toBeVisible();
      expect(sent).toHaveLength(1);
      expect(sent[0].body).toMatchObject({ kind: 'document', verdict: 'reject', note: 'The dates are wrong.' });
    });

    test('a refused review shows the server words; a stale one re-reads and keeps the note', async ({ page }) => {
      const sent = writes(page);
      await scenario(page, 'w403');
      await page.goto('/work/4130');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Approve and send' }).click();
      await expect(main.getByText('You can’t do this.')).toBeVisible();
      await expect(main.getByText('You wrote this report')).toBeVisible();
      await scenario(page, 'w409');
      await page.goto('/work/4131');
      await loaded(page);
      await main.getByLabel('Note').fill('keep me');
      await main.getByRole('button', { name: 'Return with a note' }).click();
      await expect(main.getByText('This changed while you were working. Showing the latest version.')).toBeVisible();
      await expect(main.getByLabel('Note')).toHaveValue('keep me');
      expect(sent).toHaveLength(2);
    });

    test('a dropped connection locks the buttons (write did not run)', async ({ page }) => {
      const sent = writes(page);
      await scenario(page, 'wdrop0');
      await page.goto('/work/4130');
      await loaded(page);
      const main = page.locator('main#main');
      await main.getByRole('button', { name: 'Approve and send' }).click();
      await expect(main.getByText('We couldn’t confirm that this happened. Check the page before trying again.')).toBeVisible();
      for (const name of ['Approve and send', 'Return with a note', 'Refuse']) await expect(main.getByRole('button', { name })).toBeDisabled();
      expect(sent).toHaveLength(1);
    });

    test('4132 corrects after a return: quote, form, exact body, edit block gone', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4132');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('Returned to you')).toBeVisible();
      await expect(main.getByText('Please add the 14 Nov supplier delay to Risks.')).toBeVisible();
      await main.getByRole('button', { name: 'Edit your update' }).click();
      await expect(main.getByRole('button', { name: 'Send for review' })).toBeDisabled();
      await main.getByLabel('Reason for the change').fill('Added the delay');
      await main.getByRole('button', { name: 'Send for review' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Your update was sent for review.' })).toBeVisible();
      expect(sent).toHaveLength(1);
      expect(sent[0].path).toBe('/api/v1/work/4132/weekly-report');
      expect(sent[0].body).toMatchObject({ action: 'correct', expected_revision: 6, case_revision: 12, draft_id: null, reason: 'Added the delay' });
      await expect(main.getByRole('button', { name: 'Edit your update' })).toHaveCount(0);
    });

    test('4135 says why it cannot be edited', async ({ page }) => {
      await page.goto('/work/4135');
      await loaded(page);
      await expect(page.locator('main#main').getByText(/aren’t available to edit here/)).toBeVisible();
      await expect(page.locator('main#main').getByRole('button', { name: 'Edit your update' })).toHaveCount(0);
    });
  });
}
