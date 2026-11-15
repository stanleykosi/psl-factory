import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// Clients (SCR-35 list and detail) against the contract mock: every state at 390 and 1440, axe WCAG 2.2 AA.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

test.use({ timezoneId: 'Africa/Lagos' });

// A save is kept by the mock until it is reset, so every test starts from the fixtures.
test.beforeEach(({ request }) => request.post(`http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}/__mock/reset`));

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
const clientLinks = (page: Page) => page.locator('[data-client-link]');
const h1Size = (page: Page) => page.getByRole('heading', { level: 1 }).evaluate((el) => getComputedStyle(el).fontSize);

async function listLoaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: 'Clients' })).toBeVisible();
}

async function detailLoaded(page: Page, name: string) {
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
  await expect(page.getByText('Loading…')).toHaveCount(0);
}

/** Tabs until the target has focus, then reads its outline. */
async function keyboardRing(page: Page, target: Locator) {
  for (let i = 0; i < 80; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press('Tab');
  }
  await expect(target).toBeFocused();
  return target.evaluate((el) => {
    const s = getComputedStyle(el);
    return { style: s.outlineStyle, width: s.outlineWidth };
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

async function expectTouchTargets(targets: Locator[]) {
  for (const target of targets) {
    const box = (await target.boundingBox())!;
    expect(box.width, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
    expect(box.height, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
  }
}

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;
  const w = viewport.width;
  const backLink = (page: Page, name: string) => page.getByRole('link', { name: `Back to ${name}`, exact: true });

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    test('list default: six clients, tags, one h1, the phone bar link, no back link in main', async ({ page }) => {
      await page.goto('/clients');
      await listLoaded(page);
      await expect(clientLinks(page)).toHaveCount(6);
      await expect(clientLinks(page).first()).toHaveAttribute('href', '/clients/CL-3501');
      await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
      // the SCR-35 boards' title sizes (D-93): 34px, 24px on the phone list
      expect(await h1Size(page)).toBe(phone ? '24px' : '34px');
      await expect(page.getByText('6 clients as of 14 Nov, 10:00 · 2 missing billing contact')).toBeVisible();
      await expect(page.getByText('Billing contact missing')).toHaveCount(2);
      await expect(page.getByRole('main').getByRole('link', { name: /^Back to/ })).toHaveCount(0);
      if (phone) {
        await expect(backLink(page, 'Projects')).toBeVisible();
        await expect(page.getByRole('table')).toHaveCount(0);
        await expectTouchTargets([backLink(page, 'Projects'), ...(await page.locator('ul.clients__cards > li').all())]);
      } else {
        await expect(page.getByRole('columnheader')).toHaveText(['CLIENT', 'PROJECTS', 'OWED', 'BILLING CONTACT', 'STATE']);
        await expect(page.locator('.clients__eyebrow')).toHaveText('PROJECTS');
        await expect(backLink(page, 'Projects')).toBeHidden();
      }
      await expect(page.getByText('Unknown').first()).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      expect(await page.title()).toBe('Clients · PSL Factory');
      await shot(page, `clients-${w}`);
      await expectNoAxeViolations(page);
      // Tab order: the rows in order; each takes a visible ring.
      const ring = await keyboardRing(page, clientLinks(page).first());
      expect(ring.style).not.toBe('none');
      expect(parseFloat(ring.width)).toBeGreaterThanOrEqual(2);
    });

    test('list empty', async ({ page, context }) => {
      await setCookies(context, { psl_mock_clients: 'empty' });
      await page.goto('/clients');
      await listLoaded(page);
      await expect(page.getByText('No clients to show yet.')).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, `clients-${w}-empty`);
      await expectNoAxeViolations(page);
    });

    test('list: Show more appends the next page; loading and reduced motion', async ({ page, context }) => {
      await setCookies(context, { psl_mock_clients: 'many' });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto('/clients');
      await listLoaded(page);
      await expect(clientLinks(page)).toHaveCount(20);
      await expect(page.getByText(/^20 clients loaded as of /)).toBeVisible();
      if (phone) await expectTouchTargets([page.getByRole('button', { name: 'Show more' })]);
      await page.getByRole('button', { name: 'Show more' }).click();
      await expect(clientLinks(page)).toHaveCount(25);
      await expect(page.getByRole('button', { name: 'Show more' })).toHaveCount(0);
      await expect(page.getByText(/^25 clients as of /)).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      expect(await motion(page)).toEqual({ transitions: [], running: 0 });
      await expectNoAxeViolations(page);
    });

    test('list: signed-out and error states', async ({ page }) => {
      let status = 500;
      await page.route('**/api/v1/clients', (route) =>
        status === 0 ? route.continue() : route.fulfill({ status, contentType: 'application/json', body: '{"code":"server_error","message":"x"}' }),
      );
      await page.goto('/clients');
      const card = page.getByRole('main').getByRole('alert');
      await expect(card).toContainText('We couldn’t load the clients. Your work is safe; nothing was changed.');
      await expectNoAxeViolations(page);
      status = 0;
      await card.getByRole('button', { name: 'Try again' }).click();
      await expect(clientLinks(page)).toHaveCount(6);
    });

    test('detail CL-3501: banner, empty form, project, money; one h1; phone bar link; Tab order', async ({ page }) => {
      await page.goto('/clients/CL-3501');
      await detailLoaded(page, 'Lagoon Health Ltd');
      await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
      // the SCR-35 detail boards' title sizes (D-93): 34px, 22px on the phone
      expect(await h1Size(page)).toBe(phone ? '22px' : '34px');
      await expect(page.getByText("No billing contact, so invoices for this client can't start. Add one here.")).toBeVisible();
      await expect(page.getByRole('link', { name: 'Patient app' })).toHaveAttribute('href', '/projects/P-0101');
      await expect(page.getByRole('main').getByRole('link', { name: /^Back to/ })).toHaveCount(0);
      await expect(page.getByText('Unknown')).toBeVisible();
      if (phone) await expect(backLink(page, 'Clients')).toBeVisible();
      else await expect(page.getByRole('navigation').or(page.locator('.clients__crumb')).filter({ hasText: 'Clients / Lagoon Health Ltd' }).first()).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      expect(await page.title()).toBe('Client · PSL Factory');
      await shot(page, `client-${w}`);
      await expectNoAxeViolations(page);

      await page.getByLabel('Billing contact name').fill('Ada Okoye');
      await page.getByLabel('Billing email').fill('ada@lagoon.example');
      const name = page.getByLabel('Billing contact name');
      const email = page.getByLabel('Billing email');
      const save = page.getByRole('button', { name: 'Save billing contact' });
      await expectTouchTargets([name, email, save]);
      await name.focus();
      await page.keyboard.press('Tab');
      await expect(email).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(save).toBeFocused();
      for (const target of [name, email, save]) {
        const ring = await keyboardRing(page, target);
        expect(ring.style).not.toBe('none');
      }
      await save.click();
      await expect(page.locator('.psl-callout--success')).toHaveText('Billing contact saved.');
      await expect(page.getByText("No billing contact, so invoices for this client can't start.")).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    test('detail with a 422 shown: summary announced, message beside the input, focus on the first invalid input', async ({ page }) => {
      await page.goto('/clients/CL-3501');
      await detailLoaded(page, 'Lagoon Health Ltd');
      await page.getByLabel('Billing contact name').fill('Ada Okoye');
      await page.getByLabel('Billing email').fill('not-an-email');
      await page.getByRole('button', { name: 'Save billing contact' }).click();
      await expect(page.getByRole('alert').filter({ hasText: 'Check the highlighted details.' })).toBeVisible();
      const email = page.getByLabel('Billing email');
      await expect(email).toHaveAttribute('aria-invalid', 'true');
      await expect(email).toBeFocused();
      await expect(page.getByText('Enter a valid email address.')).toBeVisible();
      await expect(page.getByLabel('Billing contact name')).toHaveValue('Ada Okoye');
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, `client-${w}-422`);
      await expectNoAxeViolations(page);
    });

    test('detail read-only: CL-3503', async ({ page }) => {
      await page.goto('/clients/CL-3503');
      await detailLoaded(page, 'Kora Logistics');
      await expect(page.getByRole('textbox')).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Save billing contact' })).toHaveCount(0);
      await expect(page.getByText('You can’t change this client’s details.')).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, `client-${w}-readonly`);
      await expectNoAxeViolations(page);
    });

    test('detail not open: CL-3599 names nothing, one h1', async ({ page }) => {
      await page.goto('/clients/CL-3599');
      await expect(page.getByRole('heading', { level: 1, name: 'You can’t open this client' })).toBeVisible();
      await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
      await expect(page.locator('body')).not.toContainText('CL-3599');
      expect(await page.title()).toBe('Client · PSL Factory');
      if (phone) await expect(backLink(page, 'Clients')).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, `client-${w}-noaccess`);
      await expectNoAxeViolations(page);
    });
  });
}
