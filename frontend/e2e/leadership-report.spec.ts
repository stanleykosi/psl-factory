import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';

// F-35 leadership report (W-3201 to W-3212) against the contract mock: the four board states and the hold, the review
// decided in place (claim, then one decision), the note rule, the uncertain decide, "Send for leadership review" where
// offered, no resend or confirm control and no action write, the phone Drawer and bar, 44px targets, and axe WCAG 2.2 AA
// at 1440 and 390. The request log is the browser's own. Persona ceo throughout (the mock has no PMO Lead persona).
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const NO_RESEND = /^(Resend|Send again|Try sending|Confirm what happened)/;

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

async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

/** Every write the page sends, in order. */
function recordWrites(page: Page) {
  const writes: { path: string; body: Record<string, unknown> }[] = [];
  page.on('request', (request: Request) => {
    if (request.method() !== 'POST' || !request.url().includes('/api/v1/')) return;
    writes.push({ path: new URL(request.url()).pathname, body: request.postDataJSON() as Record<string, unknown> });
  });
  return writes;
}

async function readyToDecide(page: Page) {
  await expect(page.getByRole('button', { name: 'Approve and send' })).toBeEnabled();
}

const resendControls = (page: Page) =>
  page.evaluate((pattern) => [...document.querySelectorAll('main button, main a')].map((el) => el.textContent?.trim() ?? '').filter((t) => new RegExp(pattern).test(t)), NO_RESEND.source);

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
    test.beforeEach(async ({ context }) => {
      expect((await fetch(`${MOCK}/__mock/reset`, { method: 'POST' })).status).toBe(204);
      await setCookies(context, { psl_mock_persona: 'ceo' });
    });

    for (const [id, status] of [
      ['W-3201', 'DRAFTING'],
      ['W-3202', 'YOUR REVIEW'],
      ['W-3203', 'PUBLISHED · NO REVIEW'],
      ['W-3204', 'RECEIVED BY EVERY RECIPIENT'],
      ['W-3205', 'DRAFT READY'],
      ['W-3206', 'AWAITING LEADERSHIP REVIEW'],
      ['W-3207', 'SETUP NEEDED'],
    ] as const) {
      test(`${id}: ${status}, one h1, no sideways scroll, axe clean`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        await expect(page.locator('.work-state')).toHaveText(status);
        if (id === 'W-3202') await readyToDecide(page);
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
      });
    }

    test('W-3201: Tola’s steps in the card, Ask Tola to /assistant, started in Lagos time, no button', async ({ page }) => {
      await page.goto('/work/W-3201');
      await loaded(page);
      const card = page.locator('.ws-lineagent');
      await expect(card).toContainText('WORKING');
      await expect(card.getByText('Send for leadership review')).toBeVisible();
      await expect(card.getByText('Started 01 Nov 08:00')).toBeVisible();
      await expect(card.getByRole('link', { name: 'Ask Tola' })).toHaveAttribute('href', '/assistant');
      if (!phone) expect(await card.evaluate((el) => el.closest('.ws-side') !== null)).toBe(true);
      await expect(page.locator('.ws').getByRole('button')).toHaveCount(0);
      await expect(page.getByText("The report only uses records you can see. Projects you can't see are left out and counted as left out, never counted as zero.")).toBeVisible();
    });

    test('W-3203: CHECKING in the amber waiting tag, recipients and Next shown, no resend or confirm, no action write', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3203');
      await loaded(page);
      await expect(page.locator('.ws-rows--recipients .ws-row')).toHaveCount(2);
      await expect(page.getByText('CHECKING', { exact: true })).toHaveClass(/psl-tag--waiting/);
      await expect(page.getByText("The factory checks the last delivery before marking it received. It won't resend until it knows.")).toBeVisible();
      expect(await resendControls(page)).toEqual([]);
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('no task write where the person cannot act: W-3206, W-3207, W-3208', async ({ page }) => {
      const writes = recordWrites(page);
      for (const id of ['W-3206', 'W-3207', 'W-3208']) {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.locator('.ws').getByRole('button')).toHaveCount(0);
      }
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('approve and send: one claim, then one decision; the sent state and "is approved" only once the re-read says so', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3202');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Approve and send' }).dblclick();
      await expect(page.locator('.work-state')).toHaveText('SENT · CHECKING DELIVERIES');
      await expect(page.getByText('Monthly report v1 is approved')).toBeVisible();
      await expect(page.locator('.ws-rows--recipients .ws-row')).toHaveText(['CEONot yet', 'CTONot yet', 'PMO LeadNot yet', 'Finance LeadNot yet']);
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-3202/claim', '/api/v1/tasks/T-3202/decision']);
      expect(writes[1].body).toEqual({ verdict: 'approve', expected_revision: 1 });
      await expect(page.getByRole('link', { name: /Open the (full )?report/ })).toHaveCount(0);
    });

    test('return needs a note: none is sent without it; with it the returned state', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3202');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Return with a note' }).click();
      if (phone) {
        const dialog = page.getByRole('dialog', { name: 'Return with a note' });
        await expect(dialog).toBeVisible();
        await expectNoAxeViolations(page);
        await dialog.getByRole('button', { name: 'Return with a note' }).click();
        await expect(dialog.getByText('Add a note to return it.')).toBeVisible();
        await expectNoAxeViolations(page);
        await page.keyboard.press('Escape');
        await expect(dialog).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Return with a note' })).toBeFocused();
        await page.getByRole('button', { name: 'Return with a note' }).click();
        await dialog.getByRole('button', { name: 'Cancel' }).click();
        await expect(dialog).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Return with a note' })).toBeFocused();
        await page.getByRole('button', { name: 'Return with a note' }).click();
        await dialog.getByLabel(/^Note/).fill('Add the Lagoon Health escalation to the summary.');
        await dialog.getByRole('button', { name: 'Return with a note' }).click();
      } else {
        await expect(page.getByText('Add a note to return it.')).toBeVisible();
        await expect(page.getByLabel(/^Note/)).toBeFocused();
        await expectNoAxeViolations(page);
        await page.getByLabel(/^Note/).fill('Add the Lagoon Health escalation to the summary.');
        await page.getByRole('button', { name: 'Return with a note' }).click();
      }
      await expect(page.locator('.work-state')).toHaveText('DRAFTING · RETURNED');
      const decisions = writes.filter((w) => w.path.endsWith('/decision'));
      expect(decisions.map((w) => w.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'Add the Lagoon Health escalation to the summary.' }]);
    });

    test('W-3209: an uncertain approve reads "result not confirmed", Finance Lead CHECKING, no resend and no action write', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3209');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Approve and send' }).click();
      await expect(page.getByText('Monthly report v1: result not confirmed')).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('SENT · DELIVERY NOT CONFIRMED');
      await expect(page.getByText('Monthly report v1 is approved')).toHaveCount(0);
      await expect(page.locator('.ws-rows--recipients .ws-row').last()).toContainText('Finance LeadCHECKING');
      expect(await resendControls(page)).toEqual([]);
      expect(await noHorizontalScroll(page)).toBe(true);
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-3209/claim', '/api/v1/tasks/T-3209/decision']);
    });

    test('W-3211 standalone: one delivery checking, no decide control, no resend, no write', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3211');
      await loaded(page);
      await expect(page.getByText('CHECKING', { exact: true })).toHaveClass(/psl-tag--waiting/);
      await expect(page.getByRole('button', { name: /Approve|Return/ })).toHaveCount(0);
      expect(await resendControls(page)).toEqual([]);
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('an aborted decide on W-3202 re-reads, shows the uncertain notice and sends nothing again', async ({ page }) => {
      const writes = recordWrites(page);
      await page.route('**/api/v1/tasks/T-3202/decision', (route) => route.abort('failed'));
      await page.goto('/work/W-3202');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Approve and send' }).click();
      await expect(page.getByText(/We couldn.t confirm your decision/)).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('YOUR REVIEW');
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('W-3205: Send for leadership review sends one step and shows the item in review with the prepared-by-you copy', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3205');
      await loaded(page);
      await expect(page.getByText('It goes to the leadership reviewer set in Setup › Rules.')).toBeVisible();
      await page.getByRole('button', { name: 'Send for leadership review' }).click();
      await expect(page.locator('.work-state')).toHaveText('AWAITING LEADERSHIP REVIEW');
      await expect(page.getByText('You prepared Monthly report v1, so someone else must review it.')).toBeVisible();
      expect(writes).toHaveLength(1);
      expect(writes[0].path).toBe('/api/v1/work/W-3205/steps');
      expect(Object.keys(writes[0].body).sort()).toEqual(['expected_revision', 'idempotency_key', 'step']);
      expect(writes[0].body).toMatchObject({ expected_revision: 3, step: 'send_for_review' });
      expect(String(writes[0].body.idempotency_key)).toMatch(/^[0-9a-f-]{36}$/);
    });

    test('W-3212: an uncertain send shows the checking notice, never "sent for review", and no second step', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3212');
      await loaded(page);
      await page.getByRole('button', { name: 'Send for leadership review' }).click();
      await expect(page.getByText('We are checking what happened. Nothing was sent again.')).toBeVisible();
      await expect(page.getByText(/sent for review/i)).toHaveCount(0);
      expect(await resendControls(page)).toEqual([]);
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.filter((w) => w.path.endsWith('/steps'))).toHaveLength(1);
      expect(writes.filter((w) => w.path.endsWith('/actions'))).toHaveLength(0);
    });

    test('the not-open view (403 on the item read) shows nothing about the item and is axe clean', async ({ page }) => {
      await page.route('**/api/v1/work/W-3203', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'Not open to you.' }) }));
      await page.goto('/work/W-3203');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByText('Sola Martins')).toHaveCount(0);
      await expect(page.getByText('Tuesday report')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    if (phone) {
      test('the phone Decide bar is pinned with both steps; every control is at least 44 by 44', async ({ page }) => {
        for (const id of ['W-3201', 'W-3203', 'W-3204', 'W-3205', 'W-3202']) {
          await page.goto(`/work/${id}`);
          await loaded(page);
          if (id === 'W-3202') {
            await readyToDecide(page);
            const bar = page.locator('.ws-idecide');
            expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
            await expect(bar.getByRole('button')).toHaveText(['Approve and send', 'Return with a note']);
          }
          const small = await page.evaluate(() =>
            [...document.querySelectorAll<HTMLElement>('main button, main a, main [role="radio"], main [role="tab"]')]
              // the frame's History link (F-17, .work-linehistory) is not this feature's; links inside sentences are exempt (D-95)
              .filter((el) => el.offsetParent !== null && !el.closest('p') && !el.closest('.work-linehistory'))
              .map((el) => ({ el: el.textContent, box: el.getBoundingClientRect() }))
              .filter(({ box }) => box.width < 44 || box.height < 44)
              .map(({ el, box }) => `${el}: ${Math.round(box.width)}x${Math.round(box.height)}`),
          );
          expect(small, id).toEqual([]);
        }
      });
    }
  });
}

test.describe('reduced motion', () => {
  test.use({ viewport: DESKTOP, reducedMotion: 'reduce' });
  test('the working agent does not animate', async ({ page, context }) => {
    expect((await fetch(`${MOCK}/__mock/reset`, { method: 'POST' })).status).toBe(204);
    await setCookies(context, { psl_mock_persona: 'ceo' });
    await page.goto('/work/W-3201');
    await loaded(page);
    const animations = await page.locator('.ws-lineagent').evaluate((el) => [...el.querySelectorAll('*')].map((n) => getComputedStyle(n).animationName).filter((n) => n !== 'none'));
    expect(animations).toEqual([]);
  });
});
