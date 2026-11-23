// F-58: sign in, the plain error, and sign out, against the contract mock (a sample sign-in pair; no real credentials).
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const PAIR = { user: 'sample.user', password: 'sample-password' };

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function fill(page: Page, user: string, password: string) {
  await page.getByLabel('Work email or sign-in name').fill(user);
  await page.getByLabel('Password').fill(password);
}

const topBar = (page: Page) => page.getByRole('navigation', { name: 'Main' });

// The mock starts signed in, so the pages that show the form begin signed out.
const signedOutFirst = async ({ context }: { context: BrowserContext }) => setCookies(context, { psl_mock_session: 'out' });

test.describe('the page', () => {
  test.beforeEach(signedOutFirst);
  test('desktop: brand column and the form, with no frame and no sign-in line about a record', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto('/sign-in');
    await expect(page).toHaveTitle('Sign in');
    await expect(page.getByRole('heading', { level: 1, name: 'Sign in' })).toBeVisible();
    await expect(page.getByText('Work you can see moving, from first draft to verified.')).toBeVisible();
    await expect(page.getByLabel('Keep me signed in')).not.toBeChecked();
    await expect(page.getByText('Forgot your password? Reset opens in a later release. Ask your administrator for help.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'My work' })).toHaveCount(0);
    await expect(page.getByRole('navigation')).toHaveCount(0);
    await expect(page.locator('body')).not.toContainText(/INV-0412|tries left|Only PMO/);
    await expectNoAxeViolations(page);
  });

  test('phone: the phone heading, label and 48px fields', async ({ page }) => {
    await page.setViewportSize(PHONE);
    await page.goto('/sign-in');
    await expect(page.getByRole('heading', { level: 1, name: 'Sign in to continue' })).toBeVisible();
    await expect(page.getByLabel('Keep me signed in on this phone')).toBeVisible();
    await expect(page.getByText('Work you can see moving')).toBeHidden();
    expect((await page.getByLabel('Password').boundingBox())!.height).toBe(48);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(PHONE.width);
    await expectNoAxeViolations(page);
  });

  test('pressing Enter in the password field never puts it in the address', async ({ page }) => {
    await page.goto('/sign-in');
    await fill(page, PAIR.user, 'wrong-secret');
    await page.getByLabel('Password').press('Enter');
    await expect(page.locator('.psl-callout--problem')).toBeVisible();
    expect(page.url()).toBe(`${test.info().project.use.baseURL}/sign-in`);
    expect(page.url()).not.toContain('secret');
  });

  test('an empty form asks for both, with no request', async ({ page }) => {
    const posts: string[] = [];
    page.on('request', (request) => request.method() === 'POST' && posts.push(request.url()));
    await page.goto('/sign-in');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText('Enter your work email.')).toBeVisible();
    await expect(page.getByText('Enter your password.')).toBeVisible();
    await expect(page.getByLabel('Work email or sign-in name')).toBeFocused();
    expect(posts).toEqual([]);
  });

  test('forgot password: plain text, no recovery request', async ({ page }) => {
    const seen: string[] = [];
    page.on('request', (request) => seen.push(new URL(request.url()).pathname));
    await page.goto('/sign-in');
    await expect(page.getByRole('link', { name: /forgot/i })).toHaveCount(0);
    expect(seen.filter((path) => path.includes('/accounts/recovery'))).toEqual([]);
  });
});

