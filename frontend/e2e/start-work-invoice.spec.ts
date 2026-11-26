import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-94: starting the invoice line (pmo-finance/v1) from the drawer, in both modes, against the mock, at 1440 and 390.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

const dialog = (page: Page) => page.getByRole('dialog');
const chooserButton = (page: Page, phone: boolean) =>
  phone ? page.locator('.shell-phone').getByRole('button', { name: 'Start work' }) : page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).first();

async function openInvoice(page: Page, context: BrowserContext, phone: boolean) {
  await page.request.post(`${MOCK}/__mock/reset`);
  const url = test.info().project.use.baseURL!;
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url }]);
  await page.goto('/my-work');
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible();
  await chooserButton(page, phone).click();
  await dialog(page).getByRole('radio', { name: /Prepare an invoice/ }).check();
  await dialog(page).getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Prepare an invoice' })).toBeVisible();
}

async function choose(page: Page, name: string, option: string) {
  await dialog(page).getByRole('combobox', { name }).click();
  await page.getByRole('option', { name: option }).click();
}

const log = async (page: Page) =>
  (await (await page.request.get(`${MOCK}/__mock/start-live-log`)).json()) as { requests: { body?: Record<string, unknown>; status: number }[]; started: unknown[] };

for (const [label, viewport, phone] of [
  ['desktop 1440', DESKTOP, false],
  ['phone 390', PHONE, true],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('Start with nothing chosen makes no request and asks for the way in first', async ({ page, context }) => {
      await openInvoice(page, context, phone);
      await expect(dialog(page).getByText('Billing coverage')).toHaveCount(0);
      await dialog(page).getByRole('button', { name: 'Start invoice' }).click();
      await expect(dialog(page).getByText('Start from is required.').first()).toBeVisible();
      expect((await log(page)).requests).toHaveLength(0);
    });

    test('completion: coverage and handoff start the line', async ({ page, context }) => {
      await openInvoice(page, context, phone);
      await choose(page, 'Project', 'Project 01');
      await dialog(page).getByRole('radio', { name: 'A completed milestone' }).click();
      await choose(page, 'Billing coverage', 'COV-0002 · 3');
      await choose(page, 'Milestone handoff', 'Go-live accepted · #22');
      await expect(dialog(page).getByText('Billing preparation')).toHaveCount(0);
      await dialog(page).getByLabel('Reference').fill('INV for go-live');
      const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
      await dialog(page).getByRole('button', { name: 'Start invoice' }).click();
      await expect(page).toHaveURL(/\/work\/4102$/);
      const [sent] = (await log(page)).requests;
      expect(sent.body!.intake).toEqual({ mode: 'completion', coverage_id: 12, handoff_id: 22 });
      expect(sent.body!.reference).toBe('INV for go-live');
    });

    test('preparation: the preparation starts the line, the invoice and due date are optional and sent as null', async ({ page, context }) => {
      await openInvoice(page, context, phone);
      await choose(page, 'Project', 'Project 01');
      await dialog(page).getByRole('radio', { name: 'An existing preparation' }).click();
      await expect(dialog(page).getByText('Choose billing preparation first.')).toBeVisible();
      await choose(page, 'Billing preparation', 'fixed_contract · COV-0002 · #32');
      await dialog(page).getByLabel('Reference').fill('INV for preparation 32');
      await dialog(page).getByRole('button', { name: 'Start invoice' }).click();
      await expect(page).toHaveURL(/\/work\/4102$/);
      const [sent] = (await log(page)).requests;
      expect(sent.body!.intake).toEqual({ mode: 'preparation', preparation_id: 32, due_date: null, invoice_id: null });
    });
  });
}
