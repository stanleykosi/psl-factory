import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

// F-40 (contract mock only): the handover to Support (SCR-48) at 1440 and 390: axe, touch targets, one column, Publish and the
// record-reply writes with their recorded requests. Nothing here publishes to Support; every "published", "received" and
// "acknowledged" is fixture text the mock returned after the write.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const GAPS = ['No contact for the credit bureau outage', 'Runbook misses the nightly export restart'];
const REPLY = { name: 'support-reply-10apr.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(40 * 1024, '%PDF-1.4\n') };

test.use({ timezoneId: 'Africa/Lagos' });

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}
async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
}
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
async function expectTouchTargets(targets: Locator[]) {
  for (const target of targets) {
    const box = (await target.boundingBox())!;
    expect(box.height, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
  }
}
function record(page: Page) {
  const writes: { path: string; body: Record<string, unknown>; csrf: string | undefined }[] = [];
  page.on('request', (r) => {
    if (r.method() === 'POST') writes.push({ path: new URL(r.url()).pathname, body: r.postDataJSON(), csrf: r.headers()['x-csrftoken'] });
  });
  return writes;
}
const replyPanel = (page: Page) => page.getByRole('region', { name: 'Record Support’s reply' });
async function fillReply(page: Page, action = 'Gaps found') {
  const panel = replyPanel(page);
  await expect(panel.getByRole('radio', { name: 'Received' })).toBeVisible();
  await panel.getByLabel('When they replied').fill('2026-04-10T11:00');
  await panel.getByRole('radio', { name: action }).check({ force: true });
  if (action === 'Gaps found') await panel.getByLabel('Gaps', { exact: true }).fill(GAPS.join('\n'));
  await panel.locator('input[type="file"]').setInputFiles(REPLY);
  await expect(panel.getByText(/Uploaded/)).toBeVisible();
  await panel.getByRole('checkbox', { name: 'I confirm this response is genuine.' }).check();
}

test.beforeEach(async ({ context, request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: test.info().project.use.baseURL! }]);
});

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;
  test.describe(label, () => {
    test.use({ viewport, reducedMotion: 'reduce', ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    test('the Delivery tab links Handover to W-3704, in the row and the sub-nav', async ({ page }) => {
      await page.goto('/projects/P-0101/delivery');
      await loaded(page);
      await expect(page.getByRole('link', { name: /Handover to Support/ })).toHaveAttribute('href', '/work/W-3704');
      if (!phone) await expect(page.getByRole('navigation', { name: 'Delivery lines' }).getByRole('link', { name: 'Handover' })).toHaveAttribute('href', '/work/W-3704');
    });

    for (const id of ['W-3701', 'W-3702', 'W-3703', 'W-3704', 'W-3705', 'W-3709']) {
      test(`${id}: one column, no sideways scroll, controls 44px, no axe violations`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        if (id === 'W-3703') await expect(replyPanel(page).getByRole('radio', { name: 'Received' })).toBeVisible();
        expect(await noHorizontalScroll(page)).toBe(true);
        if (phone) await expectTouchTargets(await page.locator('main a.psl-btn, main button, main .ws-control .psl-btn').all());
        if (id === 'W-3702') await expect(page.locator('.ws button, .ws a[href], .ws input')).toHaveCount(0);
        if (id === 'W-3709') {
          const control = page.getByRole('button', { name: 'Record Support’s reply' });
          await expect(control).toHaveAttribute('aria-disabled', 'true');
          await expect(control).toHaveAttribute('aria-describedby', /.+/);
          await expect(replyPanel(page)).toHaveCount(0);
        }
        if (id === 'W-3705') await expect(page.getByRole('link', { name: 'See what closure needs' })).toHaveAttribute('href', '/work/W-3720');
        await expectNoAxeViolations(page);
      });
    }

    test('W-3703 form with Gaps found: labelled fields, 44px targets, the remove × named, Record reply pinned on a phone, no axe violations', async ({ page }) => {
      await page.goto('/work/W-3703');
      await loaded(page);
      await fillReply(page);
      const panel = replyPanel(page);
      await expect(panel.getByRole('button', { name: 'Remove support-reply-10apr.pdf' })).toBeVisible();
      if (phone) {
        await expectTouchTargets(await panel.locator('button, input[type="datetime-local"], .psl-seg__opt').all());
        const box = (await panel.locator('.resp-chip__remove').boundingBox())!;
        expect([box.width >= 44, box.height >= 44]).toEqual([true, true]);
        const bar = (await panel.locator('.psl-actionbar').boundingBox())!;
        expect(bar.y + bar.height).toBeGreaterThan(viewport.height - 4);
      }
      expect(await noHorizontalScroll(page)).toBe(true);
      await expectNoAxeViolations(page);
    });

    test('a 422 on gaps: "Add at least one gap." under Gaps, announced, no axe violations', async ({ page }) => {
      await page.route('**/api/v1/tasks/T-3703/response', (route) => route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ code: 'invalid', message: 'Check these fields: gaps.' }) }));
      await page.goto('/work/W-3703');
      await loaded(page);
      await fillReply(page);
      await replyPanel(page).getByRole('button', { name: 'Record reply' }).click();
      await expect(replyPanel(page).getByRole('alert').filter({ hasText: 'Add at least one gap.' })).toBeVisible();
      await expectNoAxeViolations(page);
    });

    test('the uncertain state (W-3706 after Publish) has no axe violations and one column', async ({ page }) => {
      await page.goto('/work/W-3706');
      await loaded(page);
      await page.getByRole('button', { name: 'Publish to Support' }).click();
      await expect(page.getByText('Handover · delivery unconfirmed').first()).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      await expectNoAxeViolations(page);
    });

    test('the no-access view has no axe violations', async ({ page }) => {
      await page.goto('/work/W-1099');
      await expect(page.getByText('You can’t open this work item')).toBeVisible();
      await expectNoAxeViolations(page);
    });
  });
}

