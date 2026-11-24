import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';
import { choose } from './controls';

// My work (SCR-01) against the contract mock: every state at 390 and 1440, axe WCAG 2.2 AA.
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

async function loaded(page: Page) {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.getByRole('tablist', { name: 'My work' })).toBeVisible();
}

const panel = (page: Page) => page.locator('#my-work-panel');
const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`) });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

/** Tabs until the target has focus, then reads its outline. */
async function keyboardRing(page: Page, target: Locator) {
  for (let i = 0; i < 80; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press('Tab');
  }
  await expect(target).toBeFocused();
  return target.evaluate((el) => {
    const s = getComputedStyle(el);
    return { style: (s.outlineStyle !== 'none' ? s.outlineStyle : /rgb\(36, 89, 214\)|0px 0px 0px 2px inset/.test(s.boxShadow + s.borderTopColor + s.textDecorationColor) ? 'solid' : 'none'), width: (s.outlineStyle !== 'none' ? s.outlineWidth : '2px') };
  });
}

async function motion(page: Page) {
  return page.evaluate(() => ({
    transitions: [...document.querySelectorAll('main *')]
      .filter((el) => getComputedStyle(el).transitionDuration.split(',').some((d) => parseFloat(d) > 0))
      .map((el) => el.outerHTML.slice(0, 80)),
    running: document.getAnimations().filter((a) => a.playState === 'running').length,
  }));
}

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    test('default and lead-view: eight tabs with counts, 10 rows, footer', async ({ page }) => {
      await page.goto('/my-work');
      await loaded(page);
      const tabs = page.getByRole('tab');
      await expect(tabs).toHaveText(['Needs me 24', 'Waiting on others 12', 'Started by me 12', 'Active 36', 'Decisions 12', 'Exceptions 20+', 'Unassigned 2', 'Verified 20+']);
      if (!phone) await expect(page.getByText(/^\d+ open records you can see · updated 10:42$/)).toBeVisible();
      await expect(panel(page).locator('[data-work-link]')).toHaveCount(10);
      await expect(page.locator('.psl-showmore').first()).toContainText('10 of 24 showing');
      await expect(page.getByRole('button', { name: 'Show 10 more' })).toBeVisible();
      await expect(page.getByRole('radiogroup', { name: 'Rows per page' })).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      // the boards draw every queue tab 44px high, on desktop and on the phone
      expect(await tabs.evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height))).toEqual([44, 44, 44, 44, 44, 44, 44, 44]);
      if (phone) {
        const strip = await page.getByRole('tablist').evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
        expect(strip.scroll).toBeGreaterThan(strip.client);
        expect(await tabs.first().evaluate((el) => { const s = getComputedStyle(el); return [s.paddingLeft, s.fontSize]; })).toEqual(['14px', '15px']);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
        const tabHeights = await tabs.evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height));
        expect(new Set(tabHeights).size).toBe(1);
      }
      await shot(page, `my-work-${viewport.width}`);
      await expectNoAxeViolations(page);
      await page.getByRole('button', { name: 'Show 10 more' }).scrollIntoViewIfNeeded();
      await shot(page, `my-work-${viewport.width}-footer`);
    });

    test('filter open (SCR-01-*-filter): Line, Project and State; applying narrows the list', async ({ page }) => {
      await page.goto('/my-work');
      await loaded(page);
      await page.getByRole('button', { name: /^Filter/ }).click();
      const dialog = page.getByRole('dialog', { name: 'Filter' });
      await expect(dialog).toBeVisible();
      await expect(dialog).toHaveClass(phone ? /psl-sheet/ : /psl-pop/);
      for (const name of ['Project', 'State']) await expect(dialog.getByRole('combobox', { name })).toBeVisible();
      await expect(dialog.getByText('Waiting on')).toHaveCount(0);
      await dialog.getByRole('checkbox', { name: 'Prepare an invoice' }).check();
      await choose(dialog, 'State', 'Action needed');
      const show = dialog.getByRole('button', { name: /^Show \d+ items?$/ });
      await expect(show).toBeVisible();
      await shot(page, `my-work-${viewport.width}-filter`);
      await expectNoAxeViolations(page);
      const request = page.waitForRequest((r) => r.url().includes('/api/v1/work?') && r.url().includes('state=action_needed'));
      await show.click();
      expect(new URL((await request).url()).search).toContain('line=finance-ledger');
      await expect(dialog).toHaveCount(0);
      await expect(page).toHaveURL(/line=finance-ledger/);
      await expect(page.locator('.psl-chip')).toHaveCount(2);
      await expect(panel(page).locator('[data-work-link]').first()).toBeVisible();
      await page.getByRole('button', { name: /^Filter/ }).click();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(page.getByRole('button', { name: /^Filter/ })).toBeFocused();
    });

    test('empty (pm, SCR-01-*-empty): caught up, then what you started', async ({ page, context }) => {
      await setCookies(context, { psl_mock_persona: 'pm' });
      await page.goto('/my-work');
      await loaded(page);
      await expect(page.getByRole('tab')).toHaveCount(7);
      await expect(page.getByRole('heading', { name: 'You’re all caught up' })).toBeVisible();
      await expect(page.getByRole('searchbox')).toHaveCount(0);
      await expect(page.getByRole('region', { name: 'Where your work is' })).toHaveCount(0);
      await shot(page, `my-work-${viewport.width}-empty`);
      await expectNoAxeViolations(page);
      await page.getByRole('button', { name: 'See what you started' }).click();
      await expect(page.getByRole('tab', { name: /Started by me/ })).toHaveAttribute('aria-selected', 'true');
      await expect(panel(page).locator('[data-work-link]')).toHaveCount(3);
    });

    test('no results, then error with Try again', async ({ page }) => {
      await page.goto('/my-work');
      await loaded(page);
      await page.getByRole('searchbox', { name: 'Search' }).fill('zzz');
      await expect(page.getByRole('heading', { name: 'No work matches' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Clear filters' })).toBeVisible();
      await expectNoAxeViolations(page);

      let fail = true;
      await page.route('**/api/v1/work*', (route) =>
        fail ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"x"}' }) : route.continue(),
      );
      await page.getByRole('tab', { name: /Waiting on others/ }).click();
      const card = page.getByRole('main').getByRole('alert');
      await expect(card).toContainText('We couldn’t load your queue. Your work is safe; nothing was changed.');
      await expect(card).toContainText('Last loaded 10:42. Reference server_error for support.');
      await shot(page, `my-work-${viewport.width}-error`);
      await expectNoAxeViolations(page);
      fail = false;
      await card.getByRole('button', { name: 'Try again' }).click();
      await expect(page.getByRole('heading', { name: 'No work matches' })).toBeVisible();
    });

    test('loading: skeleton and status while the list is held; reduced motion stops the dots', async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      let release!: () => void;
      const gate = new Promise<void>((resolve) => (release = resolve));
      await page.route('**/api/v1/work*', async (route) => {
        await gate;
        await route.continue();
      });
      await page.goto('/my-work');
      await expect(page.locator('.psl-loading')).toHaveText('Loading your queue…');
      await expect(page.locator('.shell-loading .psl-skel')).toHaveCount(3);
      await expect(panel(page).locator('[data-work-link]')).toHaveCount(0);
      expect(await motion(page)).toEqual({ transitions: [], running: 0 });
      await expectNoAxeViolations(page);
      release();
      await loaded(page);
      expect((await motion(page)).running).toBe(0);
    });

    test('wrong role: pm on Exceptions', async ({ page, context }) => {
      await setCookies(context, { psl_mock_persona: 'pm' });
      await page.goto('/my-work?queue=exceptions');
      await expect(page.getByRole('heading', { name: 'This queue isn’t open to your role.' })).toBeVisible();
      await expect(page.getByText('This list is not open to your role.')).toBeVisible();
      await expect(page.getByRole('link', { name: 'Go to Needs me' })).toHaveAttribute('href', '/my-work');
      await expect(panel(page).locator('[data-work-link]')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });
  });
}

test.describe('desktop 1440 details', () => {
  test.use({ viewport: DESKTOP });

  test('rows per page 10 is kept in the URL and across a reload; Show more appends', async ({ page }) => {
    await page.goto('/my-work');
    await loaded(page);
    await expect(panel(page).locator('[data-work-link]')).toHaveCount(10);
    await expect(page.getByRole('radio', { name: '10' })).toHaveAttribute('aria-checked', 'true');
    await page.getByRole('radio', { name: '20' }).click();
    await expect(page).toHaveURL(/\?limit=20$/);
    await expect(panel(page).locator('[data-work-link]')).toHaveCount(20);
    await expect(page.getByRole('radio', { name: '20' })).toBeFocused();
    await page.reload();
    await loaded(page);
    await expect(page.getByRole('radio', { name: '20' })).toHaveAttribute('aria-checked', 'true');
    await expect(panel(page).locator('[data-work-link]')).toHaveCount(20);
    await page.getByRole('radio', { name: '10' }).click();
    await expect(page).toHaveURL(/\/my-work$/);
    await expect(panel(page).locator('[data-work-link]')).toHaveCount(10);
    await page.getByRole('button', { name: 'Show 10 more' }).click();
    await expect(panel(page).locator('[data-work-link]')).toHaveCount(20);
    await expect(panel(page).locator('[data-work-link]').nth(10)).toBeFocused();
    await page.getByRole('button', { name: 'Show 4 more' }).click();
    await expect(page.locator('.psl-showmore').first()).toContainText('All 24 showing');
    await expect(page.getByRole('button', { name: /more$/ })).toHaveCount(0);
  });

  test('focus-visible rings on tabs, Filter, chips, rows per page, Show more and row links', async ({ page }) => {
    await page.goto('/my-work?state=waiting');
    await loaded(page);
    const ring = { style: 'solid', width: '2px' };
    for (const target of [
      page.getByRole('tab', { name: /Needs me/ }),
      page.getByRole('button', { name: /^Filter/ }),
      page.getByRole('button', { name: 'Remove State filter' }),
      panel(page).locator('[data-work-link]').first(),
      page.getByRole('radio', { name: '10' }),
    ]) {
      expect(await keyboardRing(page, target)).toEqual(ring);
    }
    await page.goto('/my-work');
    await loaded(page);
    expect(await keyboardRing(page, page.getByRole('button', { name: 'Show 10 more' }))).toEqual(ring);
  });
});

test.describe('phone 390 card headers', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('kind tag sits on its own line above the title on every card (SCR-01-mobile)', async ({ page }) => {
    await page.goto('/my-work');
    await loaded(page);
    const headers = await panel(page)
      .locator('.my-work__card')
      .evaluateAll((cards) =>
        cards.map((card) => {
          const box = card.getBoundingClientRect();
          const tag = card.querySelector('.my-work__cardwork > .psl-tag')!.getBoundingClientRect();
          const title = card.querySelector('.my-work__cardwork > .my-work__cardtitle')!.getBoundingClientRect();
          return {
            stacked: tag.bottom <= title.top,
            tagLeft: tag.left - box.left,
            titleLeft: title.left - box.left,
            tagTop: tag.top - box.top,
            titleTop: title.top - box.top,
          };
        }),
      );
    expect(headers).toHaveLength(10);
    const first = headers[0];
    expect(first.stacked).toBe(true);
    expect(first.titleLeft).toBe(first.tagLeft);
    for (const h of headers) expect(h).toEqual(first);
  });
});
