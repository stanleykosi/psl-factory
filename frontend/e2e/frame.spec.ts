import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.locator('main#main > *').first()).toBeVisible();
}

async function focusOnStrong(page: Page) {
  return page.evaluate(() => {
    const probe = document.createElement('span');
    probe.style.color = 'var(--focus-on-strong)';
    document.body.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  });
}

async function outline(page: Page) {
  return page.evaluate(() => {
    const s = getComputedStyle(document.activeElement!);
    return { style: s.outlineStyle, width: s.outlineWidth, color: s.outlineColor };
  });
}

/** STATES error card: white surface, 2px signal border, red mono eyebrow, message, reference, 50px Try again. */
async function expectErrorCard(page: Page) {
  const card = page.getByRole('main').getByRole('alert');
  await expect(card).toHaveClass('shell-errorcard');
  await expect(card.locator(':scope > *')).toHaveText([
    'ERROR · COULDN’T LOAD',
    'We couldn’t load your account. Your work is safe; nothing was changed.',
    'Reference not_found for support.',
    'Try again',
  ]);
  const look = await card.evaluate((el) => {
    const s = getComputedStyle(el);
    const eyebrow = getComputedStyle(el.firstElementChild!);
    const button = el.querySelector('button')!.getBoundingClientRect();
    return {
      background: s.backgroundColor,
      border: `${s.borderTopWidth} ${s.borderTopStyle} ${s.borderTopColor}`,
      eyebrow: { color: eyebrow.color, size: eyebrow.fontSize, mono: eyebrow.fontFamily.includes('Plex Mono') },
      buttonHeight: button.height,
    };
  });
  expect(look).toEqual({
    background: 'rgb(255, 255, 255)',
    border: '2px solid rgb(200, 64, 28)',
    eyebrow: { color: 'rgb(154, 47, 16)', size: '11px', mono: true },
    buttonHeight: 50,
  });
  await expect(page.locator('.psl-callout--problem')).toHaveCount(0);
}

