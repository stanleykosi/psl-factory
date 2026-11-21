import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

// F-16: the decision page drawn to the SCR-03 boards, on the W-19xx board fixtures, at 1440 and 390.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function openDecision(page: Page, id: string, task: string) {
  await page.goto(`/work/${id}/decide?task=${task}`);
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeAttached();
  const approve = page.getByRole('button', { name: /^Approve v/ });
  if (await approve.count()) await expect(approve).toBeEnabled();
}

type State = { name: string; back: 'Decisions' | 'Queue'; reach: (page: Page) => Promise<void> };
const STATES: State[] = [
  { name: 'default W-1901', back: 'Decisions', reach: (page) => openDecision(page, 'W-1901', 'T-1901') },
  {
    name: 'done after approving W-1901',
    back: 'Decisions',
    reach: async (page) => {
      await openDecision(page, 'W-1901', 'T-1901');
      await page.getByRole('button', { name: 'Approve v2' }).click();
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Invoice v2 for Lagoon Health is approved');
      await expect(page.getByText(/Chidi will issue it/)).toBeVisible();
    },
  },
  {
    name: 'stale W-1902 after Approve',
    back: 'Decisions',
    reach: async (page) => {
      await openDecision(page, 'W-1902', 'T-1902');
      await page.getByRole('button', { name: 'Approve v2' }).click();
      await expect(page.getByRole('button', { name: 'Review version 3' })).toBeVisible();
    },
  },
  { name: 'not-yours W-1903', back: 'Queue', reach: (page) => openDecision(page, 'W-1903', 'T-1903') },
  { name: 'own W-1904', back: 'Queue', reach: (page) => openDecision(page, 'W-1904', 'T-1904') },
];

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

for (const [label, viewport, titleSize] of [
  ['desktop 1440', DESKTOP, '40px'],
  ['phone 390', PHONE, '26px'],
] as const) {
  test.describe(label, () => {
    test.use({ viewport });

    for (const state of STATES) {
      test(`${state.name}: no axe violations, no sideways scroll, one ${titleSize} title, the frame's back link`, async ({ page }) => {
        await state.reach(page);
        await expectNoAxeViolations(page);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
        const h1 = page.locator('h1');
        await expect(h1).toHaveCount(1);
        await expect(h1).toHaveClass(/shell-title/);
        expect(await h1.evaluate((el) => getComputedStyle(el).fontSize)).toBe(titleSize);
        const back = page.locator(`header.psl-phonebar a[aria-label="Back to ${state.back}"]`);
        await expect(back).toHaveAttribute('href', '/my-work');
        if (viewport === PHONE) await expect(back).toHaveText(`← ${state.back}`);
        else await expect(back).toBeHidden();
        await expect(page.locator('main').getByRole('link', { name: /^(←|Back to (Queue|Decisions))/ })).toHaveCount(0);
        // controls only for the person who can act
        const controls = page.getByRole('button', { name: /^(Approve|Return|Reject)/ });
        if (state.name.startsWith('default')) await expect(controls).toHaveCount(3);
        else await expect(controls).toHaveCount(0);
      });
    }

    test('no access: one title at the frame size and "← Queue"', async ({ page }) => {
      await page.route('**/api/v1/work/W-1901', (route) =>
        route.fulfill({ status: 403, contentType: 'application/json', body: '{"code":"forbidden","message":"No."}' }),
      );
      await page.goto('/work/W-1901/decide?task=T-1901');
      const h1 = page.locator('h1');
      await expect(h1).toHaveCount(1);
      expect(await h1.evaluate((el) => getComputedStyle(el).fontSize)).toBe(titleSize);
      await expect(page.locator('header.psl-phonebar a[aria-label="Back to Queue"]')).toHaveAttribute('href', '/my-work');
      await expect(page.getByText('W-1901')).toHaveCount(0);
    });

    test('Tab reaches Note, Approve, Return and Reject in order with a visible focus ring', async ({ page }) => {
      await openDecision(page, 'W-1901', 'T-1901');
      const order: Locator[] = [
        page.getByLabel(/^Note/),
        page.getByRole('button', { name: 'Approve v2' }),
        page.getByRole('button', { name: 'Return' }),
        page.getByRole('button', { name: 'Reject' }),
      ];
      for (let i = 0; i < 80; i++) {
        await page.keyboard.press('Tab');
        if (await order[0].evaluate((el) => el === document.activeElement)) break;
      }
      for (const [i, target] of order.entries()) {
        if (i > 0) await page.keyboard.press('Tab');
        expect(
          await target.evaluate((el) => {
            const s = getComputedStyle(el);
            return { focused: el === document.activeElement, style: (s.outlineStyle !== 'none' ? s.outlineStyle : /rgb\(36, 89, 214\)|0px 0px 0px 2px inset/.test(s.boxShadow + s.borderTopColor + s.textDecorationColor) ? 'solid' : 'none'), width: (s.outlineStyle !== 'none' ? s.outlineWidth : '2px') };
          }),
        ).toEqual({ focused: true, style: 'solid', width: '2px' });
      }
    });

    test('targets are at least 44px; at 390 Approve is the 54px pinned button', async ({ page }) => {
      await openDecision(page, 'W-1901', 'T-1901');
      for (const name of ['Approve v2', 'Return', 'Reject']) {
        const box = (await page.getByRole('button', { name }).boundingBox())!;
        expect(box.height).toBeGreaterThanOrEqual(44);
        expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
      }
      if (viewport === PHONE) {
        const approve = page.locator('.psl-actionbar').getByRole('button', { name: 'Approve v2' });
        expect((await approve.boundingBox())!.height).toBeGreaterThanOrEqual(54);
        expect(await page.locator('.psl-actionbar').evaluate((el) => getComputedStyle(el).position)).toBe('fixed');
      }
      const links = page.locator('main a');
      for (let i = 0; i < (await links.count()); i++) {
        const link = links.nth(i);
        if (!(await link.isVisible())) continue;
        // inline links in running text are exempt (WCAG 2.5.8); the board's standalone links are not
        const inline = await link.evaluate((el) => getComputedStyle(el).display === 'inline');
        if (!inline) expect((await link.boundingBox())!.height, (await link.textContent()) ?? '').toBeGreaterThanOrEqual(44);
      }
    });

    test('the not-yours comment box is disabled and sends nothing', async ({ page }) => {
      const writes: string[] = [];
      page.on('request', (r) => {
        if (r.method() !== 'GET') writes.push(new URL(r.url()).pathname);
      });
      await openDecision(page, 'W-1903', 'T-1903');
      const box = page.getByLabel('Comment for the Finance Lead (optional)');
      await expect(box).toBeDisabled();
      await expect(page.getByRole('button', { name: 'Add comment' })).toBeDisabled();
      await expect(page.getByText('Comments aren’t available yet.')).toBeVisible();
      await page.getByRole('button', { name: 'Add comment' }).click({ force: true });
      expect(writes).toEqual([]);
    });

    test('with reduced motion nothing animates', async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await openDecision(page, 'W-1901', 'T-1901');
      await page.getByRole('button', { name: 'Return' }).hover();
      const moving = await page.evaluate(() =>
        [...document.querySelectorAll('*')].filter((el) => {
          const s = getComputedStyle(el);
          const seconds = (v: string) => Math.max(...v.split(',').map((d) => parseFloat(d) || 0));
          return (s.animationName !== 'none' && seconds(s.animationDuration) > 0) || seconds(s.transitionDuration) > 0;
        }).length,
      );
      expect(moving).toBe(0);
    });
  });
}