test.describe('errors', () => {
  test.beforeEach(signedOutFirst);
  test('a wrong pair shows the one plain message and keeps the name; axe is clean', async ({ page }) => {
    await page.goto('/sign-in');
    await fill(page, PAIR.user, 'not-the-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    const alert = page.locator('.psl-callout--problem');
    await expect(alert).toHaveText('That email and password don’t match.');
    await expect(alert).toBeFocused();
    await expect(page.getByLabel('Password')).toHaveValue('');
    await expect(page.getByLabel('Work email or sign-in name')).toHaveValue(PAIR.user);
    await expect(page.locator('body')).not.toContainText(/\d+ tries|minutes/);
    await expectNoAxeViolations(page);
  });

  for (const [scenario, wording] of [
    ['429', 'Too many sign-in tries. Try again later.'],
    ['503', 'Sign-in isn’t working right now. Try again in a moment. Nothing was changed.'],
    ['500', 'Sign-in isn’t working right now. Try again in a moment. Nothing was changed.'],
  ]) {
    test(`scenario ${scenario}`, async ({ page, context }) => {
      await page.goto('/sign-in');
      await setCookies(context, { psl_mock_scenario: scenario });
      await fill(page, PAIR.user, PAIR.password);
      await page.getByRole('button', { name: 'Sign in' }).click();
      await expect(page.locator('.psl-callout--problem')).toHaveText(wording);
      await expect(page.getByLabel('Password')).toHaveValue('');
    });
  }

  test('a stale token: the first press says so and the second succeeds without a reload', async ({ page }) => {
    let reads = 0;
    await page.route('**/api/v1/session', async (route) => {
      if (route.request().method() !== 'GET') return route.continue();
      reads += 1;
      const response = await route.fetch();
      const body = await response.json();
      // The first read hands out a token the mock does not accept; the re-read after the 403 is the real one.
      return route.fulfill({ response, json: reads === 1 ? { ...body, csrf_token: 'stale-token' } : body });
    });
    await page.goto('/sign-in');
    await fill(page, PAIR.user, PAIR.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.locator('.psl-callout--problem')).toHaveText('Your session was refreshed. Press Sign in again. Nothing was changed.');
    await page.getByLabel('Password').fill(PAIR.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/my-work$/);
  });
});

test.describe('a full round', () => {
  test('sign in, see the frame with the person and role words, sign out, land on /sign-in, and the signed-out state links back', async ({ page, context }) => {
    await setCookies(context, { psl_mock_session: 'out' });
    await page.setViewportSize(DESKTOP);
    await page.goto('/my-work');
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in?next=%2Fmy-work');
    await page.getByRole('link', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/sign-in\?next=%2Fmy-work$/);
    const roleReads: string[] = [];
    page.on('request', (request) => new URL(request.url()).pathname === '/api/v1/role-dashboard' && roleReads.push(request.url()));
    await fill(page, PAIR.user, PAIR.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/my-work$/);
    await expect(topBar(page).locator('.shell-who-name')).toHaveText('Ada Okafor');
    await expect(topBar(page)).toContainText('Ada Okafor · Finance Lead');
    expect(roleReads.length).toBeGreaterThan(0);

    await topBar(page).getByRole('button', { name: /^Account menu: Ada Okafor/ }).click();
    await expectNoAxeViolations(page);
    await page.getByRole('menuitem', { name: /Sign out/ }).click();
    await expect(page).toHaveURL(/\/sign-in$/);
    await expect(page.getByRole('navigation')).toHaveCount(0);
    await expect(page.locator('body')).not.toContainText('Ada Okafor');

    await page.goBack();
    await expect(page.getByText('You’re signed out.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in?next=%2Fmy-work');
  });

  test('a second person signs in after a sign-out and the bar shows the new name, not the old one', async ({ page, context }) => {
    await page.goto('/my-work');
    await expect(topBar(page).locator('.shell-who-name')).toHaveText('Ada Okafor');
    await topBar(page).getByRole('button', { name: /Account menu/ }).click();
    await page.getByRole('menuitem', { name: /Sign out/ }).click();
    await expect(page).toHaveURL(/\/sign-in$/);
    await setCookies(context, { psl_mock_persona: 'ceo' });
    await page.reload();
    await fill(page, PAIR.user, PAIR.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
    await expect(topBar(page).locator('.shell-who-name')).toHaveText('Folake Bello');
    await expect(page.locator('body')).not.toContainText('Ada Okafor');
  });

  for (const next of ['https%3A%2F%2Fevil.example', '%2F%2Fevil.example']) {
    test(`?next=${next} never leaves the site`, async ({ page, context }) => {
      await setCookies(context, { psl_mock_session: 'out' });
      let body = '';
      page.on('request', (request) => request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/session' && (body = request.postData() ?? ''));
      await page.goto(`/sign-in?next=${next}`);
      await fill(page, PAIR.user, PAIR.password);
      await page.getByRole('button', { name: 'Sign in' }).click();
      await expect(page).toHaveURL(/\/my-work$/);
      expect(new URL(page.url()).origin).toBe(new URL(test.info().project.use.baseURL!).origin);
      expect(body).not.toContain('next_url');
    });
  }

  test('someone with no open work stays on the page with a plain notice and can sign out', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'none', psl_mock_session: 'out' });
    const seen: string[] = [];
    page.on('request', (request) => seen.push(new URL(request.url()).pathname));
    await page.goto('/sign-in');
    await fill(page, PAIR.user, PAIR.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText('You’re signed in, but no work is open to you yet. Ask your administrator.')).toBeVisible();
    await expect(page).toHaveURL(/\/sign-in$/);
    expect(seen.filter((path) => path.includes('getting-started'))).toEqual([]);
    await expectNoAxeViolations(page);
    await page.getByRole('button', { name: 'Sign out' }).click();
    await expect(page.getByLabel('Password')).toBeVisible();
  });

  test('a failed sign-out keeps the person in the frame with a toast', async ({ page }) => {
    await page.route('**/api/v1/session/logout', (route) => route.fulfill({ status: 500, json: { code: 'server_error', message: 'x' } }));
    await page.goto('/my-work');
    await topBar(page).getByRole('button', { name: /Account menu/ }).click();
    await page.getByRole('menuitem', { name: /Sign out/ }).click();
    await expect(page.locator('.psl-toast')).toHaveText('We couldn’t sign you out. Try again.');
    await expect(page).toHaveURL(/\/my-work$/);
  });
});

test.describe('the account menu', () => {
  test('keyboard: Enter opens, arrows move, Esc closes and returns focus to the name', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto('/my-work');
    const name = topBar(page).getByRole('button', { name: /^Account menu: Ada Okafor/ });
    await name.focus();
    await page.keyboard.press('Enter');
    const item = page.getByRole('menuitem', { name: /Sign out/ });
    await expect(item).toBeFocused();
    await expect(page.getByRole('menu', { name: 'Account' })).toBeVisible();
    await expect(page.locator('.cmp-menuhead')).toContainText('Ada Okafor');
    await page.keyboard.press('ArrowDown');
    await expect(item).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('menu')).toHaveCount(0);
    await expect(name).toBeFocused();
    await page.keyboard.press('Enter');
    await page.keyboard.press('Tab');
    await expect(page.getByRole('menu')).toHaveCount(0);
  });

  test('the open menu is inside the window and not clipped by the bar', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto('/my-work');
    await topBar(page).getByRole('button', { name: /Account menu/ }).click();
    const box = (await page.locator('.shell-accountpop .cmp-pop').boundingBox())!;
    expect(box.x + box.width).toBeLessThanOrEqual(DESKTOP.width);
    expect(box.x).toBeGreaterThan(0);
    await expect(page.getByRole('menuitem', { name: /Sign out/ })).toBeInViewport({ ratio: 1 });
  });

  test('phone: Sign out follows the destinations and works', async ({ page }) => {
    await page.setViewportSize(PHONE);
    await page.goto('/my-work');
    await page.getByRole('button', { name: 'Menu' }).click();
    const signOut = page.locator('#phone-menu').getByRole('button', { name: 'Sign out' });
    expect((await signOut.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expectNoAxeViolations(page);
    await signOut.click();
    await expect(page).toHaveURL(/\/sign-in$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Sign in to continue' })).toBeVisible();
  });
});
