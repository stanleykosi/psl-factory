import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

// F-18: team input, the RFP outcome form and its recorded states, on the contract mock (D-RFP-OUTCOME r2, proposed).
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** A date field takes "11 Nov 2026"; a when field also has its time (WAT) beside it. */
async function fillWhen(page: Page, label: string | RegExp, value: string) {
  const [date, time] = value.split('T');
  const [y, m, d] = date.split('-');
  const box = page.getByLabel(label, { exact: typeof label === 'string' }).first();
  await box.fill(`${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`);
  await box.blur();
  if (time) await page.locator('.resp-when', { has: box }).getByLabel('At (WAT)').fill(time);
}

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const TEAM = '/work/W-2101/respond?task=T-2101';
const OUTCOME = '/work/W-2103/outcome';

test.use({ timezoneId: 'Africa/Lagos' });

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function open(page: Page, path: string) {
  await page.goto(path);
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
}

const file = (name: string, size: number) => ({ name, mimeType: 'application/pdf', buffer: Buffer.alloc(size, 37) });

async function chooseResult(page: Page, result: string) {
  await page.getByRole('radio', { name: result, exact: true }).click();
}

test.beforeEach(async ({ request, context, baseURL }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
});

type State = { name: string; path: string; note?: string; title: { desktop: string; phone: string }; reach?: (page: Page) => Promise<unknown> };
const STATES: State[] = [
  { name: 'team input W-2101', path: TEAM, title: { desktop: 'Tamarind Loans · loan origination RFP', phone: 'Record team input' } },
  ...(['Won', 'Lost', 'Pending', 'Unknown'] as const).map((result) => ({
    name: `outcome form ${result}`,
    path: OUTCOME,
    note: 'OUTCOME',
    title: { desktop: 'Tamarind Loans · loan origination RFP', phone: 'Record the outcome' },
    reach: (page: Page) => chooseResult(page, result),
  })),
  ...([
    ['W-2105', 'WON', 'Won'],
    ['W-2106', 'LOST', 'Lost'],
    ['W-2107', 'PENDING', 'Decision pending'],
    ['W-2108', 'UNKNOWN', 'Outcome unknown'],
    ['W-2114', 'UNKNOWN', 'Outcome unknown'],
  ] as const).map(([id, note, word]) => ({
    name: `recorded ${id}`,
    path: `/work/${id}/outcome`,
    note,
    title: { desktop: 'Tamarind Loans · loan origination RFP', phone: word },
  })),
  { name: 'not open W-2109', path: '/work/W-2109/outcome', title: { desktop: 'Tamarind Loans · loan origination RFP', phone: 'Record the outcome' } },
];

