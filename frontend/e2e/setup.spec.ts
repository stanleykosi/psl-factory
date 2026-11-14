import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// F-11 Setup rules against the contract mock: frame, list, save flows, finance, delivery, phone, paging, reserved
// tabs, access and accessibility (A-SETUP frontend half, A-ACCESSIBILITY).
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const RESERVED = [
  ['Roles', '/setup/roles'],
  ['Costing rule', '/setup/costing-rule'],
  ['Delegation', '/setup/delegation'],
  ['Payroll visibility', '/setup/payroll-visibility'],
  ['Staff accounts', '/setup/staff'],
  ['Templates', '/setup/templates'],
] as const;

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('main#main h1:visible').first()).toBeVisible();
}

/** Opens a route as a persona with optional mock scenario cookies. */
async function openAs(page: Page, context: BrowserContext, path: string, cookies: Record<string, string> = {}) {
  await setCookies(context, { psl_mock_persona: 'admin', ...cookies });
  await page.goto(path);
  await loaded(page);
}

async function tabTo(page: Page, target: Locator) {
  for (let i = 0; i < 80; i++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((el) => el === document.activeElement)) return;
  }
  throw new Error('target never received focus');
}

const setupRequests = (page: Page) => {
  const seen: { method: string; url: string }[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/v1/setup/') || r.url().includes('/evidence')) seen.push({ method: r.method(), url: r.url() });
  });
  return seen;
};

const today = () => {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Lagos', day: '2-digit', month: 'short' }).formatToParts(new Date()).map((p) => [p.type, p.value]),
  );
  return `${parts.day} ${parts.month}`;
};

const WITHDRAWN = 'Your role does not allow this. You can no longer change these rules, so the Set a rule panel has closed. Nothing you entered was saved.';
const panel = (page: Page) => page.getByRole('region', { name: 'Set a rule' });
const table = (page: Page) => page.locator('.setup-desktop table');
const row = (page: Page, name: string) => table(page).locator('tr', { hasText: name });

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

