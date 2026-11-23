// F-49 (FE-RFP-INTAKE part 2): "Log a received RFP" in a browser against the contract mock, at 1440 and 390: the
// board's values, one upload and one start, the landing and the Unassigned row, 44px targets on a phone, axe WCAG 2.2 AA.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';
import { fillWhen } from './controls';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const TITLE = 'Log a received RFP';

test.use({ timezoneId: 'Africa/Lagos', reducedMotion: 'reduce' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page, state: string) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`), state).toEqual([]);
}

const dialog = (page: Page) => page.getByRole('dialog');
const documentBox = (page: Page) => dialog(page).getByRole('group', { name: 'The RFP document' });

/** Every upload and start the page sends, with its JSON body. */
function recordWrites(page: Page) {
  const writes: { kind: 'upload' | 'start'; body: Record<string, unknown> & { intake?: Record<string, unknown> } }[] = [];
  page.on('request', (request: Request) => {
    if (request.method() !== 'POST') return;
    const url = new URL(request.url());
    if (/\/api\/v1\/cases\/[^/]+\/evidence$/.test(url.pathname)) writes.push({ kind: 'upload', body: request.postDataJSON() });
    if (url.pathname === '/api/v1/work') writes.push({ kind: 'start', body: request.postDataJSON() });
  });
  return { uploads: () => writes.filter((w) => w.kind === 'upload'), starts: () => writes.filter((w) => w.kind === 'start') };
}

async function openMyWork(page: Page, context: BrowserContext, extra: Record<string, string> = {}) {
  await page.request.post(`${MOCK}/__mock/reset`);
  await setCookies(context, { psl_mock_persona: 'pmo_lead', ...extra });
  await page.goto('/my-work');
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible();
}

function chooserButton(page: Page, phone: boolean) {
  return phone ? page.locator('.shell-phone').getByRole('button', { name: 'Start work' }) : page.locator('nav.psl-nav').getByRole('button', { name: 'More ways to start' });
}

async function openLine(page: Page, phone: boolean) {
  await chooserButton(page, phone).click();
  await dialog(page).getByRole('radio', { name: new RegExp(`^${TITLE}`) }).check();
  await dialog(page).getByRole('button', { name: 'Next' }).click();
  await expect(dialog(page).getByRole('button', { name: 'change line' })).toBeVisible();
}

async function pick(page: Page, label: string, option: string) {
  await dialog(page).getByRole('combobox', { name: label }).click();
  await dialog(page).getByRole('option', { name: new RegExp(`^${option}`) }).first().click();
}

const MB_2_4 = Math.round(2.4 * 1024 * 1024);
async function chooseFile(page: Page, name = 'Tamarind-Loans-RFP-loan-origination.pdf', size = MB_2_4) {
  await dialog(page).locator('[data-field="rfp_document"] input[type="file"]').setInputFiles({ name, mimeType: 'application/pdf', buffer: Buffer.alloc(size, 7) });
}

/** The board's values; "Stated" is the drawn deadline state. */
async function fillBoard(page: Page, file = true) {
  await pick(page, 'Client or prospect', 'Tamarind Loans Ltd');
  await dialog(page).getByLabel('RFP reference').fill('TL-RFP-2026-014');
  if (file) {
    await chooseFile(page);
    await expect(documentBox(page).getByText('Uploaded · 2.4 MB')).toBeVisible();
  }
  await fillWhen(dialog(page), 'Received', '2026-11-12T09:40');
  await dialog(page).getByRole('radiogroup', { name: 'How the client wants it submitted' }).getByRole('radio', { name: 'Email' }).click();
  await dialog(page).getByLabel('Submit to (optional)').fill('procurement@tamarindloans.example');
  await dialog(page).getByRole('radiogroup', { name: 'Submission deadline' }).getByRole('radio', { name: 'Stated', exact: true }).click();
  await fillWhen(dialog(page), 'Deadline (optional)', '2026-11-28T17:00');
  await dialog(page).getByLabel('Note (optional)').fill('Received from their procurement lead by email.');
}

/** Every button, input, segment and select in the dialog is at least 44 by 44 (D-92c). */
async function smallTargets(page: Page) {
  return dialog(page).evaluate((root) =>
    [...root.querySelectorAll<HTMLElement>('button, input:not([type="hidden"]):not([type="file"]), textarea, [role="combobox"], [role="radio"]')]
      .filter((el) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden')
      .map((el) => {
        const r = el.getBoundingClientRect();
        return { name: el.getAttribute('aria-label') ?? el.textContent?.trim().slice(0, 30) ?? el.tagName, w: Math.round(r.width), h: Math.round(r.height) };
      })
      // "change line" is a text link in the sheet head with its own 44px box on a phone; every control counts
      .filter((t) => t.w < 44 || t.h < 44),
  );
}

for (const [label, viewport, phone] of [
  ['desktop 1440', DESKTOP, false],
  ['phone 390', PHONE, true],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('the drawer: fields and words from data, empty axe clean, no sideways scroll, 44px targets on a phone', async ({ page, context }) => {
      await openMyWork(page, context);
      await openLine(page, phone);
      // The shared Drawer draws no eyebrow on a phone (the phone board has none); desktop draws it.
      await expect(dialog(page).getByText('START WORK · PRE-SALE')).toHaveCount(phone ? 0 : 1);
      await expect(dialog(page).getByText(TITLE).first()).toBeVisible();
      const order = await dialog(page).locator('[data-field]').evaluateAll((els) => els.map((el) => el.getAttribute('data-field')));
      expect(order).toEqual(['client', 'rfp_reference', 'rfp_document', 'received_at', 'submission_method', 'deadline_status', 'note']);
      await expect(dialog(page).getByRole('button', { name: 'Log RFP' })).toBeVisible();
      await expect(dialog(page).getByRole('button', { name: 'Cancel' })).toHaveCount(phone ? 0 : 1);
      await expect(dialog(page).locator('input[type="file"]')).not.toHaveAttribute('accept');
      if (phone) expect(await smallTargets(page)).toEqual([]);
      const body = dialog(page).locator(phone ? '.psl-sheet__body' : '.psl-drawer__body');
      expect(await body.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
      await expectNoAxeViolations(page, 'empty');
      await dialog(page).getByRole('radiogroup', { name: 'Submission deadline' }).getByRole('radio', { name: 'Stated', exact: true }).click();
      await expect(dialog(page).getByLabel('Deadline (optional)')).toBeVisible();
      await expectNoAxeViolations(page, 'stated');
    });

    test('the board’s values: one upload at revision 5, one start at 6 with the example body, lands on W-3351, one more Unassigned row', async ({ page, context }) => {
      await openMyWork(page, context);
      const countOf = async () => Number((await page.getByRole('tab', { name: /Unassigned/ }).textContent())!.replace(/\D/g, ''));
      await page.goto('/my-work?queue=unassigned');
      const before = await countOf();
      await page.goto('/my-work');
      const log = recordWrites(page);
      await openLine(page, phone);
      await fillBoard(page, false);
      await expect(documentBox(page).locator('input[type="file"]')).toBeEnabled();
      await chooseFile(page);
      await expect(documentBox(page).getByText('Uploaded · 2.4 MB')).toBeVisible();
      expect(log.uploads()).toHaveLength(1);
      expect(Object.keys(log.uploads()[0].body).sort()).toEqual(['case_revision', 'content_base64', 'filename', 'kind']);
      expect([log.uploads()[0].body.kind, log.uploads()[0].body.case_revision]).toEqual(['rfp_document', 5]);
      if (phone) {
        expect(await smallTargets(page)).toEqual([]);
        await expect(documentBox(page).getByRole('button', { name: /^Remove / })).toBeVisible();
        expect(await dialog(page).locator('.psl-sheet__body').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
      }
      await expectNoAxeViolations(page, 'uploaded');
      await dialog(page).getByRole('button', { name: 'Log RFP' }).dblclick();
      await page.waitForURL('**/work/W-3351');
      expect(log.starts()).toHaveLength(1);
      const sent = log.starts()[0].body;
      expect(sent).toMatchObject({ line: 'rfp_intake', case_id: 'C-RFP-INTAKE', case_revision: 6 });
      expect(sent.intake).toEqual({
        client: 'CL-3506',
        rfp_reference: 'TL-RFP-2026-014',
        rfp_document: 'EV-SW-C-RFP-INTAKE-1',
        // 09:40 and 17:00 in Lagos
        received_at: '2026-11-12T08:40:00.000Z',
        submission_method: 'email',
        submission_target: 'procurement@tamarindloans.example',
        deadline_status: 'stated',
        deadline_at: '2026-11-28T16:00:00.000Z',
        note: 'Received from their procurement lead by email.',
      });
      await page.goto('/my-work?queue=unassigned');
      expect(await countOf()).toBe(before + 1);
      await page.getByRole('link', { name: /Tamarind Loans Ltd · RFP TL-RFP-2026-014/ }).click();
      await expect(page).toHaveURL(/\?queue=unassigned&assign=W-3351$/);
      await expect(page.getByRole('dialog', { name: /Assign accountable PM|Set an owner/ })).toBeVisible();
      await page.request.post(`${MOCK}/__mock/reset`);
      await page.goto('/my-work?queue=unassigned');
      expect(await countOf()).toBe(before);
    });

    test('states: uploading, failed, the 422 under Received, Check again; axe clean', async ({ page, context }) => {
      await openMyWork(page, context, { psl_mock_start_work: 'start_uncertain' });
      const log = recordWrites(page);
      await openLine(page, phone);
      let release!: () => void;
      const held = new Promise<void>((r) => (release = r));
      let mode: 'hold' | 'fail' | 'pass' = 'hold';
      await page.route('**/api/v1/cases/*/evidence', async (route) => {
        if (mode === 'hold') {
          await held;
          return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ code: 'server', message: 'Down.' }) });
        }
        if (mode === 'fail') return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ code: 'server', message: 'Down.' }) });
        return route.continue();
      });
      await chooseFile(page);
      await expect(documentBox(page).getByText(/Uploading…/)).toBeVisible();
      await expect(dialog(page).getByRole('button', { name: 'Log RFP' })).toBeDisabled();
      await expectNoAxeViolations(page, 'uploading');
      release();
      mode = 'fail';
      await expect(documentBox(page).getByText('Couldn’t upload. Try again.')).toBeVisible();
      await expect(dialog(page).getByRole('button', { name: 'Log RFP' })).toBeDisabled();
      if (phone) expect(await smallTargets(page)).toEqual([]);
      await expectNoAxeViolations(page, 'failed');
      mode = 'pass';
      await documentBox(page).getByRole('button', { name: 'Try again' }).click();
      await expect(documentBox(page).getByText('Uploaded · 2.4 MB')).toBeVisible();
      await pick(page, 'Client or prospect', 'Tamarind Loans Ltd');
      await dialog(page).getByLabel('RFP reference').fill('TL-RFP-2026-014');
      await fillWhen(dialog(page), 'Received', '2026-12-31T09:40');
      await dialog(page).getByRole('radiogroup', { name: 'How the client wants it submitted' }).getByRole('radio', { name: 'By hand' }).click();
      await dialog(page).getByRole('radiogroup', { name: 'Submission deadline' }).getByRole('radio', { name: 'Unknown' }).click();
      await dialog(page).getByRole('button', { name: 'Log RFP' }).click();
      await expect(dialog(page).locator('[data-field="received_at"] .psl-error')).toHaveText("Received can't be in the future.");
      await expect(dialog(page).getByRole('button', { name: 'Log RFP' })).toBeDisabled();
      await expectNoAxeViolations(page, '422');
      await fillWhen(dialog(page), 'Received', '2026-11-12T09:40');
      await dialog(page).getByRole('button', { name: 'Log RFP' }).click();
      await expect(dialog(page).getByRole('button', { name: 'Check again' })).toBeVisible();
      await expect(dialog(page).getByText('If it started, it will appear in My work.')).toBeVisible();
      await expect(dialog(page)).not.toContainText(/logged/i);
      await expectNoAxeViolations(page, 'Check again');
      await dialog(page).getByRole('button', { name: 'Check again' }).click();
      await page.waitForURL('**/work/W-3351');
      const [uncertain, again] = log.starts().slice(-2);
      expect(again.body).toEqual(uncertain.body);
    });

    test('not open: a start answered 403 shows "You can’t start this here." with no client or reference; axe clean', async ({ page, context }) => {
      await openMyWork(page, context);
      await openLine(page, phone);
      await fillBoard(page);
      await page.route('**/api/v1/work', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'No.' }) }));
      await dialog(page).getByRole('button', { name: 'Log RFP' }).click();
      const refusal = dialog(page).getByText('You can’t start this here.');
      await expect(refusal).toBeVisible();
      await expect(dialog(page).locator('.psl-callout, [role="alert"]').filter({ hasText: 'You can’t start this here.' })).not.toContainText(/Tamarind|TL-RFP|\.pdf/);
      await expectNoAxeViolations(page, 'not open');
    });

    test('a new client under the overlay: "New client", a name, sent as {new: {name}}', async ({ page, context }) => {
      await openMyWork(page, context, { psl_mock_rfp: 'new_client' });
      const log = recordWrites(page);
      await openLine(page, phone);
      await dialog(page).getByRole('combobox', { name: 'Client or prospect' }).click();
      await dialog(page).getByRole('option', { name: 'New client' }).click();
      await dialog(page).getByLabel('Name of the new client').fill('Acme Foods');
      await dialog(page).getByLabel('RFP reference').fill('AC-2026-001');
      await chooseFile(page, 'acme.pdf', 4096);
      await expect(documentBox(page).getByText('Uploaded · 4 KB')).toBeVisible();
      await fillWhen(dialog(page), 'Received', '2026-11-12T09:40');
      await dialog(page).getByRole('radiogroup', { name: 'How the client wants it submitted' }).getByRole('radio', { name: 'By hand' }).click();
      await dialog(page).getByRole('radiogroup', { name: 'Submission deadline' }).getByRole('radio', { name: 'Not stated' }).click();
      await expectNoAxeViolations(page, 'new client');
      await dialog(page).getByRole('button', { name: 'Log RFP' }).click();
      await page.waitForURL('**/work/W-3351');
      expect(log.starts()[0].body.intake!.client).toEqual({ new: { name: 'Acme Foods' } });
    });
  });
}