for (const viewport of [DESKTOP, PHONE]) {
  for (const state of STATES) {
    test(`axe, title and bar: ${state.name} at ${viewport.width}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await open(page, state.path);
      await state.reach?.(page);
      await expectNoAxeViolations(page);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
      const h1 = page.locator('h1');
      await expect(h1).toHaveCount(1);
      const phone = viewport === PHONE;
      await expect(h1).toHaveText(phone ? state.title.phone : state.title.desktop);
      expect(await h1.evaluate((el) => getComputedStyle(el).fontSize)).toBe(phone ? '26px' : '34px');
      await expect(h1).toHaveClass(/cmp-page-title/);
      const back = page.locator('.psl-phonebar').getByRole('link', { name: 'Back to RFP' });
      if (phone) {
        await expect(back).toHaveText('← RFP');
        await expect(back).toHaveAttribute('href', state.path.split('/').slice(0, 3).join('/'));
        if (state.note) await expect(page.locator('.psl-phonebar .shell-phonenote')).toHaveText(state.note);
        else await expect(page.locator('.psl-phonebar .shell-phonenote')).toHaveCount(0);
        await expect(page.getByRole('navigation', { name: 'RFP' })).toHaveCount(0);
      } else {
        await expect(back).toBeHidden();
      }
      await expect(page.locator('main').getByRole('link', { name: /^← / })).toHaveCount(0);
    });
  }
}

test('the 403/404 page has one h1 and names nothing about the item', async ({ page }) => {
  await open(page, '/work/W-1099/outcome');
  await expect(page.locator('h1')).toHaveCount(1);
  await expect(page).toHaveTitle('Record the outcome · PSL Factory');
  expect(await page.locator('main').innerText()).not.toContain('W-1099');
  expect(await page.locator('.psl-phonebar, nav[aria-label="Main"]').allInnerTexts()).not.toContain('W-1099');
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

test('the frame tabs: only built screens are in the Tab order; the current tab is marked', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await open(page, OUTCOME);
  const nav = page.getByRole('navigation', { name: 'RFP' });
  await expect(nav.getByRole('link')).toHaveCount(1);
  await expect(nav.getByRole('link', { name: /Team input/ })).toHaveAttribute('href', '/work/W-2103');
  await expect(nav.locator('[aria-current="page"]')).toHaveText('Outcome');
  await page.locator('.rfp-eyebrow').click();
  const focused: string[] = [];
  for (let i = 0; i < 3; i++) {
    await page.keyboard.press('Tab');
    focused.push(await page.evaluate(() => document.activeElement?.textContent ?? ''));
  }
  expect(focused[0]).toBe('Team input4/4');
  expect(focused.some((t) => /Requirements|Pricing|Submission/.test(t))).toBe(false);
});

test('team input Tab order is Team, the fields, Proof and its confirmation, Received and the note, each with a focus ring', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await open(page, TEAM);
  await page.getByRole('radio', { name: 'Security' }).click();
  await page.getByRole('heading', { level: 1 }).click();
  const order = [
    page.getByRole('radio', { name: 'Security' }),
    page.getByLabel('Estimate (person-days)'),
    page.getByLabel('What they gave'),
    page.locator('input[type="file"]').first(),
    page.getByRole('checkbox'),
    page.getByLabel('Received'),
    page.getByLabel(/^Note/),
  ];
  for (const target of order) {
    expect(await tabTo(page, target)).toBeLessThanOrEqual(8);
    expect(await ring(target)).toBe(true);
  }
});

test('team input records through the mock: claim, proof, record, success', async ({ page }) => {
  await open(page, TEAM);
  await page.getByRole('radio', { name: 'Security' }).click();
  await page.getByLabel('Estimate (person-days)').fill('18');
  await page.getByLabel('What they gave').fill('Security estimate and data-protection notes');
  await page.locator('input[type="file"]').setInputFiles(file('security-estimate-tamarind.xlsx', 64 * 1024));
  await expect(page.getByText('Uploaded · 64 KB')).toBeVisible();
  await fillWhen(page, 'Received', '2026-11-12T15:10');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Record input' }).click();
  await expect(page.getByText('Response recorded.')).toBeVisible();
});

test('at 390 the pinned Record is on screen, the size of F-09’s, and targets are at least 44px', async ({ page }) => {
  await page.setViewportSize(PHONE);
  for (const [path, label, reach] of [
    [TEAM, 'Record input', async () => {}],
    [OUTCOME, 'Record won', () => chooseResult(page, 'Won')],
  ] as const) {
    await open(page, path);
    await reach();
    const record = page.getByRole('button', { name: label });
    await expect(record).toBeInViewport();
    const box = (await record.boundingBox())!;
    expect(box.height).toBe(50);
    expect(box.width).toBeGreaterThanOrEqual(PHONE.width - 40);
    for (const radio of await page.locator('.resp-segbar [role="radio"]').all()) expect((await radio.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  }
});

test('nothing animates with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await open(page, OUTCOME);
  await chooseResult(page, 'Lost');
  await page.getByRole('radio', { name: 'Price' }).click();
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBe(0);
});

test('the outcome records through the mock and shows the recorded state; the work item links into it', async ({ page }) => {
  await open(page, '/work/W-2103');
  await page.getByRole('link', { name: 'Record the outcome' }).click();
  await expect(page).toHaveURL(/\/work\/W-2103\/outcome$/);
  await expect(page.getByRole('radiogroup', { name: 'Result' })).toBeVisible();
  await chooseResult(page, 'Pending');
  await fillWhen(page, 'When you learned it', '2026-12-01T15:20');
  await page.locator('input[type="file"]').setInputFiles(file('tamarind-email-decision-delayed.pdf', 42 * 1024));
  await expect(page.getByText('Uploaded · 42 KB')).toBeVisible();
  await page.getByRole('combobox', { name: 'You are recording as' }).click().then(() => page.getByRole('option').first().click());
  await page.getByRole('button', { name: 'Record pending' }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'Decision pending' })).toBeVisible();
});

test('the follow-up Edit and Send are reached by keyboard, and Send goes through the mock once', async ({ page }) => {
  let sent = 0;
  await page.route('**/rfp-outcome/followup', async (route) => {
    sent += 1;
    await route.continue();
  });
  await page.setViewportSize(DESKTOP);
  await open(page, '/work/W-2108/outcome');
  const send = page.getByRole('button', { name: 'Send follow-up' });
  const edit = page.getByRole('button', { name: 'Edit' });
  await page.getByRole('heading', { level: 2, name: 'Outcome unknown' }).click();
  expect(await tabTo(page, send)).toBeLessThanOrEqual(12);
  expect(await ring(send)).toBe(true);
  expect(await tabTo(page, edit)).toBe(1);
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Enter');
  await expect(page.getByText(/^Sent /)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send follow-up' })).toHaveCount(0);
  expect(sent).toBe(1);
});
