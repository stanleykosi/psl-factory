// F-47 (FE-M2A-PROOF): the Proof box in the Start work drawer in a browser, against the contract mock.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page, state: string) {
  // A button that just changed state fades its fill over 120ms; axe must read the settled colours, not a frame of the fade.
  await page.waitForFunction(() => document.getAnimations().every((a) => !(a instanceof CSSTransition)));
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`), state).toEqual([]);
}

const dialog = (page: Page) => page.getByRole('dialog');
const proof = (page: Page) => dialog(page).getByRole('group', { name: 'Proof' });

/** Every upload and start the page sends, with its JSON body. */
function recordWrites(page: Page) {
  const writes: { kind: 'upload' | 'start'; url: string; body: Record<string, unknown> & { intake?: Record<string, unknown> } }[] = [];
  page.on('request', (request: Request) => {
    if (request.method() !== 'POST') return;
    const url = new URL(request.url());
    if (/\/api\/v1\/cases\/[^/]+\/evidence$/.test(url.pathname)) writes.push({ kind: 'upload', url: url.pathname, body: request.postDataJSON() });
    if (url.pathname === '/api/v1/work') writes.push({ kind: 'start', url: url.pathname, body: request.postDataJSON() });
  });
  return { uploads: () => writes.filter((w) => w.kind === 'upload'), starts: () => writes.filter((w) => w.kind === 'start') };
}

async function openMyWork(page: Page, context: BrowserContext, persona: string, extra: Record<string, string> = {}) {
  await page.request.post(`${MOCK}/__mock/reset`);
  await setCookies(context, { psl_mock_persona: persona, ...extra });
  await page.goto('/my-work');
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible();
}

function chooserButton(page: Page, phone: boolean) {
  return phone ? page.locator('.shell-phone').getByRole('button', { name: 'Start work' }) : page.locator('nav.psl-nav').getByRole('button', { name: 'More ways to start' });
}

async function openLine(page: Page, phone: boolean, title: string) {
  await chooserButton(page, phone).click();
  await dialog(page).getByRole('radio', { name: new RegExp(`^${title}`) }).check();
  await dialog(page).getByRole('button', { name: 'Next' }).click();
  await expect(dialog(page).getByRole('button', { name: 'change line' })).toBeVisible();
}

async function pick(page: Page, label: string, option: string) {
  await dialog(page).getByRole('combobox', { name: label }).click();
  await dialog(page).getByRole('option', { name: new RegExp(`^${option}`) }).first().click();
}

async function choose(page: Page, name: string, size: number) {
  await dialog(page).locator('[data-field="proof"] input[type="file"]').setInputFiles({ name, mimeType: 'application/octet-stream', buffer: Buffer.alloc(size, 7) });
}

/** The board's drawers, filled as in the spec's Boards table. */
const DRAWERS = [
  {
    title: 'Formal minutes and action handoff',
    persona: 'pm',
    file: ['weekly-sync-notes-17nov.docx', 38912, '38 KB'],
    start: 'Start minutes',
    work: 'W-1403',
    fill: async (page: Page) => {
      await pick(page, 'Project', 'Lagoon Health');
      await pick(page, 'Meeting', 'Weekly sync');
      await dialog(page).getByRole('radio', { name: 'Client' }).click();
    },
  },
  {
    title: 'Controlled change and signed closure',
    persona: 'pm',
    file: ['client-request-17nov.pdf', 20480, '20 KB'],
    start: 'Log change',
    work: 'W-1405',
    fill: async (page: Page) => {
      await pick(page, 'Project', 'Lagoon Health');
      await dialog(page).getByLabel('What the client asked for').fill('Add WhatsApp reminders as well as SMS');
    },
  },
  {
    title: 'Income detail or schedule inventory',
    persona: 'finance_lead',
    file: ['income_detail_oct.xlsx', 53248, '52 KB'],
    start: 'Start schedule',
    work: 'W-4401',
    fill: async (page: Page) => {
      await dialog(page).getByRole('radio', { name: 'Income detail' }).click();
      await dialog(page).getByLabel('Reference').fill('SCH-INC-2026-10');
      await pick(page, 'Mapping note', 'Mapping run MR-0044');
    },
  },
  {
    title: 'Record a ledger source',
    persona: 'finance_lead',
    file: ['qb_export_je7741.pdf', 45056, '44 KB'],
    start: 'Record source',
    work: 'W-4201',
    fill: async (page: Page) => {
      await dialog(page).getByLabel('Key').fill('QB-JE-7741');
    },
  },
] as const;

async function atLeast44(page: Page, locator: ReturnType<Page['locator']>, what: string) {
  const box = (await locator.boundingBox())!;
  expect(box.width, `${what} width`).toBeGreaterThanOrEqual(44);
  expect(box.height, `${what} height`).toBeGreaterThanOrEqual(44);
}

for (const [label, viewport, phone] of [
  ['desktop 1440', DESKTOP, false],
  ['phone 390', PHONE, true],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    for (const drawer of DRAWERS) {
      test(`${drawer.title}: upload, "Uploaded · ${drawer.file[2]}", one start, lands on ${drawer.work}`, async ({ page, context }) => {
        await openMyWork(page, context, drawer.persona);
        const log = recordWrites(page);
        await openLine(page, phone, drawer.title);
        await drawer.fill(page);
        const pickFile = proof(page).locator('label.psl-drop');
        await expect(dialog(page).locator('input[type="file"]')).toBeEnabled();
        await expect(dialog(page).locator('input[type="file"]')).not.toHaveAttribute('accept');
        if (phone) await atLeast44(page, pickFile, 'Drop zone');
        await expectNoAxeViolations(page, 'empty');
        await choose(page, drawer.file[0], drawer.file[1]);
        await expect(proof(page).getByText(`Uploaded · ${drawer.file[2]}`)).toBeVisible();
        expect(log.uploads()).toHaveLength(1);
        expect(Object.keys(log.uploads()[0].body).sort()).toEqual(['case_revision', 'content_base64', 'filename', 'kind']);
        const remove = proof(page).getByRole('button', { name: `Remove ${drawer.file[0]}` });
        if (phone) {
          await atLeast44(page, remove, '×');
          await atLeast44(page, dialog(page).getByRole('button', { name: drawer.start }), 'Start');
          for (const control of await dialog(page).locator('.psl-seg__opt, .sw-picker > .psl-select').all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
          // the card fits: no sideways scroll in the sheet
          const body = dialog(page).locator('.psl-sheet__body');
          expect(await body.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
        }
        await expectNoAxeViolations(page, 'uploaded');
        const start = dialog(page).getByRole('button', { name: drawer.start });
        await start.dblclick();
        await page.waitForURL(`**/work/${drawer.work}`);
        expect(log.starts()).toHaveLength(1);
        const sent = log.starts()[0].body;
        const uploadedReply = sent.intake!.proof as string;
        expect(uploadedReply).toMatch(/^EV-SW-/);
        expect(sent.case_revision).toBe((log.uploads()[0].body.case_revision as number) + 1);
      });
    }

    test('ledger states: uploading, failed, the start 422 under Proof, Check again; axe clean and announced', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead', { psl_mock_start_work: 'start_uncertain' });
      const log = recordWrites(page);
      await openLine(page, phone, 'Record a ledger source');
      await dialog(page).getByLabel('Key').fill('QB-JE-7741');
      // uploading: the answer is held back
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
      await choose(page, 'qb_export_je7741.pdf', 45056);
      await expect(proof(page).getByText(/Uploading…/)).toBeVisible();
      await expect(dialog(page).getByRole('button', { name: 'Record source' })).toBeDisabled();
      await expectNoAxeViolations(page, 'uploading');
      release();
      mode = 'fail';
      await expect(proof(page).getByText('Couldn’t upload. Try again.')).toBeVisible();
      // UX-1-1: the failure is announced with its words
      await expect(dialog(page).getByRole('alert').filter({ hasText: 'Not uploaded' })).toHaveText('qb_export_je7741.pdf: Not uploaded. Couldn’t upload. Try again.');
      await expect(dialog(page).getByRole('button', { name: 'Record source' })).toBeDisabled();
      if (phone) await atLeast44(page, proof(page).getByRole('button', { name: 'Try again' }), 'Try again');
      await expectNoAxeViolations(page, 'failed');
      mode = 'pass';
      await proof(page).getByRole('button', { name: 'Try again' }).click();
      await expect(proof(page).getByText('Uploaded · 44 KB')).toBeVisible();
      // the start 422 under Proof
      await page.route('**/api/v1/work', (route) =>
        route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ code: 'invalid', message: 'Check the fields.', fields: [{ name: 'proof', message: "That proof isn't on this record. Add it again." }] }) }),
      );
      await dialog(page).getByRole('button', { name: 'Record source' }).click();
      await expect(dialog(page).locator('[data-field="proof"] .psl-error')).toHaveText("That proof isn't on this record. Add it again.");
      await expectNoAxeViolations(page, '422 under Proof');
      await page.unroute('**/api/v1/work');
      // Check again (start_uncertain): a change re-enables the start
      await proof(page).getByRole('button', { name: 'Remove qb_export_je7741.pdf' }).click();
      await choose(page, 'qb_export_je7741.pdf', 45056);
      await expect(proof(page).getByText('Uploaded · 44 KB')).toBeVisible();
      await dialog(page).getByRole('button', { name: 'Record source' }).click();
      await expect(dialog(page).getByRole('button', { name: 'Check again' })).toBeVisible();
      await expect(dialog(page).getByText('If it started, it will appear in My work.')).toBeVisible();
      await expectNoAxeViolations(page, 'Check again');
      await dialog(page).getByRole('button', { name: 'Check again' }).click();
      await page.waitForURL('**/work/W-4201');
      const [uncertain, again] = log.starts().slice(-2);
      expect(again.body).toEqual(uncertain.body);
    });

    test('upload_uncertain: "Not uploaded", Try again gets a second id, the start sends only it', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead', { psl_mock_start_work: 'upload_uncertain' });
      const log = recordWrites(page);
      await openLine(page, phone, 'Record a ledger source');
      await dialog(page).getByLabel('Key').fill('QB-JE-7741');
      await choose(page, 'qb_export_je7741.pdf', 45056);
      await expect(proof(page).getByText('Couldn’t upload. Try again.')).toBeVisible();
      await expect(proof(page).getByText(/^Uploaded/)).toHaveCount(0);
      await proof(page).getByRole('button', { name: 'Try again' }).click();
      await expect(proof(page).getByText('Uploaded · 44 KB')).toBeVisible();
      await dialog(page).getByRole('button', { name: 'Record source' }).click();
      await page.waitForURL('**/work/W-4201');
      expect(log.uploads().map((u) => u.body.case_revision)).toEqual([2, 3]);
      expect([log.starts()[0].body.case_revision, log.starts()[0].body.intake!.proof]).toEqual([4, 'EV-SW-C-FIN-LEDGER-2']);
    });

    test('minutes: changing the project drops the proof and says so; Escape closes and returns focus', async ({ page, context }) => {
      await openMyWork(page, context, 'pm');
      await openLine(page, phone, 'Formal minutes and action handoff');
      await expect(proof(page).getByText('Choose the project first.')).toBeVisible();
      await pick(page, 'Project', 'Lagoon Health');
      await choose(page, 'weekly-sync-notes-17nov.docx', 38912);
      await expect(proof(page).getByText('Uploaded · 38 KB')).toBeVisible();
      await pick(page, 'Project', 'Harmattan Bank');
      await expect(dialog(page).getByRole('status').filter({ hasText: 'Proof removed' })).toHaveText('Proof removed: it was added to the other project. Add it again.');
      await expect(dialog(page).getByText('weekly-sync-notes-17nov.docx')).toHaveCount(0);
      await expectNoAxeViolations(page, 'project changed');
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(chooserButton(page, phone)).toBeFocused();
    });
  });
}
