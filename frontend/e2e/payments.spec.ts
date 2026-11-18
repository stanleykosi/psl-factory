import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type BrowserContext, type Locator, type Page } from '@playwright/test';

// F-41: SCR-20 Payments and follow-up and the SCR-32 payment reminder against the contract mock, at 1440 and 390, axe
// WCAG 2.2 AA. Every request goes to the local mock; it sends no email and writes no money record.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

const requests: { method: string; url: URL }[] = [];
const invoiceReads = () => requests.filter((r) => r.method === 'GET' && r.url.pathname === '/api/v1/finance/invoices');
const stepPosts = () => requests.filter((r) => r.method === 'POST' && /\/api\/v1\/work\/W-\d+\/steps$/.test(r.url.pathname));
const log = async (request: APIRequestContext) => (await (await request.get(`${MOCK}/__mock/workspace-log`)).json()) as { entries: { idempotency_key: string; step: string; replay: boolean }[]; sends: Record<string, number> };

test.beforeEach(async ({ request, page }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  requests.length = 0;
  page.on('request', (r) => requests.push({ method: r.method(), url: new URL(r.url()) }));
});

async function openList(page: Page, search = '') {
  await page.goto(`/finance/payments${search}`);
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

async function openItem(page: Page, id: string) {
  await page.goto(`/work/${id}`);
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.locator('.ws')).toBeAttached();
}

const noSidewaysScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

/** Every button, button-styled link, chip button, tab and card link in main: 44 by 44 at least (D-92c; links inside sentences are exempt, D-95). */
async function expectTouchTargets(page: Page) {
  const targets = await page.locator('main button:visible, main a.psl-btn:visible, main [role=tab]:visible, main .psl-chip button:visible, main input:visible').all();
  for (const target of targets) {
    const box = (await target.boundingBox())!;
    const label = await target.evaluate((el) => el.outerHTML.slice(0, 90));
    expect(box.height, label).toBeGreaterThanOrEqual(44);
    expect(box.width, label).toBeGreaterThanOrEqual(44);
  }
}

const LIST_STATES: [string, Record<string, string>, (page: Page) => Promise<unknown>][] = [
  ['board', {}, (page) => openList(page, '?status=issued')],
  ['unknown', { psl_mock_invoices: 'unknown' }, (page) => openList(page)],
  ['empty', { psl_mock_invoices: 'empty' }, (page) => openList(page)],
  [
    'filter panel open',
    {},
    async (page) => {
      await openList(page);
      await page.getByRole('button', { name: /^Filter/ }).click();
      await expect(page.getByRole('radio', { name: 'Issued' })).toBeVisible();
    },
  ],
  ['not open (pm)', { psl_mock_persona: 'pm' }, (page) => openList(page)],
];

