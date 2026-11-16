import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type BrowserContext, type Locator, type Page } from '@playwright/test';

// F-27 Setup delegation against the contract mock: the list, the add panel and the phone sheet, the 200, 422 and
// uncertain outcomes (with the mock's own state read back), view-only, empty and not-open at 1440 and 390, targets,
// focus, reduced motion and the live announcement (A-DELEGATIONS frontend half, A-ACCESSIBILITY). The mock is a
// proposal (D-DELEGATION-VIEW), not a backend.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const NOTE = "Delegating can't give anyone authority they don't already have. Decisions made by the delegate are recorded under their own name.";
const CHANGED = 'The list changed while we were checking. Look for your delegation before adding it again.';

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
  await page.goto('/setup/delegation');
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
}

/** The mock's own list for this persona and scenario, read straight from the mock. */
async function mockList(request: APIRequestContext, scenario = 'default') {
  const res = await request.get(`${MOCK}/api/v1/setup/delegations`, { headers: { Cookie: `psl_mock_persona=admin; psl_mock_delegations=${scenario}` } });
  return (await res.json()) as { items: unknown[]; revision: number };
}

const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
const desktopRows = (page: Page) => page.locator('.setup-desktop table tbody tr');
const apiCalls = (page: Page) => {
  const seen: { method: string; url: string }[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/v1/setup/delegation')) seen.push({ method: r.method(), url: r.url() });
  });
  return seen;
};

async function fill(form: Locator, page: Page) {
  await form.getByRole('combobox', { name: 'From' }).click();
  await page.getByRole('option', { name: 'Kemi Adebayo · PMO Lead' }).click();
  await form.getByRole('combobox', { name: 'To' }).click();
  await page.getByRole('option', { name: 'Femi Ade · PMO Lead' }).click();
  await form.getByLabel('Starts').fill('01 Dec 2026');
  await form.getByLabel('Starts').press('Tab');
  await form.getByLabel('Ends').fill('03 Dec 2026');
  await form.getByLabel('Ends').press('Tab');
  await form.getByLabel('Reason').fill('Training');
}

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

