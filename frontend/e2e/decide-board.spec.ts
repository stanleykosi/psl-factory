import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// SCR-03 boards at 1440 and 390 on the mock's live decision desk: default, done, stale, not-yours. Axe, no sideways
// scroll, and 44px tap targets on the phone buttons.
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

async function open(page: Page, work: string, task: string) {
  await page.goto(`/work/${work}/decide?task=${task}`);
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
  await expect(page.getByText('Getting this decision ready…')).toHaveCount(0);
}
const pick = (page: Page) => page.getByRole('radio', { name: /client email/ }).check();

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

const STATES: [string, (page: Page) => Promise<unknown>][] = [
  ['default', (page) => open(page, '17', '41')],
  [
    'default with evidence chosen',
    async (page) => {
      await open(page, '17', '41');
      await pick(page);
    },
  ],
  [
    'done after approving',
    async (page) => {
      await open(page, '17', '41');
      await pick(page);
      await page.getByRole('button', { name: 'Approve v2' }).click();
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Invoice 3 for the Lekki handover is approved');
    },
  ],
  [
    'stale after Approve',
    async (page) => {
      await page.context().addCookies([{ name: 'psl_mock_decide', value: 'stale', domain: 'localhost', path: '/' }]);
      await open(page, '17', '41');
      await pick(page);
      await page.getByRole('button', { name: 'Approve v2' }).click();
      await expect(page.getByText('A newer version arrived while you were reading.')).toBeVisible();
    },
  ],
  ['not-yours', (page) => open(page, '18', '42')],
];

for (const [label, viewport] of [
  ['desktop 1440', { width: 1440, height: 900 }],
  ['phone 390', { width: 390, height: 844 }],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    for (const [name, reach] of STATES) {
      test(`${name}: no axe violations, no sideways scroll`, async ({ page }) => {
        await reach(page);
        const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
        expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      });
    }

    if (viewport.width === 390) {
      test('the pinned decision buttons are at least 44px tall', async ({ page }) => {
        await open(page, '17', '41');
        await pick(page);
        for (const name of [/^Approve v2/, 'Return', 'Reject']) {
          const box = await page.getByRole('button', { name }).boundingBox();
          expect(box!.height).toBeGreaterThanOrEqual(44);
        }
      });
    }
  });
}