const ITEM_STATES: [string, (page: Page) => Promise<unknown>][] = [
  ['W-3801 draft', (page) => openItem(page, 'W-3801')],
  [
    'W-3801 Edit form with its error',
    async (page) => {
      await openItem(page, 'W-3801');
      await page.getByRole('button', { name: 'Edit', exact: true }).click();
      const form = page.getByRole('form', { name: 'Edit' });
      await form.getByRole('textbox', { name: /Message/ }).fill('');
      await form.getByRole('button', { name: 'Save draft', exact: true }).click();
      await expect(form.getByRole('textbox', { name: /Message/ })).toHaveAttribute('aria-invalid', 'true');
    },
  ],
  [
    'W-3801 sent',
    async (page) => {
      await openItem(page, 'W-3801');
      await page.getByRole('button', { name: 'Send reminder' }).click();
      await expect(page.getByText('SENT · CHECKING DELIVERY').first()).toBeVisible();
    },
  ],
  [
    'W-3803 uncertain',
    async (page) => {
      await openItem(page, 'W-3803');
      await page.getByRole('button', { name: 'Send reminder' }).click();
      await expect(page.getByRole('radiogroup', { name: 'Confirm what happened' })).toBeVisible();
    },
  ],
  ['W-3808 no billing contact', (page) => openItem(page, 'W-3808')],
];

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;
  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    for (const [name, cookies, reach] of LIST_STATES) {
      test(`list ${name}: axe clean, one h1, no sideways scroll, 44px controls`, async ({ page, context }) => {
        await setCookies(context, cookies);
        await reach(page);
        await expectNoAxeViolations(page);
        await expect(page.locator('h1')).toHaveCount(1);
        expect(await noSidewaysScroll(page)).toBe(true);
        if (phone) await expectTouchTargets(page);
      });
    }

    for (const [name, reach] of ITEM_STATES) {
      test(`${name}: axe clean, no sideways scroll, 44px controls`, async ({ page }) => {
        await reach(page);
        await expectNoAxeViolations(page);
        expect(await noSidewaysScroll(page)).toBe(true);
        for (const control of await page.locator('.ws button:visible, .ws a.psl-btn:visible, .resp-reconcile button:visible').all()) {
          expect((await control.boundingBox())!.height, await control.innerText()).toBeGreaterThanOrEqual(44);
        }
      });
    }

    test('the board rows, strip and note from the mock; no record-a-payment control; the note opens the reminder', async ({ page }) => {
      await openList(page, '?status=issued');
      if (phone) {
        const cards = page.locator('.payments__card');
        await expect(cards).toHaveCount(4);
        await expect(cards.nth(0)).toContainText('INV-0398 · overdue 9 days');
        await expect(cards.nth(3)).toContainText('PAID');
      } else {
        await expect(page.getByRole('table', { name: 'Invoices' }).getByRole('row')).toHaveCount(5);
        await expect(page.locator('.psl-resultcount')).toHaveText('4 INVOICES');
        await expect(page.getByText('Updated 12 Nov 10:00')).toBeVisible();
      }
      await expect(page.getByText('₦7,300,000.00 + Unknown')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Remove State filter' })).toBeVisible();
      await expect(page.getByText(/Record a payment/)).toHaveCount(0);
      // UI-2-1: the note's standalone link is a 44px target on a phone
      if (phone) expect((await page.getByRole('link', { name: 'Open the reminder draft' }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await expect(page.getByText(/7\.3M/)).toHaveCount(0);
      expect(invoiceReads()).toHaveLength(1);
      expect(invoiceReads()[0].url.searchParams.get('status')).toBe('issued');
      await page.getByRole('link', { name: 'Open the reminder draft' }).click();
      await expect(page).toHaveURL(/\/work\/W-3801$/);
      await expect(page.getByRole('heading', { level: 1, name: 'Payment reminder · Harmattan Bank' })).toBeVisible();
      expect(stepPosts()).toHaveLength(0);
    });

    if (phone) {
      test('the reminder is one column with the full message, and the pinned bar carries the returned steps', async ({ page }) => {
        await openItem(page, 'W-3801');
        await expect(page.getByText('If you\'ve already paid, please send the payment reference so we can match it.', { exact: false })).toBeVisible();
        for (const name of ['Send reminder', 'Edit', 'Not now']) await expect(page.getByRole('button', { name, exact: true })).toBeVisible();
        expect(await noSidewaysScroll(page)).toBe(true);
      });

      test('Edit opens in the full-height Drawer; Escape and Cancel close it and focus returns to Edit', async ({ page }) => {
        await openItem(page, 'W-3801');
        const opener = page.getByRole('button', { name: 'Edit', exact: true });
        await opener.click();
        await expect(page.getByRole('dialog')).toBeVisible();
        await expect(page.getByRole('dialog').getByRole('textbox', { name: /Subject/ })).toHaveValue('Reminder: invoice INV-0391 is 21 days overdue');
        await page.keyboard.press('Escape');
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(opener).toBeFocused();
        await opener.click();
        await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click();
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(opener).toBeFocused();
        expect(stepPosts()).toHaveLength(0);
      });
    }
  });
}

test.describe('requests (desktop)', () => {
  test.use({ viewport: DESKTOP });

  test('search sends q to the server after the pause; one character sends nothing', async ({ page }) => {
    await openList(page);
    const box = page.getByRole('searchbox', { name: 'Search' });
    await box.fill('H');
    await page.waitForTimeout(500);
    expect(invoiceReads()).toHaveLength(1);
    await box.fill('Harm');
    await expect(page.getByRole('table', { name: 'Invoices' }).getByRole('row')).toHaveCount(2);
    expect(invoiceReads()).toHaveLength(2);
    expect(invoiceReads()[1].url.searchParams.get('q')).toBe('Harm');
    await expect(page).toHaveURL(/\/finance\/payments\?q=Harm$/);
    await page.reload();
    await expect(page.getByRole('table', { name: 'Invoices' }).getByRole('row')).toHaveCount(2);
    expect(invoiceReads().at(-1)!.url.searchParams.get('q')).toBe('Harm');
  });

  test('error: the problem card; Try again sends one new read', async ({ page, context }) => {
    await setCookies(context, { psl_mock_invoices: 'error' });
    await openList(page);
    await expect(page.getByText('We couldn’t load the payments. Nothing was changed.')).toBeVisible();
    expect(invoiceReads()).toHaveLength(1);
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect.poll(() => invoiceReads().length).toBe(2);
  });

  test('no request is sent on load; Send is one POST and one send on the mock; Draft v2 after Edit, then Send carries revision 2', async ({ page, request }) => {
    await openItem(page, 'W-3801');
    expect(requests.filter((r) => r.method !== 'GET')).toHaveLength(0);
    await page.getByRole('button', { name: 'Edit', exact: true }).click();
    const form = page.getByRole('form', { name: 'Edit' });
    await form.getByRole('textbox', { name: /Subject/ }).fill('Reminder: INV-0391');
    await form.getByRole('button', { name: 'Save draft', exact: true }).click();
    await expect(page.getByText('Draft v2')).toBeVisible();
    await page.getByRole('button', { name: 'Send reminder' }).dblclick();
    await expect(page.getByText('SENT · CHECKING DELIVERY').first()).toBeVisible();
    const recorded = await log(request);
    expect(recorded.entries.map((e) => e.step)).toEqual(['edit_draft', 'send_reminder']);
    expect(Object.values(recorded.sends)).toEqual([1, 1]);
    expect(stepPosts()).toHaveLength(2);
  });

  test('Not now sends one set_aside and no send', async ({ page, request }) => {
    await openItem(page, 'W-3801');
    await page.getByRole('button', { name: 'Not now' }).click();
    await expect(page.getByText('Nothing was sent. The draft is kept.')).toBeVisible();
    expect((await log(request)).entries.map((e) => e.step)).toEqual(['set_aside']);
  });

  test('a routed network abort on send: one POST, the page re-reads, Send stays off, nothing is sent again', async ({ page }) => {
    await page.route('**/api/v1/work/W-3801/steps', (route) => route.abort('failed'));
    await openItem(page, 'W-3801');
    const send = page.getByRole('button', { name: 'Send reminder' });
    await send.click();
    await expect(page.getByText('We couldn’t confirm this step. Check the page before trying again.')).toBeVisible();
    await expect(send).toHaveAttribute('aria-disabled', 'true');
    await send.click({ force: true });
    await page.waitForTimeout(500);
    expect(stepPosts()).toHaveLength(1);
  });

  test('W-3804: a 500 on send shows the uncertain item; the mock log holds one send and no second send_reminder', async ({ page, request }) => {
    await openItem(page, 'W-3804');
    await page.getByRole('button', { name: 'Send reminder' }).click();
    await expect(page.getByRole('radiogroup', { name: 'Confirm what happened' })).toBeVisible();
    await page.getByRole('button', { name: 'Send reminder' }).click({ force: true });
    await page.waitForTimeout(500);
    const recorded = await log(request);
    expect(recorded.entries.filter((e) => e.step === 'send_reminder')).toHaveLength(1);
  });
});

/** Keyboard focus is visible on the list's controls. */
test('visible focus on the search box and the note link', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await openList(page);
  const ring = async (target: Locator) => {
    for (let i = 0; i < 60; i++) {
      if (await target.evaluate((el) => el === document.activeElement)) break;
      await page.keyboard.press('Tab');
    }
    await expect(target).toBeFocused();
    return target.evaluate((el) => getComputedStyle(el).outlineStyle !== 'none');
  };
  expect(await ring(page.getByRole('searchbox', { name: 'Search' }))).toBe(true);
  expect(await ring(page.getByRole('link', { name: 'Open the reminder draft' }))).toBe(true);
});