test.describe('desktop rules', () => {
  test.use({ viewport: DESKTOP });

  test('/setup lands on rules with the frame, seven tabs and both badges (AC 1, 2)', async ({ page, context }) => {
    await openAs(page, context, '/setup');
    await expect(page).toHaveURL(/\/setup\/rules$/);
    await expect(page).toHaveTitle('Rules · Setup · PSL Factory');
    await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Setup' })).toHaveAttribute('aria-current', 'page');
    await expect(page.locator('.setup-eyebrow')).toHaveText('SETUP');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(['Roles, rules and delegation']);
    const tabs = page.getByRole('navigation', { name: 'Setup' }).getByRole('link');
    await expect(tabs).toHaveText(['Roles2', 'Rules8', 'Costing rule', 'Delegation', 'Payroll visibility', 'Staff accounts', 'Templates']);
    expect(await tabs.evaluateAll((els) => els.map((el) => el.getAttribute('href')))).toEqual([
      '/setup/roles',
      '/setup/rules',
      '/setup/costing-rule',
      '/setup/delegation',
      '/setup/payroll-visibility',
      '/setup/staff',
      '/setup/templates',
    ]);
    await expect(tabs.nth(1)).toHaveAttribute('aria-current', 'page');
    await expect(table(page).locator('tbody tr')).toHaveCount(10);
    await expect(row(page, 'Who reviews client documents').locator('td')).toHaveText(['Who reviews client documents', 'All lines', 'PMO Lead', 'v2 · since 01 Oct']);
    await expect(row(page, 'Who may assign an RFP to a PM').locator('td').nth(3)).toHaveText('HOLDS WORK');
    await expect(page.getByRole('link', { name: 'PSL standard pricing v4' })).toHaveAttribute('href', '/setup/costing-rule');
    await expect(page.getByText(/^8 rules aren’t set yet\./)).toBeVisible();
    await expect(panel(page).getByRole('checkbox')).toHaveCount(3);
    await expect(panel(page).getByRole('checkbox', { name: 'PMO Lead' })).toHaveCount(1);
    await expectNoAxeViolations(page);
  });

  test('first save: one PUT with the edit and the CSRF token, the row, badge and banner update (AC 8, 15)', async ({ page, context }) => {
    const seen = setupRequests(page);
    let putBody: unknown;
    let csrf: string | null = null;
    page.on('request', (r) => {
      if (r.method() === 'PUT') {
        putBody = r.postDataJSON();
        csrf = r.headers()['x-csrftoken'] ?? null;
      }
    });
    await openAs(page, context, '/setup/rules');
    await panel(page).getByRole('checkbox', { name: 'PMO Lead' }).check();
    await panel(page).getByLabel('Why').fill('Agreed at the PSL leadership meeting');
    await panel(page).getByLabel(/^Proof/).setInputFiles({ name: 'minutes.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(120 * 1024, 1) });
    await expect(panel(page).getByText('Uploaded · 120 KB')).toBeVisible();
    await panel(page).getByRole('button', { name: 'Save as version 1' }).click();
    await expect(panel(page).getByRole('status')).toHaveText('Saved as version 1.');
    await expect(panel(page).getByRole('status')).toBeFocused();
    expect(seen.filter((r) => r.method === 'PUT')).toHaveLength(1);
    expect(seen.filter((r) => r.method === 'POST')).toHaveLength(1);
    expect(csrf).toBe('mock-csrf-admin');
    expect(putBody).toEqual({
      expected_revision: 0,
      value: { roles: ['pmo_lead'] },
      starts: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      reason: 'Agreed at the PSL leadership meeting',
      evidence_id: expect.stringMatching(/^EV-\d+$/),
    });
    await expect(row(page, 'Who may assign an RFP to a PM').locator('td')).toHaveText(['Who may assign an RFP to a PM', 'Pre-sale', 'PMO Lead', `v1 · since ${today()}`]);
    await expect(page.getByRole('navigation', { name: 'Setup' }).getByRole('link', { name: /^Rules/ })).toHaveText('Rules7');
    await expect(page.getByText(/^7 rules aren’t set yet\./)).toBeVisible();
  });

  test('stale save: the message takes focus, the other version shows, edits clear, one PUT (AC 10)', async ({ page, context }) => {
    const seen = setupRequests(page);
    await openAs(page, context, '/setup/rules', { psl_mock_setup_save: 'stale' });
    await panel(page).getByRole('checkbox', { name: 'CEO' }).check();
    await panel(page).getByLabel('Why').fill('Mine');
    await panel(page).getByRole('button', { name: 'Save as version 1' }).click();
    const alert = panel(page).getByRole('alert');
    await expect(alert).toHaveText('Someone changed this since you opened it. Reload to see the latest version.');
    await expect(alert).toBeFocused();
    await expect(row(page, 'Who may assign an RFP to a PM').locator('td').nth(2)).toHaveText('PMO Lead');
    await expect(panel(page).getByRole('checkbox', { name: 'CEO' })).not.toBeChecked();
    await expect(panel(page).getByRole('checkbox', { name: 'PMO Lead' })).toBeChecked();
    await expect(panel(page).getByLabel('Why')).toHaveValue('');
    await expect(panel(page).getByRole('button', { name: 'Save as version 2' })).toBeVisible();
    expect(seen.filter((r) => r.method === 'PUT')).toHaveLength(1);
  });

  test('invalid save marks Why and Starts, keeps the edits, and passes axe (AC 11, 24)', async ({ page, context }) => {
    await openAs(page, context, '/setup/rules', { psl_mock_setup_save: 'invalid' });
    await panel(page).getByLabel('Why').fill('Mine');
    await panel(page).getByRole('button', { name: 'Save as version 1' }).click();
    await expect(panel(page).getByRole('alert')).toHaveText('Check these fields: reason, starts.');
    await expect(panel(page).getByLabel('Why')).toHaveAttribute('aria-invalid', 'true');
    await expect(panel(page).getByLabel('Starts')).toHaveAttribute('aria-invalid', 'true');
    await expect(panel(page).getByLabel('Why')).toHaveValue('Mine');
    await expectNoAxeViolations(page);
  });

  test('read-only Lead: same rows, no edit controls, a forced PUT is 403 (AC 5)', async ({ page, context, request }) => {
    await openAs(page, context, '/setup/rules', { psl_mock_setup: 'readonly' });
    await expect(table(page).locator('tbody tr')).toHaveCount(10);
    await expect(page.getByRole('button', { name: /Save as version/ })).toHaveCount(0);
    await expect(page.locator('main input, main select')).toHaveCount(0);
    await expectNoAxeViolations(page);
    const forced = await request.put(`${MOCK}/api/v1/setup/rules/presale.rfp_assigner`, {
      headers: { Cookie: 'psl_mock_persona=admin; psl_mock_setup=readonly', 'X-CSRFToken': 'mock-csrf-admin' },
      data: { expected_revision: 0, value: { roles: ['pmo_lead'] } },
    });
    expect(forced.status()).toBe(403);
  });

  test('right withdrawn after load: the 403 message stays above the list with focus once the panel closes (QA-1-1)', async ({ page, context }) => {
    const seen = setupRequests(page);
    await openAs(page, context, '/setup/rules');
    await panel(page).getByRole('checkbox', { name: 'PMO Lead' }).check();
    await panel(page).getByLabel('Why').fill('Mine');
    await setCookies(context, { psl_mock_setup: 'readonly' });
    await panel(page).getByRole('button', { name: 'Save as version 1' }).click();
    const alert = page.locator('.setup-desktop').getByRole('alert');
    await expect(alert).toHaveText(WITHDRAWN);
    await expect(alert).toBeFocused();
    await expect(panel(page)).toHaveCount(0);
    await expect(table(page).locator('tbody tr')).toHaveCount(10);
    expect(seen.filter((r) => r.method === 'PUT')).toHaveLength(1);
    await expectNoAxeViolations(page);
  });

  test('finance: a group losing its only editable rule after load keeps the 403 message with focus (QA-1-1)', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'finance_lead' });
    await page.goto('/setup/rules/finance');
    await loaded(page);
    const view = page.locator('.setup-desktop');
    await view.getByRole('button', { name: 'Set BU totals rules' }).click();
    await setCookies(context, { psl_mock_setup: 'readonly' });
    await panel(page).getByRole('button', { name: 'Save as version 1' }).click();
    await expect(view.getByRole('alert')).toHaveText(WITHDRAWN);
    await expect(view.getByRole('alert')).toBeFocused();
    await expect(panel(page)).toHaveCount(0);
    await expect(view.getByRole('button', { name: /^Set / })).toHaveCount(0);
  });

  test('keyboard reaches each tab, the panel controls in order and Save, with the 2px focus ring (AC 24)', async ({ page, context }) => {
    await openAs(page, context, '/setup/rules');
    for (const name of ['Roles', 'Rules', 'Templates']) {
      await tabTo(page, page.getByRole('navigation', { name: 'Setup' }).getByRole('link', { name: new RegExp(`^${name}`) }));
    }
    const order = [
      panel(page).getByRole('combobox', { name: 'Rule' }),
      panel(page).getByRole('checkbox', { name: 'PMO Lead' }),
      panel(page).getByRole('checkbox', { name: 'CEO' }),
      panel(page).getByRole('checkbox', { name: 'PMO', exact: true }),
      panel(page).getByLabel('Starts'),
      panel(page).getByLabel('Why'),
      panel(page).getByLabel(/^Proof/),
      panel(page).getByRole('button', { name: 'Save as version 1' }),
    ];
    await tabTo(page, order[0]);
    for (const [index, target] of order.slice(1).entries()) {
      await page.keyboard.press('Tab');
      // The date input holds day, month and year parts; Tab moves through them before Why.
      const afterDate = index === 4;
      for (let i = 0; afterDate && i < 3 && !(await target.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press('Tab');
      await expect(target).toBeFocused();
    }
    const ring = await panel(page).getByRole('button', { name: 'Save as version 1' }).evaluate((el) => {
      const s = getComputedStyle(el);
      return `${s.outlineStyle} ${s.outlineWidth}`;
    });
    expect(ring).toBe('solid 2px');
    await expect(panel(page).getByRole('group', { name: 'Roles allowed' })).toBeVisible();
  });

  test('paging: 50 rows, Show more appends 5 and disappears (AC 19)', async ({ page, context }) => {
    await openAs(page, context, '/setup/rules', { psl_mock_setup: 'many' });
    await expect(table(page).locator('tbody tr')).toHaveCount(50);
    await page.locator('.setup-desktop').getByRole('button', { name: 'Show more' }).click();
    await expect(table(page).locator('tbody tr')).toHaveCount(55);
    await expect(page.locator('.setup-desktop').getByRole('button', { name: 'Show more' })).toHaveCount(0);
  });

  test('a failing second page keeps the 50 rows and warns (AC 19)', async ({ page, context }) => {
    await page.route(/\/api\/v1\/setup\/rules\?.*cursor=/, (route) => route.fulfill({ status: 503, contentType: 'application/json', body: '{"code":"down","message":"Down"}' }));
    await openAs(page, context, '/setup/rules', { psl_mock_setup: 'many' });
    await page.locator('.setup-desktop').getByRole('button', { name: 'Show more' }).click();
    await expect(page.locator('.setup-desktop').getByText('We couldn’t load more rules. Choose Show more to try again.')).toBeVisible();
    await expect(table(page).locator('tbody tr')).toHaveCount(50);
  });

  test('empty: frame, "No rules to show." and no banner or panel, on all three views (AC 21)', async ({ page, context }) => {
    await openAs(page, context, '/setup/rules', { psl_mock_setup: 'empty' });
    await expect(page.getByRole('navigation', { name: 'Setup' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'No rules to show.' })).toBeVisible();
    await expect(page.getByText(/set yet/)).toHaveCount(0);
    await expect(panel(page)).toHaveCount(0);
    for (const path of ['/setup/rules/finance', '/setup/rules/delivery']) {
      await page.goto(path);
      await loaded(page);
      await expect(page.getByRole('heading', { name: 'No rules to show.' })).toBeVisible();
    }
  });

  test('access: forbidden scenario, pm persona with no rules call, 401 sign-in link (AC 14)', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'admin', psl_mock_setup: 'forbidden' });
    await page.goto('/setup/rules');
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
    await expect(page.getByText('Who may assign an RFP to a PM')).toHaveCount(0);

    const seen = setupRequests(page);
    await setCookies(context, { psl_mock_persona: 'pm', psl_mock_setup: 'desktop' });
    await page.goto('/setup/rules');
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
    expect(seen).toEqual([]);

    await setCookies(context, { psl_mock_persona: 'admin', psl_mock_scenario: '401' });
    await page.goto('/setup/rules');
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', /next=%2Fsetup%2Frules$/);
  });

  test('finance: crumb, lead, count callout, 7 groups, Set disclosures; read-only has none (AC 16)', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'finance_lead' });
    await page.goto('/setup/rules/finance');
    await loaded(page);
    await expect(page).toHaveTitle('Finance rules · Setup · PSL Factory');
    const view = page.locator('.setup-desktop');
    await expect(view.getByRole('navigation', { name: 'Breadcrumb' })).toHaveText('SETUP / RULES / FINANCE');
    await expect(view.getByText('All 25 values are Not set. Real reviewers and approvers come from PSL; none are invented here.')).toBeVisible();
    await expect(view.getByRole('heading', { level: 2 })).toHaveText(['Management accounts', 'Income schedules', 'Asset schedule', 'Cash forecast', 'BU totals', 'Ledger sources', 'Payroll']);
    await expect(view.getByText('NOT SET', { exact: true })).toHaveCount(25);
    const bu = view.getByRole('button', { name: 'Set BU totals rules' });
    await expect(bu).toHaveAttribute('aria-expanded', 'false');
    await bu.click();
    await expect(bu).toHaveAttribute('aria-expanded', 'true');
    await expect(panel(page).getByRole('combobox', { name: 'Rule' }).locator('option')).toHaveText(['Who reviews BU totals']);
    await expectNoAxeViolations(page);

    await setCookies(context, { psl_mock_setup: 'readonly' });
    await page.reload();
    await loaded(page);
    await expect(view.getByRole('button', { name: /^Set / })).toHaveCount(0);
  });

  test('delivery: table, set row, info callout, Next and no edit controls (AC 17)', async ({ page, context }) => {
    await openAs(page, context, '/setup/rules/delivery');
    await expect(page).toHaveTitle('Delivery rules · Setup · PSL Factory');
    await expect(page.locator('.setup-desktop th')).toHaveText(['RULE', 'VALUE', 'USED BY']);
    await expect(table(page).locator('tbody tr')).toHaveCount(5);
    await expect(row(page, 'Archive storage rule').locator('td')).toHaveText(['Archive storage rule', 'Keep, never purge', 'Archive']);
    await expect(page.getByText(/^These are PSL’s decisions\./)).toBeVisible();
    await expect(page.getByText('Each rule is versioned. Changing one doesn’t change work already finished.')).toBeVisible();
    await expect(page.locator('main button, main input, main select')).toHaveCount(0);
    await expectNoAxeViolations(page);
  });

  test('each reserved tab opens with the frame, that tab current and the empty pattern (AC 20)', async ({ page, context }) => {
    const seen = setupRequests(page);
    await openAs(page, context, '/setup/rules');
    seen.length = 0;
    for (const [label, path] of RESERVED) {
      await page.getByRole('navigation', { name: 'Setup' }).getByRole('link', { name: new RegExp(`^${label}`) }).click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(page.getByRole('heading', { level: 2, name: `${label} comes next.` })).toBeVisible();
      await expect(page.getByRole('navigation', { name: 'Setup' }).getByRole('link', { name: label, exact: true })).toHaveAttribute('aria-current', 'page');
      await expect(page).toHaveTitle(`${label} · Setup · PSL Factory`);
    }
    expect(seen).toEqual([]);
    await expectNoAxeViolations(page);
    await setCookies(context, { psl_mock_persona: 'pm' });
    await page.goto('/setup/delegation');
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
  });
});

