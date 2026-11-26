import { expect, test, type Page } from '@playwright/test';

// F-113B: the release gates page (SCR-44) on the live work item, on the live shapes (mock/delivery-release.mjs), at 1440 and 390.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const track = (page: Page) => {
  const log: { method: string; path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/')) log.push({ method: r.method(), path: new URL(r.url()).pathname, body: r.method() === 'POST' && !r.url().endsWith('/files') ? JSON.parse(r.postData() ?? '{}') : {} });
  });
  return { all: log, writes: () => log.filter((l) => l.method === 'POST' && /\/(planning-exit|release-register)$/.test(l.path)) };
};
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4801: the gates, the decision form, and a direct approval with one request', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4801');
      await expect(main.getByRole('heading', { name: 'Initiation' })).toBeVisible();
      for (const phase of ['Planning', 'Execution', 'Closure']) await expect(main.getByRole('heading', { name: phase, exact: true })).toBeVisible();
      await expect(main.getByText('STALE SCOPE').first()).toBeVisible();
      await expect(main.getByText('AUTHORITY CHANGED').first()).toBeVisible();
      await expect(main.getByText('UNKNOWN OR STALE').first()).toBeVisible();
      await expect(main.getByText('Proof is out of date')).toBeVisible();
      await expect(main.getByRole('combobox', { name: /Evidence \(optional\)/ })).toContainText('Choose evidence');
      await expect(main.getByRole('button', { name: 'Return with a note' })).toBeDisabled();
      await expect(main.getByRole('button', { name: /Reject/ })).toHaveCount(0);
      expect(t.writes()).toHaveLength(0);
      expect(t.all.some((l) => l.path.includes('decision-appointments'))).toBe(false);
      expect(await noSideScroll(page)).toBe(true);
      await main.getByRole('button', { name: 'Approve for release' }).dblclick();
      await expect(main.getByText(/Approved by PMO Lead, Kemi Adebayo/)).toBeVisible();
      expect(t.writes()).toHaveLength(1);
      expect(t.writes()[0].body).toMatchObject({ verdict: 'approve', packet: 'a'.repeat(64), expected_revision: 6, case_revision: 41 });
      expect(t.writes()[0].body).not.toHaveProperty('evidence_id');
      await expect(main.getByRole('button', { name: 'Approve for release' })).toHaveCount(0);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('4802 sends nothing; 4804 has no controls; 4803 says it is waiting for the packet', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4802');
      await expect(main.getByText('No evidence is on file for this decision yet.').first()).toBeVisible();
      await expect(main.getByRole('button', { name: 'Approve for release' })).toBeDisabled();
      await main.getByRole('button', { name: 'Approve for release' }).click({ force: true });
      await page.goto('/work/4804');
      await expect(main.getByText('Waiting for the PMO Lead')).toBeVisible();
      await expect(main.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
      await page.goto('/work/4803');
      await expect(main.getByText('Waiting for the packet')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Approve for release' })).toBeDisabled();
      expect(t.writes()).toHaveLength(0);
    });

    test('4805 and 4806: returned, with blockers as text and the workaround only on 4806', async ({ page }) => {
      const main = page.locator('main#main');
      await page.goto('/work/4805');
      await expect(main.getByText(/Kemi Adebayo returned the release on 25 Nov/)).toBeVisible();
      await expect(main.getByText('ISS-0301')).toBeVisible();
      await expect(main.getByText('Client workaround on file')).toHaveCount(0);
      await expect(main.getByText(/Send for decision again|Tola/)).toHaveCount(0);
      await page.goto('/work/4806');
      await expect(main.getByText('Client workaround on file')).toBeVisible();
    });

    test('4807: owner needed, with the people and a link to Setup roles', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4807');
      await expect(main.getByText('OWNER NEEDED')).toBeVisible();
      await expect(main.getByRole('link', { name: 'Open Setup roles' })).toHaveAttribute('href', '/setup/roles');
      await expect(main.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
      expect(t.all.some((l) => l.path.includes('decision-appointments'))).toBe(true);
    });

    test('4808: prepare release readiness sends one request and the page says the release is ready; 4809 has no button', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4809');
      await expect(main.getByText('Preparing release readiness')).toBeVisible();
      await expect(main.getByRole('button', { name: 'Prepare release readiness' })).toHaveCount(0);
      await page.goto('/work/4808');
      await main.getByRole('button', { name: 'Prepare release readiness' }).click();
      await expect(main.getByText(/Release ready · 1 readiness record/)).toBeVisible();
      expect(t.writes().map((w) => w.body)).toEqual([{ action: 'prepare_readiness', expected_revision: 6, case_revision: 41 }]);
      expect(await noSideScroll(page)).toBe(true);
    });

    test('4810: record the release with a checked PDF; 4811 shows it recorded', async ({ page }) => {
      const t = track(page);
      const main = page.locator('main#main');
      await page.goto('/work/4810');
      await expect(main.getByText(/Release ready/).first()).toBeVisible();
      const submit = main.getByRole('button', { name: 'Record the release' });
      await expect(submit).toBeDisabled();
      await main.getByLabel('Release date and time').fill('2026-11-26T10:30');
      await main.getByLabel('Reference').fill('REL-2026-045');
      await main.getByLabel(/^Note/).fill('Released to production');
      await main.locator('input[type="file"]').setInputFiles({ name: 'release.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 release') });
      await expect(submit).toBeDisabled();
      await main.getByLabel('I have checked this file is the release record').check();
      await expect(submit).toBeEnabled();
      expect(await noSideScroll(page)).toBe(true);
      await submit.click();
      await expect(main.getByText(/Release recorded .* · REL-2026-045/)).toBeVisible();
      expect(t.writes()).toHaveLength(1);
      expect(t.writes()[0].body).toMatchObject({ action: 'observe_release', checked: true, reference: 'REL-2026-045', readiness_id: 71, environment: null, private_log_id: null });
      expect(t.writes()[0].body).not.toHaveProperty('evidence_id');
      await page.goto('/work/4811');
      await expect(main.getByText(/Release recorded .* · REL-2026-044/)).toBeVisible();
      await expect(main.getByRole('button', { name: 'Record the release' })).toHaveCount(0);
    });

    test('a refused write shows the server words and sends nothing else; a lost answer locks the button', async ({ page, context }) => {
      const t = track(page);
      const main = page.locator('main#main');
      const base = test.info().project.use.baseURL!;
      await context.addCookies([{ name: 'psl_mock_scenario', value: 'w403', url: base }]);
      await page.goto('/work/4801');
      await main.getByRole('button', { name: 'Approve for release' }).click();
      await expect(main.getByText(/You can’t do this\. Only the PMO Lead can decide this\./)).toBeVisible();
      expect(t.writes()).toHaveLength(1);
      await context.addCookies([{ name: 'psl_mock_scenario', value: 'wdrop0', url: base }]);
      await page.goto('/work/4814');
      await main.getByRole('combobox', { name: /Evidence for this decision/ }).click();
      await page.getByRole('option', { name: /signed pdf/ }).click();
      await main.getByRole('button', { name: 'Approve for release' }).click();
      await expect(main.getByText(/We couldn’t confirm that this happened\. Check the page before trying again\./)).toBeVisible();
      await expect(main.getByRole('button', { name: 'Approve for release' })).toBeDisabled();
      expect(t.writes()).toHaveLength(2);
    });

    test('a record the account cannot see reads "This record is unavailable."', async ({ page }) => {
      await page.goto('/work/4890');
      await expect(page.getByText('This record is unavailable.').first()).toBeVisible();
    });
  });
}
