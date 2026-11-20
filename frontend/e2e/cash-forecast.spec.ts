import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';

// F-43 cash forecast (W-4001 to W-4013) against the contract mock: the four states and the two holds, the review decided
// in place (claim, then one decision), the note rule, the uncertain decide, the uncertain delivery recorded through the
// reconcile panel (proof first for "It arrived"), the phone Drawer and bar, 44px targets, the table scrolling only in its
// own region, and axe WCAG 2.2 AA at 1440 and 390. The request log is the browser's own.
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

const pdf = (name: string, size: number) => ({ name, mimeType: 'application/pdf', buffer: Buffer.alloc(size, 37) });

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
      ['W-4001', 'CHIDI INVESTIGATING', null],
      ['W-4002', 'AWAITING FINANCE DECISION', 'Approve forecast'],
      ['W-4003', 'EFFECT UNCERTAIN', null],
      ['W-4004', 'VERIFIED', null],
      ['W-4005', 'AWAITING FINANCE DECISION', null],
      ['W-4006', 'SETUP NEEDED', null],
      ['W-4007', 'SETUP NEEDED', null],
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

    test('W-4004: the verified figures are a dark strip (six across on desktop, three on a phone) with the limit as a caption under it', async ({ page }) => {
      await page.goto('/work/W-4004');
      await loaded(page);
      const cells = page.locator('.ws-figstrip__cell');
      await expect(cells.locator('dt')).toHaveText(['CALCULATED', 'REVIEWED', 'DRAFTED', 'PUBLISHED', 'RECEIPTS', 'VERIFIED']);
      await expect(cells.locator('dd')).toHaveText(['12 Nov', '13 Nov', '13 Nov', '14 Nov', '2 of 2', '14 Nov']);
      const tops = await cells.evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().top)));
      expect(new Set(tops).size).toBe(phone ? 2 : 1);
      const backgrounds = await cells.evaluateAll((els) => els.map((el) => getComputedStyle(el).backgroundColor));
      expect(new Set(backgrounds.slice(0, 5)).size).toBe(1);
      expect(backgrounds[5]).not.toBe(backgrounds[0]);
      const caption = page.locator('p.ws-caption');
      await expect(caption).toHaveText('The forecast never moves cash or authorises a payment.');
      expect((await caption.boundingBox())!.y).toBeGreaterThan((await cells.last().boundingBox())!.y);
      expect(await noHorizontalScroll(page)).toBe(true);
    });

    test('W-4002: the amounts as returned at this width, never shortened; Unknown in text; the table scrolls only in its named region', async ({ page }) => {
      await page.goto('/work/W-4002');
      await loaded(page);
      const table = page.locator('.ws-table');
      await expect(table.locator('th')).toHaveText(['MONTH', 'OPENING', 'IN', 'OUT', 'CLOSING']);
      await expect(table.locator('td[data-label="OPENING"]')).toHaveText(['₦22,600,000.00', '₦20,000,000.00', '₦7,800,000.00', 'Unknown', 'Unknown', 'Unknown']);
      await expect(table.locator('td[data-label="CLOSING"]')).toHaveText(['₦20,000,000.00', '₦7,800,000.00', 'Unknown', 'Unknown', 'Unknown', 'Unknown']);
      await expect(table.getByText(/\d+(\.\d)?M\b/)).toHaveCount(0);
      const region = page.locator('.ws-tablewrap');
      await expect(region).toHaveAttribute('tabindex', '0');
      expect(await region.getAttribute('aria-label')).toBeTruthy();
      expect(await noHorizontalScroll(page)).toBe(true);
    });

    test('no claim, decision or action where the person cannot act: W-4001, W-4004 to W-4008, W-4012', async ({ page }) => {
      const writes = recordWrites(page);
      for (const id of ['W-4001', 'W-4004', 'W-4005', 'W-4006', 'W-4007', 'W-4008', 'W-4012']) {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.locator('.ws').getByRole('button', { name: /Approve|Return|Reject/ })).toHaveCount(0);
        await expect(page.getByRole('button', { name: /Record and continue|Cancel delivery|Send again|Resend|Retry/ })).toHaveCount(0);
      }
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('approve: one claim, then one decision; APPROVED from the re-read, never Verified', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4002');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve forecast' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve forecast' }).dblclick();
      await expect(page.locator('.work-state')).toHaveText('APPROVED');
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-4002/claim', '/api/v1/tasks/T-4002/decision']);
      expect(writes[1].body).toEqual({ verdict: 'approve', expected_revision: 1 });
      await expect(page.locator('.ws-idecide')).toHaveCount(0);
      await expect(page.locator('.work-state')).not.toHaveText(/verified/i);
    });

    test('return needs a note: none is sent without it; with it the RETURNED state', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4002');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve forecast' })).toBeEnabled();
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
        await dialog.getByLabel(/^Note/).fill('Check the January receipts.');
        await dialog.getByRole('button', { name: 'Return with a note' }).click();
      } else {
        await expect(page.getByText('Add a note to return it.')).toBeVisible();
        await expect(page.getByLabel(/^Note/)).toBeFocused();
        await expectNoAxeViolations(page);
        await page.getByLabel(/^Note/).fill('Check the January receipts.');
        await page.getByRole('button', { name: 'Return with a note' }).click();
      }
      await expect(page.locator('.work-state')).toHaveText('RETURNED');
      const decisions = writes.filter((w) => w.path.endsWith('/decision'));
      expect(decisions.map((w) => w.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'Check the January receipts.' }]);
    });

    test('an aborted decide re-reads, shows the uncertain notice and sends nothing again', async ({ page }) => {
      const writes = recordWrites(page);
      await page.route('**/api/v1/tasks/T-4002/decision', (route) => route.abort('failed'));
      await page.goto('/work/W-4002');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve forecast' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve forecast' }).click();
      await expect(page.getByText(/We couldn.t confirm your decision/)).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('AWAITING FINANCE DECISION');
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('W-4013: the decide answers effect_uncertain; DECISION NOT CONFIRMED, and still so after a reload', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4013');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve forecast' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve forecast' }).click();
      await expect(page.locator('.work-state')).toHaveText('DECISION NOT CONFIRMED');
      await page.reload();
      await loaded(page);
      await expect(page.locator('.work-state')).toHaveText('DECISION NOT CONFIRMED');
      await expect(page.locator('.ws').getByRole('button', { name: /Approve|Return|Reject/ })).toHaveCount(0);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('record what happened: no choice sends nothing; "It arrived" needs the proof, then one reconcile; VERIFIED only after the reload', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4003');
      await loaded(page);
      // a named section inside the desktop side column (TECH-1-2); its own aside on a phone
      const reconcile = page.getByRole(phone ? 'complementary' : 'region', { name: 'Record what happened' });
      await expect(reconcile).toBeVisible();
      if (phone) {
        // UI-1-3: the board's order: the station line and banner under the title, then Delivery and Next, then the choices
        const top = async (locator: ReturnType<typeof page.locator>) => (await locator.boundingBox())!.y;
        const ys = [await top(page.locator('.ws-ministations')), await top(page.locator('.ws-note').first()), await top(page.getByRole('heading', { name: 'Delivery' })), await top(page.getByRole('heading', { name: 'Next' })), await top(reconcile.getByRole('group', { name: 'Record what happened' }))];
        expect([...ys].sort((a, b) => a - b)).toEqual(ys);
      }
      await expect(reconcile).not.toContainText(/client|invoiced/i);
      await expect(page.getByRole('button', { name: /Cancel delivery|Send again|Resend|Retry/ })).toHaveCount(0);
      const go = page.getByRole('button', { name: 'Record and continue' });
      // UX-1-1: pressable before a choice at both widths; the press says what is missing
      await go.click();
      await expect(page.getByRole('alert').filter({ hasText: 'Choose what happened to continue.' })).toBeVisible();
      await expectNoAxeViolations(page);
      await page.getByRole('radio', { name: /^It arrived\./ }).check();
      await expect(go).toBeDisabled();
      await expect(go).toHaveAccessibleDescription('Upload the proof to continue.');
      await page.locator('input[type="file"]').setInputFiles(pdf('ceo-receipt.pdf', 4096));
      await expect(go).toBeEnabled();
      await go.dblclick();
      await expect(page.locator('.work-state')).toHaveText('VERIFIED');
      const actions = writes.filter((w) => w.path.endsWith('/actions'));
      expect(actions).toHaveLength(1);
      expect(actions[0].body).toMatchObject({ expected_revision: 5, action: 'reconcile', outcome: 'delivered', case_revision: 3 });
      expect(typeof actions[0].body.evidence_id).toBe('string');
      expect(writes.filter((w) => /\/(steps|claim|decision)$/.test(w.path))).toEqual([]);
      await expect(reconcile).toHaveCount(0);
    });

    test('"It didn’t arrive" sends one reconcile with no evidence and reloads to NOT DELIVERED · HELD with no resend', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4003');
      await loaded(page);
      await page.getByRole('radio', { name: /^It didn’t arrive/ }).check();
      await page.getByRole('button', { name: 'Record and continue' }).click();
      await expect(page.locator('.work-state')).toHaveText('NOT DELIVERED · HELD');
      expect(writes.map((w) => w.body)).toEqual([{ expected_revision: 5, action: 'reconcile', outcome: 'not_delivered' }]);
      await expect(page.getByRole('button', { name: /Send again|Resend|Retry|Cancel delivery/ })).toHaveCount(0);
    });

    test('an aborted reconcile says the answer is unconfirmed and sends nothing again', async ({ page }) => {
      const writes = recordWrites(page);
      await page.route('**/api/v1/work/W-4003/actions', (route) => route.abort('failed'));
      await page.goto('/work/W-4003');
      await loaded(page);
      await page.getByRole('radio', { name: /^I can’t tell yet/ }).check();
      await page.getByRole('button', { name: 'Record and continue' }).click();
      await expect(page.getByText('We couldn’t confirm your answer. Reload the work item to see whether it was recorded.')).toBeVisible();
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.filter((w) => w.path.endsWith('/actions'))).toHaveLength(1);
      await expect(page.locator('.work-state')).toHaveText('EFFECT UNCERTAIN');
    });

    test('the not-open view (403 on the item read) shows nothing about the item and is axe clean', async ({ page }) => {
      await page.route('**/api/v1/work/W-4002', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'Not open to you.' }) }));
      await page.goto('/work/W-4002');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByText('₦22,600,000.00')).toHaveCount(0);
      await expect(page.getByText('Cash forecast')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    if (phone) {
      test('the phone Decide bar is pinned with the three steps; every control is at least 44 by 44', async ({ page }) => {
        for (const id of ['W-4002', 'W-4003', 'W-4001']) {
          await page.goto(`/work/${id}`);
          await loaded(page);
          if (id === 'W-4002') {
            await expect(page.getByRole('button', { name: 'Approve forecast' })).toBeEnabled();
            const bar = page.locator('.ws-idecide');
            expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
            await expect(bar.getByRole('button')).toHaveText(['Approve forecast', 'Return with a note', 'Reject']);
            await expect(page.getByText(/^Station \d of 8/i)).toBeVisible();
          }
          const small = await page.evaluate(() =>
            [...document.querySelectorAll<HTMLElement>('main button, main a, main [role="radio"], main [role="tab"]')]
              // the frame's History link (F-17, .work-linehistory) is not this feature's; F-33 and F-42 report it the same way
              .filter((el) => el.offsetParent !== null && !el.closest('p') && !el.closest('.work-linehistory'))
              .map((el) => ({ el: el.textContent, box: el.getBoundingClientRect() }))
              .filter(({ box }) => box.width < 44 || box.height < 44)
              .map(({ el, box }) => `${el}: ${Math.round(box.width)}x${Math.round(box.height)}`),
          );
          expect(small, id).toEqual([]);
          expect(await noHorizontalScroll(page), id).toBe(true);
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
    await page.goto('/work/W-4001');
    await loaded(page);
    const animations = await page.locator('.ws-lineagent').evaluate((el) => [...el.querySelectorAll('*')].map((n) => getComputedStyle(n).animationName).filter((n) => n !== 'none'));
    expect(animations).toEqual([]);
  });
});
