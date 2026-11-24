import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-72 document review (SCR-08) against the contract mock in the live document-review shape: read, return with a note,
// approve with a note, stale, no access, at 1440 and 390, axe WCAG 2.2 AA.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const PAGE = '/projects/P-0101/documents/2901';
const NOTE = 'Note for the PM';

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

/** The writes the page sends, with their bodies, in order. */
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

  test('the board: crumb, title, status, sections, audience, the note and the two buttons', async ({ page }) => {
    await open(page);
    await expect(page).toHaveTitle('Document · PSL Factory');
    await expect(page.locator('.psl-crumb')).toHaveText('Lagoon Health · patient app / Documents');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Statement of work · v2');
    await expect(page.getByText('Awaiting PMO Lead review')).toBeVisible();
    await expect(page.locator('.docrev__section h3')).toHaveText(['1. Scope', '2. Deliverables', '3. Milestones and stages', '4. Assumptions', '5. Out of scope']);
    await expect(page.getByRole('region', { name: 'Audience' }).getByText('Client · Lagoon Health')).toBeVisible();
    await expect(page.getByRole('heading', { level: 2, name: 'Your review' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Approve v2' })).toBeEnabled();
    await expect(page.getByRole('button', { name: 'Return with note' })).toBeVisible();
    await expect(page.getByLabel(NOTE)).toBeVisible();
    await expect(page.getByRole('tab', { name: /^Documents/ })).toHaveAttribute('aria-selected', 'true');
    for (const gone of ['TEST TEMPLATE', 'Checks', 'Compare', 'changed since']) await expect(page.getByText(gone)).toHaveCount(0);
    await expectNoAxeViolations(page);
  });

  test('return needs a note; with one it records once and the re-read shows the result', async ({ page }) => {
    const sent = record(page);
    await open(page);
    await page.getByRole('button', { name: 'Return with note' }).click();
    await expect(page.getByText('Add a note to record your decision.')).toBeVisible();
    expect(sent.writes()).toEqual([]);
    await page.getByLabel(NOTE).fill('Section 4: confirm week 2 or 3.');
    await page.getByRole('button', { name: 'Return with note' }).click();
    await expect(page.getByText('You returned v2.')).toBeVisible();
    await expect(page.getByText('No decision is open to you on this version.')).toBeVisible();
    await expect(page.getByText('Returned to PM')).toBeVisible();
    expect(sent.writes()).toEqual(['POST /api/v1/projects/P-0101/document-reviews/2901']);
    expect(sent.bodies).toEqual([{ expected_revision: 7, verdict: 'return', delegated: false, note: 'Section 4: confirm week 2 or 3.' }]);
    await expectNoAxeViolations(page);
  });

  test('approve with a note records once and says it was not sent to the client', async ({ page }) => {
    const sent = record(page);
    await open(page);
    await page.getByLabel(NOTE).fill('Figures match the costing.');
    await page.getByRole('button', { name: 'Approve v2' }).click();
    await expect(page.getByText('You approved v2')).toBeVisible();
    await expect(page.getByText('Not sent to the client.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
    expect(sent.bodies).toEqual([{ expected_revision: 7, verdict: 'approve', delegated: false, note: 'Figures match the costing.' }]);
  });

  test('a stale revision records nothing, keeps the note, loads the latest and the next press sends it', async ({ page, context }) => {
    await setCookies(context, { psl_mock_docreview: 'stale' });
    const sent = record(page);
    await open(page);
    await page.getByLabel(NOTE).fill('Keep this note.');
    await page.getByRole('button', { name: 'Approve v2' }).click();
    await expect(page.getByText(/This document changed while you were reading it, so nothing was recorded/)).toBeVisible();
    await expect(page.getByLabel(NOTE)).toHaveValue('Keep this note.');
    await page.getByRole('button', { name: 'Approve v2' }).click();
    await expect(page.getByText('You approved v2')).toBeVisible();
    expect(sent.bodies.map((b) => b.expected_revision)).toEqual([7, 8]);
  });

  test('a blocked document lists why and offers no decision', async ({ page, context }) => {
    await setCookies(context, { psl_mock_docreview: 'blocked' });
    await open(page);
    await expect(page.getByText('Not ready to decide yet')).toBeVisible();
    await expect(page.getByText('Section Fees is empty.')).toBeVisible();
    await expect(page.getByText('No decision is open to you on this version.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
  });

  test('section text is plain characters', async ({ page, context }) => {
    await setCookies(context, { psl_mock_docreview: 'hostile' });
    await open(page);
    await expect(page.getByText('Plain <script>alert(1)</script> text')).toBeVisible();
    await expect(page.getByText(/1\. Scope <b>bold<\/b>/)).toBeVisible();
  });

  test('the older version is not current and has no controls', async ({ page }) => {
    await open(page, '/projects/P-0101/documents/2900');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Statement of work · v1');
    await expect(page.getByText('Not the current version')).toBeVisible();
    await expect(page.getByText('Superseded by v2')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
  });

  test('no access: 403 and 404 look the same, an unreadable id sends nothing, and a persona without the project sees no text', async ({ page, context }) => {
    const shown: string[] = [];
    for (const path of ['/projects/P-0101/documents/2999', '/projects/P-0099/documents/2901']) {
      await page.goto(path);
      await expect(page.getByRole('heading', { level: 1, name: 'You can’t open this document' })).toBeVisible();
      shown.push((await page.locator('main').textContent()) ?? '');
    }
    expect(shown[0]).toBe(shown[1]);
    const sent = record(page);
    await page.goto('/projects/P-0101/documents/abc');
    await expect(page.getByRole('heading', { level: 1, name: 'You can’t open this document' })).toBeVisible();
    expect(sent.log.filter((l) => l.includes('document-reviews'))).toEqual([]);
    await setCookies(context, { psl_mock_persona: 'none' });
    await page.goto(PAGE);
    await expect(page.getByText('Statement of work')).toHaveCount(0);
  });

  test('a write that fails on the server is uncertain: buttons off, Try again only reads', async ({ page, context }) => {
    await setCookies(context, { psl_mock_docreview: 'server-error' });
    const sent = record(page);
    await open(page);
    await page.getByLabel(NOTE).fill('ok');
    await page.getByRole('button', { name: 'Approve v2' }).click();
    await expect(page.getByText('We couldn’t confirm whether your decision was recorded.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Approve v2' })).toBeDisabled();
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByRole('button', { name: 'Approve v2' })).toBeEnabled();
    expect(sent.writes()).toHaveLength(1);
  });
});

test.describe('phone 390', () => {
  test.use({ viewport: PHONE });

  test('the board: project back link with no reference, Return and Approve in the bar, each opening the note sheet', async ({ page }) => {
    const sent = record(page);
    await open(page);
    await expect(page.getByRole('link', { name: /^Back to Lagoon Health/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Approve', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Return', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expectNoAxeViolations(page);
    await page.getByRole('button', { name: 'Approve', exact: true }).click();
    const sheet = page.getByRole('dialog', { name: 'Approve with a note' });
    await expect(sheet).toBeVisible();
    await sheet.getByRole('button', { name: 'Approve v2' }).click();
    await expect(sheet.getByText('Add a note to record your decision.')).toBeVisible();
    expect(sent.writes()).toEqual([]);
    await sheet.getByLabel(NOTE).fill('Looks right.');
    await sheet.getByRole('button', { name: 'Approve v2' }).click();
    await expect(page.getByText('You approved v2')).toBeVisible();
    expect(sent.bodies).toEqual([{ expected_revision: 7, verdict: 'approve', delegated: false, note: 'Looks right.' }]);
  });

  test('a document with no decision open has no bar and passes axe', async ({ page, context }) => {
    await setCookies(context, { psl_mock_docreview: 'returned' });
    await open(page);
    await expect(page.getByText('No decision is open to you on this version.')).toBeVisible();
    await expect(page.locator('.docrev__bar')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expectNoAxeViolations(page);
  });
});
