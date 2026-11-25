import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-86: Start work on the live shapes: the chooser (SCR-04-*-lines) and the weekly report (SCR-04-*-weekly), against the mock.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

const dialog = (page: Page) => page.getByRole('dialog');
const chooserButton = (page: Page, phone: boolean) =>
  phone ? page.locator('.shell-phone').getByRole('button', { name: 'Start work' }) : page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).first();

async function openMyWork(page: Page, context: BrowserContext, cookies: Record<string, string> = {}) {
  await page.request.post(`${MOCK}/__mock/reset`);
  await setCookies(context, { psl_mock_persona: 'pm', ...cookies });
  await page.goto('/my-work');
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible();
}

async function openWeekly(page: Page, phone: boolean) {
  await chooserButton(page, phone).click();
  await dialog(page).getByRole('radio', { name: /Weekly client report/ }).check();
  await dialog(page).getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Weekly client report' })).toBeVisible();
}

const posts = async (page: Page) => (await (await page.request.get(`${MOCK}/__mock/start-live-log`)).json()) as { requests: { body: Record<string, unknown>; status: number }[]; started: unknown[] };

async function pickWeek(page: Page) {
  const range = dialog(page).locator('[data-field="week"]');
  await range.getByLabel('From').fill('16 Nov 2026');
  await range.getByLabel('From').blur();
  await range.getByLabel('To').fill('22 Nov 2026');
  await range.getByLabel('To').blur();
}

async function fillForm(page: Page) {
  await dialog(page).getByRole('combobox', { name: 'Project' }).click();
  await page.getByRole('option', { name: 'Project 01' }).click();
  await pickWeek(page);
  await dialog(page).getByLabel('Reference').fill('Week 47');
}

for (const [label, viewport, phone] of [
  ['desktop 1440', DESKTOP, false],
  ['phone 390', PHONE, true],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('the chooser lists live lines with no group heading or "Next:", and unavailable lines link to the full form', async ({ page, context }) => {
      await openMyWork(page, context);
      await chooserButton(page, phone).click();
      await expect(page.getByRole('dialog', { name: 'Choose a line' })).toBeVisible();
      await expect(dialog(page).getByText('Weekly client report')).toBeVisible();
      await expect(dialog(page).getByText(/Next:/)).toHaveCount(0);
      await expect(dialog(page).getByText('Invoice')).toHaveCount(0);
      await expect(dialog(page).getByRole('radio')).toHaveCount(7);
      const links = dialog(page).getByRole('link', { name: 'Open in the full form' });
      await expect(links).toHaveCount(2);
      await expect(links.first()).toHaveAttribute('href', '/lines/finance-payroll/');
      await expect(dialog(page).getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
      await expectNoAxeViolations(page);
    });

    test('Start report with nothing filled makes no request and lists each missing field', async ({ page, context }) => {
      await openMyWork(page, context);
      await openWeekly(page, phone);
      await dialog(page).getByRole('button', { name: 'Start report' }).click();
      await expect(dialog(page).getByRole('alert')).toContainText('3 things to fix');
      for (const text of ['Project is required.', 'Week is required.', 'Reference is required.']) await expect(dialog(page).getByText(text).first()).toBeVisible();
      expect((await posts(page)).requests).toHaveLength(0);
      await expectNoAxeViolations(page);
    });

    test('a valid start sends the weekly body and lands on the work item', async ({ page, context }) => {
      await openMyWork(page, context);
      await openWeekly(page, phone);
      await fillForm(page);
      await dialog(page).getByRole('button', { name: 'Start report' }).click();
      await expect(page).toHaveURL(/\/work\/4102$/);
      const [sent] = (await posts(page)).requests;
      expect(Object.keys(sent.body).sort()).toEqual(['case_id', 'case_revision', 'idempotency_key', 'intake', 'line', 'reference']);
      expect(sent.body.line).toBe('pmo-weekly-report/v1');
      expect(sent.body.reference).toBe('Week 47');
    });

    test('after a 503, Check again resends the same body and starts one work item', async ({ page, context }) => {
      await openMyWork(page, context, { psl_mock_scenario: 'start_uncertain' });
      await openWeekly(page, phone);
      await fillForm(page);
      await dialog(page).getByRole('button', { name: 'Start report' }).click();
      await expect(dialog(page).getByText('Not confirmed. Check before trying again.')).toBeVisible();
      await dialog(page).getByRole('button', { name: 'Check again' }).click();
      await expect(page).toHaveURL(/\/work\/4102$/);
      const log = await posts(page);
      expect(log.requests).toHaveLength(2);
      expect(log.requests[1].body).toEqual(log.requests[0].body);
      expect(log.started).toHaveLength(1);
    });

    test('a 404 says the record is unavailable and keeps the form', async ({ page, context }) => {
      await openMyWork(page, context, { psl_mock_scenario: 'start_missing' });
      await openWeekly(page, phone);
      await fillForm(page);
      await dialog(page).getByRole('button', { name: 'Start report' }).click();
      await expect(dialog(page).getByText('This record is unavailable.')).toBeVisible();
      await expect(dialog(page).getByLabel('Reference')).toHaveValue('Week 47');
    });
  });
}
