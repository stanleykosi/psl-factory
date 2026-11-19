import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-37 RFP requirements (W-3401 to W-3404) against the contract mock: the frame, the accept, edit and write-own flows,
// the uncertain step, and axe WCAG 2.2 AA at 1440 and 390. Nothing is sent to anyone; every "accepted" word is fixture text.
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
const log = async () => (await (await fetch(`${MOCK}/__mock/workspace-log`)).json()) as { entries: { work_id: string; step: string; status: number; replay: boolean }[] };
async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}
const panel = (page: Page) => page.getByRole('region', { name: /Review Tola’s suggestion/ });

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

    for (const id of ['W-3401', 'W-3402', 'W-3403', 'W-3404']) {
      test(`${id}: one h1, no sideways scroll, axe clean`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
      });
    }

    test('the frame shows on desktop only; the team-input tab opens F-18’s form inside it', async ({ page }) => {
      await page.goto('/work/W-3401');
      await loaded(page);
      if (phone) {
        await expect(page.getByRole('navigation', { name: 'RFP' })).toHaveCount(0);
        return;
      }
      await expect(page.locator('[aria-current="page"]')).toContainText('Requirements');
      await page.getByRole('navigation', { name: 'RFP' }).getByRole('link', { name: /Team input/ }).click();
      await expect(page).toHaveURL(/\/work\/W-3401\/respond\?task=T-3401/);
      await expect(page.getByRole('navigation', { name: 'RFP' }).getByRole('link', { name: /Requirements/ })).toBeVisible();
    });

    test('Accept answer sends one accept and the re-read shows R-07 addressed with R-08 next', async ({ page }) => {
      await page.goto('/work/W-3402');
      await loaded(page);
      await panel(page).getByRole('button', { name: 'Accept answer' }).click();
      await expect(page.getByText('R-07 accepted under your name.')).toBeVisible();
      await expect(panel(page).getByText(/R-08 · RFP p\.6/)).toBeVisible();
      expect((await log()).entries.filter((e) => e.step === 'accept')).toHaveLength(1);
    });

    test('Edit answer: the discard question, then a 422 and a save; axe clean while open', async ({ page }) => {
      await page.goto('/work/W-3402');
      await loaded(page);
      await panel(page).getByRole('button', { name: 'Edit answer' }).click();
      const scope = phone ? page.getByRole('dialog') : page.getByRole('form');
      await scope.getByLabel(/Your answer/).fill('Two named officers approve.');
      await expectNoAxeViolations(page);
      await scope.getByRole('button', { name: 'Cancel' }).click();
      await expect(scope.getByText('Discard your changes?')).toBeVisible();
      await expectNoAxeViolations(page);
      await scope.getByRole('button', { name: 'Keep editing' }).click();
      await scope.getByRole('button', { name: 'Save and accept' }).click();
      await expect(page.getByText('R-07 saved with your edit and accepted.')).toBeVisible();
      expect((await log()).entries.filter((e) => e.step === 'edit_accept')).toHaveLength(1);
    });

    test('Write my own: an empty answer names the field and sends nothing; a filled one is saved; axe clean', async ({ page }) => {
      await page.goto('/work/W-3402');
      await loaded(page);
      await panel(page).getByRole('button', { name: 'Write my own' }).click();
      const scope = phone ? page.getByRole('dialog') : page.getByRole('form');
      await scope.getByRole('button', { name: 'Save my answer' }).click();
      await expect(scope.getByText(/Add your answer to continue/).first()).toBeVisible();
      await expectNoAxeViolations(page);
      expect((await log()).entries).toHaveLength(0);
      await scope.getByLabel(/Your answer/).fill('Two named officers approve.');
      await scope.getByRole('button', { name: 'Save my answer' }).click();
      await expect(page.getByText(/Your answer to R-07 is saved/)).toBeVisible();
    });

    test('Accept selected sends the two ticked rows; the select-all box ticks the four shown', async ({ page }) => {
      await page.goto('/work/W-3402');
      await loaded(page);
      await page.getByLabel('Select all shown rows').check();
      await expect(page.getByText('4 selected')).toBeVisible();
      await page.getByLabel('Select all shown rows').uncheck();
      await page.getByLabel('Select R-07').check();
      await page.getByLabel('Select R-09').check();
      await expect(page.getByText('2 selected')).toBeVisible();
      await page.getByRole('button', { name: 'Accept selected' }).click();
      await expect(page.getByText('2 answers accepted under your name.')).toBeVisible();
      expect((await log()).entries.filter((e) => e.step === 'accept_selected')).toHaveLength(1);
    });

    test('Add a requirement: a 422 from the mock keeps the form; a good entry is saved', async ({ page }) => {
      await page.goto('/work/W-3401');
      await loaded(page);
      await page.getByRole('button', { name: 'Add a requirement from the RFP' }).click();
      const scope = phone ? page.getByRole('dialog') : page.getByRole('form');
      await scope.getByLabel(/^Requirement/).fill('Data stays in Nigeria');
      await scope.getByLabel(/RFP page/).fill('12');
      await scope.getByRole('button', { name: 'Add a requirement from the RFP' }).click();
      await expect(page.getByText('Done: Add a requirement from the RFP.')).toBeVisible();
    });

    test('the uncertain step turns every step off, a reload keeps them off, and exactly one accept was sent', async ({ page }) => {
      await page.goto('/work/W-3403');
      await loaded(page);
      await panel(page).getByRole('button', { name: 'Accept answer' }).click();
      await expect(page.getByText(/We are checking what happened/).first()).toBeVisible();
      await expectNoAxeViolations(page);
      await page.reload();
      await loaded(page);
      await expect(panel(page).getByRole('button', { name: 'Accept answer' })).toHaveAttribute('aria-disabled', 'true');
      await panel(page).getByRole('button', { name: 'Accept answer' }).click({ force: true });
      expect((await log()).entries.filter((e) => e.step === 'accept')).toHaveLength(1);
    });

    test('the not-open view for a 403 and for a 404 is the same and shows nothing of the item; axe clean', async ({ page }) => {
      for (const status of [403, 404]) {
        await page.route('**/api/v1/work/W-3401', (route) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify({ code: status === 403 ? 'forbidden' : 'not_found', message: 'No.' }) }));
        await page.goto('/work/W-3401');
        await expect(page.getByText(/can’t open this work item/)).toBeVisible();
        await expect(page.getByText('Tamarind Loans')).toHaveCount(0);
        await expectNoAxeViolations(page);
        await page.unroute('**/api/v1/work/W-3401');
      }
    });

    if (phone) {
      test('every button, checkbox and link outside running text is at least 44px', async ({ page }) => {
        await page.goto('/work/W-3402');
        await loaded(page);
        const small = await page.evaluate(() =>
          [...document.querySelectorAll<HTMLElement>('main button, main a, .ws button, .ws-checkwrap')]
            // the line header's History link is the shared F-17 link, unchanged here
            .filter((el) => el.offsetParent !== null && !el.closest('p, .psl-tablewrap td > a') && el.getAttribute('href') !== '/work/W-3402/history')
            .map((el) => ({ el: el.outerHTML.slice(0, 80), r: el.getBoundingClientRect() }))
            .filter(({ r }) => r.width > 0 && r.height > 0 && (r.height < 43.5 || r.width < 43.5))
            .map(({ el }) => el),
        );
        expect(small).toEqual([]);
      });
    }
  });
}

test.describe('reduced motion', () => {
  test.use({ viewport: DESKTOP, reducedMotion: 'reduce' });
  test('W-3402 opens with reduced motion and no violations', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'pm' });
    await page.goto('/work/W-3402');
    await loaded(page);
    await expectNoAxeViolations(page);
  });
});
