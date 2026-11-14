import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
}

/** Opens a decision and, when it is actionable, waits for the claim to enable Approve. */
async function openDecision(page: Page, id: string, task: string) {
  await page.goto(`/work/${id}/decide?task=${task}`);
  await loaded(page);
  await expect(page).toHaveTitle('Decision · PSL Factory');
  const approve = page.getByRole('button', { name: /^Approve v/ });
  if (await approve.count()) await expect(approve).toBeEnabled();
}

/** Tabs forward until the target has keyboard focus. */
async function tabTo(page: Page, target: Locator) {
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((el) => el === document.activeElement)) return;
  }
  throw new Error('target never received focus');
}

const focusRing = (target: Locator) =>
  target.evaluate((el) => {
    const s = getComputedStyle(el);
    return { focused: el === document.activeElement, style: s.outlineStyle, width: s.outlineWidth };
  });

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

/**
 * Decide fails in the network and every item read fails until the returned switch is turned off. The decide
 * never reaches the mock, so its state is untouched; the failed reads are 503s from the browser route.
 */
async function reachUnconfirmed(page: Page) {
  const state = { down: false };
  await page.route('**/api/v1/tasks/T-1201/decision', (route) => {
    state.down = true;
    return route.abort('failed');
  });
  await page.route('**/api/v1/work/W-1201', (route) =>
    state.down ? route.fulfill({ status: 503, contentType: 'application/json', body: '{"code":"server_error","message":"Down."}' }) : route.continue(),
  );
  await openDecision(page, 'W-1201', 'T-1201');
  await page.getByRole('button', { name: 'Approve v2' }).click();
  await expect(page.getByText('We couldn’t confirm whether your decision was recorded.')).toBeVisible();
  return state;
}

const STATES: [string, (page: Page) => Promise<unknown>][] = [
  ['default W-1201', (page) => openDecision(page, 'W-1201', 'T-1201')],
  [
    'done after approving W-1201',
    async (page) => {
      await openDecision(page, 'W-1201', 'T-1201');
      await page.getByRole('button', { name: 'Approve v2' }).click();
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Invoice v2 is approved');
      await expect(page.getByText('Chidi issues invoice v2 and emails it to Lagoon Health.')).toBeVisible();
    },
  ],
  [
    'stale W-1207 after Approve',
    async (page) => {
      await openDecision(page, 'W-1207', 'T-1207');
      await page.getByRole('button', { name: 'Approve v2' }).click();
      await expect(page.getByText('A newer version arrived while you were reading.')).toBeVisible();
    },
  ],
  ['unconfirmed W-1201 (decide and reload both failed)', reachUnconfirmed],
  ['not-yours W-1203', (page) => openDecision(page, 'W-1203', 'T-1203')],
  ['own W-1204', (page) => openDecision(page, 'W-1204', 'T-1204')],
];

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    for (const [name, reach] of STATES) {
      test(`${name} has no axe violations and no sideways page scroll`, async ({ page }) => {
        await reach(page);
        await page.screenshot({ path: test.info().outputPath(`${name.replace(/\W+/g, '_')}.png`), fullPage: true });
        await expectNoAxeViolations(page);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
      });
    }
  });
}

test('at 390 the action bar is pinned in view with 44px targets', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await openDecision(page, 'W-1201', 'T-1201');
  const bar = page.locator('.psl-actionbar');
  const box = (await bar.boundingBox())!;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(PHONE.height + 0.5);
  expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
  for (const name of ['Approve v2', 'Return', 'Reject']) {
    const b = (await bar.getByRole('button', { name }).boundingBox())!;
    expect(b.height).toBeGreaterThanOrEqual(44);
    expect(b.y + b.height).toBeLessThanOrEqual(PHONE.height);
  }
  await expect(bar.getByText('Approving earns APPROVED only. Issue is the next station.')).toBeVisible();
  // the note stays in the content, above the bar
  expect(await bar.locator('textarea').count()).toBe(0);
  await expect(page.getByText('Station 4 of 7 · Finance review · only a Finance Lead can decide')).toBeVisible();
  await expect(page.getByRole('list', { name: 'Facts' })).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('at 390 Approve is the 54px action-blue phone footer button', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await openDecision(page, 'W-1201', 'T-1201');
  const approve = page.locator('.psl-actionbar').getByRole('button', { name: 'Approve v2' });
  expect((await approve.boundingBox())!.height).toBeGreaterThanOrEqual(54);
  // toHaveCSS retries, so the check waits for the colour transition to settle.
  await expect(approve).toHaveCSS('background-color', 'rgb(36, 89, 214)');
});

