import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// SCR-24 "Assign accountable PM" (F-36) against the contract mock: the panel over My work's Unassigned list at 1440 and 390,
// the writes, the uncertain cases, 44px targets on a phone, axe WCAG 2.2 AA.
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

const dialog = (page: Page) => page.getByRole('dialog', { name: /Assign accountable PM|Set an owner/ });
const panelUrl = (id: string) => `/my-work?queue=unassigned&assign=${id}`;

async function openPanel(page: Page, id: string) {
  await page.goto(panelUrl(id));
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page).getByText('Loading…')).toHaveCount(0);
}

async function choose(page: Page, label: RegExp | string, option: RegExp | string) {
  await dialog(page).getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
}

/** Every visible button, link and field in the dialog is at least 44px in its smaller side. */
async function smallTargets(page: Page) {
  return dialog(page).evaluate((root) =>
    [...root.querySelectorAll<HTMLElement>('button, a[href], input:not([type="hidden"]), textarea, [role="combobox"]')]
      .filter((el) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden')
      .map((el) => {
        const r = el.getBoundingClientRect();
        return { name: el.getAttribute('aria-label') ?? el.textContent?.trim().slice(0, 30) ?? el.tagName, w: Math.round(r.width), h: Math.round(r.height) };
      })
      .filter((t) => Math.min(t.w, t.h) < 44),
  );
}

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const mockLog = async (page: Page) => (await (await page.request.get(`${MOCK}/__mock/workspace-log`)).json()) as { assignments: { work_id: string; status: number; written: boolean }[] };
const eml = (name = 'assignment-email.eml') => ({ name, mimeType: 'message/rfc822', buffer: Buffer.alloc(18 * 1024, 65) });

test.beforeEach(async ({ request, context }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await setCookies(context, { psl_mock_persona: 'pmo_lead' });
});

test.describe('desktop 1440', () => {
  test.use({ viewport: DESKTOP });

  test('a row opens the panel over the list; Escape, Cancel and × close it and return focus to the row link', async ({ page }) => {
    await page.goto('/my-work?queue=unassigned');
    const link = page.getByRole('link', { name: /Tamarind Loans · loan origination RFP/ }).first();
    await link.click();
    await expect(dialog(page)).toBeVisible();
    await expect(page).toHaveURL(/\?queue=unassigned&assign=W-33\d\d$/);
    await expect(dialog(page).getByText('Tamarind Loans · TL-RFP-2026-014')).toBeVisible();
    await expect(dialog(page).getByRole('combobox', { name: /Accountable PM/ })).toContainText('Choose a PM');
    await expect(page.getByRole('tab', { name: /Unassigned/ })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dialog(page)).toHaveCount(0);
    await expect(link).toBeFocused();
    await link.click();
    await dialog(page).getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog(page)).toHaveCount(0);
    await link.click();
    await dialog(page).getByRole('button', { name: 'Close' }).click();
    await expect(dialog(page)).toHaveCount(0);
    await expect(link).toBeFocused();
    expect((await mockLog(page)).assignments).toEqual([]);
  });

  test('assigns W-3301: the notice appears only after the read-back, the row is gone, the count is one lower', async ({ page }) => {
    await openPanel(page, 'W-3301');
    await expect(dialog(page).getByText('3 people can prepare RFPs here')).toBeVisible();
    await expect(dialog(page).getByText('PMO Lead', { exact: true })).toBeVisible();
    await choose(page, /Accountable PM/, /Tunde Bello/);
    await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'TL-RFP-2026-014 is now with Tunde Bello.' })).toBeVisible();
    await expect(dialog(page)).toHaveCount(0);
    await expect(page.getByRole('tab', { name: /Unassigned/ })).toBeFocused();
    await expect(page.getByRole('tab', { name: /Unassigned/ })).toContainText('5');
    await expect(page.getByRole('link', { name: /Tamarind Loans · loan origination RFP/ })).toHaveCount(1);
    expect((await mockLog(page)).assignments).toMatchObject([{ work_id: 'W-3301', status: 200, written: true }]);
  });

  test('W-3302 uploads proof, sends acting_role and the evidence, and records it', async ({ page }) => {
    await openPanel(page, 'W-3302');
    await expect(dialog(page).getByText('Tola starts reading the RFP once the PM opens it.')).toBeVisible();
    await choose(page, /You are assigning as/, 'CEO');
    await choose(page, /Accountable PM/, /Tunde Bello/);
    await dialog(page).locator('input[type="file"]').setInputFiles(eml());
    await expect(dialog(page).getByText('Uploaded · 18 KB')).toBeVisible();
    await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'TL-RFP-2026-014 is now with Tunde Bello.' })).toBeVisible();
    expect((await mockLog(page)).assignments).toMatchObject([{ work_id: 'W-3302', status: 200, written: true }]);
  });

  test('a written-then-failed write (W-3306) shows the read-back and one assignment; the uncertain cookie writes none', async ({ page, context }) => {
    await openPanel(page, 'W-3306');
    await choose(page, /Accountable PM/, /Tunde Bello/);
    await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
    await expect(dialog(page).getByText('Assigned to Tunde Bello')).toBeVisible();
    await expect(dialog(page).getByRole('combobox')).toHaveCount(0);
    expect((await mockLog(page)).assignments).toMatchObject([{ work_id: 'W-3306', status: 500, written: true }]);
    await dialog(page).getByRole('button', { name: 'Close' }).last().click();
    await expect(dialog(page)).toHaveCount(0);
    await setCookies(context, { psl_mock_assign: 'uncertain' });
    await openPanel(page, 'W-3301');
    await choose(page, /Accountable PM/, /Tunde Bello/);
    await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
    await expect(dialog(page).getByText(/We couldn’t confirm the PM was assigned/)).toBeVisible();
    await expect(dialog(page).getByRole('button', { name: 'Try again' })).toBeVisible();
    expect((await mockLog(page)).assignments.map((a) => [a.work_id, a.written])).toEqual([['W-3306', true], ['W-3301', false]]);
  });

  test('W-3305 has no assign and goes on to the work item; the Finance Lead’s receipt rows still end on their items', async ({ page, context }) => {
    await page.goto(panelUrl('W-3305'));
    await expect(page).toHaveURL(/\/work\/W-3305$/);
    await expect(page.getByRole('button', { name: 'Assign PM' })).toHaveCount(0);
    await setCookies(context, { psl_mock_persona: 'finance_lead' });
    await page.goto('/my-work?queue=unassigned');
    await page.getByRole('link', { name: /Ikeja Retail · Receipt for INV-0416/ }).click();
    await expect(page).toHaveURL(/\/work\/W-1137$/);
    await page.goto('/my-work?queue=unassigned');
    await page.getByRole('link', { name: /Eko Insurance · November statement/ }).click();
    await expect(page).toHaveURL(/\/work\/W-1138$/);
  });

  test('persona pm keeps "Only Leads can see unassigned work."', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'pm' });
    await page.goto('/my-work?queue=unassigned');
    await expect(page.getByText('Only Leads can see unassigned work.')).toBeVisible();
  });

  const STATES: [string, (page: Page) => Promise<unknown>][] = [
    ['W-3301', (page) => openPanel(page, 'W-3301')],
    ['W-3302 before upload', (page) => openPanel(page, 'W-3302')],
    ['W-3302 after upload', async (page) => {
      await openPanel(page, 'W-3302');
      await dialog(page).locator('input[type="file"]').setInputFiles(eml());
      await expect(dialog(page).getByText('Uploaded · 18 KB')).toBeVisible();
    }],
    ['W-3304 empty', async (page) => {
      await openPanel(page, 'W-3304');
      await expect(dialog(page).getByText('No one can prepare RFPs here yet.')).toBeVisible();
    }],
    ['validation', async (page) => {
      await openPanel(page, 'W-3303');
      await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
      await expect(dialog(page).getByText('Choose a PM to continue.').first()).toBeVisible();
    }],
    ['422', async (page) => {
      await setCookies(page.context(), { psl_mock_assign: 'invalid' });
      await openPanel(page, 'W-3301');
      await choose(page, /Accountable PM/, /Tunde Bello/);
      await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
      await expect(dialog(page).getByText('Check person_id.').first()).toBeVisible();
    }],
    ['uncertain', async (page) => {
      await setCookies(page.context(), { psl_mock_assign: 'uncertain' });
      await openPanel(page, 'W-3301');
      await choose(page, /Accountable PM/, /Tunde Bello/);
      await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
      await expect(dialog(page).getByText(/We couldn’t confirm the PM was assigned/)).toBeVisible();
    }],
    ['not open (W-3399)', async (page) => {
      await openPanel(page, 'W-3399');
      await expect(dialog(page).getByText('You can’t open this item.')).toBeVisible();
    }],
    ['list after success', async (page) => {
      await openPanel(page, 'W-3301');
      await choose(page, /Accountable PM/, /Tunde Bello/);
      await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'is now with Tunde Bello.' })).toBeVisible();
    }],
  ];
  for (const [name, setup] of STATES) {
    test(`axe: ${name}`, async ({ page }) => {
      await setup(page);
      await expectNoAxeViolations(page);
    });
  }

  test('nothing animates under reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await openPanel(page, 'W-3301');
    const running = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running' && a.effect && (a.effect as KeyframeEffect).target?.closest?.('[role="dialog"]')).length);
    expect(running).toBe(0);
  });
});