async function noHorizontalScroll(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
}

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('/ goes to My work; the top bar follows /me; no font CDN calls', async ({ page }) => {
    const fontRequests: string[] = [];
    page.on('request', (r) => {
      if (/fonts\.(googleapis|gstatic)\.com/.test(r.url())) fontRequests.push(r.url());
    });
    await page.goto('/');
    await expect(page).toHaveURL(/\/my-work$/);
    await loaded(page);
    await expect(page).toHaveTitle('My work · PSL Factory');
    const bar = page.getByRole('navigation', { name: 'Main' });
    await expect(bar.getByRole('link')).toHaveText(['My work', 'Projects', 'Overview', 'Assistant', 'Setup']);
    await expect(bar.getByRole('link', { name: 'My work' })).toHaveAttribute('aria-current', 'page');
    const current = await bar.getByRole('link', { name: 'My work' }).evaluate((a) => {
      const s = getComputedStyle(a);
      return { border: s.borderBottomColor, width: s.borderBottomWidth };
    });
    expect(current).toEqual({ border: 'rgb(200, 64, 28)', width: '3px' });
    await expect(bar.getByText('PSL FACTORY')).toBeVisible();
    await expect(bar.locator('.psl-sample')).toHaveText('SAMPLE DATA');
    await expect(bar.getByText('Ada Okafor · Finance Lead')).toBeVisible();
    await page.goto('/my-work');
    await loaded(page);
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.fonts.check('800 17px Archivo'))).toBe(true);
    expect(fontRequests).toEqual([]);
    await page.screenshot({ path: test.info().outputPath('my-work-1440.png') });
    await expectNoAxeViolations(page);
    expect(await noHorizontalScroll(page)).toBe(true);
  });

  test('pm sees three destinations; /overview is not open', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'pm' });
    await page.goto('/overview');
    await loaded(page);
    const bar = page.getByRole('navigation', { name: 'Main' });
    await expect(bar.getByRole('link')).toHaveText(['My work', 'Projects', 'Assistant']);
    await expect(bar.getByText('Tunde Bello · PM')).toBeVisible();
    await expect(page.getByText('This section isn’t open to your role.')).toBeVisible();
    await expect(page.getByRole('main').getByRole('link')).toHaveAttribute('href', '/my-work');
    await expectNoAxeViolations(page);
  });

  test('skip link first, then focus rings on the ink bar', async ({ page }) => {
    await page.goto('/my-work');
    await loaded(page);
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('main#main')).toBeFocused();

    await page.goto('/my-work');
    await loaded(page);
    await page.keyboard.press('Tab');
    const white = await focusOnStrong(page);
    expect(white).toBe('rgb(255, 255, 255)');
    for (const name of ['My work', 'Projects', 'Overview', 'Assistant', 'Setup']) {
      await page.keyboard.press('Tab');
      await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name })).toBeFocused();
      expect(await outline(page)).toEqual({ style: 'solid', width: '2px', color: white });
    }
  });

  test('401 shows signed out with a sign-in link', async ({ page, context }) => {
    await setCookies(context, { psl_mock_scenario: '401' });
    await page.goto('/my-work');
    await expect(page.getByText('You’re signed out.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/accounts/login/?next=%2Fmy-work');
    await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link')).toHaveCount(0);
    await expect(page.locator('.psl-sample').first()).toBeVisible();
    await expectNoAxeViolations(page);
  });

  test('403 and none persona states', async ({ page, context }) => {
    await setCookies(context, { psl_mock_scenario: '403' });
    await page.goto('/my-work');
    await expect(page.getByText('Your account can’t use PSL Factory.')).toBeVisible();
    await expect(page.locator('.psl-sample').first()).toBeVisible();
    await context.clearCookies();
    await setCookies(context, { psl_mock_persona: 'none' });
    await page.goto('/my-work');
    await expect(page.getByText('No sections are open to your role yet.')).toBeVisible();
    await expect(page.getByText('Sample Person · Staff')).toBeVisible();
    await expect(page.locator('.psl-sample').first()).toBeVisible();
    await expectNoAxeViolations(page);
  });

  test('404 shows the error pattern; Try again after clearing the cookie loads the bar', async ({ page, context }) => {
    await setCookies(context, { psl_mock_scenario: '404' });
    await page.goto('/my-work');
    await expectErrorCard(page);
    await expect(page.locator('.psl-sample').first()).toBeVisible();
    await expectNoAxeViolations(page);
    await context.clearCookies();
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link')).toHaveCount(5);
  });

  test('loading shows a status message and no destinations; nothing moves with reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    await page.route('**/api/v1/me', async (route) => {
      await gate;
      await route.continue();
    });
    await page.goto('/my-work');
    await expect(page.getByRole('status')).toHaveText('Loading…');
    await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link')).toHaveCount(0);
    await expect(page.locator('.psl-sample').first()).toBeVisible();
    expect(await motion(page)).toEqual({ transitions: [], running: 0 });
    release();
    await loaded(page);
    expect(await motion(page)).toEqual({ transitions: [], running: 0 });
  });
});

async function motion(page: Page) {
  return page.evaluate(() => ({
    transitions: [...document.querySelectorAll('body *')]
      .filter((el) => getComputedStyle(el).transitionDuration.split(',').some((d) => parseFloat(d) > 0))
      .map((el) => el.outerHTML.slice(0, 80)),
    running: document.getAnimations().filter((a) => a.playState === 'running').length,
  }));
}

