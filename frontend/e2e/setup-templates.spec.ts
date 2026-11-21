import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-20 Setup templates against the contract mock: list, upload panel, the 422 and 409 outcomes, empty and not-open
// states at 1440 and 390, keyboard order, targets, focus rings, reduced motion and the live announcements
// (A-TEMPLATE-VERSION frontend half, A-ACCESSIBILITY). The mock is a proposal (D-TEMPLATES-VIEW r1), not a backend.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const UPLOAD = "Upload PSL's version";
const FILE = { name: 'invoice-v2.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 template') };

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function openAs(page: Page, context: BrowserContext, cookies: Record<string, string> = {}, persona = 'admin') {
  await setCookies(context, { psl_mock_persona: persona, ...cookies });
  await page.goto('/setup/templates');
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
}

const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
const desktopRow = (page: Page, name: string) => page.locator('.setup-desktop table tbody tr', { hasText: name }).first();
const phoneCard = (page: Page, name: string) => page.locator('.setup-phone li', { hasText: name });
const apiCalls = (page: Page) => {
  const seen: { method: string; url: string }[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/v1/setup/templates')) seen.push({ method: r.method(), url: r.url() });
  });
  return seen;
};

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

test.describe('desktop', () => {
  test.use({ viewport: DESKTOP });

  test('the frame, banner, count and eight rows as drawn, one h1 at 34px, Templates current, axe clean (AC 4, 5, 15, 16, 18)', async ({ page, context }) => {
    await openAs(page, context);
    await expect(page).toHaveTitle('Templates · Setup · PSL Factory');
    const h1 = page.getByRole('heading', { level: 1 });
    await expect(h1).toHaveText(['Roles, rules and delegation']);
    expect(await h1.evaluate((el) => getComputedStyle(el).fontSize)).toBe('34px');
    const tabs = page.getByRole('tablist', { name: 'Setup' }).getByRole('tab');
    await expect(tabs).toHaveText(['Roles', 'Rules', 'Costing rule', 'Delegation', 'Payroll visibility', 'Staff accounts', 'Templates']);
    await expect(tabs.nth(6)).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('.setup-tabs .psl-badge')).toHaveCount(0);
    await expect(page.getByText(/^Every document currently uses a test template\./)).toBeVisible();
    await expect(page.getByText('8 TEMPLATES · 8 TEST')).toBeVisible();
    await expect(page.locator('.setup-desktop').getByText('AS OF 12 NOV, 10:40')).toBeVisible();
    await expect(page.locator('.setup-desktop table tbody tr strong')).toHaveText(['Invoice', 'Statement of work', 'Weekly client report', 'Minutes', 'RFP response', 'Go-live document', 'Support handover', 'Closure report']);
    await expect(page.locator('.setup-desktop').getByText('TEST TEMPLATE', { exact: true })).toHaveCount(8);
    await expect(page.locator('.setup-desktop').getByRole('button', { name: UPLOAD })).toHaveCount(8);
    await expect(desktopRow(page, 'Closure report')).toContainText('3 versions · Changed by Ada Okafor, 12 Nov');
    await expectNoAxeViolations(page);
  });

  test('upload: the panel, keyboard order, Escape, one POST, the new version, focus and the announcement (AC 7, 8, 12, 18)', async ({ page, context }) => {
    const seen = apiCalls(page);
    let body: Record<string, unknown> = {};
    let csrf: string | null = null;
    page.on('request', (r) => {
      if (r.method() === 'POST') {
        body = r.postDataJSON();
        csrf = r.headers()['x-csrftoken'] ?? null;
      }
    });
    await openAs(page, context);
    const button = desktopRow(page, 'Invoice').getByRole('button', { name: UPLOAD });
    expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await button.click();
    const panel = page.getByRole('region', { name: 'Upload a version of Invoice' });
    await panel.getByLabel('File').setInputFiles(FILE);
    await expect(panel.getByText('invoice-v2.pdf · 17 B')).toBeVisible();
    await panel.getByLabel('Note (optional)').fill('Real template from PSL legal');
    await expectNoAxeViolations(page);

    await panel.getByLabel('File').focus();
    await page.keyboard.press('Tab');
    await expect(panel.getByLabel('Note (optional)')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(panel.getByRole('button', { name: 'Upload version' })).toBeFocused();
    expect(await panel.getByRole('button', { name: 'Upload version' }).evaluate((el) => (getComputedStyle(el).outlineStyle !== 'none' ? getComputedStyle(el).outlineStyle : /rgb\(36, 89, 214\)|0px 0px 0px 2px inset/.test(getComputedStyle(el).boxShadow + getComputedStyle(el).borderTopColor + getComputedStyle(el).textDecorationColor) ? 'solid' : 'none'))).not.toBe('none');
    await page.keyboard.press('Tab');
    await expect(panel.getByRole('button', { name: 'Cancel' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(panel).toHaveCount(0);
    await expect(button).toBeFocused();

    await button.click();
    await panel.getByLabel('File').setInputFiles(FILE);
    await panel.getByLabel('Note (optional)').fill('Real template from PSL legal');
    await panel.getByRole('button', { name: 'Upload version' }).dblclick();
    await expect(page.locator('.psl-toast')).toHaveText('Version 2 uploaded for Invoice');
    expect(seen.filter((r) => r.method === 'POST')).toHaveLength(1);
    expect(seen.filter((r) => r.method === 'GET')).toHaveLength(2);
    expect(csrf).toBe('mock-csrf-admin');
    expect(Object.keys(body).sort()).toEqual(['content_base64', 'expected_revision', 'filename', 'note']);
    expect(body).toMatchObject({ expected_revision: 1, filename: 'invoice-v2.pdf', note: 'Real template from PSL legal' });
    expect(Buffer.from(body.content_base64 as string, 'base64').toString()).toBe('%PDF-1.4 template');
    await expect(panel).toHaveCount(0);
    await expect(desktopRow(page, 'Invoice')).toContainText('Version 2');
    await expect(desktopRow(page, 'Invoice')).toContainText('Changed by Ada Okafor');
    await expect(desktopRow(page, 'Invoice').getByText('TEST TEMPLATE')).toBeVisible();
    await expect(desktopRow(page, 'Invoice').locator('strong')).toBeFocused();
    await expectNoAxeViolations(page);
  });

  test('invalid: the fields are marked, the alert shows and the entries stay, axe clean (AC 10, 18)', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_templates_save: 'invalid' });
    await desktopRow(page, 'Invoice').getByRole('button', { name: UPLOAD }).click();
    const panel = page.getByRole('region', { name: 'Upload a version of Invoice' });
    await panel.getByLabel('File').setInputFiles(FILE);
    await panel.getByLabel('Note (optional)').fill('keep me');
    await panel.getByRole('button', { name: 'Upload version' }).click();
    await expect(panel.getByRole('alert')).toHaveText('Check these fields: filename, note.');
    await expect(panel.getByLabel('File')).toHaveAttribute('aria-invalid', 'true');
    await expect(panel.getByLabel('Note (optional)')).toHaveAttribute('aria-invalid', 'true');
    await expect(panel.getByLabel('Note (optional)')).toHaveValue('keep me');
    await expect(panel.getByLabel('File')).toHaveAccessibleDescription(/That file type isn’t accepted\./);
    await expectNoAxeViolations(page);
  });

  test('stale: the message shows, the list reloads, the panel closes and the file is gone, axe clean (AC 9, 18)', async ({ page, context }) => {
    const seen = apiCalls(page);
    await openAs(page, context, { psl_mock_templates_save: 'stale' });
    await desktopRow(page, 'Invoice').getByRole('button', { name: UPLOAD }).click();
    const panel = page.getByRole('region', { name: 'Upload a version of Invoice' });
    await panel.getByLabel('File').setInputFiles(FILE);
    await panel.getByRole('button', { name: 'Upload version' }).click();
    const notice = page.locator('.setup-desktop').getByText('This template changed. Reload to see the newer version.');
    await expect(notice).toBeVisible();
    await expect(panel).toHaveCount(0);
    await expect(desktopRow(page, 'Invoice')).toContainText('Version 2');
    expect(seen.filter((r) => r.method === 'POST')).toHaveLength(1);
    expect(seen.filter((r) => r.method === 'GET')).toHaveLength(2);
    await expectNoAxeViolations(page);
  });

  test('read-only rows have no control; empty and not-open states are axe clean; pm makes no template call (AC 6, 11, 14, 18)', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_templates: 'readonly' });
    await expect(page.locator('.setup-desktop table tbody tr')).toHaveCount(8);
    await expect(page.getByRole('button', { name: /Upload/ })).toHaveCount(0);
    await expectNoAxeViolations(page);
    await openAs(page, context, { psl_mock_templates: 'empty' });
    await expect(page.locator('.setup-desktop').getByText('No templates to show.')).toBeVisible();
    await expect(page.locator('table')).toHaveCount(0);
    await expectNoAxeViolations(page);
    await openAs(page, context, { psl_mock_templates: 'forbidden' });
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
    await expect(page.getByText('Invoice')).toHaveCount(0);
    await expectNoAxeViolations(page);
    const seen = apiCalls(page);
    await openAs(page, context, { psl_mock_templates: 'desktop' }, 'pm');
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
    expect(seen).toEqual([]);
  });

  test('Tab order is the tabs, the search, then each row’s Upload button', async ({ page, context }) => {
    await openAs(page, context);
    await page.getByRole('tablist', { name: 'Setup' }).getByRole('tab', { name: 'Templates' }).focus();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('searchbox', { name: 'Search' })).toBeFocused();
    // The shared Table's frame takes focus so a keyboard can scroll it sideways.
    await page.keyboard.press('Tab');
    await expect(page.locator('.setup-desktop').getByRole('region', { name: 'Document templates' })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(desktopRow(page, 'Invoice').getByRole('button', { name: UPLOAD })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(desktopRow(page, 'Statement of work').getByRole('button', { name: UPLOAD })).toBeFocused();
  });

  test('many: Show more appends the next page', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_templates: 'many' });
    await expect(page.locator('.setup-desktop table tbody tr')).toHaveCount(10);
    await page.locator('.setup-desktop').getByRole('radio', { name: '50' }).click();
    await expect(page.locator('.setup-desktop table tbody tr')).toHaveCount(50);
    await expect(page.getByText('50 SHOWN · 50 TEST')).toBeVisible();
    await expect(page.getByText(/^Every document currently uses a test template\./)).toHaveCount(0);
    await page.locator('.setup-desktop').getByRole('button', { name: 'Show more' }).click();
    await expect(page.locator('.setup-desktop table tbody tr')).toHaveCount(60);
  });
});