test.describe('desktop', () => {
  test.use({ viewport: DESKTOP });
  const panelOf = (page: Page) => page.getByRole('complementary', { name: 'Add a delegation' });

  test('the frame, the two rows and the add panel as drawn, Delegation current, axe clean (AC 3, 19)', async ({ page, context }) => {
    await openAs(page, context);
    await expect(page).toHaveTitle('Delegation · Setup · PSL Factory');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(['Roles, rules and delegation']);
    const tabs = page.getByRole('tablist', { name: 'Setup' }).getByRole('tab');
    await expect(tabs.nth(3)).toHaveText('Delegation');
    await expect(tabs.nth(3)).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('.setup-desktop thead th')).toHaveText(['FROM', 'TO', 'DATES', 'REASON', 'STATE']);
    await expect(desktopRows(page).nth(0).locator('td')).toHaveText(['Kemi Adebayo · PMO Lead', 'Femi Ade · PMO Lead', '18–25 Nov 2026', 'Annual leave', 'Upcoming']);
    await expect(desktopRows(page).nth(1).locator('td')).toHaveText(['Ada Okafor · Finance Lead', 'Chika Obi · Finance Lead', '02–04 Nov 2026', 'Conference', 'Ended']);
    const panel = panelOf(page);
    await expect(panel.getByText('Only people who already hold the same role are listed')).toBeVisible();
    await expect(panel.getByText(NOTE)).toBeVisible();
    await expect(panel.getByRole('group', { name: 'Dates' })).toBeVisible();
    await expectNoAxeViolations(page);
  });

  test('add: one PUT with the CSRF header and the body, the re-read row, the announcement and focus (AC 9, 11, 19)', async ({ page, context, request }) => {
    const seen = apiCalls(page);
    let body: Record<string, unknown> = {};
    let csrf: string | null = null;
    page.on('request', (r) => {
      if (r.method() === 'PUT') {
        body = r.postDataJSON();
        csrf = r.headers()['x-csrftoken'] ?? null;
      }
    });
    await openAs(page, context);
    const panel = panelOf(page);
    await expect(panel.getByRole('combobox', { name: 'To' })).toBeDisabled();
    await fill(panel, page);
    await expectNoAxeViolations(page);
    const add = panel.getByRole('button', { name: 'Add delegation' });
    await add.focus();
    expect(await add.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none');
    await add.dblclick();
    await expect(page.locator('[aria-live="polite"]')).toHaveText('Delegation added: Kemi Adebayo to Femi Ade, 01–03 Dec 2026.');
    await expect(desktopRows(page)).toHaveCount(3);
    await expect(desktopRows(page).nth(2).locator('td')).toHaveText(['Kemi Adebayo · PMO Lead', 'Femi Ade · PMO Lead', '01–03 Dec 2026', 'Training', 'Upcoming']);
    await expect(desktopRows(page).nth(2).locator('[data-row-for]')).toBeFocused();
    expect(seen.filter((r) => r.method === 'PUT')).toHaveLength(1);
    expect(seen.filter((r) => r.method === 'GET')).toHaveLength(2);
    expect(csrf).toBe('mock-csrf-admin');
    expect(body).toEqual({ expected_revision: 2, from_person_id: 'P-KEMI', delegate: 'P-FEMI', starts: '2026-12-01', ends: '2026-12-03', reason: 'Training' });
    await expect(panel.getByLabel('Reason')).toHaveValue('');
    expect((await mockList(request)).items).toHaveLength(3);
    await expectNoAxeViolations(page);
  });

  test('422: the top message and the messages under To and Ends, focus to To, entries kept, axe clean (AC 12, 19)', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_delegations_save: 'invalid' });
    const panel = panelOf(page);
    await fill(panel, page);
    await panel.getByRole('button', { name: 'Add delegation' }).click();
    await expect(panel.getByText('Check these fields: delegate, ends.')).toBeVisible();
    await expect(panel.getByRole('combobox', { name: 'To' })).toBeFocused();
    await expect(panel.getByRole('combobox', { name: 'To' })).toHaveAttribute('aria-invalid', 'true');
    await expect(panel.getByRole('combobox', { name: 'To' })).toHaveAccessibleDescription(/This person can’t take this delegation\./);
    await expect(panel.getByLabel('Ends')).toHaveAccessibleDescription(/Choose an end date within the next 90 days\./);
    await expect(panel.getByLabel('Reason')).toHaveValue('Training');
    await expectNoAxeViolations(page);
  });

  test('uncertain: never added, nothing in the mock; uncertain_written: one row in the mock, the warning, Add held until Start again (AC 14, 19)', async ({ page, context, request }) => {
    await openAs(page, context, { psl_mock_delegations_save: 'uncertain' });
    let panel = panelOf(page);
    await fill(panel, page);
    await panel.getByRole('button', { name: 'Add delegation' }).click();
    await expect(panel.getByText('It was not added. You can add it again.')).toBeVisible();
    await expect(panel.getByRole('button', { name: 'Add delegation' })).toBeEnabled();
    await expect(page.getByText(/Delegation added/)).toHaveCount(0);
    expect(await mockList(request)).toMatchObject({ revision: 2, items: [{}, {}] });
    await expectNoAxeViolations(page);

    await openAs(page, context, { psl_mock_delegations_save: 'uncertain_written' });
    panel = panelOf(page);
    await fill(panel, page);
    await panel.getByRole('button', { name: 'Add delegation' }).click();
    await expect(panel.getByText(CHANGED)).toBeVisible();
    await expect(desktopRows(page)).toHaveCount(3);
    await expect(panel.getByRole('button', { name: 'Add delegation' })).toBeDisabled();
    expect((await mockList(request)).items).toHaveLength(3);
    await expectNoAxeViolations(page);
    await panel.getByRole('button', { name: 'Start again' }).click();
    await expect(panel.getByRole('button', { name: 'Add delegation' })).toBeEnabled();
    await expect(panel.getByLabel('Reason')).toHaveValue('');
    expect((await mockList(request)).items).toHaveLength(3);
  });

  test('readonly has no add control; empty and not-open are axe clean; pm makes no delegation call (AC 4, 15, 19)', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_delegations: 'readonly' });
    await expect(desktopRows(page)).toHaveCount(2);
    await expect(page.getByRole('button', { name: /Add delegation/ })).toHaveCount(0);
    await expect(page.getByText(NOTE)).toHaveCount(0);
    await expectNoAxeViolations(page);
    await openAs(page, context, { psl_mock_delegations: 'empty' });
    await expect(page.locator('.setup-desktop').getByText('No delegations to show.')).toBeVisible();
    await expect(panelOf(page)).toBeVisible();
    await expectNoAxeViolations(page);
    await openAs(page, context, { psl_mock_delegations: 'forbidden' });
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
    await expect(page.getByText('Kemi Adebayo')).toHaveCount(0);
    await expectNoAxeViolations(page);
    const seen = apiCalls(page);
    await openAs(page, context, { psl_mock_delegations: 'default' }, 'pm');
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
    expect(seen).toEqual([]);
  });
});

