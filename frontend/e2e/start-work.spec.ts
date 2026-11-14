import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

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

/** The fixture table: each line's chooser title, its drawer title on the board, its field labels in order and its
 *  primary button. The invoice sheet on the phone is titled "Invoice preparation" (SCR-04-mobile). */
const LINES: [string, string, string[], string][] = [
  ['Invoice preparation and delivery', 'Invoice preparation and delivery', ['Project', 'Completed milestone', 'Anything Chidi should know (optional)'], 'Start the invoice'],
  ['Reviewed weekly client report', 'Weekly client report', ['Project', 'Week', 'Template'], 'Start report'],
  ['Formal minutes and action handoff', 'Minutes after a meeting', ['Project', 'Meeting', 'Audience', 'Proof'], 'Start minutes'],
  ['Issue investigation and owner follow-up', 'Chase an open issue', ['Project', 'Issue'], 'Start follow-up'],
  ['Controlled change and signed closure', 'Scope or timeline change', ['Project', 'What the client asked for', 'Proof'], 'Log change'],
  ['Emergency change for an incident', 'Emergency change for an incident', ['Project', 'Incident', 'Plan'], 'Ask for preauthorisation'],
  ['Escalate and communicate', 'Escalate and communicate', ['Project', 'From issue', 'Escalate to'], 'Raise escalation'],
  ['Leadership report', 'Leadership report', ['Report', 'Period', 'Audience'], 'Start report'],
];
const titleOn = (title: string, phone: boolean) => (phone && title.startsWith('Invoice') ? 'Invoice preparation' : title);

const dialog = (page: Page) => page.getByRole('dialog');

async function openMyWork(page: Page, context: BrowserContext, persona: string) {
  await page.request.post(`${MOCK}/__mock/reset`);
  await setCookies(context, { psl_mock_persona: persona });
  await page.goto('/my-work');
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible();
}

/** The visible Start work control that opens the chooser: the chevron on desktop, "+ Start" on the phone. */
function chooserButton(page: Page, phone: boolean) {
  return phone
    ? page.locator('.shell-phone').getByRole('button', { name: 'Start work' })
    : page.locator('nav.psl-nav').getByRole('button', { name: 'More ways to start' });
}

async function openLine(page: Page, phone: boolean, line: string, title: string) {
  await chooserButton(page, phone).click();
  await dialog(page).getByRole('radio', { name: new RegExp(line) }).check();
  await dialog(page).getByRole('button', { name: 'Next' }).click();
  await expect(page.getByRole('dialog', { name: titleOn(title, phone) })).toBeVisible();
}

