import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-38 RFP submission (W-3501 to W-3509) against the contract mock: the frame, send for review, the reviewer's decision in
// place, the uncertain paths, the phone Drawer and 44px targets, and axe WCAG 2.2 AA at 1440 and 390. Nothing is submitted,
// emailed or delivered; every "Submitted", "Emailed" and "Received" word is fixture text shown only after the re-read.
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
const workspaceLog = async () => (await (await fetch(`${MOCK}/__mock/workspace-log`)).json()) as { entries: { work_id: string; step: string; status: number; replay: boolean }[] };
async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}
/** Every /api request the page sends, by method and path. */
function recorder(page: Page) {
  const seen: { method: string; path: string; origin: string; body: string | null }[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/')) seen.push({ method: request.method(), path: url.pathname, origin: url.origin, body: request.postData() });
  });
  return seen;
}
const decisions = (seen: ReturnType<typeof recorder>) => seen.filter((r) => r.method === 'POST' && r.path.endsWith('/decision'));
const reviewerReady = (page: Page) => expect(page.getByRole('button', { name: 'Approve and submit' })).toBeEnabled();

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

    for (const id of ['W-3501', 'W-3502', 'W-3503', 'W-3504', 'W-3505', 'W-3506', 'W-3507', 'W-3508', 'W-3509']) {
      test(`${id}: one h1, no sideways scroll, axe clean`, async ({ page }) => {
        const seen = recorder(page);
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
        // loading sends reads only; the one write a reviewer's page makes on load is the claim, never a decision or a step
        expect(seen.filter((r) => r.method !== 'GET' && !r.path.endsWith('/claim'))).toEqual([]);
      });
    }

    test('the frame shows on desktop with Submission current; on a phone there is none and the bar goes back to the RFP', async ({ page }) => {
      await page.goto('/work/W-3501');
      await loaded(page);
      if (phone) {
        await expect(page.getByRole('navigation', { name: 'RFP' })).toHaveCount(0);
        await expect(page.getByRole('link', { name: /RFP$/ }).first()).toHaveAttribute('href', '/work/W-2101');
        return;
      }
      await expect(page.locator('[aria-current="page"]')).toContainText('Submission');
      await expect(page.getByRole('navigation', { name: 'RFP' }).getByRole('link', { name: /Team input/ })).toHaveAttribute('href', '/work/W-2101');
    });

    if (phone) {
      test('the draft keeps Send for review and Edit cover letter in a bar pinned to the bottom, whatever the scroll (UI-1-8)', async ({ page }) => {
        await page.goto('/work/W-3501');
        await loaded(page);
        const bar = page.locator('.ws-decide').filter({ has: page.getByRole('button', { name: 'Send for review' }) });
        await expect(bar.getByRole('button', { name: 'Edit cover letter' })).toBeVisible();
        expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
        for (const y of [0, 100000]) {
          await page.evaluate((top) => window.scrollTo(0, top), y);
          const box = await bar.boundingBox();
          expect(Math.round(box!.y + box!.height)).toBe(viewport.height);
        }
      });
    }

    test('Send for review sends one step and the re-read shows the in-review state; nothing says it was sent first', async ({ page }) => {
      const seen = recorder(page);
      await page.goto('/work/W-3501');
      await loaded(page);
      await expect(page.getByText('IN REVIEW')).toHaveCount(0);
      await page.getByRole('button', { name: 'Send for review' }).click();
      await expect(page.getByText('IN REVIEW').first()).toBeVisible();
      await expect(page.getByText(/You prepared Submission pack v1/)).toBeVisible();
      expect((await workspaceLog()).entries.filter((e) => e.step === 'send_for_review')).toHaveLength(1);
      expect(seen.filter((r) => r.method === 'POST' && r.path.endsWith('/steps'))).toHaveLength(1);
      expect(seen.every((r) => r.origin === new URL(page.url()).origin)).toBe(true);
    });

    test('Edit cover letter opens with the current letter (in the Drawer on a phone) and saves one edit; axe clean while open', async ({ page }) => {
      await page.goto('/work/W-3501');
      await loaded(page);
      await page.getByRole('button', { name: 'Edit cover letter' }).click();
      const scope = phone ? page.getByRole('dialog') : page.getByRole('form');
      await expect(scope.getByLabel(/Cover letter/)).toHaveValue(/Dear Tamarind Loans procurement team/);
      await expectNoAxeViolations(page);
      await scope.getByLabel(/Cover letter/).fill('Dear team, our response is attached.');
      await scope.getByRole('button', { name: /Edit cover letter|Save/ }).last().click();
      await expect(page.getByText('Cover letter saved.')).toBeVisible();
      expect((await workspaceLog()).entries.filter((e) => e.step === 'edit_cover_letter')).toHaveLength(1);
    });

    test('Approve and submit: one claim, one decision, and Submitted only after the re-read; then Record the outcome opens the F-18 form', async ({ page }) => {
      const seen = recorder(page);
      await page.goto('/work/W-3502');
      await loaded(page);
      await reviewerReady(page);
      await expect(page.getByText('Goes to procurement@tamarindloans.example')).toBeVisible();
      await expect(page.getByText('Submitted · delivery confirmed')).toHaveCount(0);
      await page.getByRole('button', { name: 'Approve and submit' }).click();
      await expect(page.getByText('Submitted · delivery confirmed')).toBeVisible();
      await expect(page.getByRole('heading', { name: 'What happened' })).toBeVisible();
      await expect(page.getByRole('region', { name: 'Sent to' })).toContainText('Received');
      expect(decisions(seen)).toHaveLength(1);
      expect(JSON.parse(decisions(seen)[0].body!)).toEqual({ verdict: 'approve', expected_revision: 1 });
      expect(seen.filter((r) => r.path.endsWith('/claim'))).toHaveLength(1);
      await expectNoAxeViolations(page);
      await page.getByRole('link', { name: 'Record the outcome' }).click();
      await expect(page).toHaveURL(/\/work\/W-3502\/outcome/);
      // the phone outcome page asks for the result first; the returned submission line is on the desktop form
      if (phone) await expect(page.getByRole('heading', { name: 'Record the outcome', level: 1 })).toBeVisible();
      else await expect(page.getByText(/Submission pack v1/).first()).toBeVisible();
    });

    test('Return needs a note: none sends nothing, the note is announced and focused; with a note it re-reads to RETURNED TO PM', async ({ page }) => {
      const seen = recorder(page);
      await page.goto('/work/W-3502');
      await loaded(page);
      await reviewerReady(page);
      await page.getByRole('button', { name: 'Return' }).click();
      const scope = phone ? page.getByRole('dialog') : page.locator('.ws-idecide');
      if (phone) await scope.getByRole('button', { name: 'Return' }).click();
      await expect(scope.getByText('Add a note to return it.')).toBeVisible();
      await expect(scope.getByLabel(/^Note/)).toBeFocused();
      await expectNoAxeViolations(page);
      expect(decisions(seen)).toHaveLength(0);
      await scope.getByLabel(/^Note/).fill('Name the contact for the forms.');
      await scope.getByRole('button', { name: 'Return' }).click();
      await expect(page.getByText('RETURNED TO PM').first()).toBeVisible();
      await expect(page.getByText(/Submitted/)).toHaveCount(0);
      expect(decisions(seen)).toHaveLength(1);
    });

    test('the pack changed (W-3506): the first approve is refused as stale, v2 is shown and no second decision goes out', async ({ page }) => {
      const seen = recorder(page);
      await page.goto('/work/W-3506');
      await loaded(page);
      await reviewerReady(page);
      await page.getByRole('button', { name: 'Approve and submit' }).click();
      await expect(page.getByText('Submission pack · v2')).toBeVisible();
      await expect(page.getByText('This review changed while you were reading it, so nothing was recorded.')).toBeVisible();
      await expectNoAxeViolations(page);
      expect(decisions(seen)).toHaveLength(1);
      await expect(page.getByText(/Submitted/)).toHaveCount(0);
    });

    test('uncertain: the approve answers effect uncertain, the panel shows and no control sends again; a reload keeps it', async ({ page }) => {
      const seen = recorder(page);
      await page.goto('/work/W-3505');
      await loaded(page);
      await reviewerReady(page);
      await page.getByRole('button', { name: 'Approve and submit' }).click();
      await expect(page.getByText('Submission pack v1 · delivery not confirmed')).toBeVisible();
      await expect(page.getByRole('group', { name: /what happened/ })).toBeVisible();
      await expect(page.getByRole('region', { name: 'Sent to' })).toContainText('Uncertain');
      await expect(page.getByText(/Submitted|Record the outcome/)).toHaveCount(0);
      await expect(page.getByRole('button', { name: /send again|resend|submit again/i })).toHaveCount(0);
      await expectNoAxeViolations(page);
      await page.reload();
      await loaded(page);
      await expect(page.getByRole('group', { name: /what happened/ })).toBeVisible();
      expect(decisions(seen)).toHaveLength(1);
    });

    test('a decide that fails on the network re-reads and shows the uncertain notice; no decision is sent again', async ({ page }) => {
      const seen = recorder(page);
      await page.route('**/api/v1/tasks/T-3502/decision', (route) => route.abort('failed'));
      await page.goto('/work/W-3502');
      await loaded(page);
      await reviewerReady(page);
      await page.getByRole('button', { name: 'Approve and submit' }).click();
      await expect(page.getByText(/We couldn.t confirm your decision/)).toBeVisible();
      await expectNoAxeViolations(page);
      await expect(page.getByText('Submitted · delivery confirmed')).toHaveCount(0);
      expect(decisions(seen)).toHaveLength(1);
    });

    test('W-3508 holds Approve with its reason; W-3507 holds Edit cover letter with Not available yet', async ({ page }) => {
      await page.goto('/work/W-3508');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve and submit' })).toBeDisabled();
      await expect(page.getByText('A part still uses a test template.')).toBeVisible();
      await page.goto('/work/W-3507');
      await loaded(page);
      await expect(page.getByText('Not available yet')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Edit cover letter' })).toHaveAttribute('aria-disabled', 'true');
    });

    test('Open the full pack reads the document once and shows Test template', async ({ page }) => {
      const seen = recorder(page);
      await page.goto('/work/W-3502');
      await loaded(page);
      await page.getByRole('button', { name: 'Open the full pack (PDF, 6.1 MB)' }).click();
      await expect(page.getByText('Submission pack · Tamarind Loans')).toBeVisible();
      await expect(page.getByText('Test template').first()).toBeVisible();
      expect(seen.filter((r) => r.path === '/api/v1/documents/D-3501/versions/1')).toHaveLength(1);
    });

    test('the not-open view for a 404 shows nothing of the RFP', async ({ page }) => {
      await page.route('**/api/v1/work/W-3503', (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '404' } }));
      await page.goto('/work/W-3503');
      await expect(page.getByText(/isn.t open to you|can.t open|not open/i).first()).toBeVisible();
      await expect(page.getByText(/Tamarind|TL-RFP-2026-014|procurement@|Submission pack/)).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    if (phone) {
      test('every button and link in the page body is at least 44 by 44 (links inside sentences, the shell bar and the shared History link excepted)', async ({ page }) => {
        for (const id of ['W-3501', 'W-3502', 'W-3503']) {
          await page.goto(`/work/${id}`);
          await loaded(page);
          const small = await page.evaluate(() =>
            [...document.querySelectorAll<HTMLElement>('main button, main a')]
              .filter((el) => el.offsetParent !== null && !el.closest('p, li') && !el.closest('.work-linehistory') && !el.classList.contains('psl-skip'))
              .map((el) => ({ text: (el.textContent ?? '').trim().slice(0, 30), r: el.getBoundingClientRect() }))
              .filter(({ r }) => r.width > 0 && (r.width < 43.5 || r.height < 43.5))
              .map(({ text, r }) => `${text}: ${Math.round(r.width)}x${Math.round(r.height)}`),
          );
          expect(small, id).toEqual([]);
        }
      });
    }
  });
}

test('reduced motion: nothing animates on the submitted page', async ({ page, context }) => {
  await setCookies(context, { psl_mock_persona: 'pm' });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize(DESKTOP);
  await page.goto('/work/W-3503');
  await loaded(page);
  const animated = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length);
  expect(animated).toBe(0);
});
