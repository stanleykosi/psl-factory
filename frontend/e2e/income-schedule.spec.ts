import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';

// F-33 income schedule (W-2701 to W-2711) against the contract mock: the four states and the hold, the review decided in
// place (claim, then one decision), the note rule, the uncertain decide, correct and resubmit, the phone Drawer and bar,
// 44px targets, and axe WCAG 2.2 AA at 1440 and 390. The request log is the browser's own.
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

async function readyToDecide(page: Page) {
  await expect(page.getByRole('button', { name: 'Approve schedule' })).toBeEnabled();
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

    for (const [id, status] of [
      ['W-2701', 'CHIDI INVESTIGATING'],
      ['W-2702', 'AWAITING FINANCE DECISION'],
      ['W-2703', 'RETURNED · CORRECT AND RESUBMIT'],
      ['W-2704', 'VERIFIED'],
      ['W-2705', 'AWAITING FINANCE DECISION'],
      ['W-2706', 'SETUP NEEDED'],
    ] as const) {
      test(`${id}: ${status}, one h1, no sideways scroll, axe clean`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        await expect(page.getByText(status, { exact: true }).first()).toBeVisible();
        if (id === 'W-2702') await readyToDecide(page);
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
      });
    }

    test('W-2702: the amount as returned at this width, never shortened', async ({ page }) => {
      await page.goto('/work/W-2702');
      await loaded(page);
      await expect(page.getByText('₦12,400,000.00')).toBeVisible();
      await expect(page.getByText('12.4M')).toHaveCount(0);
    });

    test('no task write where the person cannot act: W-2705, W-2706, W-2708', async ({ page }) => {
      const writes = recordWrites(page);
      for (const id of ['W-2705', 'W-2706', 'W-2708']) {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.locator('.ws').getByRole('button')).toHaveCount(0);
      }
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('approve: one claim, then one decision; Verified only once the re-read says so', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-2702');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Approve schedule' }).dblclick();
      await expect(page.locator('.work-state')).toHaveText('VERIFIED');
      await expect(page.getByText('Schedule v1 is approved')).toBeVisible();
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-2702/claim', '/api/v1/tasks/T-2702/decision']);
      expect(writes[1].body).toEqual({ verdict: 'approve', expected_revision: 1 });
      await expect(page.getByRole('button', { name: /Export|Withdraw/ })).toHaveCount(0);
    });

    test('return needs a note: none is sent without it; with it the returned state, then correct and resubmit', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-2702');
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
        await dialog.getByLabel(/^Note/).fill('Row 12 is a reclassification.');
        await dialog.getByRole('button', { name: 'Return with a note' }).click();
      } else {
        await expect(page.getByText('Add a note to return it.')).toBeVisible();
        await expect(page.getByLabel(/^Note/)).toBeFocused();
        await expectNoAxeViolations(page);
        await page.getByLabel(/^Note/).fill('Row 12 is a reclassification.');
        await page.getByRole('button', { name: 'Return with a note' }).click();
      }
      await expect(page.locator('.work-state')).toHaveText('RETURNED · CORRECT AND RESUBMIT');
      const decisions = writes.filter((w) => w.path.endsWith('/decision'));
      expect(decisions.map((w) => w.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'Row 12 is a reclassification.' }]);
      await page.getByRole('button', { name: 'Correct and resubmit' }).click();
      if (phone) await expect(page.getByRole('dialog', { name: 'Correct and resubmit' })).toBeVisible();
      await expect(page.getByRole('radiogroup', { name: /Row 12 relationship/ })).toBeVisible();
    });

    test('W-2703: correct and resubmit sends one step and shows the item back in review', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-2703');
      await loaded(page);
      await page.getByRole('button', { name: 'Correct and resubmit' }).click();
      const scope = phone ? page.getByRole('dialog', { name: 'Correct and resubmit' }) : page.locator('.ws');
      await scope.getByRole('radio', { name: 'Reclassification' }).click();
      if (phone) await expectNoAxeViolations(page);
      await scope.locator('button[type="submit"]').click();
      await expect(page.locator('.work-state')).toHaveText('AWAITING FINANCE DECISION');
      await expect(page.getByText('You prepared Schedule v1, so someone else must review it.')).toBeVisible();
      expect(writes).toHaveLength(1);
      expect(writes[0].path).toBe('/api/v1/work/W-2703/steps');
      expect(writes[0].body).toMatchObject({ expected_revision: 4, step: 'correct_and_resubmit', inputs: { row_12_relationship: 'reclassification' } });
      expect(String(writes[0].body.idempotency_key)).toMatch(/^[0-9a-f-]{36}$/);
    });

    test('an aborted decide re-reads, shows the uncertain notice and sends nothing again', async ({ page }) => {
      const writes = recordWrites(page);
      await page.route('**/api/v1/tasks/T-2702/decision', (route) => route.abort('failed'));
      await page.goto('/work/W-2702');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Approve schedule' }).click();
      await expect(page.getByText(/We couldn.t confirm your decision/)).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('AWAITING FINANCE DECISION');
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('the not-open view (403 on the item read) shows nothing about the item and is axe clean', async ({ page }) => {
      await page.route('**/api/v1/work/W-2702', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'Not open to you.' }) }));
      await page.goto('/work/W-2702');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByText('₦12,400,000.00')).toHaveCount(0);
      await expect(page.getByText('Income detail')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    if (phone) {
      test('the phone Decide bar is pinned with the three steps; every control is at least 44 by 44', async ({ page }) => {
        await page.goto('/work/W-2702');
        await loaded(page);
        await readyToDecide(page);
        const bar = page.locator('.ws-idecide');
        expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
        await expect(bar.getByRole('button')).toHaveText(['Approve schedule', 'Return with a note', 'Reject']);
        const small = await page.evaluate(() =>
          [...document.querySelectorAll<HTMLElement>('main button, main a, main [role="radio"], main [role="tab"]')]
            // the frame's History link (F-17, .work-linehistory) is not this feature's; it is reported in build.md
            .filter((el) => el.offsetParent !== null && !el.closest('p') && !el.closest('.work-linehistory'))
            .map((el) => ({ el: el.textContent, box: el.getBoundingClientRect() }))
            .filter(({ box }) => box.width < 44 || box.height < 44)
            .map(({ el, box }) => `${el}: ${Math.round(box.width)}x${Math.round(box.height)}`),
        );
        expect(small).toEqual([]);
      });
    }
  });
}

test.describe('reduced motion', () => {
  test.use({ viewport: DESKTOP, reducedMotion: 'reduce' });
  test('the working agent tag does not animate', async ({ page, context }) => {
    expect((await fetch(`${MOCK}/__mock/reset`, { method: 'POST' })).status).toBe(204);
    await setCookies(context, { psl_mock_persona: 'finance_lead' });
    await page.goto('/work/W-2701');
    await loaded(page);
    const animations = await page.locator('.ws-lineagent').evaluate((el) => [...el.querySelectorAll('*')].map((n) => getComputedStyle(n).animationName).filter((n) => n !== 'none'));
    expect(animations).toEqual([]);
  });
});
