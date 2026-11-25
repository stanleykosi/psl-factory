import { expect, test, type Page } from '@playwright/test';

// F-136: the client's response and SOW signature on the live work item (SCR-16), on the live shapes (mock/commercial-live.mjs).
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.getByText('What is to be signed')).toBeVisible();
};
const writes = (page: Page) => {
  const sent: { path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/api/')) sent.push({ path: new URL(r.url()).pathname, body: JSON.parse(r.postData() ?? '{}') });
  });
  return sent;
};
const noSideways = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const choose = async (page: Page, label: string | RegExp, option: string | RegExp) => {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
};

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('shows what is to be signed, the proof files and who may record, with nothing the API does not serve', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4660');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByText('Version record 2')).toBeVisible();
      await expect(main.getByText(/Available to attach: client-email-reply\.pdf/)).toBeVisible();
      await expect(main.getByText('You may record it')).toBeVisible();
      await expect(main.getByText('No response from the client has been recorded yet.')).toBeVisible();
      await expect(main.getByText(/Agent note|Company forms|What happens next/)).toHaveCount(0);
      expect(sent).toEqual([]);
      expect(await noSideways(page)).toBe(true);
    });

    test('records the client’s signed response and says so only after the page is re-read', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4660');
      await loaded(page);
      await page.getByRole('button', { name: 'Record the client’s response' }).click();
      await expect(page.getByText('Choose what the client was sent.')).toBeVisible();
      expect(sent).toEqual([]);
      await choose(page, 'What the client answered', /Statement of work/);
      await page.getByLabel('Name of the person who answered').fill('Dayo Adesina');
      await choose(page, 'Answer', /^Signed/);
      await page.getByLabel('When the client answered').fill('2026-11-24T15:20');
      await page.getByRole('checkbox', { name: 'client-email-reply.pdf' }).check();
      await page.getByLabel('Note').fill('Replied by email with the signed page.');
      await page.getByRole('checkbox', { name: /This is the client’s own response/ }).check();
      await page.getByRole('button', { name: 'Record the client’s response' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'The client’s response is recorded.' })).toContainText('This item is now:');
      expect(sent).toHaveLength(1);
      expect(sent[0].path).toBe('/api/v1/projects/00000000-0000-4000-8000-000000004660/commercial-response');
      expect(sent[0].body).toMatchObject({ action: 'witness', case_revision: 89, revision_id: 2, receipt_id: 5, outcome: 'signed', genuine: true, proof_ids: [31] });
      await expect(page.locator('main#main').getByText('Dayo Adesina')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Record the signatures' })).toBeVisible();
      expect(await noSideways(page)).toBe(true);
    });

    test('adopts a signed baseline that has its signatures, and nothing is offered once it is adopted', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4662');
      await loaded(page);
      await page.getByRole('button', { name: 'Adopt the signed baseline' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'The signed baseline is adopted.' })).toBeVisible();
      expect(sent).toEqual([{ path: '/api/v1/projects/00000000-0000-4000-8000-000000004662/commercial-response', body: { action: 'adopt', case_revision: 89, response_id: 9 } }]);
      await expect(page.locator('main#main').getByText('Adopted', { exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: /Record|Adopt/ })).toHaveCount(0);
    });

    test('holds the form with its reason when nothing has been sent, and shows no form to a person who may not record', async ({ page }) => {
      await page.goto('/work/4664');
      await loaded(page);
      await expect(page.getByText('Nothing has been sent to the client yet.')).toBeVisible();
      await page.goto('/work/4665');
      await loaded(page);
      await expect(page.getByText('Not open to you')).toBeVisible();
      await expect(page.getByRole('button', { name: /Record/ })).toHaveCount(0);
    });

    test('controls are at least 44 by 44 on the phone', async ({ page }) => {
      test.skip(label !== 'phone 390', 'phone only');
      await page.goto('/work/4660');
      await loaded(page);
      const box = await page.getByRole('button', { name: 'Record the client’s response' }).boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(44);
      expect(box!.width).toBeGreaterThanOrEqual(44);
    });
  });
}
