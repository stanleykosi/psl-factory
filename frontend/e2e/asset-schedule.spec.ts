import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';

// F-42 fixed asset schedule (W-3901 to W-3912) against the contract mock: the four states and the three holds, the
// register and date reviews decided in place on one item (claim, then one decision each), the note rule, the uncertain
// decide, the phone Drawer and bar, 44px targets, and axe WCAG 2.2 AA at 1440 and 390. The request log is the browser's own.
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

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
    test.beforeEach(async ({ context }) => {
      expect((await fetch(`${MOCK}/__mock/reset`, { method: 'POST' })).status).toBe(204);
      await setCookies(context, { psl_mock_persona: 'finance_lead' });
    });

    for (const [id, status, approve] of [
      ['W-3901', 'CHIDI INVESTIGATING', null],
      ['W-3902', 'AWAITING FINANCE DECISION', 'Approve register'],
      ['W-3903', 'AWAITING FINANCE DECISION', 'Approve dates'],
      ['W-3904', 'PROCESSING', null],
      ['W-3907', 'SETUP NEEDED', null],
      ['W-3909', 'SETUP NEEDED', null],
    ] as const) {
      test(`${id}: ${status}, one h1, no sideways scroll, axe clean`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        await expect(page.locator('.work-state')).toHaveText(status);
        if (approve) await expect(page.getByRole('button', { name: approve })).toBeEnabled();
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
      });
    }

    test('W-3902: the costs as returned at this width, never shortened; the table has column headers and no column is cut off', async ({ page }) => {
      await page.goto('/work/W-3902');
      await loaded(page);
      for (const cost of ['₦8,400,000.00', '₦14,000,000.00', '₦3,150,000.00']) await expect(page.getByText(cost, { exact: true })).toBeVisible();
      await expect(page.getByText(/\d+(\.\d)?M\b/)).toHaveCount(0);
      await expect(page.locator('.ws-table th')).toHaveText(['ASSET', 'CHANGE', 'COST']);
      expect(await noHorizontalScroll(page)).toBe(true);
    });

    test('W-3903: all three columns of the date table are on screen at this width', async ({ page }) => {
      await page.goto('/work/W-3903');
      await loaded(page);
      for (const text of ['A-0412 server rack', '"Oct 2026"', 'Delivered 02 Oct, live 15 Oct', 'Issued 09 Oct']) {
        const cell = page.getByText(text, { exact: true });
        await cell.scrollIntoViewIfNeeded();
        await expect(cell).toBeInViewport();
      }
      const clipped = await page.evaluate(() => [...document.querySelectorAll('.ws-tablewrap')].some((el) => el.scrollWidth > el.clientWidth + 1));
      expect(clipped).toBe(false);
    });

    test('no task write where the person cannot act: W-3901, W-3904 to W-3909 and W-3912', async ({ page }) => {
      const writes = recordWrites(page);
      for (const id of ['W-3901', 'W-3904', 'W-3905', 'W-3906', 'W-3907', 'W-3908', 'W-3909', 'W-3912']) {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.locator('.ws').getByRole('button', { name: /Approve|Return|Reject/ })).toHaveCount(0);
      }
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('approve the register: one claim, then one decision; the waiting state only once the re-read says so', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3902');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve register' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve register' }).dblclick();
      await expect(page.locator('.work-state')).toHaveText('WAITING FOR DATE EXPLANATIONS');
      await expect(page.getByText('October register is approved')).toBeVisible();
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-3902/claim', '/api/v1/tasks/T-3902/decision']);
      expect(writes[1].body).toEqual({ verdict: 'approve', expected_revision: 1 });
      await expect(page.locator('.ws-idecide')).toHaveCount(0);
    });

    test('approve the dates: one claim and one decision for T-3903 only; PROCESSING from the re-read', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3903');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve dates' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve dates' }).click();
      await expect(page.locator('.work-state')).toHaveText('PROCESSING');
      await expect(page.getByText('REGISTER · APPROVED')).toBeVisible();
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-3903/claim', '/api/v1/tasks/T-3903/decision']);
      expect(writes[1].body).toEqual({ verdict: 'approve', expected_revision: 1 });
    });

    test('return needs a note: none is sent without it; with it the returned state and no correction step', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3902');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve register' })).toBeEnabled();
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
        await dialog.getByLabel(/^Note/).fill('The Hilux was sold on 21 Oct.');
        await dialog.getByRole('button', { name: 'Return with a note' }).click();
      } else {
        await expect(page.getByText('Add a note to return it.')).toBeVisible();
        await expect(page.getByLabel(/^Note/)).toBeFocused();
        await expectNoAxeViolations(page);
        await page.getByLabel(/^Note/).fill('The Hilux was sold on 21 Oct.');
        await page.getByRole('button', { name: 'Return with a note' }).click();
      }
      await expect(page.locator('.work-state')).toHaveText('RETURNED');
      const decisions = writes.filter((w) => w.path.endsWith('/decision'));
      expect(decisions.map((w) => w.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'The Hilux was sold on 21 Oct.' }]);
      await expect(page.locator('.ws').getByRole('button')).toHaveCount(0);
    });

    test('an aborted decide re-reads, shows the uncertain notice and sends nothing again', async ({ page }) => {
      const writes = recordWrites(page);
      await page.route('**/api/v1/tasks/T-3902/decision', (route) => route.abort('failed'));
      await page.goto('/work/W-3902');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve register' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve register' }).click();
      await expect(page.getByText(/We couldn.t confirm your decision/)).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('AWAITING FINANCE DECISION');
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('W-3911: the decide answers effect_uncertain; "result not confirmed" and DECISION NOT CONFIRMED, and still so after a reload', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3911');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve register' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve register' }).click();
      await expect(page.getByText('October register: result not confirmed')).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('DECISION NOT CONFIRMED');
      await expect(page.getByText('October register is approved')).toHaveCount(0);
      await page.reload();
      await loaded(page);
      await expect(page.locator('.work-state')).toHaveText('DECISION NOT CONFIRMED');
      await expect(page.locator('.ws').getByRole('button', { name: /Approve|Return|Reject/ })).toHaveCount(0);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('the not-open view (403 on the item read) shows nothing about the item and is axe clean', async ({ page }) => {
      await page.route('**/api/v1/work/W-3902', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'Not open to you.' }) }));
      await page.goto('/work/W-3902');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByText('₦14,000,000.00')).toHaveCount(0);
      await expect(page.getByText('Fixed asset schedule')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    if (phone) {
      test('the phone Decide bar is pinned with the three steps; every control is at least 44 by 44', async ({ page }) => {
        for (const [id, approve] of [
          ['W-3902', 'Approve register'],
          ['W-3903', 'Approve dates'],
        ] as const) {
          await page.goto(`/work/${id}`);
          await loaded(page);
          await expect(page.getByRole('button', { name: approve })).toBeEnabled();
          const bar = page.locator('.ws-idecide');
          expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
          await expect(bar.getByRole('button')).toHaveText([approve, 'Return with a note', 'Reject']);
          await expect(page.getByText(/^Station \d of 6/i)).toBeVisible();
          const small = await page.evaluate(() =>
            [...document.querySelectorAll<HTMLElement>('main button, main a, main [role="radio"], main [role="tab"]')]
              // the frame's History link (F-17, .work-linehistory) is not this feature's; F-33 reports it the same way
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
  test('the working agent tag does not animate', async ({ page, context }) => {
    expect((await fetch(`${MOCK}/__mock/reset`, { method: 'POST' })).status).toBe(204);
    await setCookies(context, { psl_mock_persona: 'finance_lead' });
    await page.goto('/work/W-3901');
    await loaded(page);
    const animations = await page.locator('.ws-lineagent').evaluate((el) => [...el.querySelectorAll('*')].map((n) => getComputedStyle(n).animationName).filter((n) => n !== 'none'));
    expect(animations).toEqual([]);
  });
});
