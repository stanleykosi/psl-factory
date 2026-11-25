import { expect, test, type Page } from '@playwright/test';

// F-98: the RFP submission panel on the live work item (SCR-40): the pack, the PM's send, the reviewer's verdict, the send to the client
// (live shapes in mock/bid-pack-live.mjs).
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.getByText('What will be sent')).toBeVisible();
};
const writes = (page: Page) => {
  const sent: { path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/api/')) sent.push({ path: new URL(r.url()).pathname, body: JSON.parse(r.postData() ?? '{}') });
  });
  return sent;
};
const noSideways = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('shows the pack, what will be sent and the file checks, with nothing the API does not serve', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4501');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('Not sent for review yet')).toBeVisible();
      await expect(main.getByText(/Dear Lagoon Health team/)).toBeVisible();
      await expect(main.getByText('6.4 MB')).toBeVisible();
      await expect(main.getByRole('link', { name: 'Open the pack as a PDF' })).toBeVisible();
      await expect(main.getByText(/Company forms|What happened|Agent note/)).toHaveCount(0);
      expect(sent).toEqual([]);
      expect(await noSideways(page)).toBe(true);
    });

    test('the PM sends the pack for review and the page says it is with the reviewer', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4501');
      await loaded(page);
      await page.getByRole('button', { name: 'Send for review' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'The pack was sent for review.' })).toContainText('This item is now:');
      expect(sent).toEqual([{ path: '/api/v1/work/4501/bid-pack/review-request', body: { expected_revision: 9, case_revision: 89, pack_id: 77, version_id: 801 } }]);
      await expect(page.locator('main#main').getByText('With the reviewer')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Send for review' })).toHaveCount(0);
    });

    test('the reviewer approves the exact pack, then the pack is sent to the client as its own step', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4502');
      await loaded(page);
      await expect(page.getByText('Your review of pack version 2')).toBeVisible();
      // return needs a note
      await page.getByRole('button', { name: 'Return with a note' }).click();
      await expect(page.getByText('Write a note first.')).toBeVisible();
      expect(sent).toEqual([]);
      await page.getByLabel(/Note/).fill('Reads well.');
      await page.getByRole('button', { name: 'Approve', exact: true }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Your approval was recorded.' })).toBeVisible();
      expect(sent).toEqual([{ path: '/api/v1/work/4502/reviews', body: { expected_revision: 9, case_revision: 89, kind: 'bid', subject: 'document', target_id: 801, role: 'Quality reviewer', verdict: 'approve', evidence_id: null, note: 'Reads well.' } }]);
      await page.getByRole('button', { name: 'Send to the client' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'The pack was handed over to be sent.' })).toBeVisible();
      expect(sent[1]).toEqual({ path: '/api/v1/work/4502/bid-submission', body: { expected_revision: 10, case_revision: 90, version_id: 801 } });
      await expect(page.locator('main#main').getByText('Queued')).toBeVisible();
      expect(await noSideways(page)).toBe(true);
    });

    test('a person who may not decide sees the pack with the reviewer and no verdict; failed file checks hold the send', async ({ page }) => {
      await page.goto('/work/4503');
      await loaded(page);
      await expect(page.locator('main#main').getByText('With the reviewer')).toBeVisible();
      await expect(page.getByRole('button', { name: /Approve|Return|Refuse|Send for review/ })).toHaveCount(0);
      await page.goto('/work/4507');
      await loaded(page);
      await expect(page.getByText('The client asks for a PDF; this file is a Word document.')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Send to the client' })).toBeDisabled();
      await expect(page.getByText(/file checks found problems/).last()).toBeVisible();
    });

    test('controls are at least 44 by 44 on the phone', async ({ page }) => {
      test.skip(label !== 'phone 390', 'phone only');
      await page.goto('/work/4502');
      await loaded(page);
      for (const name of ['Approve', 'Return with a note', 'Refuse']) {
        const box = await page.getByRole('button', { name, exact: true }).boundingBox();
        expect(box!.height).toBeGreaterThanOrEqual(44);
        expect(box!.width).toBeGreaterThanOrEqual(44);
      }
    });
  });
}