for (const [label, viewport, phone] of [
  ['desktop 1440', DESKTOP, false],
  ['phone 390', PHONE, true],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('the chooser: bordered line cards, the count, search from 720px, and no axe violations', async ({ page, context }) => {
      await openMyWork(page, context, 'pm');
      if (phone) {
        const plus = page.locator('.shell-phone').getByRole('button', { name: 'Start work' });
        await expect(plus).toHaveText('Start');
        // Drawn inside the phone bar at its right end, 44px tall.
        const [bar, box] = [(await page.locator('header.psl-phonebar').boundingBox())!, (await plus.boundingBox())!];
        expect(box.y >= bar.y && box.y + box.height <= bar.y + bar.height).toBe(true);
        expect(Math.round(bar.x + bar.width - (box.x + box.width))).toBe(16);
        expect(box.height).toBeGreaterThanOrEqual(44);
      }
      await chooserButton(page, phone).click();
      await expect(page.getByRole('dialog', { name: 'Choose a line' })).toBeVisible();
      if (phone) {
        // SCR-04-mobile-lines: the count in the sheet head, titles only, no search; focus on the first line.
        await expect(dialog(page).getByText('Lines you can start · 8')).toBeVisible();
        await expect(dialog(page).getByRole('searchbox')).toHaveCount(0);
        await expect(dialog(page).getByRole('radio').first()).toBeFocused();
      } else {
        await expect(dialog(page).getByText('LINES YOU CAN START · 8')).toBeVisible();
        await expect(dialog(page).getByRole('searchbox', { name: 'Find a line' })).toBeFocused();
      }
      const card = dialog(page).locator('label.sw-line').first();
      expect(await card.evaluate((el) => getComputedStyle(el).borderTopWidth)).toBe('2px');
      await expectNoAxeViolations(page);
      if (phone) {
        const box = (await dialog(page).boundingBox())!;
        expect([box.x, box.width]).toEqual([0, PHONE.width]);
        await expect(dialog(page)).toHaveClass(/psl-sheet/);
      } else {
        await expect(dialog(page)).toHaveClass(/psl-drawer/);
      }
      if (!phone) {
        await dialog(page).getByRole('searchbox', { name: 'Find a line' }).fill('minutes');
        await expect(dialog(page).getByRole('radio')).toHaveCount(1);
      }
    });

    test('the invoice drawer and its validation state have no axe violations; Esc closes and focus returns', async ({ page, context }) => {
      await openMyWork(page, context, 'pm');
      let opener;
      if (phone) {
        await openLine(page, phone, 'Invoice preparation and delivery', 'Invoice preparation and delivery');
        opener = chooserButton(page, phone);
      } else {
        opener = page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' });
        await opener.click();
        await expect(page.getByRole('dialog', { name: 'Invoice preparation and delivery' })).toBeVisible();
        await expect(dialog(page).getByRole('button', { name: 'change line' })).toBeVisible();
      }
      await expect(dialog(page).getByRole('combobox', { name: 'Project' })).toBeFocused();
      await expectNoAxeViolations(page);

      // Tab stays inside the dialog.
      for (let i = 0; i < 12; i += 1) {
        await page.keyboard.press('Tab');
        expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true);
      }

      await dialog(page).getByRole('combobox', { name: 'Project' }).click();
      await dialog(page).getByRole('option', { name: 'Lagoon Health · patient app' }).click();
      // With a project chosen, the start button is the start orange, 48px or more tall, and about twice Back's width from 720px.
      const start = dialog(page).getByRole('button', { name: 'Start the invoice' });
      await expect(start).toHaveCSS('background-color', 'rgb(200, 64, 28)');
      const startBox = (await start.boundingBox())!;
      expect(startBox.height).toBeGreaterThanOrEqual(48);
      if (phone) {
        await expect(dialog(page).getByRole('button', { name: 'Back' })).toHaveCount(0);
      } else {
        const backBox = (await dialog(page).getByRole('button', { name: 'Back' }).boundingBox())!;
        // flex 2 : 1 beside the padding, as the boards draw it (about twice).
        expect(startBox.width / backBox.width).toBeGreaterThan(1.7);
      }
      await dialog(page).getByRole('button', { name: 'Start the invoice' }).click();
      await expect(dialog(page).getByText('Completed milestone is required.')).toBeVisible();
      await expect(dialog(page).getByRole('combobox', { name: 'Completed milestone' })).toHaveAttribute('aria-invalid', 'true');
      await expect(dialog(page).getByRole('alert')).toHaveText(phone ? '1 thing to fix' : '1 thing to fix before Chidi can start.');
      await expect(dialog(page).getByRole('alert')).toBeFocused();
      await expectNoAxeViolations(page);

      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(opener).toBeFocused();
    });

    test('the ceo main button opens the chooser with all 8 lines; no axe violations', async ({ page, context }) => {
      await openMyWork(page, context, 'ceo');
      const main = phone
        ? page.locator('.shell-phone').getByRole('button', { name: 'Start work' })
        : page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' });
      await main.click();
      await expect(page.getByRole('dialog', { name: 'Choose a line' })).toBeVisible();
      await expect(dialog(page).getByText(phone ? 'Lines you can start · 8' : 'LINES YOU CAN START · 8')).toBeVisible();
      await expectNoAxeViolations(page);
    });

    test('each of the 8 drawers shows its board title, fields and start label; Proof is drawn but disabled', async ({ page, context }) => {
      await openMyWork(page, context, 'pm');
      for (const [line, title, labels, start] of LINES) {
        await openLine(page, phone, line, title);
        const fieldLabels = await dialog(page).locator('[data-field] > .psl-label').allTextContents();
        expect(fieldLabels, title).toEqual(labels);
        await expect(dialog(page).getByRole('button', { name: start })).toBeVisible();
        await expect(dialog(page).getByText('Proof upload comes next')).toHaveCount(labels.includes('Proof') ? 1 : 0);
        await expect(dialog(page).getByRole('button', { name: 'Cancel' })).toHaveCount(phone || line.startsWith('Invoice') ? 0 : 1);
        // Two-option choices fill the field's width.
        for (const seg of await dialog(page).locator('.psl-seg').all()) {
          const [segBox, fieldBox] = [(await seg.boundingBox())!, (await seg.locator('..').boundingBox())!];
          expect(Math.round(segBox.width), title).toBe(Math.round(fieldBox.width));
        }
        await page.keyboard.press('Escape');
        await expect(page.getByRole('dialog')).toHaveCount(0);
      }
    });
  });
}

test.describe('a start, end to end on the contract mock', () => {
  test.use({ viewport: DESKTOP });

  test('pm starts an invoice on Lagoon and lands on W-1401; one POST with CSRF and exactly the five keys', async ({ page, context }) => {
    await openMyWork(page, context, 'pm');
    await page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).click();
    await dialog(page).getByRole('combobox', { name: 'Project' }).click();
    await dialog(page).getByRole('option', { name: 'Lagoon Health · patient app' }).click();
    await dialog(page).getByRole('combobox', { name: 'Completed milestone' }).click();
    await dialog(page).getByRole('option', { name: /Milestone 3/ }).click();
    const posted = page.waitForRequest((r) => r.method() === 'POST' && new URL(r.url()).pathname === '/api/v1/work');
    await dialog(page).getByRole('button', { name: 'Start the invoice' }).click();
    const request = await posted;
    expect(request.headers()['x-csrftoken']).toBe('mock-csrf-pm');
    const body = request.postDataJSON();
    expect(Object.keys(body).sort()).toEqual(['case_id', 'case_revision', 'idempotency_key', 'intake', 'line']);
    expect(body).toMatchObject({ line: 'invoice', case_id: 'C-0101', case_revision: 6, intake: { project: 'P-0101', milestone: 'M-0103' } });
    await expect(page).toHaveURL(/\/work\/W-1401$/);
    await expect(page.getByText('Lagoon Health · Invoice preparation and delivery').first()).toBeVisible();
  });

  test('ceo at /my-work sees the chooser from the main button', async ({ page, context }) => {
    await openMyWork(page, context, 'ceo');
    await page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).click();
    await expect(page.getByText('Choose a line')).toBeVisible();
    await expect(page.getByText('LINES YOU CAN START · 8')).toBeVisible();
  });
});
