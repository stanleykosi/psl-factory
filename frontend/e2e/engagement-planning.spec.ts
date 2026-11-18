import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-31 engagement and planning (W-2601 to W-2604) against the contract mock: the pages, confirm PM, register, record
// department input, the uncertain registration, and axe WCAG 2.2 AA at 1440 and 390. Nothing is sent to anyone.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}
async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const log = async () => (await (await fetch(`${MOCK}/__mock/workspace-log`)).json()) as { entries: { work_id: string; step: string; status: number; replay: boolean }[]; assignments: { written: boolean }[] };
const pdf = (name: string) => ({ name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 plan\n'.repeat(80)) });
async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;
  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
    test.beforeEach(async ({ context }) => {
      expect((await fetch(`${MOCK}/__mock/reset`, { method: 'POST' })).status).toBe(204);
      await setCookies(context, { psl_mock_persona: 'pm' });
    });

    for (const id of ['W-2601', 'W-2602', 'W-2603', 'W-2604']) {
      test(`${id}: one h1, no sideways scroll, axe clean`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
      });
    }

    test('the not-open view for a 403 and for a 404 is the same and shows nothing of the item; axe clean', async ({ page }) => {
      for (const status of [403, 404]) {
        await page.route('**/api/v1/work/W-2603', (route) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify({ code: status === 403 ? 'forbidden' : 'not_found', message: 'No.' }) }));
        await page.goto('/work/W-2603');
        await expect(page.getByText(/can’t open this work item/)).toBeVisible();
        await expect(page.getByText('Ojo Foods')).toHaveCount(0);
        await expectNoAxeViolations(page);
        await page.unroute('**/api/v1/work/W-2603');
      }
    });

    test('confirm the PM, register, then reach planning from the re-read item', async ({ page }) => {
      await page.goto('/work/W-2601');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Confirm PM' })).toBeVisible();
      await expectNoAxeViolations(page);
      await page.getByRole('button', { name: 'Confirm PM' }).click();
      await expect(page.getByText('PM confirmed: Sola Martins')).toBeVisible();
      expect((await log()).assignments.filter((a) => a.written)).toHaveLength(1);
      await page.getByRole('button', { name: 'Register engagement' }).click();
      const scope = phone ? page.getByRole('dialog') : page.locator('form[aria-labelledby]');
      await expectNoAxeViolations(page);
      const uploaded = page.waitForResponse((r) => r.url().includes('/evidence') && r.request().method() === 'POST');
      await scope.locator('input[type="file"]').setInputFiles(pdf('kickoff-plan-v1.pdf'));
      await uploaded;
      await expect(scope.getByText(/Add another file/)).toBeVisible();
      await scope.getByLabel(/Start date/).fill('15 Jan 2027');
      await scope.getByLabel(/Start date/).press('Tab');
      await scope.getByLabel(/Client project contact/).fill('Ngozi Bello');
      await scope.getByRole('button', { name: 'Register engagement' }).click();
      await expect(page.getByText('Engagement EN-0042 registered.')).toBeVisible();
      await expect(page.getByRole('link', { name: 'Planning · PLN-0031' })).toHaveAttribute('href', '/work/W-2603');
      await expect(page.getByRole('link', { name: 'Ojo Foods · ordering app' })).toHaveAttribute('href', '/projects/P-0106');
      expect((await log()).entries.filter((e) => e.step === 'register_engagement' && !e.replay)).toHaveLength(1);
    });

    test('an uncertain registration leaves every step off and sends once', async ({ page }) => {
      await page.goto('/work/W-2604');
      await loaded(page);
      await page.getByRole('button', { name: 'Register engagement' }).click();
      const scope = phone ? page.getByRole('dialog') : page.locator('form[aria-labelledby]');
      const uploaded = page.waitForResponse((r) => r.url().includes('/evidence') && r.request().method() === 'POST');
      await scope.locator('input[type="file"]').setInputFiles(pdf('kickoff-plan-v1.pdf'));
      await uploaded;
      await expect(scope.getByText(/Add another file/)).toBeVisible();
      await scope.getByRole('button', { name: 'Register engagement' }).click();
      await expect(page.getByText('We couldn’t confirm the engagement was registered.')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Register engagement' })).toHaveAttribute('aria-disabled', 'true');
      await page.reload();
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Register engagement' })).toHaveAttribute('aria-disabled', 'true');
      expect((await log()).entries.filter((e) => e.work_id === 'W-2604' && !e.replay)).toHaveLength(1);
      await expectNoAxeViolations(page);
    });

    test('record QA’s input: the Drawer, axe, one write, the re-read shows QA in', async ({ page }) => {
      await page.goto('/work/W-2603');
      await loaded(page);
      const button = page.locator('tr').filter({ has: page.locator('td', { hasText: /^QA$/ }) }).getByRole('button', { name: 'Record input' });
      if (phone) expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await button.click();
      const dialog = page.getByRole('dialog', { name: 'Record department input' });
      await expect(dialog.getByLabel(/What they gave/)).toBeVisible();
      await expectNoAxeViolations(page);
      await dialog.getByLabel('Who gave it').selectOption({ label: 'QA · QA lead, PSL' });
      await dialog.getByLabel(/Estimate/).fill('45');
      await dialog.getByLabel(/What they gave/).fill('Test plan and QA effort');
      await dialog.locator('input[type="file"]').setInputFiles(pdf('qa-plan.pdf'));
      await expect(dialog.getByText(/Uploaded/)).toBeVisible();
      await dialog.getByLabel(/Received/).fill('2026-12-11T16:05');
      await dialog.getByRole('checkbox').check();
      await dialog.getByRole('button', { name: /^Record/ }).click();
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(page.locator('.work-state')).toHaveText('PLANNING · 3 OF 5 IN');
      await expect(page.getByRole('button', { name: 'Record input' })).toHaveCount(1);
      await expect(page.getByText(/Recorded under your name/)).toBeVisible();
      await expectNoAxeViolations(page);
    });

    test('Cancel closes the Drawer and returns focus to the button', async ({ page }) => {
      await page.goto('/work/W-2603');
      await loaded(page);
      const button = page.getByRole('button', { name: 'Record input' }).first();
      await button.click();
      await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click();
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(button).toBeFocused();
    });

    test('Planning is reached from the project, and the back link on a phone reads Project', async ({ page }) => {
      await page.goto('/projects/P-0106');
      await page.getByRole('link', { name: /Plan a project/ }).click();
      await page.waitForURL('**/work/W-2603');
      await loaded(page);
      if (phone) await expect(page.getByRole('link', { name: 'Back to Project' })).toHaveAttribute('href', '/projects/P-0106');
    });

    test('reduced motion: nothing animates on the planning page', async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto('/work/W-2603');
      await loaded(page);
      const moving = await page.evaluate(() => [...document.querySelectorAll('.ws *')].filter((el) => getComputedStyle(el).animationName !== 'none').length);
      expect(moving).toBe(0);
    });
  });
}
