import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// F-30 issue detail (W-2411 to W-2414) against the contract mock: the four states, the three writes, the register row
// that opens the issue, the phone Drawer, and axe WCAG 2.2 AA at 1440 and 390.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const log = async () => (await (await fetch(`${MOCK}/__mock/workspace-log`)).json()) as { assignments: { written: boolean }[] };

async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
    test.beforeEach(async ({ context }) => {
      expect((await fetch(`${MOCK}/__mock/reset`, { method: 'POST' })).status).toBe(204);
      await setCookies(context, { psl_mock_persona: 'pm' });
    });

    for (const [id, status] of [
      ['W-2411', 'FIX IN TESTING'],
      ['W-2412', 'NO RESPONSE · 3 DAYS'],
      ['W-2413', 'OWNER NEEDED'],
      ['W-2414', 'FOLLOW-UP VERIFIED'],
    ] as const) {
      test(`${id}: ${status}, one h1, no sideways scroll, axe clean`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
        await expect(page.getByText(status, { exact: true }).first()).toBeVisible();
        expect(await noHorizontalScroll(page)).toBe(true);
        await expectNoAxeViolations(page);
      });
    }

    test('post an owner update: the form, axe on it, one write, the new item from the re-read', async ({ page }) => {
      await page.goto('/work/W-2411');
      await loaded(page);
      await page.getByRole('button', { name: 'Post update' }).click();
      const form = page.getByRole('form', { name: 'Post update' });
      await expect(form).toBeVisible();
      await expectNoAxeViolations(page);
      await form.getByRole('button', { name: 'Post update' }).click();
      await expect(form.getByText(/Add update type to continue|Add update to continue/).first()).toBeVisible();
      await expectNoAxeViolations(page);
      await form.getByText('Progress update').click();
      await form.getByLabel('Update', { exact: true }).fill('Fix verified on 2 of 3 models; third model test tomorrow.');
      await form.getByRole('button', { name: 'Post update' }).click();
      await expect(page.getByText('Done: update posted.')).toBeVisible();
      await expect(page.getByText('Owner update · recorded by PM')).toBeVisible();
    });

    test('record a reply, then Raise an escalation opens Start work and starts nothing', async ({ page }) => {
      await page.goto('/work/W-2412');
      await loaded(page);
      await page.getByRole('button', { name: 'Raise an escalation' }).click();
      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();
      await expect(dialog.getByText(/escalat/i).first()).toBeVisible();
      await expectNoAxeViolations(page);
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Raise an escalation' })).toBeFocused();
      await page.getByRole('button', { name: 'Record a reply' }).click();
      const form = page.getByRole('form', { name: 'Record a reply' });
      await form.getByLabel('Reply', { exact: true }).fill('Engineering is looking at it today.');
      await form.getByRole('button', { name: 'Record a reply' }).click();
      await expect(page.getByText('Owner reply · recorded by PM')).toBeVisible();
    });

    test('set an owner: the form, one write, no second assignment offered', async ({ page }) => {
      await page.goto('/work/W-2413');
      await loaded(page);
      await page.getByRole('button', { name: 'Set an owner' }).click();
      const form = page.getByRole('form', { name: 'Set an owner' });
      await expect(form).toBeVisible();
      if (phone) await expect(page.getByRole('dialog')).toBeVisible();
      await expectNoAxeViolations(page);
      await form.getByRole('button', { name: 'Set owner' }).click();
      await expect(form.getByText('Choose an owner to continue.').first()).toBeVisible();
      await expectNoAxeViolations(page);
      await form.getByRole('combobox', { name: /Owner/ }).click();
      await page.getByRole('option', { name: /Engineering/ }).click();
      await form.getByRole('button', { name: 'Set owner' }).click();
      await expect(page.getByText('Owner set: Engineering')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Set an owner' })).toHaveCount(0);
      expect((await log()).assignments.filter((a) => a.written)).toHaveLength(1);
    });

    test('psl_mock_assign=uncertain: not recorded, nothing written, the form is offered again', async ({ page, context }) => {
      await setCookies(context, { psl_mock_assign: 'uncertain' });
      await page.goto('/work/W-2413');
      await loaded(page);
      await page.getByRole('button', { name: 'Set an owner' }).click();
      const form = page.getByRole('form', { name: 'Set an owner' });
      await form.getByRole('combobox', { name: /Owner/ }).click();
      await page.getByRole('option', { name: /Tunde Bello/ }).click();
      await form.getByRole('button', { name: 'Set owner' }).click();
      await expect(page.getByText('Not recorded')).toBeVisible();
      await expectNoAxeViolations(page);
      expect((await log()).assignments.filter((a) => a.written)).toHaveLength(0);
      await expect(form.getByRole('button', { name: 'Try again' })).toBeVisible();
    });

    test('psl_mock_assign=uncertain_written: the re-read shows the owner and no second assignment is offered', async ({ page, context }) => {
      await setCookies(context, { psl_mock_assign: 'uncertain_written' });
      await page.goto('/work/W-2413');
      await loaded(page);
      await page.getByRole('button', { name: 'Set an owner' }).click();
      const form = page.getByRole('form', { name: 'Set an owner' });
      await form.getByRole('combobox', { name: /Owner/ }).click();
      await page.getByRole('option', { name: /Tunde Bello/ }).click();
      await form.getByRole('button', { name: 'Set owner' }).click();
      await expect(page.getByText('FOLLOW-UP STARTED')).toBeVisible();
      await expect(page.getByRole('button', { name: /Set an owner|Set owner|Try again/ })).toHaveCount(0);
      expect((await log()).assignments.filter((a) => a.written)).toHaveLength(1);
    });

    test('an unknown issue is the same not-open view with no name', async ({ page }) => {
      await page.goto('/work/W-2499');
      await expect(page.getByText('Loading…')).toHaveCount(0);
      await expect(page.getByText('Login fails on older Android phones')).toHaveCount(0);
      await expectNoAxeViolations(page);
    });

    if (!phone) {
      test('the register row opens the issue, and its project tabs link to their pages', async ({ page }) => {
        await page.goto('/projects/P-0101/registers');
        await loaded(page);
        await page.getByRole('link', { name: 'Login fails on older Android phones' }).click();
        await expect(page).toHaveURL(/\/work\/W-2411$/);
        await expect(page.getByText('Engineering (recorded by PM)').first()).toBeVisible();
        const bar = page.getByRole('navigation', { name: 'Project' });
        await expect(bar.getByRole('link')).toHaveCount(6);
        await expect(bar.getByRole('link', { name: 'Registers' })).toHaveAttribute('href', '/projects/P-0101/registers');
        await expect(bar.locator('[aria-current]')).toHaveCount(0);
      });
    }

    if (phone) {
      test('the phone forms open in the full-height Drawer; Escape and Cancel close it and focus returns', async ({ page }) => {
        await page.goto('/work/W-2411');
        await loaded(page);
        await expect(page.getByRole('link', { name: /Project/ }).first()).toHaveAttribute('href', '/projects/P-0101');
        const opener = page.getByRole('button', { name: 'Post update' });
        await opener.click();
        await expect(page.getByRole('dialog')).toBeVisible();
        await page.keyboard.press('Escape');
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(opener).toBeFocused();
        await opener.click();
        await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click();
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(opener).toBeFocused();
        for (const target of [opener]) expect((await target.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      });
    }
  });
}

test('no animation under reduced motion', async ({ page, context }) => {
  await setCookies(context, { psl_mock_persona: 'pm' });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/work/W-2411');
  await loaded(page);
  const moving = await page.evaluate(() => [...document.querySelectorAll('.ws *')].filter((el) => getComputedStyle(el).animationName !== 'none').length);
  expect(moving).toBe(0);
});
