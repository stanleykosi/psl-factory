import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// Clients (SCR-35 list, group page and project contacts) against the contract mock in the live shape, at 1440 and 390, axe WCAG 2.2 AA.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const ACME = 'a1b2c3d4'.repeat(8);
const WAREHOUSE = '0b6f9e1a-3c44-4d0a-9d52-000000000001';
const FLEET = '0b6f9e1a-3c44-4d0a-9d52-000000000002';

test.use({ timezoneId: 'Africa/Lagos' });

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    test('list: groups and ungrouped projects, billing words, no owed column', async ({ page }) => {
      await page.goto('/clients');
      await expect(page.getByRole('heading', { level: 1, name: 'Clients' })).toBeVisible();
      await expect(page.getByText('Loading…')).toHaveCount(0);
      await expect(page.locator('[data-client-link]')).toHaveCount(8);
      await expect(page.getByText(/^8 clients loaded as of /)).toBeVisible();
      await expect(page.getByRole('link', { name: 'Acme Logistics' })).toHaveAttribute('href', `/clients/${ACME}`);
      await expect(page.getByText('Unknown').first()).toBeVisible();
      await expect(page.getByText('Owed')).toHaveCount(0);
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, 'list');
      await expectNoAxeViolations(page);
    });

    test('group page: projects with billing tags, owed per currency, pointer line', async ({ page }) => {
      await page.goto('/clients');
      await page.getByRole('link', { name: 'Acme Logistics' }).click();
      await expect(page.getByRole('heading', { level: 1, name: 'Acme Logistics' })).toBeVisible();
      await expect(page.getByText('Loading…')).toHaveCount(0);
      await expect(page.getByRole('link', { name: 'Warehouse portal', exact: true })).toHaveAttribute('href', `/projects/${WAREHOUSE}`);
      await expect(page.getByText('₦1,250,000.00')).toBeVisible();
      await expect(page.getByText('1 project with an amount not known')).toBeVisible();
      await expect(page.getByText('2 projects with an amount not known')).toBeVisible();
      await expect(page.getByText('Billing contacts are recorded for each project.')).toBeVisible();
      await expect(page.locator('main form, main input')).toHaveCount(0);
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, 'group');
      await expectNoAxeViolations(page);
    });

    test('project contacts: read only, add control held with its reason, history', async ({ page }) => {
      await page.goto(`/clients/${FLEET}`);
      await expect(page.getByRole('heading', { level: 1, name: 'Fleet tracking' })).toBeVisible();
      await expect(page.getByText('ada@example.org')).toBeVisible();
      const add = page.getByRole('button', { name: 'Add billing contact' });
      await expect(add).toBeDisabled();
      await expect(page.getByText(/not available yet/)).toBeVisible();
      await page.getByRole('button', { name: 'Show history' }).click();
      await expect(page.getByRole('list', { name: 'Billing contact history, newest first' })).toBeVisible();
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, 'contacts');
      await expectNoAxeViolations(page);
    });

    test('a key from nowhere shows no access and names nothing', async ({ page }) => {
      await page.goto(`/clients/${'f'.repeat(64)}`);
      await expect(page.getByRole('heading', { level: 1, name: 'You can’t open this client' })).toBeVisible();
      await expect(page).toHaveTitle('Client · PSL Factory');
    });
  });
}
