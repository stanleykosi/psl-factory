// F-51 (FE-M2A-PROOF part 2): the fixed asset schedule's Proof box and the cash forecast in the Start work drawer, in a
// browser, against the contract mock.
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

async function atLeast44(locator: ReturnType<Page['locator']>, what: string) {
  const box = (await locator.boundingBox())!;
  expect(box.width, `${what} width`).toBeGreaterThanOrEqual(44);
  expect(box.height, `${what} height`).toBeGreaterThanOrEqual(44);
}

const ASSETS = 'Fixed asset schedule';
const FORECAST = 'Cash forecast';

async function fillAssets(page: Page) {
  await pick(page, 'Prior schedule', 'PPE-0005');
}

async function fillForecast(page: Page, months = '6') {
  await pick(page, 'Scenario', 'Base case · v4');
  const asOf = dialog(page).getByLabel('As of');
  await asOf.fill('31 Oct 2026');
  await asOf.blur();
  await dialog(page).getByLabel('Months').fill(months);
  await dialog(page).getByRole('radio', { name: 'Internal' }).click();
}

async function noSideways(page: Page) {
  const body = dialog(page).locator('.psl-sheet__body');
  expect(await body.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
}

for (const [label, viewport, phone] of [
  ['desktop 1440', DESKTOP, false],
  ['phone 390', PHONE, true],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('fixed assets: upload to C-FIN-PPE, "Uploaded · 96 KB", one start, lands on W-3901', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead');
      const log = recordWrites(page);
      await openLine(page, phone, ASSETS);
      await expect(dialog(page).locator('[data-field]')).toHaveCount(3);
      await expect(dialog(page).locator('input[type="file"]')).not.toHaveAttribute('accept');
      const pickFile = proof(page).getByRole('button', { name: 'Choose a file' });
      if (phone) await atLeast44(pickFile, 'Choose a file');
      await expectNoAxeViolations(page, 'assets empty');
      await fillAssets(page);
      await choose(page, 'ppe_register_oct.xlsx', 98304);
      await expect(proof(page).getByText('Uploaded · 96 KB')).toBeVisible();
      expect(log.uploads()).toHaveLength(1);
      expect(log.uploads()[0].url).toBe('/api/v1/cases/C-FIN-PPE/evidence');
      expect(log.uploads()[0].body).toMatchObject({ kind: 'ppe_register', filename: 'ppe_register_oct.xlsx', case_revision: 4 });
      if (phone) {
        await atLeast44(proof(page).getByRole('button', { name: 'Remove ppe_register_oct.xlsx' }), '×');
        await atLeast44(dialog(page).getByRole('button', { name: 'Start schedule' }), 'Start');
        for (const control of await dialog(page).locator('.psl-seg__opt, .sw-picker > .psl-select').all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
        await noSideways(page);
      }
      await expectNoAxeViolations(page, 'assets uploaded');
      await dialog(page).getByRole('button', { name: 'Start schedule' }).dblclick();
      await page.waitForURL('**/work/W-3901');
      expect(log.starts()).toHaveLength(1);
      expect(log.starts()[0].body).toMatchObject({ line: 'fixed_assets', case_id: 'C-FIN-PPE', case_revision: 5, intake: { proof: 'EV-SW-C-FIN-PPE-1', prior_schedule: 'PPE-0005' } });
    });

    test('forecast: no Proof box, the typed values only, one start, lands on W-4001', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead');
      const log = recordWrites(page);
      await openLine(page, phone, FORECAST);
      await expect(dialog(page).locator('input[type="file"]')).toHaveCount(0);
      await expect(dialog(page).getByText('Choose a file')).toHaveCount(0);
      await expect(dialog(page).getByText('All 3 accepted')).toBeVisible();
      await expect(dialog(page).getByRole('radio', { checked: true })).toHaveCount(0);
      await expectNoAxeViolations(page, 'forecast empty');
      await fillForecast(page);
      if (phone) {
        await atLeast44(dialog(page).getByRole('button', { name: 'Start forecast' }), 'Start');
        for (const control of await dialog(page).locator('.psl-seg__opt, .sw-picker > .psl-select').all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
        await noSideways(page);
      }
      await dialog(page).getByRole('button', { name: 'Start forecast' }).dblclick();
      await page.waitForURL('**/work/W-4001');
      expect(log.uploads()).toHaveLength(0);
      expect(log.starts()).toHaveLength(1);
      expect(log.starts()[0].body).toMatchObject({ line: 'cash_forecast', case_id: 'C-FIN-FORECAST', case_revision: 2, intake: { scenario: 'FC-SC-4', as_of: '2026-10-31', months: 6, audience: 'internal' } });
      expect(Object.keys(log.starts()[0].body.intake!).sort()).toEqual(['as_of', 'audience', 'months', 'scenario']);
    });

    test('forecast 422 under Months keeps the typed values; axe clean', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead');
      await openLine(page, phone, FORECAST);
      await fillForecast(page, '13');
      await dialog(page).getByRole('button', { name: 'Start forecast' }).click();
      await expect(dialog(page).locator('[data-field="months"] .psl-error')).toHaveText('Months must be between 1 and 12.');
      await expect(dialog(page).getByLabel('Months')).toHaveValue('13');
      await expect(dialog(page).getByRole('radio', { name: 'Internal' })).toBeChecked();
      await expectNoAxeViolations(page, 'forecast 422 Months');
    });

    test('forecast Check again (start_uncertain): same body, one start recorded, axe clean', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead', { psl_mock_start_work: 'start_uncertain' });
      const log = recordWrites(page);
      await openLine(page, phone, FORECAST);
      await fillForecast(page);
      await dialog(page).getByRole('button', { name: 'Start forecast' }).click();
      await expect(dialog(page).getByRole('button', { name: 'Check again' })).toBeVisible();
      await expect(dialog(page).getByText('If it started, it will appear in My work.')).toBeVisible();
      await expectNoAxeViolations(page, 'forecast Check again');
      await dialog(page).getByRole('button', { name: 'Check again' }).click();
      await page.waitForURL('**/work/W-4001');
      const [first, again] = log.starts();
      expect(again.body).toEqual(first.body);
    });

    test('start_hold: a forecast start lands on W-4006, which says SETUP NEEDED with no Decide panel', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead', { psl_mock_start_work: 'start_hold' });
      await openLine(page, phone, FORECAST);
      await fillForecast(page);
      await dialog(page).getByRole('button', { name: 'Start forecast' }).click();
      await page.waitForURL('**/work/W-4006');
      await expect(page.getByText('SETUP NEEDED').first()).toBeVisible();
      await expect(page.getByRole('button', { name: /^Decide/ })).toHaveCount(0);
      await expect(page.getByText(/prepared by/i)).toHaveCount(0);
    });

    test('assets states: uploading, failed, the 422 under Proof, Check again; axe clean', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead', { psl_mock_start_work: 'start_uncertain' });
      const log = recordWrites(page);
      await openLine(page, phone, ASSETS);
      let release!: () => void;
      const held = new Promise<void>((r) => (release = r));
      let mode: 'hold' | 'fail' | 'pass' = 'hold';
      await page.route('**/api/v1/cases/*/evidence', async (route) => {
        if (mode === 'hold') await held;
        if (mode !== 'pass') return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ code: 'server', message: 'Down.' }) });
        return route.continue();
      });
      await choose(page, 'ppe_register_oct.xlsx', 98304);
      await expect(proof(page).getByText(/Uploading…/)).toBeVisible();
      await expect(dialog(page).getByRole('button', { name: 'Start schedule' })).toBeDisabled();
      await expectNoAxeViolations(page, 'assets uploading');
      release();
      mode = 'fail';
      await expect(proof(page).getByText('Couldn’t upload. Try again.')).toBeVisible();
      await expect(dialog(page).getByRole('button', { name: 'Start schedule' })).toBeDisabled();
      if (phone) await atLeast44(proof(page).getByRole('button', { name: 'Try again' }), 'Try again');
      await expectNoAxeViolations(page, 'assets failed');
      mode = 'pass';
      await proof(page).getByRole('button', { name: 'Try again' }).click();
      await expect(proof(page).getByText('Uploaded · 96 KB')).toBeVisible();
      await page.route('**/api/v1/work', (route) =>
        route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ code: 'invalid', message: 'Check the fields.', fields: [{ name: 'proof', message: "That proof isn't on this record. Add it again." }] }) }),
      );
      await dialog(page).getByRole('button', { name: 'Start schedule' }).click();
      await expect(dialog(page).locator('[data-field="proof"] .psl-error')).toHaveText("That proof isn't on this record. Add it again.");
      await expectNoAxeViolations(page, 'assets 422 under Proof');
      await page.unroute('**/api/v1/work');
      await proof(page).getByRole('button', { name: 'Remove ppe_register_oct.xlsx' }).click();
      await choose(page, 'ppe_register_oct.xlsx', 98304);
      await expect(proof(page).getByText('Uploaded · 96 KB')).toBeVisible();
      await dialog(page).getByRole('button', { name: 'Start schedule' }).click();
      await expect(dialog(page).getByRole('button', { name: 'Check again' })).toBeVisible();
      await expectNoAxeViolations(page, 'assets Check again');
      await dialog(page).getByRole('button', { name: 'Check again' }).click();
      await page.waitForURL('**/work/W-3901');
      const [uncertain, again] = log.starts().slice(-2);
      expect(again.body).toEqual(uncertain.body);
    });

    test('Escape closes each drawer and returns focus', async ({ page, context }) => {
      await openMyWork(page, context, 'finance_lead');
      for (const title of [ASSETS, FORECAST]) {
        await openLine(page, phone, title);
        await page.keyboard.press('Escape');
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(chooserButton(page, phone)).toBeFocused();
      }
    });
  });
}