test('the approve done view has the green success banner; return has the neutral one', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openDecision(page, 'W-1201', 'T-1201');
  await expect(page.getByRole('button', { name: 'Approve v2' })).toHaveCSS('background-color', 'rgb(36, 89, 214)');
  await page.getByRole('button', { name: 'Approve v2' }).click();
  const banner = page.locator('.decide-banner');
  await expect(banner.getByRole('heading', { level: 1 })).toHaveText('Invoice v2 is approved');
  await expect(banner).toHaveCSS('background-color', 'rgb(221, 239, 227)');
  await expect(banner.getByText(/^YOU APPROVED · \d\d:\d\d$/)).toHaveCSS('color', 'rgb(22, 80, 47)');
  await expect(banner.getByRole('heading', { level: 1 })).toHaveCSS('color', 'rgb(22, 80, 47)');

  await page.request.post(`${MOCK}/__mock/reset`);
  await openDecision(page, 'W-1201', 'T-1201');
  await page.getByLabel(/^Note/).fill('Wrong PO');
  await page.getByRole('button', { name: 'Return' }).click();
  await expect(banner.getByRole('heading', { level: 1 })).toHaveText('Invoice v2 was returned');
  await expect(banner).toHaveCSS('background-color', 'rgb(226, 229, 224)');
});

test('decide and reload both fail: the controls stay off and Try again only re-reads the item', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.method() === 'POST') writes.push(new URL(r.url()).pathname);
  });
  const state = await reachUnconfirmed(page);
  for (const name of ['Approve v2', 'Return', 'Reject']) await expect(page.getByRole('button', { name })).toBeDisabled();
  await expect(page.getByText(/We’ve reloaded this item/)).toHaveCount(0);
  // Still down: Try again reads, fails, and the controls stay off.
  const read = page.waitForResponse((r) => r.url().endsWith('/api/v1/work/W-1201') && r.request().method() === 'GET');
  await page.getByRole('button', { name: 'Try again' }).click();
  expect((await read).status()).toBe(503);
  await expect(page.getByRole('button', { name: 'Try again' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Approve v2' })).toBeDisabled();
  // Back up: the task is still open at the claimed revision, so the controls return for a deliberate tap.
  state.down = false;
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('button', { name: 'Approve v2' })).toBeEnabled();
  await expect(page.getByText('We couldn’t confirm whether your decision was recorded.')).toHaveCount(0);
  expect(writes).toEqual(['/api/v1/tasks/T-1201/claim', '/api/v1/tasks/T-1201/decision']);
});

test('at 1440 the panel is a right-hand column beside the decision', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openDecision(page, 'W-1201', 'T-1201');
  const panel = (await page.getByRole('region', { name: 'Your decision' }).boundingBox())!;
  const rows = (await page.getByRole('list', { name: 'Facts' }).boundingBox())!;
  expect(panel.x).toBeGreaterThan(rows.x + rows.width - 1);
  await expect(page.getByRole('list', { name: 'Facts' })).toBeVisible();
});

for (const [label, viewport] of [
  ['desktop', DESKTOP],
  ['phone', PHONE],
] as const) {
  test(`${label}: Tab reaches Note, Approve, Return and Reject in order with a visible focus ring`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await openDecision(page, 'W-1201', 'T-1201');
    const order = [
      page.getByLabel(/^Note/),
      page.getByRole('button', { name: 'Approve v2' }),
      page.getByRole('button', { name: 'Return' }),
      page.getByRole('button', { name: 'Reject' }),
    ];
    await tabTo(page, order[0]);
    for (const [i, target] of order.entries()) {
      if (i > 0) await page.keyboard.press('Tab');
      expect(await focusRing(target)).toEqual({ focused: true, style: 'solid', width: '2px' });
    }
  });
}

test('with reduced motion nothing animates', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize(PHONE);
  await openDecision(page, 'W-1201', 'T-1201');
  await page.getByRole('button', { name: 'Return' }).hover();
  const moving = await page.evaluate(() =>
    [...document.querySelectorAll('*')].filter((el) => {
      const s = getComputedStyle(el);
      const seconds = (v: string) => Math.max(...v.split(',').map((d) => parseFloat(d) || 0));
      return (s.animationName !== 'none' && seconds(s.animationDuration) > 0) || seconds(s.transitionDuration) > 0;
    }).length,
  );
  expect(moving).toBe(0);
});

test('stale flow on the mock: one decide, then Review version 3 claims revision 5', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  const writes: { url: string; body: string | null }[] = [];
  page.on('request', (r) => {
    if (r.method() === 'POST') writes.push({ url: new URL(r.url()).pathname, body: r.postData() });
  });
  await openDecision(page, 'W-1207', 'T-1207');
  await page.getByRole('button', { name: 'Approve v2' }).click();
  await expect(page.getByText('Version 3 was drafted at 12 Nov 10:46.')).toBeVisible();
  await expect(page.getByText('Version 2 can no longer be approved.')).toBeVisible();
  const current = page.getByRole('region', { name: 'VERSION 3 · CURRENT' });
  await expect(page.getByRole('region', { name: 'VERSION 2 · REPLACED' })).toBeVisible();
  await expect(current.getByText('billing@lagoonhealth.example · changed')).toBeVisible();
  await expect(current.getByText('₦4,250,000.00 · unchanged')).toBeVisible();
  await page.getByRole('button', { name: 'Review version 3' }).click();
  await expect(page.getByRole('button', { name: 'Approve v3' })).toBeEnabled();
  expect(writes).toEqual([
    { url: '/api/v1/tasks/T-1207/claim', body: '{"expected_revision":4}' },
    { url: '/api/v1/tasks/T-1207/decision', body: '{"expected_revision":4,"verdict":"approve"}' },
    { url: '/api/v1/tasks/T-1207/claim', body: '{"expected_revision":5}' },
  ]);
});
