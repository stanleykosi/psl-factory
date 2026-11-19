import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';

// F-45 ledger source LED-0052 (W-4201 to W-4213) against the contract mock: the four states and the two holds, recording
// what was found with a proof upload (E-EVIDENCE-UPLOAD then E-WORK-STEP), the review decided in place (claim, then one
// decision), the note rule, the stale and uncertain decides, the phone Drawer and bar, 44px targets (the uploaded chip's
// "×" too), and axe WCAG 2.2 AA at 1440 and 390. The request log is the browser's own. No QuickBooks call is made.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const PNG = { name: 'qb-screenshot-je7741.png', mimeType: 'image/png', buffer: Buffer.alloc(310 * 1024, 7) };

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

/** Controls under 44 by 44 in the page (links inside sentences are exempt, D-95; the frame's History link is F-17's). */
const smallTargets = (page: Page, scope = 'main') =>
  page.evaluate((root) =>
    [...document.querySelectorAll<HTMLElement>(`${root} button, ${root} a, ${root} [role="combobox"], ${root} [role="option"], .psl-sheet button`)]
      .filter((el) => el.offsetParent !== null && !el.closest('p') && !el.closest('.work-linehistory'))
      .map((el) => ({ el: el.getAttribute('aria-label') ?? el.textContent, box: el.getBoundingClientRect() }))
      .filter(({ box }) => box.width < 44 || box.height < 44)
      .map(({ el, box }) => `${el}: ${Math.round(box.width)}x${Math.round(box.height)}`),
  scope);

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

    for (const [id, status, button] of [
      ['W-4201', 'CHIDI INVESTIGATING', null],
      ['W-4202', 'RECORD WHAT YOU FOUND', 'Record observation'],
      ['W-4203', 'AWAITING FINANCE DECISION', 'Approve reference'],
      ['W-4204', 'VERIFIED', null],
      ['W-4205', 'SETUP NEEDED', null],
      ['W-4209', 'CHECK HELD', null],
    ] as const) {
      test(`${id}: ${status}, one h1, the title as returned, no amount, no sideways scroll, axe clean`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        await expect(page.getByRole('heading', { level: 1 })).toHaveText('QuickBooks journal JE-7741 · October');
        await expect(page.locator('.work-state')).toHaveText(status);
        if (button) await expect(page.getByRole('button', { name: button })).toBeEnabled();
        await expect(page.getByText(/₦|\d{1,3}(,\d{3})+/)).toHaveCount(0);
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
      });
    }

    test('W-4201: Chidi’s card in the agent style with Ask Chidi to /assistant; every request stays on the app’s origin', async ({ page }) => {
      const origins = new Set<string>();
      const apiPaths: string[] = [];
      page.on('request', (request) => {
        const url = new URL(request.url());
        if (url.protocol === 'data:' || url.protocol === 'blob:') return;
        origins.add(url.origin);
        if (url.pathname.startsWith('/api/')) apiPaths.push(url.pathname);
      });
      await page.goto('/work/W-4201');
      await loaded(page);
      const card = page.locator('.ws-lineagent');
      await expect(card.getByText('WORKING')).toBeVisible();
      await expect(card.getByText('QB_EXPORT_JE7741.PDF')).toBeVisible();
      await expect(card.getByText(/Started 15:12/)).toBeVisible();
      await expect(card.getByRole('link', { name: 'Ask Chidi' })).toHaveAttribute('href', '/assistant');
      await page.waitForTimeout(300);
      expect([...origins]).toEqual([new URL(test.info().project.use.baseURL!).origin]);
      expect(apiPaths.every((p) => p.startsWith('/api/v1/'))).toBe(true);
    });

    test('no write where the person cannot act: W-4201, W-4204 to W-4207, W-4209 and W-4210, whatever is pressed', async ({ page }) => {
      const writes = recordWrites(page);
      for (const id of ['W-4201', 'W-4204', 'W-4205', 'W-4206', 'W-4207', 'W-4209', 'W-4210']) {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.locator('.ws').getByRole('button', { name: /Approve|Reject/ })).toHaveCount(0);
        for (const button of await page.locator('.ws button').all()) await button.click({ force: true });
        await expect(page.locator('.ws form')).toHaveCount(0);
        await expect(page.getByRole('dialog')).toHaveCount(0);
      }
      await page.waitForTimeout(300);
      expect(writes).toEqual([]);
    });

    test('W-4206 and W-4207 give the backend’s reason with no button; W-4210 draws the step inert with its reason', async ({ page }) => {
      await page.goto('/work/W-4206');
      await loaded(page);
      await expect(page.getByText('You prepared LED-0052 v1, so someone else must review it.')).toBeVisible();
      await page.goto('/work/W-4207');
      await loaded(page);
      await expect(page.getByText('This decision needs a Ledger reviewer.')).toBeVisible();
      await page.goto('/work/W-4210');
      await loaded(page);
      await expect(page.getByText('You captured this source, so someone else must look it up.')).toBeVisible();
      await expectNoAxeViolations(page);
    });

    test('record what you found: the field errors, then one upload and one step; the re-read is the review the observer cannot decide', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4202');
      await loaded(page);
      await page.getByRole('button', { name: 'Record observation' }).click();
      const scope = phone ? page.getByRole('dialog', { name: 'Record observation' }) : page.locator('.ws form');
      await expect(scope.getByRole('combobox', { name: /What you found/ })).toHaveText('Choose…');
      await scope.getByRole('button', { name: 'Record observation' }).click();
      await expect(scope.getByText('Add what you found to continue.')).toBeVisible();
      await expect(scope.getByText('Add proof to continue.')).toBeVisible();
      await expect(scope.getByRole('combobox', { name: /What you found/ })).toBeFocused();
      await expectNoAxeViolations(page);
      await scope.getByRole('combobox', { name: /What you found/ }).click();
      await page.getByRole('option', { name: 'Found', exact: true }).click();
      await scope.locator('input[type="file"]').setInputFiles(PNG);
      await expect(scope.getByText('qb-screenshot-je7741.png · 310 KB')).toBeVisible();
      await expect(scope.getByText(/Uploading…/)).toHaveCount(0);
      await expectNoAxeViolations(page);
      if (phone) expect(await smallTargets(page)).toEqual([]);
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/cases/C-LED-0052/evidence']);
      expect(writes[0].body).toMatchObject({ kind: 'ledger_observation', filename: 'qb-screenshot-je7741.png', case_revision: 4 });
      await scope.getByRole('button', { name: 'Record observation' }).dblclick();
      await expect(page.locator('.work-state')).toHaveText('AWAITING FINANCE DECISION');
      await expect(page.getByText('You prepared LED-0052 v1, so someone else must review it.')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Approve reference' })).toHaveCount(0);
      const steps = writes.filter((w) => w.path.endsWith('/steps'));
      expect(steps).toHaveLength(1);
      expect(steps[0].path).toBe('/api/v1/work/W-4202/steps');
      expect(Object.keys(steps[0].body).sort()).toEqual(['evidence_ids', 'expected_revision', 'idempotency_key', 'inputs', 'step']);
      expect(steps[0].body).toMatchObject({ expected_revision: 2, step: 'record_observation', inputs: { found: 'found' }, evidence_ids: ['EV-C-LED-0052-1'] });
      const log = (await (await fetch(`${MOCK}/__mock/workspace-log`)).json()) as { entries: { replay: boolean }[] };
      expect(log.entries.filter((e) => !e.replay)).toHaveLength(1);
    });

    test('W-4208: Unknown with proof shows the backend’s CHECK HELD hold from the re-read, with no control', async ({ page }) => {
      await page.goto('/work/W-4208');
      await loaded(page);
      await page.getByRole('button', { name: 'Record observation' }).click();
      const scope = phone ? page.getByRole('dialog', { name: 'Record observation' }) : page.locator('.ws form');
      await scope.getByRole('combobox', { name: /What you found/ }).click();
      await page.getByRole('option', { name: 'Unknown', exact: true }).click();
      await scope.locator('input[type="file"]').setInputFiles(PNG);
      await expect(scope.getByText('qb-screenshot-je7741.png · 310 KB')).toBeVisible();
      await expect(scope.getByText(/Uploading…/)).toHaveCount(0);
      await scope.getByRole('button', { name: 'Record observation' }).click();
      await expect(page.locator('.work-state')).toHaveText('CHECK HELD');
      await expect(page.locator('.ws').getByRole('button')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    test('W-4213: the step is written then answers 500; the page shows the re-read review and “couldn’t confirm”, never “Observation recorded.”', async ({ page }) => {
      await page.goto('/work/W-4213');
      await loaded(page);
      await page.getByRole('button', { name: 'Record observation' }).click();
      const scope = phone ? page.getByRole('dialog', { name: 'Record observation' }) : page.locator('.ws form');
      await scope.getByRole('combobox', { name: /What you found/ }).click();
      await page.getByRole('option', { name: 'Found', exact: true }).click();
      await scope.locator('input[type="file"]').setInputFiles(PNG);
      await expect(scope.getByText('qb-screenshot-je7741.png · 310 KB')).toBeVisible();
      await expect(scope.getByText(/Uploading…/)).toHaveCount(0);
      await scope.getByRole('button', { name: 'Record observation' }).click();
      await expect(page.getByText('We couldn’t confirm this step. Check the page before trying again.')).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('AWAITING FINANCE DECISION');
      await expect(page.getByText('Observation recorded.')).toHaveCount(0);
      await expectNoAxeViolations(page);
      const log = (await (await fetch(`${MOCK}/__mock/workspace-log`)).json()) as { entries: { work_id: string; replay: boolean }[] };
      expect(log.entries.filter((e) => e.work_id === 'W-4213' && !e.replay)).toHaveLength(1);
    });

    test('approve: one claim, then one decision; VERIFIED only once the re-read says so', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4203');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve reference' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve reference' }).dblclick();
      await expect(page.locator('.work-state')).toHaveText('VERIFIED');
      expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-4203/claim', '/api/v1/tasks/T-4203/decision']);
      expect(writes[1].body).toEqual({ verdict: 'approve', expected_revision: 1 });
      await expect(page.getByText('YES · 14 NOV')).toBeVisible();
      await expect(page.locator('.ws-idecide')).toHaveCount(0);
    });

    test('reject needs a note: none is sent without it; with it REJECTED read-only and no Correct step', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4203');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve reference' })).toBeEnabled();
      if (phone) expect(await page.locator('.ws-idecide').evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
      if (phone) expect(await smallTargets(page)).toEqual([]);
      await page.getByRole('button', { name: 'Reject' }).click();
      if (phone) {
        const dialog = page.getByRole('dialog', { name: 'Reject' });
        await expect(dialog).toBeVisible();
        await expectNoAxeViolations(page);
        await dialog.getByRole('button', { name: 'Reject' }).click();
        await expect(dialog.getByText('Add a note to reject it.')).toBeVisible();
        await expectNoAxeViolations(page);
        await page.keyboard.press('Escape');
        await expect(dialog).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Reject' })).toBeFocused();
        await page.getByRole('button', { name: 'Reject' }).click();
        await dialog.getByRole('button', { name: 'Cancel' }).click();
        await expect(dialog).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Reject' })).toBeFocused();
        await page.getByRole('button', { name: 'Reject' }).click();
        await dialog.getByLabel(/^Note/).fill('  Wrong journal: JE-7714 was meant.  ');
        await dialog.getByRole('button', { name: 'Reject' }).click();
      } else {
        await expect(page.getByText('Add a note to reject it.')).toBeVisible();
        await expect(page.getByLabel(/^Note/)).toBeFocused();
        await expectNoAxeViolations(page);
        await page.getByLabel(/^Note/).fill('  Wrong journal: JE-7714 was meant.  ');
        await page.getByRole('button', { name: 'Reject' }).click();
      }
      await expect(page.locator('.work-state')).toHaveText('REJECTED');
      expect(writes.filter((w) => w.path.endsWith('/decision')).map((w) => w.body)).toEqual([{ verdict: 'reject', expected_revision: 1, note: 'Wrong journal: JE-7714 was meant.' }]);
      await expect(page.locator('.ws').getByRole('button')).toHaveCount(0);
    });

    test('two reviewers: A approves first; B’s reject gets 409 and B sees the verified state, the stale sentence and the unsent note', async ({ page, context }) => {
      const other = await context.newPage();
      await other.goto('/work/W-4203');
      await page.goto('/work/W-4203');
      await loaded(other);
      await loaded(page);
      await expect(other.getByRole('button', { name: 'Approve reference' })).toBeEnabled();
      await expect(page.getByRole('button', { name: 'Approve reference' })).toBeEnabled();
      await other.getByRole('button', { name: 'Approve reference' }).click();
      await expect(other.locator('.work-state')).toHaveText('VERIFIED');
      const writes = recordWrites(page);
      await page.getByRole('button', { name: 'Reject' }).click();
      const scope = phone ? page.getByRole('dialog', { name: 'Reject' }) : page;
      await scope.getByLabel(/^Note/).fill('Stale tab note');
      await scope.getByRole('button', { name: 'Reject' }).click();
      await expect(page.locator('.work-state')).toHaveText('VERIFIED');
      await expect(page.getByText('This review changed while you were reading it, so nothing was recorded.')).toBeVisible();
      await expect(page.getByText('Your note wasn’t sent: “Stale tab note”')).toBeVisible();
      await expect(page.getByText(/was rejected/)).toHaveCount(0);
      expect(writes.filter((w) => w.path.endsWith('/decision')).map((w) => w.body)).toEqual([{ verdict: 'reject', expected_revision: 1, note: 'Stale tab note' }]);
      await expectNoAxeViolations(page);
      await other.close();
    });

    test('an aborted decide re-reads, shows the uncertain notice and sends nothing again', async ({ page }) => {
      const writes = recordWrites(page);
      await page.route('**/api/v1/tasks/T-4203/decision', (route) => route.abort('failed'));
      await page.goto('/work/W-4203');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve reference' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve reference' }).click();
      await expect(page.getByText(/We couldn.t confirm your decision/)).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('AWAITING FINANCE DECISION');
      await expectNoAxeViolations(page);
      await page.waitForTimeout(1500);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('W-4212: the decide answers effect_uncertain; “result not confirmed” and CHECKING, never VERIFIED', async ({ page }) => {
      const writes = recordWrites(page);
      await page.goto('/work/W-4212');
      await loaded(page);
      await expect(page.getByRole('button', { name: 'Approve reference' })).toBeEnabled();
      await page.getByRole('button', { name: 'Approve reference' }).click();
      await expect(page.getByText('LED-0052 v1: result not confirmed')).toBeVisible();
      await expect(page.locator('.work-state')).toHaveText('CHECKING');
      await expect(page.getByText('LED-0052 v1 is approved')).toHaveCount(0);
      expect(writes.filter((w) => w.path.endsWith('/decision'))).toHaveLength(1);
    });

    test('the not-open view (403 on the item read) shows nothing about the item and is axe clean', async ({ page }) => {
      await page.route('**/api/v1/work/W-4203', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'forbidden', message: 'Not open to you.' }) }));
      await page.goto('/work/W-4203');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByText('QuickBooks journal JE-7741 · October')).toHaveCount(0);
      await expect(page.getByText('JE-7741')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });
  });
}

test.describe('reduced motion', () => {
  test.use({ viewport: DESKTOP, reducedMotion: 'reduce' });
  test('the working agent tag does not animate', async ({ page, context }) => {
    expect((await fetch(`${MOCK}/__mock/reset`, { method: 'POST' })).status).toBe(204);
    await setCookies(context, { psl_mock_persona: 'finance_lead' });
    await page.goto('/work/W-4201');
    await loaded(page);
    const animations = await page.locator('.ws-lineagent').evaluate((el) => [...el.querySelectorAll('*')].map((n) => getComputedStyle(n).animationName).filter((n) => n !== 'none'));
    expect(animations).toEqual([]);
  });
});