test.describe('phone', () => {
  test.use({ viewport: PHONE });

  const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= 390);

  test('rules, finance and delivery as drawn, read-only, no side scroll, one h1, axe clean (AC 18, 24)', async ({ page, context }) => {
    await openAs(page, context, '/setup/rules', { psl_mock_setup: 'mobile' });
    const bar = page.locator('header.psl-phonebar');
    await expect(bar.getByRole('link', { name: 'Back to Setup' })).toHaveAttribute('href', '/setup/roles');
    await expect(bar.getByRole('button', { name: 'Menu' })).toHaveCount(0);
    await expect(page.locator('.setup-phone').getByRole('link', { name: /Setup/ })).toHaveCount(0);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(['Rules · 6 not set']);
    await expect(page.locator('.setup-card')).toHaveCount(6);
    await expect(page.locator('.setup-card').first()).toContainText('Not set · Pre-sale');
    await expect(page.getByRole('navigation', { name: 'Setup' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /Save as version/ })).toHaveCount(0);
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);

    await page.goto('/setup/rules/finance');
    await loaded(page);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(['Finance rules']);
    await expect(page.getByText('25 values Not set.')).toBeVisible();
    await expect(page.locator('.setup-phone .setup-card')).toHaveCount(3);
    await expect(page.getByText('+ 4 MORE LINES · OPEN ON DESKTOP')).toBeVisible();
    await expect(bar.getByRole('link', { name: 'Back to Setup' })).toBeVisible();
    await expect(bar.locator('.shell-phonenote')).toHaveText('RULES');
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);

    await page.goto('/setup/rules/delivery');
    await loaded(page);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(['Delivery rules']);
    await expect(page.locator('.setup-phone li')).toHaveCount(4);
    await expect(bar.locator('.shell-phonenote')).toHaveText('RULES');
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);

    await page.goto('/setup/templates');
    await loaded(page);
    expect(await noSideScroll(page)).toBe(true);
    await expectNoAxeViolations(page);
  });

  test('read-only scenario on the phone passes axe', async ({ page, context }) => {
    await openAs(page, context, '/setup/rules', { psl_mock_setup: 'readonly' });
    await expectNoAxeViolations(page);
  });
});
