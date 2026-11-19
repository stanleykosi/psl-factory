import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

// F-32 (contract mock only): the Delivery tab (SCR-43) and the release work item (SCR-44) at 1440 and 390: axe, touch targets,
// the sub-nav, and the approve flow with the recorded requests. Nothing here releases or deploys anything.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.use({ timezoneId: 'Africa/Lagos' });

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByText('Loading…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
}

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

async function expectTouchTargets(targets: Locator[]) {
  for (const target of targets) {
    const box = (await target.boundingBox())!;
    const label = await target.evaluate((el) => el.outerHTML.slice(0, 80));
    expect(box.height, label).toBeGreaterThanOrEqual(44);
  }
}

test.beforeEach(async ({ context, request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  const url = test.info().project.use.baseURL!;
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url }]);
});

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;
  test.describe(label, () => {
    test.use({ viewport, reducedMotion: 'reduce', ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    test('Delivery tab: six rows, links, sub-nav only at 1440, no axe violations, no sideways scroll', async ({ page }) => {
      await page.goto('/projects/P-0101/delivery');
      await loaded(page);
      const tabs = page.getByRole('tablist', { name: 'Project' }).getByRole('tab');
      await expect(tabs).toHaveText(['Journey', 'Delivery', 'Milestones 4', 'Documents 6', 'Money', 'Registers 6', 'Actions 9']);
      await expect(page.getByRole('tab', { name: 'Delivery' })).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('ol.delivery__rows > li')).toHaveCount(6);
      await expect(page.getByRole('link', { name: 'Release gates' })).toHaveAttribute('href', '/work/W-2503');
      await expect(page.getByRole('link', { name: 'Go-live acceptance' })).toHaveAttribute('href', '/work/W-2510');
      const nav = page.getByRole('navigation', { name: 'Delivery lines' });
      if (phone) await expect(nav).toBeHidden();
      else await expect(nav.getByRole('link')).toHaveText(['Release', 'Go-live', 'Hypercare']);
      expect(await noHorizontalScroll(page)).toBe(true);
      if (phone) await expectTouchTargets([page.getByRole('link', { name: 'Release gates' }), page.getByRole('link', { name: 'Go-live acceptance' }), page.getByRole('link', { name: 'Ask Tola' })]);
      await expectNoAxeViolations(page);
    });

    test('an unknown project tab is still a 404 page', async ({ page }) => {
      await page.goto('/projects/P-0101/planning');
      await expect(page.getByText('This page doesn’t exist.')).toBeVisible();
      await expect(page.getByRole('tab', { name: 'Delivery' })).toHaveCount(0);
    });

    test('empty Delivery tab and the no-access views have no axe violations', async ({ page }) => {
      await page.route('**/api/v1/projects/P-0101', async (route) => {
        const response = await route.fetch();
        const body = await response.json();
        body.delivery = [];
        delete body.delivery_agent;
        await route.fulfill({ response, json: body });
      });
      await page.goto('/projects/P-0101/delivery');
      await loaded(page);
      await expect(page.getByText('No delivery lines yet.')).toBeVisible();
      await expectNoAxeViolations(page);
      await page.unroute('**/api/v1/projects/P-0101');
      await page.goto('/projects/P-0099/delivery');
      await expect(page.getByText('You can’t open this project')).toBeVisible();
      await expectNoAxeViolations(page);
      await page.goto('/work/W-1099');
      await expect(page.getByText('You can’t open this work item')).toBeVisible();
      await expectNoAxeViolations(page);
    });

    for (const id of ['W-2501', 'W-2502', 'W-2503', 'W-2504', 'W-2507']) {
      test(`${id}: one column at 390, no sideways scroll, controls 44px, no axe violations`, async ({ page }) => {
        await page.goto(`/work/${id}`);
        await loaded(page);
        expect(await noHorizontalScroll(page)).toBe(true);
        if (phone) await expectTouchTargets(await page.locator('main a.psl-btn, main button[aria-disabled]').all());
        if (id === 'W-2504') {
          const control = page.getByRole('button', { name: 'Approve for release' });
          await expect(control).toHaveAttribute('aria-disabled', 'true');
          await expect(control).toHaveAttribute('aria-describedby', /.+/);
          await expect(page.getByText('This decision needs a PMO Lead.').first()).toBeVisible();
        }
        await expectNoAxeViolations(page);
      });
    }
  });
}

