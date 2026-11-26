import { expect, test, type Locator, type Page } from '@playwright/test';

// F-112: the change request (SCR-31, part 1) on the live work item, on the live shapes (mock/change-live.mjs), at 1440 and 390.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const track = (page: Page) => {
  const log: { method: string; path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/')) log.push({ method: r.method(), path: new URL(r.url()).pathname, body: r.method() === 'POST' ? JSON.parse(r.postData() ?? '{}') : {} });
  });
  return { all: log, writes: () => log.filter((l) => l.method === 'POST' && /\/(change|ordinary-changes)$/.test(l.path)) };
};
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const choose = async (main: Locator, label: RegExp | string, option: RegExp) => {
  await main.getByRole('combobox', { name: label }).click();
  await main.page().getByRole('option', { name: option }).click();
};

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4901: the track, four impact rows, one Record an assessment, and one request to record it', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4901');
      await expect(main.getByText('Being assessed · 3 of 4')).toBeVisible();
      await expect(main.getByText('1 · Authorization')).toBeVisible();
      await expect(main.getByText('5 · Signatures')).toBeVisible();
      await expect(main.getByRole('table', { name: /Impact assessments/ }).getByRole('row')).toHaveCount(5);
      await expect(main.getByText('Not given yet')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Record an assessment' })).toHaveCount(1);
      await expect(main.getByRole('button', { name: /Approve|Return|Reject|authorisation/i })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);

      await main.getByRole('button', { name: 'Record an assessment' }).click();
      await expect(main.getByRole('button', { name: 'Record assessment' })).toBeDisabled();
      await main.getByLabel('Assessment', { exact: true }).fill('Uses the existing SMS provider.');
      await choose(main, 'Changes the cost', /^No$/);
      await choose(main, 'Changes the timeline', /^No$/);
      await choose(main, 'The client will see it', /^Yes$/);
      await choose(main, 'Affects production', /^Not known$/);
      await choose(main, 'Proof', /security assessment/);
      expect(await noSideScroll(page)).toBe(true);
      await main.getByRole('button', { name: 'Record assessment' }).dblclick();
      await expect(main.getByText('Being assessed · 4 of 4')).toHaveCount(0);
      await expect(main.getByRole('button', { name: 'Record an assessment' })).toHaveCount(0);
      const writes = t.writes();
      expect(writes).toHaveLength(1);
      expect(writes[0].body).toEqual({
        action: 'assess', expected_revision: 6, case_revision: 41, change_version_id: 1, contributor: 'Security', cost_impact: false, timeline_impact: false, client_facing: true, production_impact: null,
        scope_items: null, outputs: null, effort_person_days: null, evidence: 7901, note: 'Uses the existing SMS provider.', proof_upload: null,
      });
      await expect(main.getByText('Not recorded').first()).toBeVisible();
    });

    test('4902: decide as the Client with a note and proof; return asks first and Cancel sends nothing', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4902');
      await expect(main.getByRole('table', { name: /Deciders/ }).getByRole('row')).toHaveCount(6);
      await expect(main.getByRole('group', { name: 'Security Manager decision' })).toHaveCount(0);
      const client = main.getByRole('group', { name: 'Client decision' });
      await expect(client.getByRole('button', { name: 'Approve for Client' })).toBeDisabled();
      await client.getByLabel('Client note').fill('Not this phase.');
      await choose(client, 'Client proof', /meeting minutes/);
      await client.getByRole('button', { name: 'Return for Client' }).click();
      const dialog = page.getByRole('alertdialog', { name: 'Return for Client' });
      await expect(dialog.getByText('Not this phase.')).toBeVisible();
      await dialog.getByRole('button', { name: 'Cancel' }).click();
      expect(t.writes()).toHaveLength(0);
      await client.getByRole('button', { name: 'Approve for Client' }).click();
      await expect(main.getByRole('group', { name: 'Client decision' })).toHaveCount(0);
      expect(t.writes().map((w) => w.body)).toEqual([{ action: 'decide', expected_revision: 6, case_revision: 41, change_version_id: 2, role: 'Client', verdict: 'approve', evidence: 7902, note: 'Not this phase.' }]);
      await expect(main.getByRole('group', { name: 'Engineering Lead decision' })).toBeVisible();
      expect(await noSideScroll(page)).toBe(true);
    });

    test('4902: a rejection asks first, then the page shows Rejected and no authorise control', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4902');
      const client = main.getByRole('group', { name: 'Client decision' });
      await client.getByLabel('Client note').fill('Not this phase; revisit after go-live.');
      await choose(client, 'Client proof', /meeting minutes/);
      await client.getByRole('button', { name: 'Reject for Client' }).click();
      await page.getByRole('alertdialog').getByRole('button', { name: 'Reject' }).click();
      await expect(main.getByText('You can log a new change later.')).toBeVisible();
      await expect(main.getByText('Rejected').first()).toBeVisible();
      await expect(main.getByRole('button', { name: /authorisation|Approve|Return|Reject/ })).toHaveCount(0);
    });

    test('4904: record the authorisation with a confirm step; no Authorised by field is drawn', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4904');
      await expect(main.getByText('Approved · to authorise')).toBeVisible();
      await expect(main.getByLabel(/Authorised by|Authorised on/)).toHaveCount(0);
      await choose(main, /Linked commercial item/, /#11/);
      await main.getByRole('button', { name: 'Record authorisation' }).click();
      const dialog = page.getByRole('alertdialog');
      await expect(dialog.getByText('This commits the change. It cannot be undone here.')).toBeVisible();
      await dialog.getByRole('button', { name: 'Record authorisation' }).click();
      await expect(main.getByText('Recorded (#7104)')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Record authorisation' })).toHaveCount(0);
      expect(t.writes().map((w) => w.body)).toEqual([{ action: 'authorize', expected_revision: 6, case_revision: 41, change_version_id: 4, commercial: 11 }]);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('4905, 4906, 4903, 4999: read only, authorised, rejected and not found', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4905');
      await expect(main.getByRole('heading', { name: 'Deciders' })).toBeVisible();
      await expect(main.getByRole('button', { name: /Record|Approve|Return|Reject/ })).toHaveCount(0);
      await expect(main.getByText(/can’t|not allowed/)).toHaveCount(0);
      await page.goto('/work/4906');
      await expect(main.getByText('Recorded (#7001)')).toBeVisible();
      await expect(main.getByRole('button', { name: /authorisation/i })).toHaveCount(0);
      await page.goto('/work/4903');
      await expect(main.getByText('You can log a new change later.')).toBeVisible();
      await page.goto('/work/4999');
      await expect(main.getByText('This record is unavailable.').first()).toBeVisible();
    });

    test('4909: a stale decision keeps the note and shows no decide button', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4909');
      const product = main.getByRole('group', { name: 'Product decision' });
      await product.getByLabel('Product note').fill('Approved after the call.');
      await choose(product, 'Product proof', /meeting minutes/);
      await product.getByRole('button', { name: 'Approve for Product' }).click();
      await expect(main.getByText(/This changed while you were working/)).toBeVisible();
      await expect(main.getByRole('button', { name: /Approve for Product/ })).toHaveCount(0);
      await expect(main.getByText('Approved after the call.')).toBeVisible();
      expect(t.writes()).toHaveLength(1);
    });

    test('4908: no proof recorded holds the writes with the words', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4908');
      await main.getByRole('button', { name: 'Record an assessment' }).click();
      await expect(main.getByText('No proof file is recorded for this case yet').first()).toBeVisible();
      await expect(main.getByRole('button', { name: 'Record assessment' })).toBeDisabled();
    });

    test('log a change: the Changes register opens the form and one capture is sent', async ({ page }) => {
      const t = track(page);
      await page.goto('/projects/P-0101/registers?register=changes');
      await page.getByRole('button', { name: 'Log a change' }).click();
      const dialog = page.getByRole('dialog', { name: 'Log a change' });
      await dialog.getByRole('button', { name: 'Log the change' }).click();
      await expect(dialog.getByText(/to continue\./).first()).toBeVisible();
      expect(t.writes()).toHaveLength(0);
      await dialog.getByLabel('Reference').fill('CR-0099');
      await choose(dialog, 'Category', /^Normal$/);
      await dialog.getByLabel('Module').fill('Billing');
      await dialog.getByLabel('Description').fill('Change the invoice footer');
      await dialog.getByLabel('Reason').fill('The client asked');
      await choose(dialog, 'Proof', /security assessment/);
      await dialog.getByRole('button', { name: 'Log the change' }).click();
      await expect(dialog.getByText(/Logged: CR-0099/)).toBeVisible();
      expect(t.writes().map((w) => w.body)).toEqual([{ action: 'capture', case_revision: 12, reference: 'CR-0099', category: 'Normal', module: 'Billing', description: 'Change the invoice footer', reason: 'The client asked', evidence_id: 7901 }]);
      expect(await noSideScroll(page)).toBe(true);
    });
  });
}