test.describe('desktop with reduced motion', () => {
  test.use({ viewport: DESKTOP, reducedMotion: 'reduce' });

  test('nothing animates (AC 19)', async ({ page, context }) => {
    await openAs(page, context);
    const durations = await page.locator('.setup-desktop button, .setup-desktop input').evaluateAll((els) => els.map((el) => getComputedStyle(el).transitionDuration));
    expect(durations.every((d) => d.split(',').every((part) => part.trim() === '0s'))).toBe(true);
  });
});

test.describe('phone', () => {
  test.use({ viewport: PHONE });

  test('cards as drawn, one h1 "Delegation", the bottom Add delegation, 44px targets, no side scroll, axe clean (AC 3, 19)', async ({ page, context }) => {
    await openAs(page, context);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(['Delegation']);
    const cards = page.locator('.setup-phone li');
    await expect(cards).toHaveCount(2);
    await expect(cards.nth(0)).toContainText('Kemi Adebayo → Femi Ade');
    await expect(cards.nth(0)).toContainText('PMO Lead · 18–25 Nov 2026 · Annual leave');
    await expect(cards.nth(0)).toContainText('Upcoming');
    const add = page.getByRole('button', { name: 'Add delegation' });
    expect((await add.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);
  });

  test('the sheet: same fields, Escape and Cancel return focus, a 422 inside it, a success closes it and shows the new card (AC 12, 17, 19)', async ({ page, context }) => {
    await openAs(page, context);
    const add = page.getByRole('button', { name: 'Add delegation' });
    await add.click();
    let sheet = page.getByRole('dialog', { name: 'Add a delegation' });
    await expect(sheet.getByRole('combobox', { name: 'From' })).toBeVisible();
    await expect(sheet.getByText(NOTE)).toBeVisible();
    for (const target of await sheet.getByRole('button').all()) {
      if (await target.isVisible()) expect((await target.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);
    await page.keyboard.press('Escape');
    await expect(sheet).toHaveCount(0);
    await expect(add).toBeFocused();
    await add.click();
    await sheet.getByRole('button', { name: 'Cancel' }).click();
    await expect(sheet).toHaveCount(0);
    await expect(add).toBeFocused();

    await openAs(page, context, { psl_mock_delegations_save: 'invalid' });
    await add.click();
    sheet = page.getByRole('dialog', { name: 'Add a delegation' });
    await fill(sheet, page);
    await sheet.getByRole('button', { name: 'Add delegation' }).click();
    await expect(sheet.getByText('Check these fields: delegate, ends.')).toBeVisible();
    await expect(sheet.getByRole('combobox', { name: 'To' })).toBeFocused();
    await expectNoAxeViolations(page);

    await openAs(page, context, { psl_mock_delegations_save: '' });
    await add.click();
    await fill(sheet, page);
    await sheet.getByRole('button', { name: 'Add delegation' }).click();
    await expect(sheet).toHaveCount(0);
    await expect(page.locator('.setup-phone li')).toHaveCount(3);
    await expect(page.locator('.setup-phone li').nth(2).locator('[data-row-for]')).toBeFocused();
    await expect(page.locator('[aria-live="polite"]')).toHaveText('Delegation added: Kemi Adebayo to Femi Ade, 01–03 Dec 2026.');
  });

  test('uncertain warning, empty, readonly and not-open pass axe with no side scroll (AC 19)', async ({ page, context }) => {
    await openAs(page, context, { psl_mock_delegations_save: 'uncertain_written' });
    await page.getByRole('button', { name: 'Add delegation' }).click();
    const sheet = page.getByRole('dialog', { name: 'Add a delegation' });
    await fill(sheet, page);
    await sheet.getByRole('button', { name: 'Add delegation' }).click();
    await expect(sheet.getByText(CHANGED)).toBeVisible();
    await expectNoAxeViolations(page);
    for (const scenario of ['empty', 'readonly', 'forbidden']) {
      await openAs(page, context, { psl_mock_delegations: scenario, psl_mock_delegations_save: '' });
      expect(await noSideScroll(page)).toBe(true);
      await expectNoAxeViolations(page);
    }
  });
});
