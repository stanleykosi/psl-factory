import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const RESPOND = '/work/W-1601/respond?task=T-1601';

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
}

async function openForm(page: Page, path = RESPOND) {
  await page.goto(path);
  await loaded(page);
  await expect(page).toHaveTitle('Record a response · PSL Factory');
}

const pdf = (name: string, size: number) => ({ name, mimeType: 'application/pdf', buffer: Buffer.alloc(size, 37) });

async function fill(page: Page, { file = true, attest = true } = {}) {
  await page.getByRole('radio', { name: 'Approved' }).check();
  await page.getByLabel('When they responded').fill('2026-11-11T16:20');
  if (file) {
    await page.locator('input[type="file"]').setInputFiles(pdf('Lagoon_UAT_signoff_11Nov.pdf', 184 * 1024));
    await expect(page.getByText('Lagoon_UAT_signoff_11Nov.pdf · 184 KB')).toBeVisible();
  }
  if (attest) await page.getByRole('checkbox').check();
}

async function record(page: Page) {
  await page.getByRole('button', { name: 'Record response' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Response recorded.' })).toBeVisible();
}

test.beforeEach(async ({ request, context, baseURL }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
});

const STATES: [string, 'pm' | 'finance_lead', (page: Page) => Promise<unknown>][] = [
  ['W-1601 default', 'pm', (page) => openForm(page)],
  ['W-1601 validation', 'pm', async (page) => {
    await openForm(page);
    await fill(page, { file: false, attest: false });
    await expect(page.getByRole('alert').filter({ hasText: 'Add the proof and confirm it’s genuine to record this.' })).toBeVisible();
  }],
  ['W-1601 success', 'pm', async (page) => {
    await openForm(page);
    await fill(page);
    await record(page);
  }],
  ['W-1602 SOW signature', 'pm', (page) => openForm(page, '/work/W-1602/respond?task=T-1602')],
  ['W-1603 reconcile', 'finance_lead', async (page) => {
    await page.goto('/work/W-1603');
    await loaded(page);
    await expect(page.getByRole('radiogroup', { name: 'Confirm what happened' })).toBeVisible();
  }],
];

for (const viewport of [DESKTOP, PHONE]) {
  for (const [name, who, reach] of STATES) {
    test(`axe: ${name} at ${viewport.width}`, async ({ page, context, baseURL }) => {
      await context.addCookies([{ name: 'psl_mock_persona', value: who, url: baseURL! }]);
      await page.setViewportSize(viewport);
      await reach(page);
      await expectNoAxeViolations(page);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    });
  }
}

test('at 390 Record and "Record and continue" are on screen, at least 44px tall, and nothing scrolls sideways', async ({ page, context, baseURL }) => {
  await page.setViewportSize(PHONE);
  await openForm(page);
  await fill(page);
  const recordButton = page.getByRole('button', { name: 'Record response' });
  await expect(recordButton).toBeInViewport();
  expect((await recordButton.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  await page.goto('/work/W-1603');
  await loaded(page);
  await page.getByRole('radio', { name: /It didn’t arrive/ }).check();
  const go = page.getByRole('button', { name: 'Record and continue' });
  await expect(go).toBeInViewport();
  expect((await go.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

/** Tabs forward until the target has keyboard focus; returns how many presses it took. */
async function tabTo(page: Page, target: Locator) {
  for (let i = 1; i <= 60; i++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((el) => el === document.activeElement)) return i;
  }
  throw new Error('target never received focus');
}
const ring = (target: Locator) =>
  target.evaluate((el) => {
    const s = getComputedStyle(el);
    return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2;
  });

test('SCR-16 tab order is Who, When, the actions, Version, Note, the proof button, the attestation and Record, each with a focus ring', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openForm(page);
  await fill(page);
  await page.getByRole('heading', { level: 1 }).click();
  const order = [
    page.getByLabel('Who responded'),
    page.getByLabel('When they responded'),
    page.getByRole('radio', { name: 'Approved' }),
    page.getByLabel('For which version'),
    page.getByLabel(/^Note/),
    page.getByRole('button', { name: 'Add another file' }),
    page.getByRole('checkbox'),
    page.getByRole('button', { name: 'Record response' }),
  ];
  // Each next stop is reached within a few presses (the date field has an inner stop per part and a calendar button), never by wrapping round.
  for (const target of order) {
    expect(await tabTo(page, target)).toBeLessThanOrEqual(8);
    expect(await ring(target)).toBe(true);
  }
});

test('every radio group is named and nothing animates with reduced motion', async ({ page, context, baseURL }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openForm(page);
  await expect(page.getByRole('radiogroup', { name: 'What they did' })).toBeVisible();
  await page.getByRole('radio', { name: 'Approved' }).check();
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBe(0);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  await page.goto('/work/W-1603');
  await loaded(page);
  await expect(page.getByRole('radiogroup', { name: 'Confirm what happened' })).toBeVisible();
  await page.getByRole('radio', { name: /It arrived/ }).check();
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBe(0);
});

test('an uncertain record (record-then-fail) is re-read, shows the success view and is not sent again', async ({ page }) => {
  let sent = 0;
  await page.route('**/api/v1/tasks/T-1601/response', async (route) => {
    sent += 1;
    await route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': 'record-then-fail' } });
  });
  await openForm(page);
  await fill(page);
  await page.getByRole('button', { name: 'Record response' }).click();
  await expect(page.getByText('We couldn’t confirm your response was recorded. We’ve reloaded this item so you can see whether it was.')).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Response recorded.' })).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Client UAT response');
  expect(sent).toBe(1);
});

test('success at 390 shows the way back to the work item and the queue', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await openForm(page);
  await fill(page);
  await record(page);
  const back = page.locator('.psl-phonebar').getByRole('link', { name: 'Back to Work item' });
  await expect(back).toHaveText('← Work item');
  await expect(back).toHaveAttribute('href', '/work/W-1601');
  await expect(page.getByRole('button', { name: 'Menu' })).toHaveCount(0);
  await expect(page.locator('.resp-phoneref')).toHaveText('REL-0077');
  await expect(page.getByRole('link', { name: 'Back to my queue' })).toBeInViewport();
});

test('the work item links into the form and reconcile reloads the page after the answer', async ({ page, context, baseURL }) => {
  await page.goto('/work/W-1601');
  await loaded(page);
  await page.getByRole('link', { name: 'Record the client’s response' }).click();
  await expect(page).toHaveURL(/\/work\/W-1601\/respond\?task=T-1601$/);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  await page.goto('/work/W-1603');
  await loaded(page);
  await page.getByRole('radio', { name: /It didn’t arrive/ }).check();
  await page.getByRole('button', { name: 'Record and continue' }).click();
  await expect(page.getByRole('complementary', { name: 'Confirm what happened' })).toHaveCount(0);
  await expect(page.getByText('Processing', { exact: true }).first()).toBeVisible();
});