test.describe('phone 390', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('phone bar and menu disclosure', async ({ page }) => {
    await page.goto('/my-work');
    await loaded(page);
    await expect(page.getByRole('navigation', { name: 'Main' })).toHaveCount(0);
    const header = page.locator('header.psl-phonebar');
    const menu = header.getByRole('button', { name: 'Menu' });
    await expect(menu).toBeVisible();
    await expect(header.getByText('PSL FACTORY')).toBeVisible();
    await expect(header.locator('.psl-sample')).toHaveText('SAMPLE DATA');
    expect(await noHorizontalScroll(page)).toBe(true);
    await expectNoAxeViolations(page);

    await menu.click();
    await expect(menu).toHaveAttribute('aria-expanded', 'true');
    const panel = page.getByRole('navigation', { name: 'Main' });
    await expect(panel.getByRole('link')).toHaveText(['My work', 'Projects', 'Overview', 'Assistant', 'Setup']);
    await expect(panel.getByRole('link', { name: 'My work' })).toHaveAttribute('aria-current', 'page');
    await expect(panel).toContainText('Ada Okafor');
    await page.screenshot({ path: test.info().outputPath('my-work-390-menu.png') });
    await expectNoAxeViolations(page);
    for (const target of [menu, ...(await panel.getByRole('link').all())]) {
      const box = (await target.boundingBox())!;
      expect(box.width).toBeGreaterThanOrEqual(44);
      expect(box.height).toBeGreaterThanOrEqual(44);
    }

    await page.keyboard.press('Escape');
    await expect(panel).toHaveCount(0);
    await expect(menu).toHaveAttribute('aria-expanded', 'false');
    await expect(menu).toBeFocused();

    await menu.click();
    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Projects' }).click();
    await expect(page).toHaveURL(/\/projects$/);
    await expect(page.getByRole('navigation', { name: 'Main' })).toHaveCount(0);
    await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible();
  });

  test('Menu button keyboard focus ring is white on the ink bar; menu items ring stays visible', async ({ page }) => {
    await page.goto('/my-work');
    await loaded(page);
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    const menu = page.getByRole('button', { name: 'Menu' });
    await expect(menu).toBeFocused();
    expect(await outline(page)).toEqual({ style: 'solid', width: '2px', color: await focusOnStrong(page) });
    await page.keyboard.press('Enter');
    await page.keyboard.press('Tab');
    await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'My work' })).toBeFocused();
    const ring = await outline(page);
    expect(ring.style).toBe('solid');
    expect(ring.color).not.toBe('rgb(255, 255, 255)');
  });

  test('404 error card at phone width; Try again is full width', async ({ page, context }) => {
    await setCookies(context, { psl_mock_scenario: '404' });
    await page.goto('/my-work');
    await expectErrorCard(page);
    const widths = await page.getByRole('main').getByRole('alert').evaluate((el) => ({
      card: el.clientWidth - 28,
      button: el.querySelector('button')!.getBoundingClientRect().width,
    }));
    expect(widths.button).toBe(widths.card);
    expect(await noHorizontalScroll(page)).toBe(true);
    await expectNoAxeViolations(page);
  });

  test('401 state at phone width', async ({ page, context }) => {
    await setCookies(context, { psl_mock_scenario: '401' });
    await page.goto('/my-work');
    await expect(page.getByText('You’re signed out.')).toBeVisible();
    await expect(page.locator('header.psl-phonebar .psl-sample')).toBeVisible();
    await expectNoAxeViolations(page);
  });
});

test('no horizontal scroll at 768px', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await page.goto('/my-work');
  await loaded(page);
  await page.screenshot({ path: test.info().outputPath('my-work-768.png') });
  expect(await noHorizontalScroll(page)).toBe(true);
  const bar = await page.locator('.psl-nav__in').evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
  expect(bar.scroll).toBeLessThanOrEqual(bar.client);
  await expect(page.locator('.psl-nav .psl-sample')).toHaveText('SAMPLE DATA');
  expect(await page.locator('.psl-nav .psl-sample').evaluate((el) => el.getBoundingClientRect().height)).toBeLessThan(24);
});

// Design owner, 13 Nov 2026: from 720px up to bp-desktop (1080px) the bar shows the name only, on one line;
// from 1080px the full "name · role". The role stays in the accessible text at every width.
for (const width of [720, 740, 768, 820, 900, 1079, 1080, 1440]) {
  test(`top bar at ${width}px fits and shows who is signed in`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/my-work');
    await loaded(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    const bar = page.getByRole('navigation', { name: 'Main' });
    await expect(bar.getByRole('link')).toHaveCount(5);
    const who = await bar.locator('.psl-nav__who').evaluate((el) => {
      const r = el.getBoundingClientRect();
      const role = el.querySelector('.shell-who-role')!.getBoundingClientRect();
      return {
        text: el.textContent,
        fits: el.scrollWidth <= el.clientWidth && r.right <= window.innerWidth,
        oneLine: r.height < 24,
        roleShown: role.width > 1,
      };
    });
    expect(who).toEqual({ text: 'Ada Okafor · Finance Lead', fits: true, oneLine: true, roleShown: width >= 1080 });
    await expect(bar.locator('.shell-who-name')).toHaveText('Ada Okafor');
    await expect(bar.locator('.shell-who-name')).toBeVisible();
    await expect(bar).toContainText('Ada Okafor · Finance Lead');
    if (width === 720 || width === 1080) await expectNoAxeViolations(page);
  });
}

test('an unknown address shows a plain not-found page with a way back', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto('/nonexistent');
  await loaded(page);
  await expect(page).toHaveTitle('Page not found · PSL Factory');
  await expect(page.getByRole('heading', { name: 'This page doesn’t exist.' })).toBeVisible();
  await page.getByRole('main').getByRole('link', { name: 'Go to My work' }).click();
  await expect(page).toHaveURL(/\/my-work$/);
  await expectNoAxeViolations(page);
});