test.describe('the line tab bar', () => {
  test.use({ viewport: DESKTOP });
  test('on W-2501 shows the same seven tabs, linked, none current', async ({ page }) => {
    await page.goto('/work/W-2501');
    await loaded(page);
    const bar = page.getByRole('navigation', { name: 'Project' });
    await expect(bar.getByRole('link')).toHaveText(['Journey', 'Delivery', 'Milestones', 'Documents', 'Money', 'Registers', 'Actions']);
    await expect(bar.getByRole('link').nth(1)).toHaveAttribute('href', '/projects/P-0101/delivery');
    await expect(bar.locator('[aria-current]')).toHaveCount(0);
  });
});

test.describe('the approve flow', () => {
  test.use({ viewport: DESKTOP });

  function record(page: Page) {
    const writes: { path: string; body: unknown; csrf: string | undefined }[] = [];
    page.on('request', (r) => {
      if (r.method() === 'POST') writes.push({ path: new URL(r.url()).pathname, body: r.postDataJSON(), csrf: r.headers()['x-csrftoken'] });
    });
    return writes;
  }

  test('Approve for release: the work page writes nothing; the F-16 page claims once and decides once; the re-read shows Release ready', async ({ page }) => {
    const writes = record(page);
    await page.goto('/work/W-2502');
    await loaded(page);
    await page.getByRole('link', { name: 'Approve for release' }).click();
    await expect(page).toHaveURL(/\/work\/W-2502\/decide\?task=T-2502/);
    expect(writes).toEqual(expect.not.arrayContaining([expect.objectContaining({ path: '/api/v1/work/W-2502/steps' })]));
    const approve = page.getByRole('button', { name: /^Approve v1/ });
    await expect(approve).toBeEnabled();
    await approve.click();
    await expect(page.getByRole('heading', { level: 1 })).toContainText('approved');
    expect(writes.map((w) => w.path)).toEqual(['/api/v1/tasks/T-2502/claim', '/api/v1/tasks/T-2502/decision']);
    expect(writes[1].body).toMatchObject({ verdict: 'approve', expected_revision: 1 });
    expect(writes.every((w) => w.csrf === 'mock-csrf-pm')).toBe(true);
    await page.goto('/work/W-2502');
    await loaded(page);
    await expect(page.getByText('Release ready', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/Release ready and verified on 25 Mar/)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Next' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Open go-live' })).toHaveAttribute('href', '/work/W-2510');
    await page.getByRole('link', { name: 'Open go-live' }).click();
    await expect(page).toHaveURL(/\/work\/W-2510$/);
  });

  for (const [name, fail] of [
    ['409', (route: import('@playwright/test').Route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': '409' } })],
    ['500', (route: import('@playwright/test').Route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"Down."}' })],
    ['network failure', (route: import('@playwright/test').Route) => route.abort('failed')],
  ] as const) {
    test(`a ${name} on the decide shows the F-16 problem state; neither page shows approved or Release ready`, async ({ page }) => {
      await page.route('**/api/v1/tasks/T-2502/decision', fail);
      await page.goto('/work/W-2502/decide?task=T-2502');
      await loaded(page);
      const approve = page.getByRole('button', { name: /^Approve v1/ });
      await expect(approve).toBeEnabled();
      await approve.click();
      await page.waitForTimeout(500);
      await expect(page.getByText(/Release ready/)).toHaveCount(0);
      await expect(page.getByRole('heading', { level: 1 })).not.toContainText(/is approved|you approved/i);
      await page.unroute('**/api/v1/tasks/T-2502/decision');
      await page.goto('/work/W-2502');
      await loaded(page);
      await expect(page.getByText('Your decision', { exact: true }).first()).toBeVisible();
      await expect(page.getByText('Release ready', { exact: true })).toHaveCount(0);
    });
  }

  test('Return needs a note: an empty note sends nothing; with a note one decide goes and the work page shows no Release ready', async ({ page }) => {
    const writes = record(page);
    await page.goto('/work/W-2502/decide?task=T-2502');
    await loaded(page);
    await expect(page.getByRole('button', { name: /^Approve v1/ })).toBeEnabled();
    const before = writes.length;
    await page.getByRole('button', { name: 'Return', exact: true }).click();
    expect(writes.length).toBe(before);
    await expect(page.getByText(/note/i).first()).toBeVisible();
    await page.getByLabel(/^Note/).fill('Rollback plan is missing');
    await page.getByRole('button', { name: 'Return', exact: true }).click();
    await expect.poll(() => writes.filter((w) => w.path.endsWith('/decision')).length).toBe(1);
    expect(writes.find((w) => w.path.endsWith('/decision'))!.body).toMatchObject({ verdict: 'return' });
    await page.goto('/work/W-2502');
    await loaded(page);
    await expect(page.getByText('Release ready', { exact: true })).toHaveCount(0);
  });
});
