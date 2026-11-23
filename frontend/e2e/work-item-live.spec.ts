import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-85: the work item on the live shapes (integer ids, served by mock/work-live.mjs).
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const SHOTS = process.env.F85_SHOTS;

const loaded = async (page: Page) => {
  await expect(page.locator('.psl-loading')).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
};
const writes = (page: Page) => {
  const sent: string[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/api/')) sent.push(`${r.method()} ${new URL(r.url()).pathname}`);
  });
  return sent;
};

for (const [label, viewport] of [['desktop 1440', { width: 1440, height: 900 }], ['phone 390', { width: 390, height: 844 }]] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    test('4102 processing: the live parts only, the weekly report panel, no write buttons', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4102');
      await loaded(page);
      const main = page.locator('main#main');
      await expect(main.getByRole('heading', { level: 1 })).toHaveText('Weekly update for Lagoon Health');
      await expect(main.locator('.work-state')).toHaveText('Processing');
      await expect(main.getByText('Drafting the weekly update')).toBeVisible();
      await expect(main.locator('.psl-track, .work-facts, .work-agent, .work-agentsec')).toHaveCount(0);
      await expect(main.getByText(/not available/i)).toHaveCount(0);
      // the weekly report panel through the adapter
      await expect(main.getByRole('heading', { name: 'Period' })).toBeVisible();
      await expect(main.getByText('3 records cited')).toBeVisible();
      await expect(main.getByText('No receipt yet')).toBeVisible();
      await expect(main.getByText('Wait for the client to confirm receipt.')).toBeVisible();
      await expect(main.getByRole('button', { name: /resume|cancel|check what happened|release|start|correct/i })).toHaveCount(0);
      expect(sent).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4102-${viewport.width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => v.id)).toEqual([]);
    });

    test('4103 decisions waiting: one link, for the task that can be decided', async ({ page }) => {
      const sent = writes(page);
      await page.goto('/work/4103');
      await loaded(page);
      const links = page.getByRole('link', { name: 'Open decision' });
      await expect(links).toHaveCount(1);
      await expect(links).toHaveAttribute('href', '/work/4103/decide?task=9101');
      expect(sent).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4103-${viewport.width}.png`, fullPage: true });
    });

    test('4101 verified shows the output link; 4103 shows none', async ({ page }) => {
      await page.goto('/work/4101');
      await loaded(page);
      await expect(page.getByRole('link', { name: 'Open the output' })).toHaveAttribute('href', '/api/v1/work/4101/output');
      await page.goto('/work/4103');
      await loaded(page);
      await expect(page.getByRole('link', { name: 'Open the output' })).toHaveCount(0);
    });

    test('4104 and 4105 load with null revisions, and show no 0', async ({ page }) => {
      for (const id of [4104, 4105]) {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.locator('main#main')).not.toContainText(/revision\s*0/i);
      }
      await page.goto('/work/4104');
      await loaded(page);
      await expect(page.getByText('A policy value is missing.')).toBeVisible();
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4104-${viewport.width}.png`, fullPage: true });
    });

    test('4106 is unavailable, in the same words as any unknown id', async ({ page }) => {
      await page.goto('/work/4106');
      await expect(page.getByRole('heading', { name: 'This record is unavailable.' })).toBeVisible();
      const first = await page.locator('main#main').innerText();
      await page.goto('/work/999999');
      await expect(page.getByRole('heading', { name: 'This record is unavailable.' })).toBeVisible();
      expect(await page.locator('main#main').innerText()).toBe(first);
    });

    test('history: tabs ask by kind, no counts or Show more, the latest-30 caption only at 30 rows', async ({ page }) => {
      const asked: string[] = [];
      page.on('request', (r) => {
        if (r.url().includes('/api/v1/work/') && r.url().includes('/history')) asked.push(new URL(r.url()).searchParams.get('kind') ?? 'all');
      });
      await page.goto('/work/4101/history');
      await loaded(page);
      await expect(page.getByText('Odd station')).toBeVisible();
      for (const name of ['Decisions', 'Agent work', 'Evidence']) await page.getByRole('radio', { name }).click();
      await expect.poll(() => asked).toEqual(['all', 'decision', 'worker', 'evidence']);
      await expect(page.getByText(/show more/i)).toHaveCount(0);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/4101-history-${viewport.width}.png`, fullPage: true });
      await page.goto('/work/4108/history');
      await expect(page.getByText(/Showing the latest 30 changes\./)).toBeVisible();
    });

    test('a failed history read keeps the tab and Try again recovers', async ({ page, context }) => {
      await page.goto('/work/4101/history');
      await loaded(page);
      await context.addCookies([{ name: 'psl_mock_scenario', value: '503', url: test.info().project.use.baseURL! }]);
      await page.getByRole('radio', { name: 'Agent work' }).click();
      await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
      await expect(page.getByRole('radio', { name: 'Agent work' })).toBeChecked();
      await context.clearCookies({ name: 'psl_mock_scenario' });
      await page.getByRole('button', { name: 'Try again' }).click();
      await expect(page.getByRole('list', { name: /History/ })).toBeVisible();
    });
  });
}
