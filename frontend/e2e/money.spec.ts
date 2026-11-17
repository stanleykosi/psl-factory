import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// F-26 Money tab (SCR-12) against the contract mock at 390 and 1440, axe WCAG 2.2 AA. Every request the page makes
// goes to the app's /api/v1, which the app proxies to the mock (MOCK_PORT); nothing reaches a real backend.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const panel = (page: Page) => page.getByRole('tabpanel', { name: 'Money' });
const rows = (page: Page) => panel(page).locator('tbody tr');
const cards = (page: Page) => panel(page).locator('.money__card');

/** Records every request the page makes to an API path. */
function apiCalls(page: Page) {
  const seen: URL[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/')) seen.push(url);
  });
  return seen;
}

async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.locator('.psl-loading')).toHaveCount(0);
}

async function expectTouchTargets(targets: Locator[]) {
  for (const target of targets) {
    const box = (await target.boundingBox())!;
    expect(box.height, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
    expect(box.width, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
  }
}

test.beforeEach(async ({ context }) => {
  await setCookies(context, { psl_mock_persona: 'finance_lead' });
});

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;
  const w = viewport.width;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    test('P-0101 board rows from data: four stages, amounts, invoice, paid, the note and the time', async ({ page }) => {
      const calls = apiCalls(page);
      await page.goto('/projects/P-0101/money');
      await loaded(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Lagoon Health · patient app');
      await expect(panel(page).getByRole('heading', { level: 2 })).toHaveText('Lagoon Health · billing by contract stage');
      if (phone) {
        await expect(cards(page)).toHaveCount(4);
        await expect(cards(page).locator('.money__stage')).toHaveText(['Stage 1 · kick-off', 'Stage 2 · UAT', 'Stage 3 · go-live', 'Stage 4 · hypercare']);
        await expect(cards(page).nth(3)).toContainText('UnknownNot yet due · amount set at go-live');
        await expect(panel(page).getByText('Paid · Finance tracks')).toHaveCount(1);
        await expect(cards(page).nth(0)).toContainText('Paid · Finance tracks');
        const hint = panel(page).getByText('Tap an amount to see where it comes from');
        await expect(hint).toBeVisible();
        await expect(hint.locator('a')).toHaveCount(0);
        await expect(page.getByRole('complementary')).toHaveCount(0);
        await expectTouchTargets([...(await cards(page).locator('a').all())]);
      } else {
        await expect(rows(page)).toHaveCount(4);
        await expect(panel(page).locator('tfoot')).toHaveCount(0);
        await expect(rows(page).locator('td:nth-child(2)')).toHaveText(['₦3,000,000.00', '₦4,250,000.00', '₦4,250,000.00', 'UnknownNot yet due · amount set at go-live']);
        // textContent: the hidden reference and "No invoice" / "Not due" are part of each cell's text for screen readers.
        await expect(rows(page).locator('td:nth-child(3)')).toHaveText(['Verified 03 Nov, INV-0398', 'Awaiting Finance decision, INV-0412', 'Held · owner needed, INV-0419', '—No invoice']);
        await expect(rows(page).locator('td:nth-child(4)')).toHaveText(['Finance tracks', '—Not due', '—Not due', '—Not due']);
        await expect(page.getByRole('complementary', { name: 'Choose an amount to see where it comes from.' })).toBeVisible();
        await expect(rows(page).nth(0).getByRole('link', { name: /^Verified 03 Nov ?, INV-0398$/ })).toHaveAttribute('href', '/work/W-1713');
      }
      await expect(panel(page).locator('.psl-unknown')).toHaveText(['Unknown']);
      await expect(panel(page).locator('.money__asof')).toHaveText('As of 12 Nov 16:40');
      const text = await panel(page).innerText();
      expect(text).not.toMatch(/₦0(?![\d,.])|(?<![\d,])0\.00|NaN/);
      expect(text).not.toMatch(/total|outstanding|balance/i);
      expect(await noHorizontalScroll(page)).toBe(true);
      expect(calls.map((u) => `${u.host}${u.pathname}`)).toEqual(
        expect.arrayContaining([`localhost:${new URL(page.url()).port}/api/v1/projects/P-0101/money`, `localhost:${new URL(page.url()).port}/api/v1/reports/R-0101`]),
      );
      expect(calls.every((u) => u.host === new URL(page.url()).host)).toBe(true);
      await shot(page, `money-default-${w}`);
      await expectNoAxeViolations(page);
    });

    test('deep link ?figure=FIG-0101-S2 opens Stage 2 with its three sources; a reload keeps it', async ({ page }) => {
      await page.goto('/projects/P-0101/money?figure=FIG-0101-S2');
      await loaded(page);
      const surface = phone ? page.getByRole('dialog', { name: 'Where ₦4,250,000.00 comes from' }) : page.getByRole('complementary', { name: /^Where ₦4,250,000\.00 comes from ?, Stage 2 · UAT amount$/ });
      await expect(surface).toBeVisible();
      await expect(surface.locator('ol > li')).toHaveText([
        'Signed SOW v2, stage table, row 2 SOW-0198 v2',
        'Stage terms v1, active since 30 Jun RULE · stage terms',
        'Milestone 2 completion, recorded by Tunde Bello HB-M2',
      ]);
      await expect(surface.locator('ol a')).toHaveCount(0);
      await expect(surface.getByRole('link', { name: 'Ask me' })).toHaveAttribute('href', '/assistant?agent=chidi');
      if (!phone) await shot(page, `money-figure-${w}`);
      await page.reload();
      await loaded(page);
      await expect(surface).toBeVisible();
      await expect(surface.locator('ol > li')).toHaveCount(3);
      if (phone) await shot(page, `money-sheet-${w}`);
      await expectNoAxeViolations(page);
    });

    test('P-0102 edges, P-0103 report failure and P-0105 empty pass axe with no sideways scroll', async ({ page }) => {
      for (const path of ['/projects/P-0102/money', '/projects/P-0102/money?figure=FIG-0102-S1', '/projects/P-0103/money', '/projects/P-0105/money']) {
        await page.goto(path);
        await loaded(page);
        if (path.includes('P-0105')) await expect(panel(page).getByRole('heading', { level: 2, name: 'No contract stages yet' })).toBeVisible();
        if (path.includes('FIG-0102-S1')) await expect(page.getByText('These figures differ: the table shows ₦2,500,000.00; the report shows ₦2,400,000.00.')).toBeVisible();
        if (path.includes('P-0103')) await expect(page.getByText('We couldn’t load where these figures come from.')).toBeVisible();
        expect(await noHorizontalScroll(page), path).toBe(true);
        await expectNoAxeViolations(page);
        if (path.includes('FIG')) await page.keyboard.press('Escape');
      }
    });

    test('money refused (P-0107 403, P-0108 404), pm on P-0104 and P-0099: no stage, no amount, no report read', async ({ page, context }) => {
      const calls = apiCalls(page);
      for (const id of ['P-0107', 'P-0108']) {
        await page.goto(`/projects/${id}/money`);
        await loaded(page);
        await expect(panel(page).getByText('You can’t see this project’s money.')).toBeVisible();
        const text = await page.locator('body').innerText();
        for (const word of ['Stage 1', '7,100,000', '₦', 'billing by contract stage', 'Your role does not allow this', 'We could not find that record']) expect(text).not.toContain(word);
        await expectNoAxeViolations(page);
      }
      await setCookies(context, { psl_mock_persona: 'pm' });
      for (const id of ['P-0104', 'P-0099']) {
        await page.goto(`/projects/${id}/money`);
        await loaded(page);
        await expect(page.getByText('You can’t open this project')).toBeVisible();
        expect(await page.locator('body').innerText()).not.toContain('₦');
      }
      expect(calls.filter((u) => u.pathname.startsWith('/api/v1/reports/'))).toEqual([]);
      expect(calls.filter((u) => /P-0104\/money|P-0099\/money/.test(u.pathname))).toEqual([]);
    });

    test('P-0103: Try again makes exactly one more report request and no money request', async ({ page }) => {
      const calls = apiCalls(page);
      await page.goto('/projects/P-0103/money');
      await loaded(page);
      // On phones the report's error sits under the cards (UX-1-1); on desktop in the aside.
      const surface = phone ? panel(page).locator('.money__cards ~ .money__explain') : page.getByRole('complementary');
      await expect(surface).toContainText('We couldn’t load where these figures come from. Your work is safe; nothing was changed.');
      await expect(rows(page).or(cards(page))).toHaveCount(4);
      await expect(panel(page).locator('a[href*="figure="]')).toHaveCount(0);
      const before = calls.length;
      await surface.getByRole('button', { name: 'Try again' }).click();
      await expect(surface).toContainText('We couldn’t load where these figures come from.');
      await expect.poll(() => calls.length).toBe(before + 1);
      expect(calls.slice(before).map((u) => u.pathname)).toEqual(['/api/v1/reports/R-0103']);
    });

    if (!phone) {
      test('press Stage 3: the URL is replaced, the aside shows its own sources, focus and aria-current stay, it is announced', async ({ page }) => {
        await page.goto('/projects/P-0101/money?figure=FIG-0101-S2');
        await loaded(page);
        const entries = await page.evaluate(() => window.history.length);
        const stage3 = rows(page).nth(2).getByRole('link', { name: '₦4,250,000.00' });
        await stage3.click();
        await expect(page).toHaveURL(/\/projects\/P-0101\/money\?figure=FIG-0101-S3$/);
        expect(await page.evaluate(() => window.history.length)).toBe(entries);
        const aside = page.getByRole('complementary', { name: /^Where ₦4,250,000\.00 comes from ?, Stage 3 · go-live amount$/ });
        await expect(aside.locator('ol > li')).toHaveText(['Signed SOW v2, stage table, row 3 SOW-0198 v2', 'Stage terms v1, active since 30 Jun RULE · stage terms', 'Go-live invoice, held for an owner INV-0419']);
        await expect(aside.getByRole('link', { name: 'Go-live invoice, held for an owner' })).toHaveAttribute('href', '/work/W-1714');
        await expect(stage3).toBeFocused();
        await expect(stage3).toHaveAttribute('aria-current', 'true');
        await expect(rows(page).nth(1).getByRole('link', { name: '₦4,250,000.00' })).not.toHaveAttribute('aria-current', 'true');
        await expect(panel(page).locator('[aria-live="polite"]')).toHaveText('Showing where ₦4,250,000.00 comes from');
        // Visible focus ring on the amount (keyboard focus).
        await page.keyboard.press('Shift+Tab');
        await page.keyboard.press('Tab');
        await expect(stage3).toBeFocused();
        const ring = await stage3.evaluate((el) => getComputedStyle(el).outlineStyle);
        expect(ring).not.toBe('none');
        await expectNoAxeViolations(page);
      });
    } else {
      test('press Stage 2: a bottom sheet with the same title and sources; Esc and Close drop figure and return focus', async ({ page }) => {
        await page.goto('/projects/P-0101/money');
        await loaded(page);
        const stage2 = cards(page).nth(1).getByRole('link', { name: '₦4,250,000.00' });
        await stage2.click();
        const sheet = page.getByRole('dialog', { name: 'Where ₦4,250,000.00 comes from' });
        await expect(sheet).toBeVisible();
        await expect(page).toHaveURL(/\?figure=FIG-0101-S2$/);
        await expect(sheet.locator('ol > li .money__ref')).toHaveText(['SOW-0198 v2', 'RULE · stage terms', 'HB-M2']);
        await expectNoAxeViolations(page);
        await page.keyboard.press('Escape');
        await expect(sheet).toHaveCount(0);
        await expect(page).toHaveURL(/\/projects\/P-0101\/money$/);
        await expect(stage2).toBeFocused();
        await stage2.click();
        await expect(sheet).toBeVisible();
        await sheet.getByRole('button', { name: 'Close' }).click();
        await expect(sheet).toHaveCount(0);
        await expect(page).toHaveURL(/\/projects\/P-0101\/money$/);
        await expect(stage2).toBeFocused();
      });
    }
  });
}
