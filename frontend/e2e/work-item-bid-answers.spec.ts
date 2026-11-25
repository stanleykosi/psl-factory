import { expect, test, type Page } from '@playwright/test';

// F-96: the RFP response panel on the live work item (SCR-26): rows, review decisions, ask Tola, undo, on the live shapes (mock/bid-answers-live.mjs).
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.getByRole('list', { name: 'Requirements' })).toBeVisible();
};
const writes = (page: Page) => {
  const sent: { path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/api/')) sent.push({ path: new URL(r.url()).pathname, body: JSON.parse(r.postData() ?? '{}') });
  });
  return sent;
};
const row = (page: Page, key: string) => page.getByRole('heading', { level: 3, name: key }).locator('xpath=ancestor::li');

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('shows each row with its disposition and status, and no filters or checklist', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4401');
      await loaded(page);
      const main = page.locator('main#main');
      for (const [key, status] of [['R2', 'Suggestion ready'], ['R4', 'Queued'], ['R5', 'Tola is working'], ['R6', 'On hold'], ['R7', 'Out of date']] as const) await expect(row(page, key).getByText(status, { exact: true })).toBeVisible();
      await expect(row(page, 'R8').getByText('Needs clarification')).toBeVisible();
      await expect(main.getByText(/Before review|filter/i)).toHaveCount(0);
      await expect(main.getByRole('button', { name: 'Send for review' })).toBeDisabled();
      await expect(main.getByText(/needs the bid pack/)).toBeVisible();
      expect(sent).toEqual([]);
      // no page-wide sideways scroll
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test('Accept saves the suggestion, then Undo puts the earlier answer back', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4401');
      await loaded(page);
      await row(page, 'R2').getByRole('button', { name: 'Accept' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Your answer for R2 was saved.' })).toContainText('This item is now:');
      expect(sent).toEqual([{ path: '/api/v1/work/4401/bid-answers', body: { action: 'review', expected_revision: 6, case_revision: 12, decisions: [{ suggestion: 501, predecessor: 0, verdict: 'accept', answer: 'Data is encrypted at rest and in transit.', disposition: 'addressed', note: '' }] } }]);
      await expect(row(page, 'R2').getByText('Reviewed')).toBeVisible();
      await row(page, 'R2').getByRole('button', { name: 'Undo' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'The earlier answer for R2 is back.' })).toBeVisible();
      await expect(row(page, 'R2').getByText('Suggestion ready')).toBeVisible();
    });

    test('Write your own needs words, then saves them as a replacement', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4401');
      await loaded(page);
      await row(page, 'R2').getByRole('button', { name: 'Write your own' }).click();
      await expect(row(page, 'R2').getByRole('button', { name: 'Save answer' })).toBeDisabled();
      await row(page, 'R2').getByLabel('Answer').fill('Our own words.');
      await row(page, 'R2').getByRole('button', { name: 'Save answer' }).click();
      await expect(row(page, 'R2').getByText('Reviewed')).toBeVisible();
      expect(sent[0].body.decisions).toEqual([{ suggestion: 501, predecessor: 0, verdict: 'replace', answer: 'Our own words.', disposition: 'addressed', note: '' }]);
    });

    test('Ask Tola queues the requirement', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4401');
      await loaded(page);
      await row(page, 'R1').getByRole('button', { name: 'Ask Tola' }).click();
      await expect(row(page, 'R1').getByText('Queued')).toBeVisible();
      expect(sent[0].body).toMatchObject({ action: 'suggest', key: 'R1' });
    });

    test('a read-only response has no controls', async ({ page }) => {
      await page.goto('/work/4402');
      await loaded(page);
      await expect(page.getByText(/Engineering Lead: returned/)).toBeVisible();
      await expect(page.locator('main#main').getByRole('button', { name: /Accept|Ask Tola|Undo|Send for review/ })).toHaveCount(0);
    });

    if (label.startsWith('phone')) {
      test('the row buttons are at least 44 by 44', async ({ page }) => {
        await page.goto('/work/4401');
        await loaded(page);
        for (const [key, name] of [['R2', 'Accept'], ['R2', 'Edit'], ['R2', 'Write your own'], ['R3', 'Undo'], ['R1', 'Ask Tola']] as const) {
          const box = await row(page, key).getByRole('button', { name }).boundingBox();
          expect(box!.height, `${key} ${name}`).toBeGreaterThanOrEqual(44);
          expect(box!.width, `${key} ${name}`).toBeGreaterThanOrEqual(44);
        }
      });
    }
  });
}
