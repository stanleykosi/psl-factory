import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-29 document review (SCR-08) against the contract mock: the four boards' states at 1440 and 390, the decision
// writes, the states a person without access sees, axe WCAG 2.2 AA. Fields beyond the typed E-DOCUMENT ones are proposals.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const PAGE = '/projects/P-0101/documents/D-2901?v=2';

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

/** The writes the page sends and the reads of the document, in order. */
function record(page: Page) {
  const log: string[] = [];
  const bodies: Record<string, unknown>[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/v1/') || url.pathname === '/api/v1/me') return;
    log.push(`${request.method()} ${url.pathname}`);
    if (request.method() === 'POST') bodies.push(request.postDataJSON());
  });
  return { log, bodies, writes: () => log.filter((l) => l.startsWith('POST')) };
}

async function open(page: Page, path = PAGE) {
  await page.goto(path);
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

test.beforeEach(async ({ request, context }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await setCookies(context, { psl_mock_persona: 'pm' });
});

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('the default board: crumb, title, tags, five sections, the note, checks, audience and the two buttons', async ({ page }) => {
    await open(page);
    await expect(page).toHaveTitle('Document · PSL Factory');
    await expect(page.locator('.psl-crumb')).toHaveText('Lagoon Health / Documents / SOW-0198');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Statement of work · v2');
    await expect(page.getByText('Awaiting PMO Lead review')).toBeVisible();
    await expect(page.locator('.docrev__testtemplate')).toHaveText('TEST TEMPLATE');
    await expect(page.locator('.docrev__section h3')).toHaveText(['1. Scope', '2. Deliverables', '3. Milestones and stages', '4. Assumptions', '5. Out of scope']);
    await expect(page.locator('.docrev__section.is-changed')).toHaveCount(1);
    await expect(page.locator('.docrev__note')).toContainText('Tola (agent note): the minutes say "week 3". Check which is right.');
    const checks = page.getByRole('region', { name: 'Checks' });
    await expect(checks.getByText('Matches COST-0140 v2')).toBeVisible();
    await expect(checks.getByText('5 of 5')).toBeVisible();
    await expect(checks.getByText('Client · Lagoon Health')).toBeVisible();
    await expect(page.getByRole('heading', { level: 2, name: 'Your review · PMO Lead' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Approve v2' })).toBeEnabled();
    await expect(page.getByRole('button', { name: 'Return with note' })).toBeVisible();
    await expect(page.getByLabel('Note for the PM (needed to return)')).toBeVisible();
    await expect(page.getByText('Approving records your name and time. Approving does not send it to the client.')).toBeVisible();
    await expect(page.getByRole('tab', { name: /^Documents/ })).toHaveAttribute('aria-selected', 'true');
    await expectNoAxeViolations(page);
  });

  test('approve sends one claim then one decision with the read revision and no note, then shows the re-read result', async ({ page }) => {
    const sent = record(page);
    await open(page);
    await expect(page.getByRole('button', { name: 'Approve v2' })).toBeEnabled();
    await page.getByRole('button', { name: 'Approve v2' }).click();
    const done = page.locator('.psl-toast').filter({ hasText: 'You approved v2' });
    await expect(done).toHaveText(/^You approved v2 · Kemi Adebayo · 17 Nov 10:05\. Not sent to the client\.$/);
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
    await expect(page.getByText('Approved', { exact: true })).toBeVisible();
    expect(sent.writes()).toEqual(['POST /api/v1/tasks/T-2901/claim', 'POST /api/v1/tasks/T-2901/decision']);
    expect(sent.bodies[1]).toEqual({ expected_revision: 2, verdict: 'approve' });
    await expectNoAxeViolations(page);
    // a fresh load shows the decision as made, with no controls
    await open(page);
    await expect(page.getByText('This decision has already been made.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
  });

  test('return with an empty note shows the field error and sends no decision; with a note it shows the returned state', async ({ page }) => {
    const sent = record(page);
    await open(page);
    await expect(page.getByRole('button', { name: 'Return with note' })).toBeEnabled();
    await page.getByRole('button', { name: 'Return with note' }).click();
    const note = page.getByLabel('Note for the PM (needed to return)');
    await expect(page.getByText('Add a note to return it.')).toBeVisible();
    await expect(note).toBeFocused();
    await expect(note).toHaveAttribute('aria-invalid', 'true');
    expect(sent.writes().filter((w) => w.endsWith('/decision'))).toEqual([]);
    await note.fill('Section 4: please confirm the week.');
    await page.getByRole('button', { name: 'Return with note' }).click();
    await expect(page.locator('.docrev__returnedhead')).toHaveText(/^Returned by Kemi Adebayo \(PMO Lead\) · 17 Nov 14:20$/);
    await expect(page.locator('.docrev__quote')).toContainText('Section 4');
    expect(sent.bodies.at(-1)).toEqual({ expected_revision: 2, verdict: 'return', note: 'Section 4: please confirm the week.' });
    expect(sent.writes().filter((w) => w.endsWith('/decision'))).toHaveLength(1);
    await expect(page.getByRole('button', { name: /^Approve/ })).toHaveCount(0);
  });

  test('the returned board: banner, quote, rule sentence, the agent panel, held buttons and the sections', async ({ page, context }) => {
    await setCookies(context, { psl_mock_document: 'returned' });
    const sent = record(page);
    await open(page);
    await expect(page.getByText('Returned to PM')).toBeVisible();
    await expect(page.locator('.docrev__returnedhead')).toHaveText('Returned by Kemi Adebayo (PMO Lead) · 17 Nov 14:20');
    await expect(page.locator('.docrev__quote')).toContainText('Section 4: confirm week 2 or week 3');
    await expect(page.getByText('Approval on v2 is not carried over.', { exact: false })).toBeVisible();
    await expect(page.getByText('I can draft v3 with section 4 changed')).toBeVisible();
    await expect(page.locator('.docrev__section')).toHaveCount(5);
    for (const name of [/Ask Tola to draft v3/, /Edit as v3/]) {
      const button = page.getByRole('button', { name });
      await expect(button).toBeDisabled();
      await button.click({ force: true });
    }
    await expect(page.getByText('Not available yet')).toHaveCount(2);
    expect(sent.writes()).toEqual([]);
    expect(sent.log.filter((l) => /draft|document.*(POST|PUT)/i.test(l) && !l.startsWith('GET'))).toEqual([]);
    await expectNoAxeViolations(page);
  });

  test('a returned document whose note is not shown says so and quotes nothing', async ({ page, context }) => {
    await setCookies(context, { psl_mock_document: 'returned-hidden' });
    await open(page);
    await expect(page.getByText('The note isn’t shown to you.')).toBeVisible();
    await expect(page.locator('.docrev__quote')).toHaveText('The note isn’t shown to you.');
  });

  test('the reviewer who prepared it has no controls and reads why', async ({ page, context }) => {
    await setCookies(context, { psl_mock_document: 'cannot-act' });
    const sent = record(page);
    await open(page);
    await expect(page.getByText('You prepared Statement of work v2, so someone else must review it.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
    await expect(page.getByLabel('Note for the PM (needed to return)')).toHaveCount(0);
    expect(sent.writes()).toEqual([]);
    await expectNoAxeViolations(page);
  });

  test('with no review task the page is read-only and sends no write', async ({ page, context }) => {
    await setCookies(context, { psl_mock_document: 'no-review' });
    const sent = record(page);
    await open(page);
    await expect(page.getByText('This review isn’t open to you here.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
    expect(sent.writes()).toEqual([]);
    expect(sent.log.filter((l) => l.includes('/api/v1/work/'))).toEqual([]);
  });

  test('an unknown amount reads Unknown and never Matches', async ({ page, context }) => {
    await setCookies(context, { psl_mock_document: 'amount-unknown' });
    await open(page);
    const row = page.locator('.docrev__check', { hasText: 'Amounts match approved costing' });
    await expect(row.getByText('Unknown', { exact: true })).toBeVisible();
    await expect(page.getByText(/Matches/)).toHaveCount(0);
  });

  test('section text and notes are plain characters; no sections gives the download link', async ({ page, context }) => {
    await setCookies(context, { psl_mock_document: 'hostile' });
    await open(page);
    await expect(page.getByText('Plain <script>alert(1)</script> text')).toBeVisible();
    await expect(page.locator('article script, article b')).toHaveCount(0);
    await setCookies(context, { psl_mock_document: 'no-sections' });
    await open(page);
    await expect(page.getByText('The text isn’t available here.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Download' })).toHaveAttribute('href', 'https://files.example.test/sow-d-2901-v2.pdf');
    await setCookies(context, { psl_mock_document: 'empty-sections' });
    await open(page);
    await expect(page.getByText('This document has no sections yet.')).toBeVisible();
  });

  test('each version shows its own state; a missing or unreadable version is not found', async ({ page }) => {
    await open(page, '/projects/P-0101/documents/D-2901?v=1');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Statement of work · v1');
    await expect(page.getByText('Replaced by v2')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
    for (const path of ['/projects/P-0101/documents/D-2901', '/projects/P-0101/documents/D-2901?v=latest', '/projects/P-0101/documents/D-2901?v=3']) {
      await open(page, path);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('You can’t open this document');
    }
  });

  test('401 shows signed out, 403 and 404 look the same with no title, and a persona without the project sees no text', async ({ page, context }) => {
    await setCookies(context, { psl_mock_scenario: '401' });
    await page.goto(PAGE);
    // /me answers 401 first: the frame's signed-out state shows, with no sign-in link (F-57).
    await expect(page.getByText('You’re signed out.')).toBeVisible();
    await expect(page.getByRole('main').getByRole('link')).toHaveCount(0);
    await context.clearCookies({ name: 'psl_mock_scenario' });
    for (const scenario of ['403', '404']) {
      // only the document read fails; the frame's own reads (/me) are not given the scenario
      await page.unroute('**/api/v1/documents/**');
      await page.route('**/api/v1/documents/**', (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': scenario } }));
      await open(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('You can’t open this document');
      await expect(page.getByText(/Statement of work|Scope/)).toHaveCount(0);
    }
    await page.unroute('**/api/v1/documents/**');
    await setCookies(context, { psl_mock_persona: 'admin' }); // the CEO sees every project since D-150; Admin has no access to this one
    await open(page);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('You can’t open this document');
    await expect(page.getByText(/Scope|Lagoon/)).toHaveCount(0);
  });

  test('a 409 on the decision says so, sends no second decision and enables nothing by itself', async ({ page, context }) => {
    const sent = record(page);
    await open(page);
    await expect(page.getByRole('button', { name: 'Approve v2' })).toBeEnabled();
    await setCookies(context, { psl_mock_scenario: '409' });
    await page.getByRole('button', { name: 'Approve v2' }).click();
    await expect(page.getByText(/changed while you were reading it/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Approve v2' })).toHaveCount(0);
    expect(sent.writes().filter((w) => w.endsWith('/decision'))).toHaveLength(1);
  });

  test('a 422 on the decision shows the note error', async ({ page, context }) => {
    await open(page);
    await expect(page.getByRole('button', { name: 'Return with note' })).toBeEnabled();
    await page.getByLabel('Note for the PM (needed to return)').fill('Fix it');
    await setCookies(context, { psl_mock_scenario: '422' });
    await page.getByRole('button', { name: 'Return with note' }).click();
    await expect(page.locator('.psl-field [role="alert"], .psl-field .psl-field__error, .psl-field .is-error').first()).toBeVisible();
    await expect(page.getByLabel('Note for the PM (needed to return)')).toHaveAttribute('aria-invalid', 'true');
  });

  test('a network failure on the decision shows no approval, re-reads, and sends the decision once', async ({ page }) => {
    const sent = record(page);
    await page.route('**/api/v1/tasks/T-2901/decision', (route) => route.abort('failed'));
    await open(page);
    await expect(page.getByRole('button', { name: 'Approve v2' })).toBeEnabled();
    const reads = () => sent.log.filter((l) => l === 'GET /api/v1/work/W-2901').length;
    const before = reads();
    await page.getByRole('button', { name: 'Approve v2' }).click();
    await expect(page.getByText(/couldn’t confirm your decision/)).toBeVisible();
    await expect(page.getByText(/You approved/)).toHaveCount(0);
    expect(reads()).toBeGreaterThan(before);
    expect(sent.writes().filter((w) => w.endsWith('/decision'))).toHaveLength(1);
  });

  test('a failed read shows Try again that reads again', async ({ page }) => {
    let fail = true;
    await page.route('**/api/v1/documents/D-2901/versions/2', (route) => (fail ? route.fulfill({ status: 503, contentType: 'application/json', body: '{"code":"server_error","message":"Down."}' }) : route.continue()));
    await page.goto(PAGE);
    const retry = page.getByRole('button', { name: 'Try again' });
    await expect(retry).toBeVisible();
    fail = false;
    await retry.click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Statement of work · v2');
  });
});

test.describe('the Documents tab', () => {
  test.use({ viewport: DESKTOP });

  test('lists the documents; only a row with a work item opens its review', async ({ page }) => {
    await page.goto('/projects/P-0101/documents');
    const rows = page.getByRole('table', { name: 'Documents' }).getByRole('row');
    await expect(rows).toHaveCount(7);
    await expect(rows.nth(1)).toContainText('Statement of work');
    await expect(rows.nth(1)).toContainText('TEST TEMPLATE');
    await expect(rows.nth(2).getByRole('link')).toHaveCount(0);
    await rows.nth(1).getByRole('link', { name: 'Statement of work' }).click();
    await expect(page).toHaveURL(/\/projects\/P-0101\/documents\/D-2901\?v=2$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Statement of work · v2');
  });
});

test.describe('phone 390', () => {
  test.use({ viewport: PHONE });

  test('the default board: back link, one amounts tag, the flag line, Approve and Return in the bar, Return opens the drawer', async ({ page }) => {
    const sent = record(page);
    await open(page);
    await expect(page.getByRole('link', { name: /Lagoon Health/ }).first()).toBeVisible();
    await expect(page.locator('.docrev__phonetags')).toContainText('MATCHES COST-0140 V2');
    await expect(page.locator('.docrev__flag')).toHaveText('Tola flagged section 4: the minutes say "week 3". Check which is right.');
    const approve = page.getByRole('button', { name: 'Approve', exact: true });
    const ret = page.getByRole('button', { name: 'Return', exact: true });
    await expect(approve).toBeEnabled();
    for (const button of [approve, ret]) {
      const box = (await button.boundingBox())!;
      expect(box.height).toBeGreaterThanOrEqual(44);
      expect(box.width).toBeGreaterThanOrEqual(44);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expectNoAxeViolations(page);
    await ret.click();
    const drawer = page.getByRole('dialog');
    await expect(drawer.getByLabel('Note for the PM (needed to return)')).toBeVisible();
    await drawer.getByRole('button', { name: 'Return with note' }).click();
    await expect(drawer.getByText('Add a note to return it.')).toBeVisible();
    expect(sent.writes().filter((w) => w.endsWith('/decision'))).toEqual([]);
    await drawer.getByLabel('Note for the PM (needed to return)').fill('Fix section 4');
    await drawer.getByRole('button', { name: 'Return with note' }).click();
    await expect(page.locator('.docrev__returnedhead')).toBeVisible();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(sent.bodies.at(-1)).toEqual({ expected_revision: 2, verdict: 'return', note: 'Fix section 4' });
  });

  test('the returned board has no scroll sideways and passes axe; cannot-act has no bar', async ({ page, context }) => {
    await setCookies(context, { psl_mock_document: 'returned' });
    await open(page);
    await expect(page.locator('.docrev__returnedhead')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expectNoAxeViolations(page);
    await setCookies(context, { psl_mock_document: 'cannot-act' });
    await open(page);
    await expect(page.getByText('You prepared Statement of work v2, so someone else must review it.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
    await expectNoAxeViolations(page);
  });
});
