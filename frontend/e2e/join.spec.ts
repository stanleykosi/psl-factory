// F-60: account set-up from an invitation, against the contract mock (fixture tokens, no real credentials).
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const link = (letter: string) => `/staff/join/#${letter.repeat(43)}`;
const GOOD = 'a-long-enough-password';

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

async function fillPasswords(page: Page, password = GOOD, confirm = password) {
  await page.getByLabel('New password', { exact: true }).fill(password);
  await page.getByLabel('Confirm new password').fill(confirm);
}

test.describe('the page', () => {
  test('desktop: layout, no frame, address cleared, no-referrer, nothing stored, reload is unavailable', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto(link('v'));
    await expect(page).toHaveTitle('Set up your account');
    await expect(page.getByRole('heading', { level: 1, name: 'Set up your account' })).toBeVisible();
    await expect(page.locator('.join-welcome')).toHaveText('Welcome, Sola Martins. You’ve been given PMO for Ojo Foods and Kora Logistics.');
    await expect(page.getByText(/This invitation works until \d+ Nov 2026, \d\d:\d\d\./)).toBeVisible();
    await expect(page.getByLabel('Work email')).toHaveValue('sola.martins@psl.example');
    await expect(page.getByText('At least 12 characters')).toBeVisible();
    await expect(page.getByText('Work you can see moving, from first draft to verified.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'My work' })).toHaveCount(0);
    await expect(page.getByRole('navigation')).toHaveCount(0);
    expect(page.url()).toBe(`${test.info().project.use.baseURL}/staff/join/`);
    expect(await page.locator('meta[name=referrer]').getAttribute('content')).toBe('no-referrer');
    const stored = await page.evaluate(() => JSON.stringify([{ ...localStorage }, { ...sessionStorage }, document.cookie]));
    expect(stored).not.toContain('v'.repeat(43));
    await expect(page.locator('body')).not.toContainText(/72 hours|WhatsApp/);
    await expectNoAxeViolations(page);
    await page.reload();
    await expect(page.getByText('This invitation can’t be used')).toBeVisible();
  });

  test('phone: 48px fields, a full-width button, axe clean', async ({ page }) => {
    await page.setViewportSize(PHONE);
    await page.goto(link('v'));
    await expect(page.getByLabel('Confirm new password')).toBeVisible();
    expect((await page.getByLabel('Confirm new password').boundingBox())!.height).toBe(48);
    const button = (await page.getByRole('button', { name: 'Finish setup' }).boundingBox())!;
    expect(button.width).toBeGreaterThan(300);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(PHONE.width);
    await expectNoAxeViolations(page);
  });

  test('keyboard order: email, New password, Confirm, Finish setup; Enter never changes the address', async ({ page }) => {
    await page.goto(link('v'));
    await page.getByLabel('Work email').focus();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('New password', { exact: true })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('Confirm new password')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: 'Finish setup' })).toBeFocused();
    await page.getByLabel('Confirm new password').fill('secret-one');
    await page.getByLabel('Confirm new password').press('Enter');
    await expect(page.getByText('Enter a new password.')).toBeVisible();
    expect(page.url()).toBe(`${test.info().project.use.baseURL}/staff/join/`);
  });

  test('two access groups read as two sentences', async ({ page }) => {
    await page.goto(link('m'));
    await expect(page.locator('.join-welcome')).toHaveText('Welcome, Sola Martins. You’ve been given PMO for Ojo Foods. You’ve also been given Finance Lead for Kora Logistics.');
  });
});

test.describe('states', () => {
  for (const [size, viewport] of [['desktop', DESKTOP], ['phone', PHONE]] as const) {
    test(`${size}: unavailable, and the same for expired, used and unknown`, async ({ page }) => {
      await page.setViewportSize(viewport);
      const seen: string[] = [];
      for (const letter of ['e', 'u', 'x']) {
        await page.goto(link(letter));
        await expect(page.getByText('This invitation can’t be used')).toBeVisible();
        seen.push(await page.locator('main').innerText());
        await expect(page.getByRole('link', { name: 'Already set up? Sign in' })).toHaveAttribute('href', '/sign-in');
      }
      expect(new Set(seen).size).toBe(1);
      await expectNoAxeViolations(page);
    });
  }

  test('a field error and a page error, each axe clean', async ({ page, context }) => {
    await page.goto(link('v'));
    await page.getByRole('button', { name: 'Finish setup' }).click();
    await expect(page.getByText('Enter a new password.')).toBeVisible();
    await expect(page.getByLabel('New password', { exact: true })).toBeFocused();
    await expectNoAxeViolations(page);
    await fillPasswords(page, 'short', 'short');
    await page.getByRole('button', { name: 'Finish setup' }).click();
    const alert = page.locator('.psl-callout--problem');
    await expect(alert).toContainText('This password is too short. It must contain at least 12 characters.');
    await expect(alert).toBeFocused();
    await expect(page.getByLabel('New password', { exact: true })).toHaveValue('');
    await expectNoAxeViolations(page);
    await fillPasswords(page, GOOD, 'another-long-password');
    await page.getByRole('button', { name: 'Finish setup' }).click();
    await expect(page.getByText('The two passwords don’t match.')).toBeVisible();
    await setCookies(context, { psl_mock_scenario: '503' });
    await fillPasswords(page);
    await page.getByRole('button', { name: 'Finish setup' }).click();
    await expect(page.locator('.psl-callout--problem')).toContainText('Set-up isn’t working right now. Try again in a moment. Nothing was changed.');
    await expect(page.locator('.psl-callout--problem')).toContainText('try signing in; your account may already be set up.');
    await expectNoAxeViolations(page);
  });

  for (const scenario of ['429', '503', '500']) {
    test(`preview under scenario ${scenario} says it could not open, and Try again recovers`, async ({ page, context }) => {
      await setCookies(context, { psl_mock_scenario: scenario });
      await page.goto(link('v'));
      await expect(page.getByText('We couldn’t open your invitation. Nothing was changed.')).toBeVisible();
      await expect(page.getByLabel('New password', { exact: true })).toHaveCount(0);
      await context.clearCookies({ name: 'psl_mock_scenario' });
      await page.getByRole('button', { name: 'Try again' }).click();
      await expect(page.getByRole('button', { name: 'Finish setup' })).toBeVisible();
    });
  }

  test('the renewed link ends in the unavailable state after a failed accept', async ({ page }) => {
    await page.goto(link('r'));
    await fillPasswords(page);
    await page.getByRole('button', { name: 'Finish setup' }).click();
    await expect(page.getByText('This invitation can’t be used')).toBeVisible();
    await expectNoAxeViolations(page);
  });

  for (const [size, viewport] of [['desktop', DESKTOP], ['phone', PHONE]] as const) {
    test(`${size}: set-up finishes with a plain heading and a Sign in link, and the link cannot be used twice`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto(link('m'));
      await fillPasswords(page);
      await page.getByRole('button', { name: 'Finish setup' }).click();
      const heading = page.getByRole('heading', { level: 1, name: 'Your account is ready.' });
      await expect(heading).toBeFocused();
      await expect(page.getByText('Sign in with sola.martins@psl.example.')).toBeVisible();
      await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in');
      await expect(page.locator('.psl-callout')).toHaveCount(0);
      await expectNoAxeViolations(page);
      await page.goto(link('m'));
      await expect(page.getByText('This invitation can’t be used')).toBeVisible();
    });
  }
});