test.describe('Publish and the uncertain paths', () => {
  test.use({ viewport: DESKTOP });

  test('W-3701: one step with the revision, a key and CSRF; "published 08 Apr" appears after the re-read; the mock logs one send', async ({ page }) => {
    const writes = record(page);
    await page.goto('/work/W-3701');
    await loaded(page);
    await expect(page.getByText('Handover · ready to publish').first()).toBeVisible();
    await expect(page.getByText('This sends to the client.')).toHaveCount(0);
    const button = page.getByRole('button', { name: 'Publish to Support' });
    await button.dblclick();
    await expect(page.getByText('Handover · published 08 Apr').first()).toBeVisible();
    expect(writes).toHaveLength(1);
    expect(writes[0]).toMatchObject({ path: '/api/v1/work/W-3701/steps', csrf: 'mock-csrf-pm', body: { step: 'publish', expected_revision: 1 } });
    expect(writes[0].body.idempotency_key).toBeTruthy();
    await expect(replyPanel(page)).toBeVisible();
    const log = await (await page.request.get(`${MOCK}/__mock/workspace-log`)).json();
    expect(Object.values(log.sends)).toEqual([1]);
  });

  for (const id of ['W-3706', 'W-3707']) {
    test(`${id}: the uncertain banner and reconcile panel, Publish off, a second press sends nothing`, async ({ page }) => {
      const writes = record(page);
      await page.goto(`/work/${id}`);
      await loaded(page);
      await page.getByRole('button', { name: 'Publish to Support' }).click();
      await expect(page.getByText('Handover · delivery unconfirmed').first()).toBeVisible();
      await expect(page.getByText(/It arrived\./)).toBeVisible();
      const control = page.getByRole('button', { name: 'Publish to Support' });
      await expect(control).toHaveAttribute('aria-disabled', 'true');
      await control.click({ force: true });
      expect(writes.filter((w) => w.path.endsWith('/steps'))).toHaveLength(1);
      await expect(page.locator('body')).not.toContainText(/Handover · published/);
      const log = await (await page.request.get(`${MOCK}/__mock/workspace-log`)).json();
      expect(Object.values(log.sends)).toEqual([1]);
    });
  }

  test('W-3706 reconcile: delivered, with proof, serves the record state from the re-read', async ({ page }) => {
    await page.goto('/work/W-3706');
    await loaded(page);
    await page.getByRole('button', { name: 'Publish to Support' }).click();
    await expect(page.getByText(/It arrived\./)).toBeVisible();
    await page.getByRole('radio', { name: /It arrived\./ }).check({ force: true });
    await page.locator('input[type="file"]').first().setInputFiles(REPLY);
    await expect(page.getByText(/support-reply-10apr.pdf/).first()).toBeVisible();
    await page.getByRole('button', { name: 'Record and continue' }).click();
    await expect(replyPanel(page)).toBeVisible();
    await expect(page.getByText('Handover · published 08 Apr').first()).toBeVisible();
  });

  test('W-3708 (409): the stale notice and the re-read status, never Done', async ({ page }) => {
    await page.goto('/work/W-3708');
    await loaded(page);
    await page.getByRole('button', { name: 'Publish to Support' }).click();
    await expect(page.getByText('This changed while you were working. Showing version 2.')).toBeVisible();
    await expect(page.getByText('Handover · published 08 Apr').first()).toBeVisible();
    await expect(page.locator('.ws-notices').getByText(/Done:/)).toHaveCount(0);
  });

  test('a network failure on Publish locks it, re-reads and asks for a check', async ({ page }) => {
    await page.route('**/api/v1/work/W-3701/steps', (route) => route.abort('failed'));
    await page.goto('/work/W-3701');
    await loaded(page);
    await page.getByRole('button', { name: 'Publish to Support' }).click();
    await expect(page.getByText('We couldn’t confirm this step. Check the page before trying again.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Publish to Support' })).toHaveAttribute('aria-disabled', 'true');
    await expect(page.locator('.ws-notices').getByText(/Done:/)).toHaveCount(0);
  });

  test('W-3704: Ask Tola to draft v2 sends one step; the re-read says Drafting v2 with the gaps still OPEN', async ({ page }) => {
    const writes = record(page);
    await page.goto('/work/W-3704');
    await loaded(page);
    await page.getByRole('button', { name: 'Ask Tola to draft v2' }).click();
    await expect(page.getByText('Drafting v2').first()).toBeVisible();
    await expect(page.locator('.ws-notices').getByText('Waiting: Tola is drafting v2.')).toBeVisible();
    await expect(page.getByText('OPEN')).toHaveCount(2);
    await expect(page.locator('.ws .ws-note.psl-callout--success')).toHaveCount(0);
    expect(writes).toHaveLength(1);
    expect(writes[0].body).toMatchObject({ step: 'draft_v2', expected_revision: 1 });
  });
});