test.describe('desktop with reduced motion', () => {
  test.use({ viewport: DESKTOP, reducedMotion: 'reduce' });

  test('nothing animates', async ({ page, context }) => {
    await openAs(page, context);
    await desktopRow(page, 'Invoice').getByRole('button', { name: UPLOAD }).click();
    const durations = await page.locator('.setup-desktop button, .setup-desktop input, .setup-desktop textarea').evaluateAll((els) =>
      els.map((el) => getComputedStyle(el).transitionDuration),
    );
    expect(durations.every((d) => d.split(',').every((part) => part.trim() === '0s'))).toBe(true);
  });
});

test.describe('phone', () => {
  test.use({ viewport: PHONE });

  test('cards as drawn with the note, one h1 "Templates", the bar link, no side scroll, axe clean (AC 5, 15, 18)', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_templates: 'mobile' });
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(['Templates']);
    expect(await page.getByRole('heading', { level: 1 }).evaluate((el) => getComputedStyle(el).fontSize)).toBe('22px');
    await expect(page.locator('header.psl-phonebar').getByRole('link', { name: 'Back to Setup' })).toHaveText('← Setup');
    await expect(page.locator('main#main').getByRole('link')).toHaveCount(0);
    await expect(page.getByText('All 8 are test templates until PSL supplies its own.')).toBeVisible();
    await expect(page.locator('.setup-phone li')).toHaveCount(8);
    await expect(phoneCard(page, 'Invoice').getByText('TEST TEMPLATE')).toBeVisible();
    await expect(phoneCard(page, 'Invoice').getByRole('button', { name: UPLOAD })).toBeVisible();
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);
  });

  test('upload works inside the card; axe clean with the panel open and a file chosen (AC 18)', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_templates: 'mobile' });
    const card = phoneCard(page, 'Minutes');
    const button = card.getByRole('button', { name: UPLOAD });
    expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await button.click();
    const panel = card.getByRole('region', { name: 'Upload a version of Minutes' });
    await panel.getByLabel('File').setInputFiles(FILE);
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);
    await panel.getByRole('button', { name: 'Upload version' }).click();
    await expect(page.locator('.psl-toast')).toHaveText('Version 2 uploaded for Minutes');
    await expect(card).toContainText('Version 2');
    await expect(card.locator('strong')).toBeFocused();
  });

  test('invalid and stale outcomes, empty and not-open states pass axe with no side scroll', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_templates: 'mobile', psl_mock_templates_save: 'invalid' });
    const card = phoneCard(page, 'Invoice');
    await card.getByRole('button', { name: UPLOAD }).click();
    await card.getByLabel('File').setInputFiles(FILE);
    await card.getByRole('button', { name: 'Upload version' }).click();
    await expect(card.getByRole('alert')).toHaveText('Check these fields: filename, note.');
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);
    await openAs(page, context, { psl_mock_templates: 'mobile', psl_mock_templates_save: 'stale' });
    await phoneCard(page, 'Invoice').getByRole('button', { name: UPLOAD }).click();
    await phoneCard(page, 'Invoice').getByLabel('File').setInputFiles(FILE);
    await phoneCard(page, 'Invoice').getByRole('button', { name: 'Upload version' }).click();
    await expect(page.locator('.setup-phone').getByText('This template changed. Reload to see the newer version.')).toBeVisible();
    await expectNoAxeViolations(page);
    for (const scenario of ['empty', 'forbidden']) {
      await openAs(page, context, { psl_mock_templates: scenario, psl_mock_templates_save: '' });
      expect(await noSideScroll(page)).toBe(true);
      await expectNoAxeViolations(page);
    }
  });
});