test.describe('phone 390', () => {
  test.use({ viewport: PHONE });

  test('the sheet shows the same parts in one column, with 44px targets before and after an upload', async ({ page }) => {
    await openPanel(page, 'W-3302');
    await expect(dialog(page).getByText('Tamarind Loans · TL-RFP-2026-014')).toBeVisible();
    await expect(dialog(page).getByText('3 people can prepare RFPs here')).toBeVisible();
    await expect(dialog(page).getByText('Only people allowed to prepare RFPs for this workspace are listed.', { exact: false })).toBeVisible();
    await expect(dialog(page).getByRole('button', { name: 'Cancel' })).toHaveCount(0);
    expect(await smallTargets(page)).toEqual([]);
    expect(await noHorizontalScroll(page)).toBe(true);
    await dialog(page).locator('input[type="file"]').setInputFiles(eml());
    await expect(dialog(page).getByText('Uploaded · 18 KB')).toBeVisible();
    expect(await smallTargets(page)).toEqual([]);
    const send = dialog(page).getByRole('button', { name: 'Assign PM' });
    const box = (await send.boundingBox())!;
    const sheet = (await dialog(page).boundingBox())!;
    expect(box.width).toBeGreaterThan(sheet.width - 40);
    expect(box.y + box.height).toBeGreaterThan(sheet.y + sheet.height - 40);
  });

  test('a failed upload shows Try again at 44px', async ({ page }) => {
    await page.route('**/api/v1/cases/**/evidence', (route) => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ code: 'server_error', message: 'x' }) }));
    await openPanel(page, 'W-3302');
    await dialog(page).locator('input[type="file"]').setInputFiles(eml());
    await expect(dialog(page).getByRole('button', { name: 'Try again' })).toBeVisible();
    expect(await smallTargets(page)).toEqual([]);
    await choose(page, /Accountable PM/, /Sola Martins/);
    await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
    await expect(dialog(page).getByText('Remove the file that didn’t upload, or try it again.')).toBeVisible();
    expect((await mockLog(page)).assignments).toEqual([]);
  });

  test('assigning on a phone closes the sheet and shows the notice', async ({ page }) => {
    await openPanel(page, 'W-3301');
    await choose(page, /Accountable PM/, /Tunde Bello/);
    await dialog(page).getByRole('button', { name: 'Assign PM' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'TL-RFP-2026-014 is now with Tunde Bello.' })).toBeVisible();
    await expect(dialog(page)).toHaveCount(0);
  });

  for (const id of ['W-3301', 'W-3302', 'W-3304']) {
    test(`axe: ${id}`, async ({ page }) => {
      await openPanel(page, id);
      await expectNoAxeViolations(page);
    });
  }
});
