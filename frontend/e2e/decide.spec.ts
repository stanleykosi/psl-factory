import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// SCR-03 on the mock's live decision desk (mock/live-decide.mjs): work 17 / task 41 decides, 18 / 42 is not yours.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
}

async function openDecision(page: Page, work: string, task: string) {
  await page.goto(`/work/${work}/decide?task=${task}`);
  await loaded(page);
  await expect(page).toHaveTitle('Decision · PSL Factory');
  await expect(page.getByText('Getting this decision ready…')).toHaveCount(0);
}

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const STATES: [string, (page: Page) => Promise<unknown>][] = [
  ['default', (page) => openDecision(page, '17', '41')],
  [
    'done after approving',
    async (page) => {
      await openDecision(page, '17', '41');
      await page.getByRole('radio', { name: /client email/ }).check();
      await page.getByRole('button', { name: 'Approve v2' }).click();
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Invoice 3 for the Lekki handover is approved');
    },
  ],
  [
    'stale after Approve',
    async (page) => {
      await page.context().addCookies([{ name: 'psl_mock_decide', value: 'stale', url: MOCK.replace('127.0.0.1', 'localhost') }]);
      await openDecision(page, '17', '41');
      await page.getByRole('radio', { name: /client email/ }).check();
      await page.getByRole('button', { name: 'Approve v2' }).click();
      await expect(page.getByText('A newer version arrived while you were reading.')).toBeVisible();
    },
  ],
  ['not-yours', (page) => openDecision(page, '18', '42')],
];

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    for (const [name, reach] of STATES) {
      test(`${name} has no axe violations and no sideways page scroll`, async ({ page }) => {
        await reach(page);
        await expectNoAxeViolations(page);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      });
    }
  });
}
