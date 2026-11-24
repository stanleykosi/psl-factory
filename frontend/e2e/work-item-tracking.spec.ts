import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-91: the station track, six facts, agent card, reference, started line and paged history (mock/work-live.mjs).
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const SHOTS = process.env.F91_SHOTS;

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
};
const sent = (page: Page) => {
  const methods: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/')) methods.push(r.method());
  });
  return methods;
};

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4102: five stations with holders, the execution station current, Drafted Unknown, agent card without steps', async ({ page }) => {
      const methods = sent(page);
      await page.goto('/work/4102');
      await loaded(page);
      const stations = page.getByRole('list', { name: 'Stations in order' }).getByRole('listitem');
      await expect(stations).toHaveCount(5);
      await expect(stations.nth(0)).toContainText('Tunde Bello');
      await expect(stations.nth(1)).toContainText('Tola');
      await expect(stations.nth(2)).toContainText('Unassigned');
      await expect(stations.nth(1)).toHaveAttribute('aria-current', 'step');
      const facts = page.getByRole('list', { name: 'Facts' }).getByRole('listitem');
      await expect(facts).toHaveCount(6);
      await expect(facts.nth(0)).toContainText('Unknown');
      await expect(page.getByRole('list', { name: 'Facts' })).not.toContainText(/\bNo\b|\b0\b/);
      await expect(page.getByText(/Started by Tunde Bello/)).toBeVisible();
      const agent = page.getByRole('region', { name: 'Agent at work' });
      await expect(agent).toContainText('Tola');
      await expect(agent).toContainText('Drafting the weekly update');
      await expect(agent.locator('ol, .psl-step')).toHaveCount(0);
      expect(methods.every((m) => m === 'GET')).toBe(true);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4102-${viewport.width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4101 verified: only Verified shows a time; the reference sits beside the id', async ({ page }) => {
      await page.goto('/work/4101');
      await loaded(page);
      const facts = page.getByRole('list', { name: 'Facts' }).getByRole('listitem');
      await expect(facts.locator('time')).toHaveCount(1);
      await expect(facts.nth(5).locator('time')).toBeVisible();
      await expect(facts.nth(0)).toContainText('Earned');
      if (viewport.width > 700) await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toContainText('INV-0412');
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4101-${viewport.width}.png`, fullPage: true });
    });

    test('4103 reviewed is Unknown; 4104 has no reference and a stopped station', async ({ page }) => {
      await page.goto('/work/4103');
      await loaded(page);
      await expect(page.getByRole('list', { name: 'Facts' }).getByRole('listitem').nth(1)).toContainText('Unknown');
      await page.goto('/work/4104');
      await loaded(page);
      await expect(page.locator('main#main')).not.toContainText('INV-');
      await expect(page.locator('.psl-station--stopped')).toHaveCount(1);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4104-${viewport.width}.png`, fullPage: true });
    });

    test('4105 has no tracking: no track, no facts, no started line', async ({ page }) => {
      await page.goto('/work/4105');
      await loaded(page);
      await expect(page.locator('.psl-track, .psl-facts')).toHaveCount(0);
      await expect(page.getByText(/Started by/)).toHaveCount(0);
    });

    test('4107: a failed tracking read shows one callout; Try again reads tracking only', async ({ page }) => {
      const reads: string[] = [];
      page.on('request', (r) => {
        if (r.url().includes('/api/v1/work/4107')) reads.push(new URL(r.url()).pathname);
      });
      await page.goto('/work/4107');
      await loaded(page);
      await expect(page.getByText(/couldn’t load where this work is held/)).toBeVisible();
      const before = reads.length;
      await page.getByRole('button', { name: 'Try again' }).first().click();
      await expect.poll(() => reads.filter((p) => p.endsWith('/tracking')).length).toBe(2);
      expect(reads.length - before).toBe(1);
    });

    test('history: actor tags, Older events appends 30 more, no duplicates, the button goes away', async ({ page }) => {
      const methods = sent(page);
      await page.goto('/work/4101/history');
      await loaded(page);
      await expect(page.getByText('AGENT').first()).toBeVisible();
      await expect(page.getByText('PERSON').first()).toBeVisible();
      await expect(page.locator('.work-hcard')).toHaveCount(30);
      await expect(page.getByText(/Showing the latest 30 changes\./)).toBeVisible();
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4101-history-${viewport.width}.png`, fullPage: true });
      await page.getByRole('button', { name: 'Older events' }).click();
      await expect(page.locator('.work-hcard')).toHaveCount(60);
      await expect(page.getByRole('button', { name: 'Older events' })).toHaveCount(0);
      await expect(page.getByText(/Showing all changes\./)).toBeVisible();
      expect(methods.every((m) => m === 'GET')).toBe(true);
    });
  });
}
