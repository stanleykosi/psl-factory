import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';

// F-39 escalation (W-3601 to W-3609) against the contract mock: the four states, the PMO Lead's decision in place (claim, then
// one decision), the note rule, the uncertain decide, Send for review and its hold, the phone Drawer and bar, 44px targets,
// and axe WCAG 2.2 AA at 1440 and 390. Nothing here reaches the client. The request log is the browser's own.
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

const readyToDecide = (page: Page) => expect(page.getByRole('button', { name: 'Escalate to the client' })).toBeEnabled();

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

    for (const [id, status] of [
      ['W-3601', 'INVESTIGATING'],
      ['W-3602', 'YOUR DECISION'],
      ['W-3603', 'NOT ESCALATED'],
      ['W-3604', 'MESSAGE DRAFTED'],
      ['W-3608', 'MESSAGE DRAFTED'],
    ] as const) {
      test(`${id}: ${status}, one h1, no sideways scroll, axe clean`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        await expect(page.getByText(status, { exact: true }).first()).toBeVisible();
        if (id === 'W-3602') await readyToDecide(page);
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
      });
    }

    test('the phone bar goes back to the project with ESC-0012; the tab bar marks none current', async ({ page }) => {
      await page.goto('/work/W-3601');
      await loaded(page);
      await expect(page.locator('[aria-current="page"]')).toHaveCount(0);
      if (phone) await expect(page.getByRole('link', { name: /Project/ }).first()).toHaveAttribute('href', '/projects/P-0101');
    });

    test('W-3605 and W-3601: no decide button and no task write', async ({ page }) => {
      const writes = recordWrites(page);
      for (const id of ['W-3601', 'W-3605']) {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.locator('.ws').getByRole('button')).toHaveCount(0);
      }
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('escalate: one claim, then one decision; MESSAGE DRAFTED only once the re-read says so', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3602');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Escalate to the client' }).dblclick();
      await expect(page.locator('.work-state')).toHaveText('MESSAGE DRAFTED');
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-3602/claim', '/api/v1/tasks/T-3602/decision']);
      expect(writes[1].body).toEqual({ verdict: 'approve', expected_revision: 1 });
      await expect(page.getByRole('button', { name: /Approve and send|Edit/ })).toHaveCount(0);
    });

    test('don’t escalate needs a note: none is sent without it; with it NOT ESCALATED and the link to the issue', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3602');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: "Don't escalate" }).click();
      if (phone) {
        const dialog = page.getByRole('dialog', { name: "Don't escalate" });
        await expect(dialog).toBeVisible();
        await expectNoAxeViolations(page);
        await dialog.getByRole('button', { name: "Don't escalate" }).click();
        await expect(dialog.getByText('Add a note to reject it.')).toBeVisible();
        await expectNoAxeViolations(page);
        await page.keyboard.press('Escape');
        await expect(dialog).toHaveCount(0);
        await expect(page.getByRole('button', { name: "Don't escalate" })).toBeFocused();
        await page.getByRole('button', { name: "Don't escalate" }).click();
        await dialog.getByRole('button', { name: 'Cancel' }).click();
        await expect(dialog).toHaveCount(0);
        await page.getByRole('button', { name: "Don't escalate" }).click();
        await dialog.getByLabel(/^Note/).fill('Their new lead starts Monday.');
        await dialog.getByRole('button', { name: "Don't escalate" }).click();
      } else {
        await expect(page.getByText('Add a note to reject it.')).toBeVisible();
        await expect(page.getByLabel(/^Note/)).toBeFocused();
        await expectNoAxeViolations(page);
        await page.getByLabel(/^Note/).fill('Their new lead starts Monday.');
        await page.getByRole('button', { name: "Don't escalate" }).click();
      }
      await expect(page.locator('.work-state')).toHaveText('NOT ESCALATED');
      expect(writes.filter((w) => w.path.endsWith('/decision')).map((w) => w.body)).toEqual([{ verdict: 'reject', expected_revision: 1, note: 'Their new lead starts Monday.' }]);
      await page.getByRole('link', { name: 'Back to the issue' }).click();
      await expect(page).toHaveURL(/\/work\/W-3609$/);
      await expect(page.getByText('NO RESPONSE · 15 DAYS')).toBeVisible();
    });

    test('QA-3-1: two reviewers, A escalates first; B’s don’t escalate gets 409 and B sees MESSAGE DRAFTED, the stale sentence and the unsent note', async ({ page, context }) => {
      const other = await context.newPage();
      await other.goto('/work/W-3602');
      await page.goto('/work/W-3602');
      await loaded(other);
      await loaded(page);
      await readyToDecide(other);
      await readyToDecide(page);
      await other.getByRole('button', { name: 'Escalate to the client' }).click();
      await expect(other.locator('.work-state')).toHaveText('MESSAGE DRAFTED');
      const writes = recordWrites(page);
      await page.getByRole('button', { name: "Don't escalate" }).click();
      const scope = phone ? page.getByRole('dialog', { name: "Don't escalate" }) : page;
      await scope.getByLabel(/^Note/).fill('Second reviewer: wait for their reply first.');
      await scope.getByRole('button', { name: "Don't escalate" }).click();
      await expect(page.locator('.work-state')).toHaveText('MESSAGE DRAFTED');
      await expect(page.getByText('This review changed while you were reading it, so nothing was recorded.')).toBeVisible();
      await expect(page.getByText('Your note wasn’t sent: “Second reviewer: wait for their reply first.”')).toBeVisible();
      // still there once the page has settled, not a flash before the re-read removes it
      await page.waitForTimeout(1500);
      await expect(page.getByText('This review changed while you were reading it, so nothing was recorded.')).toBeVisible();
      expect(writes.filter((w) => w.path.endsWith('/decision')).map((w) => w.body)).toEqual([{ verdict: 'reject', expected_revision: 1, note: 'Second reviewer: wait for their reply first.' }]);
      await expectNoAxeViolations(page);
      await other.close();
    });

    test('Send for review sends one step with a UUID key and shows WAITING FOR REVIEW from the re-read', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3604');
      await loaded(page);
      await page.getByRole('button', { name: 'Send for review' }).click();
      await expect(page.locator('.work-state')).toHaveText('WAITING FOR REVIEW');
      expect(writes).toHaveLength(1);
      expect(writes[0].path).toBe('/api/v1/work/W-3604/steps');
      expect(writes[0].body).toMatchObject({ expected_revision: 2, step: 'send_for_review' });
      expect(String(writes[0].body.idempotency_key)).toMatch(/^[0-9a-f-]{36}$/);
      await expect(page.locator('.ws').getByRole('button')).toHaveCount(0);
    });

    test('W-3608: Send for review is held with the returned reason and sends nothing', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-3608');
      await loaded(page);
      await expect(page.getByText('No one is set to review client messages yet. An admin sets this in Setup.')).toBeVisible();
      const button = page.getByRole('button', { name: 'Send for review' });
      if (await button.count()) await button.click({ force: true });
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('an aborted decide re-reads, shows the uncertain notice and sends nothing again', async ({ page }) => {
      const writes = recordWrites(page);
      await page.route('**/api/v1/tasks/T-3602/decision', (route) => route.abort('failed'));
      await page.goto('/work/W-3602');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Escalate to the client' }).click();
      await expect(page.getByText(/We couldn.t confirm your decision/)).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('YOUR DECISION');
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('W-3607: the result not confirmed is never worded as escalated; axe clean', async ({ page }) => {
      await page.goto('/work/W-3607');
      await loaded(page);
      await readyToDecide(page);
      await page.getByRole('button', { name: 'Escalate to the client' }).click();
      await expect(page.locator('.work-state')).toHaveText('RESULT NOT CONFIRMED');
      await expect(page.getByText('Escalation ESC-0012: result not confirmed')).toBeVisible();
      await expect(page.getByText('MESSAGE DRAFTED')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    test('the not-open view (403 on the item read) shows nothing about the item and is axe clean', async ({ page }) => {
      await page.route('**/api/v1/work/W-3602', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'Not open to you.' }) }));
      await page.goto('/work/W-3602');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByText('Client test data')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    if (phone) {
      test('the phone Decide bar is pinned with both steps; every control is at least 44 by 44', async ({ page }) => {
        await page.goto('/work/W-3602');
        await loaded(page);
        await readyToDecide(page);
        const bar = page.locator('.ws-idecide');
        expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
        await expect(bar.getByRole('button')).toHaveText(['Escalate to the client', "Don't escalate"]);
        const small = await page.evaluate(() =>
          [...document.querySelectorAll<HTMLElement>('main button, main a, main [role="radio"], main [role="tab"]')]
            // the frame's History link (F-17, .work-linehistory) is not this feature's
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
    await setCookies(context, { psl_mock_persona: 'pm' });
    await page.goto('/work/W-3601');
    await loaded(page);
    const animations = await page.locator('.ws-lineagent').evaluate((el) => [...el.querySelectorAll('*')].map((n) => getComputedStyle(n).animationName).filter((n) => n !== 'none'));
    expect(animations).toEqual([]);
  });
});
