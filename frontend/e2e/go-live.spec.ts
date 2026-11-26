import { expect, test, type Locator, type Page } from '@playwright/test';

// F-114: go-live acceptance (SCR-45) on the live work item, on the live shapes (mock/go-live.mjs), at 1440 and 390.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const track = (page: Page) => {
  const log: { method: string; path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/')) log.push({ method: r.method(), path: new URL(r.url()).pathname, body: r.method() === 'POST' && !r.url().endsWith('/files') ? JSON.parse(r.postData() ?? '{}') : {} });
  });
  return { all: log, writes: () => log.filter((l) => l.method === 'POST' && /\/go-live-/.test(l.path)) };
};
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const choose = async (main: Locator, label: RegExp | string, option: RegExp) => {
  await main.getByRole('combobox', { name: label }).click();
  await main.page().getByRole('option', { name: option }).click();
};
const fill = async (main: Locator, role: 'PM' | 'Client') => {
  const values: Record<string, string> = { 'source system': 'DocuSign', 'source reference': 'ENV-1', 'decision id': 'D-9', 'decision version': '2', 'signer reference': 'S-1' };
  for (const [name, value] of Object.entries(values)) await main.getByLabel(`${role} ${name}`).fill(value);
  await main.getByLabel(`${role} signed at`).fill('2026-11-25T11:00');
};

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4411: the sent block, both signer blocks, a client copy kept, and one request to record', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4411');
      await expect(main.getByText(/Delivery recorded 25 Nov/)).toBeVisible();
      await expect(main.getByRole('heading', { name: 'PM signature' })).toBeVisible();
      await expect(main.getByRole('heading', { name: 'Client signature' })).toBeVisible();
      await expect(main.getByRole('button', { name: 'Record signatures' })).toBeDisabled();
      await expect(main.getByText(/Needs reconciliation/).first()).toBeVisible();
      expect(t.writes()).toHaveLength(0);
      expect(await noSideScroll(page)).toBe(true);

      // a signed copy for the Client: upload, tick, add
      const zone = main.getByRole('group', { name: 'Client signed copy' });
      await zone.locator('input[type="file"]').last().setInputFiles({ name: 'client-signed.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 signed') });
      const adds = main.getByRole('button', { name: 'Add signed copy' });
      await expect(zone.getByText(/Uploaded/)).toBeVisible();
      await expect(adds.nth(1)).toBeDisabled();
      await main.getByLabel('I checked this is the signed copy of this go-live document for this signer').nth(1).check();
      await adds.nth(1).click();
      await expect(main.getByRole('combobox', { name: /Client signature record/ })).toContainText('#70');
      expect(t.writes().map((w) => [w.path, w.body.role, w.body.checked])).toEqual([['/api/v1/work/4411/go-live-signoff/proofs', 'Client', true]]);

      await fill(main, 'PM');
      await fill(main, 'Client');
      await choose(main, /PM signature record/, /#61/);
      await main.getByLabel('Note', { exact: true }).fill('Both signed copies checked');
      await expect(main.getByRole('button', { name: 'Record signatures' })).toBeEnabled();
      // the same record for both is refused
      await choose(main, /Client signature record/, /#61/);
      await expect(main.getByText('Choose a different signature record for each signer').first()).toBeVisible();
      await expect(main.getByRole('button', { name: 'Record signatures' })).toBeDisabled();
      await choose(main, /Client signature record/, /#70/);
      await main.getByRole('button', { name: 'Record signatures' }).dblclick();
      await expect(main.getByText(/Go-live accepted/)).toBeVisible();
      const signoff = t.writes().filter((w) => w.path.endsWith('/go-live-signoff'));
      expect(signoff).toHaveLength(1);
      expect(signoff[0].body).toMatchObject({ expected_revision: 6, case_revision: 42, version_id: 11, receipt_id: 51, pm_signature_id: 61, client_signature_id: 70, mode: 'fresh_signatures', prior_acceptance_id: null });
      await expect(main.getByRole('button', { name: 'Record signatures' })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('4417: a conflict says so, keeps nothing as recorded, and the next press uses the new revisions', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4417');
      await expect(main.getByText(/Delivery recorded/)).toBeVisible();
      await fill(main, 'PM');
      await fill(main, 'Client');
      await choose(main, /PM signature record/, /#61/);
      await choose(main, /Client signature record/, /#62/);
      await main.getByLabel('Note', { exact: true }).fill('ok');
      await main.getByRole('button', { name: 'Record signatures' }).click();
      await expect(main.getByText(/This changed while you were working/)).toBeVisible();
      await expect(main.getByText(/Go-live accepted/)).toHaveCount(0);
      await expect(main.getByRole('button', { name: 'Record signatures' })).toBeEnabled();
      await main.getByRole('button', { name: 'Record signatures' }).click();
      await expect(main.getByText(/Go-live accepted/)).toBeVisible();
      const bodies = t.writes().map((w) => [w.body.expected_revision, w.body.case_revision]);
      expect(bodies).toEqual([[6, 41], [7, 42]]);
    });

    test('4415, 4420 and 4412: not the appointed PM, nothing delivered, and accepted', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4415');
      await expect(main.getByText('Only the appointed PM records the signatures.')).toBeVisible();
      await expect(main.getByRole('button', { name: /Record signatures/ })).toHaveCount(0);
      await expect(main.getByText('What this unlocks')).toBeVisible();
      await page.goto('/work/4420');
      await expect(main.getByText('The go-live document hasn’t been sent to the client yet.')).toBeVisible();
      await expect(main.getByRole('button', { name: /Record signatures|Add signed copy/ })).toHaveCount(0);
      await page.goto('/work/4412');
      await expect(main.getByText(/Go-live accepted/)).toBeVisible();
      await expect(main.getByText('Accepted (#7001)')).toBeVisible();
      await expect(main.getByText('Go-live · Not recorded yet')).toBeVisible();
      await expect(main.getByText(/Mark milestone|Hypercare|Archive and handover/)).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('4416: an earlier acceptance is named and binding is offered, not the accepted banner', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4416');
      await expect(main.getByText('An earlier acceptance is on file (#6990)')).toBeVisible();
      await expect(main.getByText(/Go-live accepted/)).toHaveCount(0);
      await main.getByRole('combobox', { name: 'How to record' }).click();
      await expect(page.getByRole('option', { name: /Use the earlier acceptance \(#6990\)/ })).toBeVisible();
    });

    test('4413 and 4414: changes asked for and declined', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4413');
      await expect(main.getByText(/“Add the bureau outage contact to the incident plan\.”/).first()).toBeVisible();
      await expect(main.getByText('Only the person who sent the document records the reply.')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Record signatures' })).toHaveCount(0);
      await main.getByLabel('Why a new version is needed').fill('Add the outage contact');
      await main.getByRole('button', { name: 'Prepare v2' }).click();
      await expect(main.getByText('A new go-live report is being prepared.')).toBeVisible();
      expect(t.writes().map((w) => w.path)).toEqual(['/api/v1/work/4413/go-live-replies/successor']);
      await page.goto('/work/4414');
      await expect(main.getByText(/“We are not ready to go live this quarter\.”/).first()).toBeVisible();
      await expect(main.getByText('Response rules')).toBeVisible();
      await choose(main, 'Issue', /ISS-0301/);
      await main.getByLabel('Note on the issue').fill('Tracked');
      await main.getByRole('button', { name: 'Link the issue' }).click();
      await expect(main.getByText(/1 · #301/)).toBeVisible();
      expect(await noSideScroll(page)).toBe(true);
    });

    test('4418 and 4419: a hidden reply and a withdrawn one', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4418');
      await expect(main.getByText(/Details not available to you/).first()).toBeVisible();
      await expect(main.getByText(/\bnull\b/)).toHaveCount(0);
      await page.goto('/work/4419');
      await expect(main.getByText(/Reply 2 · Withdrawn/)).toBeVisible();
      await expect(main.getByText(/Reply 1 · Changes requested/)).toBeVisible();
    });
  });
}
