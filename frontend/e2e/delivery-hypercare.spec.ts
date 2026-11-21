import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';
import { fillWhen } from './controls';

// F-34 (contract mock only): the hypercare work item (SCR-46) at 1440 and 390: axe, touch targets, one column, and the
// record-release and log-observation writes with their recorded requests. Nothing here deploys, evaluates or qualifies anything.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

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
const proof = { name: 'release-1.0.0-log.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n') };

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

    test('the Delivery tab links Hypercare to W-3101', async ({ page }) => {
      await page.goto('/projects/P-0101/delivery');
      await loaded(page);
      await expect(page.getByRole('link', { name: 'Hypercare' }).first()).toHaveAttribute('href', '/work/W-3101');
    });

    for (const id of ['W-3101', 'W-3102', 'W-3103', 'W-3104', 'W-3109', 'W-3111']) {
      test(`${id}: one column, no sideways scroll, controls 44px, no axe violations`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        expect(await noHorizontalScroll(page)).toBe(true);
        if (phone) await expectTouchTargets(await page.locator('main a.psl-btn, main button').all());
        if (id === 'W-3103') await expect(page.locator('.ws button')).toHaveCount(0);
        if (id === 'W-3109') {
          const control = page.getByRole('button', { name: 'Log an observation' });
          await expect(control).toHaveAttribute('aria-disabled', 'true');
          await expect(control).toHaveAttribute('aria-describedby', /.+/);
        }
        await expectNoAxeViolations(page);
      });
    }

    test('W-3102 with the record form open: 44px controls, a labelled proof, no axe violations, focus on the heading, back to the button on Cancel', async ({ page }) => {
      await page.goto('/work/W-3102');
      await loaded(page);
      await page.getByRole('button', { name: 'Record release' }).click();
      const form = page.getByRole('form');
      await expect(form).toBeVisible();
      await expect(form.getByRole('heading', { name: 'Record release' })).toBeFocused();
      await fillWhen(form, 'Released on', '2026-04-01T22:00');
      await form.locator('input[type="file"]').setInputFiles(proof);
      await expect(form.getByText(/release-1.0.0-log.pdf/)).toBeVisible();
      if (phone) {
        await expectTouchTargets(await form.locator('button, input:not([type="file"])').all());
        const box = (await form.locator('.resp-chip__remove').boundingBox())!;
        expect([box.width >= 44, box.height >= 44]).toEqual([true, true]);
      }
      expect(await noHorizontalScroll(page)).toBe(true);
      await expectNoAxeViolations(page);
      await form.getByRole('button', { name: 'Cancel' }).click();
      await expect(page.getByRole('button', { name: 'Record release' })).toBeFocused();
    });

    test('the no-access view has no axe violations', async ({ page }) => {
      await page.goto('/work/W-1099');
      await expect(page.getByText('You can’t open this work item')).toBeVisible();
      await expectNoAxeViolations(page);
    });
  });
}

test.describe('the writes', () => {
  test.use({ viewport: DESKTOP });

  test('Record release: blank date and no proof send nothing; then one upload and one step; the re-read is the hold', async ({ page }) => {
    const writes = record(page);
    await page.goto('/work/W-3102');
    await loaded(page);
    await page.getByRole('button', { name: 'Record release' }).click();
    const form = page.getByRole('form');
    await expect(form.getByLabel(/Version/)).toHaveValue('Build 1.0.0');
    await expect(form.getByLabel(/Environment/)).toHaveValue('Production · Lagoon Health');
    await expect(page.getByText(/the hypercare window starts from the release date/).first()).toBeVisible();
    await form.getByRole('button', { name: 'Record release' }).click();
    expect(writes).toHaveLength(0);
    await fillWhen(form, 'Released on', '2026-04-01T22:00');
    await form.getByRole('button', { name: 'Record release' }).click();
    expect(writes).toHaveLength(0);
    await form.locator('input[type="file"]').setInputFiles(proof);
    await expect.poll(() => writes.length).toBe(1);
    expect(writes[0]).toMatchObject({ path: '/api/v1/cases/P-0101/evidence', body: { kind: 'deployment_log', case_revision: 2 }, csrf: 'mock-csrf-pm' });
    await form.getByRole('button', { name: 'Record release' }).click();
    await expect(page.getByText('Setup needed', { exact: true }).first()).toBeVisible();
    expect(writes).toHaveLength(2);
    expect(writes[1]).toMatchObject({ path: '/api/v1/work/W-3102/steps', csrf: 'mock-csrf-pm' });
    expect(writes[1].body).toMatchObject({ step: 'record_release', expected_revision: 1, evidence_ids: [expect.any(String)], inputs: { version: 'Build 1.0.0', environment: 'Production · Lagoon Health' } });
    expect(writes[1].body.idempotency_key).toBeTruthy();
    await expect(page.locator('.ws button')).toHaveCount(0);
    const log = await (await page.request.get(`${MOCK}/__mock/workspace-log`)).json();
    expect(Object.values(log.sends)).toEqual([1]);
  });

  test('a network failure on the step shows the failed message, never Done, and the form is still the record', async ({ page }) => {
    await page.route('**/api/v1/work/W-3102/steps', (route) => route.abort('failed'));
    await page.goto('/work/W-3102');
    await loaded(page);
    await page.getByRole('button', { name: 'Record release' }).click();
    const form = page.getByRole('form');
    await fillWhen(form, 'Released on', '2026-04-01T22:00');
    await form.locator('input[type="file"]').setInputFiles(proof);
    await expect(form.getByText(/release-1.0.0-log.pdf/)).toBeVisible();
    await form.getByRole('button', { name: 'Record release' }).click();
    await expect(page.getByText('We couldn’t confirm this step. Check the page before trying again.')).toBeVisible();
    await expect(page.locator('.ws-notices').getByText(/Done:/)).toHaveCount(0);
    await expect(page.getByText('Hypercare · release not recorded').first()).toBeVisible();
  });

  test('Log an observation: blank sends nothing; with text one step goes and the re-read shows OBS-0013', async ({ page }) => {
    const writes = record(page);
    await page.goto('/work/W-3101');
    await loaded(page);
    await page.getByRole('button', { name: 'Log an observation' }).click();
    const form = page.getByRole('form');
    await form.getByRole('button', { name: 'Log an observation' }).click();
    expect(writes).toHaveLength(0);
    await form.getByLabel(/What did you notice/).fill('Checkout page slow once on day 10');
    await form.getByRole('button', { name: 'Log an observation' }).click();
    await expect(page.getByText('OBS-0013')).toBeVisible();
    expect(writes).toHaveLength(1);
    expect(writes[0].body).toMatchObject({ step: 'log_observation', inputs: { what: 'Checkout page slow once on day 10' } });
    expect(writes[0].body).not.toHaveProperty('evidence_ids');
  });
});
