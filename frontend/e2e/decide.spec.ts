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

const STATES: [string, (page: Page) => Promise<void>][] = [
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