test.describe('Record Support’s reply', () => {
  test.use({ viewport: DESKTOP });

  test('Gaps found: one upload then one response with the gaps, no claim; the gaps state and the notice come from the re-read; focus returns to the heading', async ({ page }) => {
    const writes = record(page);
    await page.goto('/work/W-3703');
    await loaded(page);
    await expect(replyPanel(page).getByText('Femi Ojo · Support lead')).toBeVisible();
    await expect(replyPanel(page).getByLabel('Gaps', { exact: true })).toHaveCount(0);
    await fillReply(page);
    await replyPanel(page).getByRole('button', { name: 'Record reply' }).dblclick();
    await expect(page.getByText('Gaps · 2').first()).toBeVisible();
    await expect(page.getByText(/Recorded under your name/)).toBeVisible();
    expect(writes.map((w) => w.path)).toEqual(['/api/v1/cases/P-0101/evidence', '/api/v1/tasks/T-3703/response']);
    expect(writes[1].csrf).toBe('mock-csrf-pm');
    expect(writes[1].body).toMatchObject({ expected_revision: 1, who: 'R-3701', action: 'changes_requested', attested: true, version_id: 'V-3701', gaps: GAPS });
    expect(writes[1].body.responded_at).toBe('2026-04-10T11:00:00+01:00');
    await expect(page.getByText('OPEN')).toHaveCount(2);
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeFocused();
  });

  test('Received sends no gaps and the acknowledged state shows from the re-read', async ({ page }) => {
    const writes = record(page);
    await page.goto('/work/W-3703');
    await loaded(page);
    await fillReply(page, 'Received');
    await replyPanel(page).getByRole('button', { name: 'Record reply' }).click();
    await expect(page.getByText('Handover acknowledged').first()).toBeVisible();
    expect(writes[1].body).toMatchObject({ action: 'approved' });
    expect(writes[1].body).not.toHaveProperty('gaps');
    await expect(page.getByRole('link', { name: 'See what closure needs' })).toHaveAttribute('href', '/work/W-3720');
  });

  test('record-then-fail (written, then 502): re-reads, says so, shows the gaps state, and sends nothing again', async ({ page }) => {
    const writes = record(page);
    await page.route('**/api/v1/tasks/T-3703/response', (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': 'record-then-fail' } }));
    await page.goto('/work/W-3703');
    await loaded(page);
    await fillReply(page);
    await replyPanel(page).getByRole('button', { name: 'Record reply' }).click();
    await expect(page.getByText('Gaps · 2').first()).toBeVisible();
    await expect(page.getByText('We couldn’t confirm the reply was recorded. We’ve reloaded this item so you can see whether it was.')).toBeVisible();
    expect(writes.filter((w) => w.path.endsWith('/response'))).toHaveLength(1);
    await expect(page.locator('body')).not.toContainText(/Recorded under your name/);
  });

  test('a 409 keeps the entries and shows the stale notice', async ({ page }) => {
    await page.route('**/api/v1/tasks/T-3703/response', (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '409' } }));
    await page.goto('/work/W-3703');
    await loaded(page);
    await fillReply(page);
    await replyPanel(page).getByRole('button', { name: 'Record reply' }).click();
    await expect(page.getByText(/This changed while you were recording/)).toBeVisible();
    await expect(replyPanel(page).getByLabel('Gaps', { exact: true })).toHaveValue(GAPS.join('\n'));
    await expect(page.locator('body')).not.toContainText(/Recorded under your name/);
  });

  test('a 403 on the write shows the not-open view and nothing reads as recorded', async ({ page }) => {
    await page.route('**/api/v1/tasks/T-3703/response', (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '403' } }));
    await page.goto('/work/W-3703');
    await loaded(page);
    await fillReply(page);
    await replyPanel(page).getByRole('button', { name: 'Record reply' }).click();
    await expect(page.getByText('You can’t open this work item')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(/Recorded under your name|Femi Ojo/);
  });

  test('the ceo persona is not on P-0101’s list: the Delivery tab is the no-access view with no handover text', async ({ page, context }) => {
    await context.addCookies([{ name: 'psl_mock_persona', value: 'ceo', url: test.info().project.use.baseURL! }]);
    await page.goto('/projects/P-0101/delivery');
    await expect(page.getByText('You can’t open this project')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(/Handover to Support|HND-0048|Femi Ojo/);
  });
});
