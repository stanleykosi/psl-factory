import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-92: starting a line from the drawer when its form is built from the served request_schema: issues (JSON) and minutes (multipart
// with the notes file), against the mock, at 1440 and 390.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

const dialog = (page: Page) => page.getByRole('dialog');
const chooserButton = (page: Page, phone: boolean) =>
  phone ? page.locator('.shell-phone').getByRole('button', { name: 'Start work' }) : page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).first();

async function openMyWork(page: Page, context: BrowserContext, cookies: Record<string, string> = {}) {
  await page.request.post(`${MOCK}/__mock/reset`);
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries({ psl_mock_persona: 'pm', ...cookies }).map(([name, value]) => ({ name, value, url })));
  await page.goto('/my-work');
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible();
}

async function openLine(page: Page, phone: boolean, line: RegExp, heading: string) {
  await chooserButton(page, phone).click();
  await dialog(page).getByRole('radio', { name: line }).check();
  await dialog(page).getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByRole('dialog', { name: heading })).toBeVisible();
}

async function choose(page: Page, name: string, option: string) {
  await dialog(page).getByRole('combobox', { name }).click();
  await page.getByRole('option', { name: option }).click();
}

const log = async (page: Page) =>
  (await (await page.request.get(`${MOCK}/__mock/start-live-log`)).json()) as {
    requests: { body?: Record<string, unknown>; minutes?: { parts: string[]; file: string | null; fields: Record<string, string> }; status: number }[];
    started: unknown[];
  };

for (const [label, viewport, phone] of [
  ['desktop 1440', DESKTOP, false],
  ['phone 390', PHONE, true],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('the chooser offers the five engine lines and marks the leadership report as not available here', async ({ page, context }) => {
      await openMyWork(page, context);
      await chooserButton(page, phone).click();
      for (const title of ['Chase an open issue', 'Escalate an issue', 'Record an emergency', 'Start a change', 'Minutes after a meeting']) {
        await expect(dialog(page).getByRole('radio', { name: new RegExp(title) })).toBeVisible();
      }
      await expect(dialog(page).getByText('Leadership report')).toBeVisible();
      await expect(dialog(page).getByRole('link', { name: 'Open in the full form' }).last()).toHaveAttribute('href', '/lines/pmo-leadership-report/');
    });

    test('Start with nothing chosen makes no request and names each missing control', async ({ page, context }) => {
      await openMyWork(page, context);
      await openLine(page, phone, /Minutes after a meeting/, 'Minutes after a meeting');
      await dialog(page).getByRole('button', { name: 'Start minutes' }).click();
      await expect(dialog(page).getByRole('alert')).toContainText('5 things to fix');
      for (const text of ['Project is required.', 'Template is required.', 'Audience is required.', 'Notes file is required.', 'Reference is required.']) {
        await expect(dialog(page).getByText(text).first()).toBeVisible();
      }
      const seen = await log(page);
      expect(seen.requests).toHaveLength(0);
    });

    test('issues: a project and an issue start the line and open the work item', async ({ page, context }) => {
      await openMyWork(page, context);
      await openLine(page, phone, /Chase an open issue/, 'Chase an open issue');
      await expect(dialog(page).getByLabel('Reference')).toHaveCount(0);
      await choose(page, 'Project', 'Project 01');
      await choose(page, 'Issue', 'ISS- 12');
      const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
      await dialog(page).getByRole('button', { name: 'Start chase' }).click();
      await expect(page).toHaveURL(/\/work\/4102$/);
      const [sent] = (await log(page)).requests;
      expect(Object.keys(sent.body!).sort()).toEqual(['case_id', 'case_revision', 'idempotency_key', 'intake', 'line']);
      expect(sent.body!.intake).toEqual({ issue_id: 12 });
    });

    test('minutes: the notes file goes as multipart to the minutes route, and a 503 is checked again with the same file and key', async ({ page, context }) => {
      await openMyWork(page, context, { psl_mock_scenario: 'start_uncertain' });
      const filesCalls: string[] = [];
      page.on('request', (request) => {
        if (/\/files$/.test(request.url())) filesCalls.push(request.url());
      });
      await openLine(page, phone, /Minutes after a meeting/, 'Minutes after a meeting');
      await choose(page, 'Project', 'Project 01');
      await choose(page, 'Template', 'Minutes, internal and client');
      await dialog(page).getByRole('radio', { name: 'Internal' }).click();
      await dialog(page).locator('input[type="file"]').setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('notes of the meeting') });
      await dialog(page).getByLabel('Reference').fill('Minutes of 17 November');
      await dialog(page).getByRole('button', { name: 'Start minutes' }).click();
      await expect(dialog(page).getByText('Not confirmed. Check before trying again.')).toBeVisible();
      await dialog(page).getByRole('button', { name: 'Check again' }).click();
      await expect(page).toHaveURL(/\/work\/4102$/);
      const seen = await log(page);
      expect(seen.requests).toHaveLength(2);
      const [first, second] = seen.requests;
      expect(first.minutes!.parts.sort()).toEqual(['audience', 'case_revision', 'idempotency_key', 'notes_file', 'reference', 'template_id']);
      expect(first.minutes!.file).toBe('notes.txt');
      expect(second.minutes!.file).toBe('notes.txt');
      expect(second.minutes!.fields.idempotency_key).toBe(first.minutes!.fields.idempotency_key);
      expect(seen.started).toHaveLength(1);
      expect(filesCalls).toEqual([]);
    });
  });
}
