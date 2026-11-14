import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Locator, type Page } from '@playwright/test';

// Projects (SCR-22 list, SCR-07 journey) against the contract mock: every state at 390 and 1440, axe WCAG 2.2 AA.
const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844 };
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

test.use({ timezoneId: 'Africa/Lagos' });

async function setCookies(context: BrowserContext, cookies: Record<string, string>) {
  const url = test.info().project.use.baseURL!;
  await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, url })));
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

const shot = (page: Page, name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true });
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
const projectLinks = (page: Page) => page.locator('[data-project-link]');
const lineLinks = (page: Page) => page.locator('ol.projects__lines a');

async function listLoaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible();
}

async function journeyLoaded(page: Page) {
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

/** Tabs until the target has focus, then reads its outline. */
async function keyboardRing(page: Page, target: Locator) {
  for (let i = 0; i < 80; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press('Tab');
  }
  await expect(target).toBeFocused();
  return target.evaluate((el) => {
    const s = getComputedStyle(el);
    return { style: s.outlineStyle, width: s.outlineWidth };
  });
}

async function motion(page: Page) {
  return page.evaluate(() => ({
    transitions: [...document.querySelectorAll('main *')]
      .filter((el) => getComputedStyle(el).transitionDuration.split(',').some((d) => parseFloat(d) > 0))
      .map((el) => el.outerHTML.slice(0, 80)),
    running: document.getAnimations().filter((a) => a.playState === 'running').length,
  }));
}

async function expectTouchTargets(targets: Locator[]) {
  for (const target of targets) {
    const box = (await target.boundingBox())!;
    expect(box.width, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
    expect(box.height, await target.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThanOrEqual(44);
  }
}

for (const [label, viewport] of [
  ['desktop 1440', DESKTOP],
  ['phone 390', PHONE],
] as const) {
  const phone = viewport === PHONE;
  const w = viewport.width;

  test.describe(label, () => {
    test.use({ viewport, ...(phone ? { hasTouch: true, isMobile: true } : {}) });

    test('list default: 20 projects, 20 shown, Show more, rows per page', async ({ page }) => {
      await page.goto('/projects');
      await listLoaded(page);
      await expect(projectLinks(page)).toHaveCount(20);
      await expect(projectLinks(page).first()).toHaveAttribute('href', '/projects/P-0101');
      await expect(page.locator('.psl-resultcount')).toHaveText('20 shown');
      await expect(page.getByRole('button', { name: 'Show more' })).toBeVisible();
      await expect(page.getByRole('radiogroup', { name: 'Rows per page' })).toBeVisible();
      await expect(page.getByText('You see projects your roles cover.')).toBeVisible();
      await expect(page.getByRole('tab')).toHaveCount(0);
      await expect(page.getByRole('button', { name: /filter/i })).toHaveCount(0);
      if (phone) {
        await expect(page.getByRole('table')).toHaveCount(0);
        await expect(projectLinks(page).first()).toContainText('Release · UAT with client · PM Tunde Bello');
        await expectTouchTargets([
          page.getByRole('searchbox', { name: 'Search projects' }),
          ...(await page.getByRole('radio').all()),
          page.getByRole('button', { name: 'Show more' }),
          ...(await projectLinks(page).all()).slice(0, 3),
        ]);
      } else {
        await expect(page.getByRole('columnheader')).toHaveText(['PROJECT', 'PM', 'WHERE IT IS']);
      }
      expect(await noHorizontalScroll(page)).toBe(true);
      await expect(page.locator('main .psl-sample')).toHaveCount(0);
      await shot(page, `projects-${w}`);
      await expectNoAxeViolations(page);
    });

    test('list no results, Clear search; then error with Try again', async ({ page }) => {
      await page.goto('/projects?q=zzz');
      await listLoaded(page);
      await expect(page.getByRole('heading', { name: 'No projects match' })).toBeVisible();
      await expectNoAxeViolations(page);
      await shot(page, `projects-${w}-no-results`);
      await page.getByRole('button', { name: 'Clear search' }).click();
      await expect(projectLinks(page)).toHaveCount(20);
      await expect(page).toHaveURL(/\/projects$/);

      let fail = true;
      await page.route('**/api/v1/projects*', (route) =>
        fail ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"x"}' }) : route.continue(),
      );
      await page.getByRole('radio', { name: '10' }).click();
      const card = page.getByRole('main').getByRole('alert');
      await expect(card).toContainText('We couldn’t load your projects. Your work is safe; nothing was changed.');
      await expect(card).toContainText('Reference server_error for support.');
      await shot(page, `projects-${w}-error`);
      await expectNoAxeViolations(page);
      fail = false;
      await card.getByRole('button', { name: 'Try again' }).click();
      await expect(projectLinks(page)).toHaveCount(10);
    });

    test('list loading: status and no rows while held; reduced motion', async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      let release!: () => void;
      const gate = new Promise<void>((resolve) => (release = resolve));
      await page.route('**/api/v1/projects*', async (route) => {
        await gate;
        await route.continue();
      });
      await page.goto('/projects');
      await expect(page.getByRole('status')).toBeVisible();
      await expect(projectLinks(page)).toHaveCount(0);
      expect(await motion(page)).toEqual({ transitions: [], running: 0 });
      await expectNoAxeViolations(page);
      release();
      await listLoaded(page);
      expect((await motion(page)).running).toBe(0);
    });

    test('journey default: P-0101 with every line in order and its tag', async ({ page }) => {
      await page.goto('/projects/P-0101');
      await journeyLoaded(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Lagoon Health · patient app');
      const tabs = page.getByRole('navigation', { name: 'Project' }).getByRole('link');
      await expect(tabs).toHaveText(['Journey']);
      await expect(tabs.first()).toHaveAttribute('aria-current', 'page');
      await expect(page.locator('.psl-callout')).toContainText('What is next');
      await expect(lineLinks(page)).toHaveCount(12);
      await expect(lineLinks(page).nth(5)).toHaveAttribute('href', '/work/W-1004');
      if (phone) {
        await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toBeHidden();
        await expect(page.getByRole('link', { name: '← Projects' })).toBeVisible();
        await expectTouchTargets([page.getByRole('link', { name: '← Projects' }), tabs.first(), ...(await lineLinks(page).all())]);
      } else {
        await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toHaveText('Projects / Lagoon Health · patient app');
        await expect(page.getByRole('link', { name: '← Projects' })).toBeHidden();
      }
      const tagWraps = await page.locator('ol.projects__lines .psl-tag').evaluateAll((els) => els.filter((el) => el.getBoundingClientRect().height > 30).length);
      expect(tagWraps).toBe(0);
      expect(await noHorizontalScroll(page)).toBe(true);
      expect(await page.title()).toBe('Project · PSL Factory');
      await shot(page, `project-journey-${w}`);
      await expectNoAxeViolations(page);
    });

    test('journey empty: P-0105', async ({ page }) => {
      await page.goto('/projects/P-0105');
      await journeyLoaded(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sabi Market · web store');
      await expect(page.getByRole('navigation', { name: 'Project' })).toBeVisible();
      await expect(page.getByText('No work on this project yet.')).toBeVisible();
      await expect(page.locator('main ol')).toHaveCount(0);
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, `project-empty-${w}`);
      await expectNoAxeViolations(page);
    });

    test('journey no access: P-0099 names nothing', async ({ page }) => {
      await page.goto('/projects/P-0099');
      await expect(page.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Back to projects' })).toHaveAttribute('href', '/projects');
      await expect(page.getByRole('navigation', { name: 'Project' })).toHaveCount(0);
      expect(await page.title()).toBe('Project · PSL Factory');
      const text = await page.locator('body').innerText();
      expect(text).not.toContain('P-0099');
      expect(text).not.toContain('We could not find that record.');
      expect(await noHorizontalScroll(page)).toBe(true);
      if (phone) await expectTouchTargets([page.getByRole('link', { name: 'Back to projects' })]);
      await shot(page, `project-no-access-${w}`);
      await expectNoAxeViolations(page);
    });

    test('not open: a 403 on the list shows the section is not open', async ({ page }) => {
      await page.route('**/api/v1/projects*', (route) =>
        route.fulfill({ status: 403, contentType: 'application/json', body: '{"code":"forbidden","message":"Your role does not allow this."}' }),
      );
      await page.goto('/projects');
      await expect(page.getByRole('heading', { name: 'This section isn’t open to your role.' })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Go to My work' })).toBeVisible();
      await expectNoAxeViolations(page);
    });
  });
}

test.describe('desktop 1440 details', () => {
  test.use({ viewport: DESKTOP });

  test('search: lagoon returns only P-0101 and writes ?q=lagoon; zzz then Clear search restores', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    const request = page.waitForRequest((r) => r.url().includes('/api/v1/projects?') && r.url().includes('q=lagoon'));
    await page.getByRole('searchbox', { name: 'Search projects' }).fill('lagoon');
    expect(new URL((await request).url()).search).toBe('?limit=20&q=lagoon');
    await expect(page).toHaveURL(/\/projects\?q=lagoon$/);
    await expect(projectLinks(page)).toHaveText(['Lagoon Health · patient app']);
    await page.getByRole('searchbox', { name: 'Search projects' }).fill('zzz');
    await expect(page.getByRole('heading', { name: 'No projects match' })).toBeVisible();
    await page.getByRole('button', { name: 'Clear search' }).click();
    await expect(projectLinks(page)).toHaveCount(20);
  });

  test('paging: Show more appends; 10 rows per page is kept across a reload; ?limit=7 falls back to 20', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    const more = page.waitForRequest((r) => r.url().includes('cursor='));
    await page.getByRole('button', { name: 'Show more' }).click();
    expect(new URL((await more).url()).search).toBe('?limit=20&cursor=o20');
    await expect(projectLinks(page)).toHaveCount(24);
    await expect(projectLinks(page).nth(20)).toBeFocused();
    await expect(page.locator('.psl-showmore')).toContainText('All 24 showing');
    await expect(page.getByRole('button', { name: 'Show more' })).toHaveCount(0);

    await page.getByRole('radio', { name: '10' }).click();
    await expect(page).toHaveURL(/\?limit=10$/);
    await expect(projectLinks(page)).toHaveCount(10);
    await page.reload();
    await listLoaded(page);
    await expect(projectLinks(page)).toHaveCount(10);
    await expect(page.getByRole('radio', { name: '10' })).toHaveAttribute('aria-checked', 'true');
    await page.getByRole('radio', { name: '10' }).focus();
    await page.keyboard.press('ArrowRight');
    await expect(page).toHaveURL(/\/projects$/);
    await expect(page.getByRole('radio', { name: '20' })).toBeFocused();

    await page.goto('/projects?limit=7');
    await listLoaded(page);
    await expect(projectLinks(page)).toHaveCount(20);
  });

  test('a failed Show more keeps the rows and shows the inline problem', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    await page.route('**/api/v1/projects?*cursor=*', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"x"}' }),
    );
    await page.getByRole('button', { name: 'Show more' }).click();
    await expect(page.getByText('We couldn’t load more. Nothing was changed.')).toBeVisible();
    await expect(projectLinks(page)).toHaveCount(20);
  });

  test('a journey line opens its work item: W-1004', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    await projectLinks(page).first().click();
    await expect(page).toHaveURL(/\/projects\/P-0101$/);
    await journeyLoaded(page);
    await lineLinks(page).nth(5).click();
    await expect(page).toHaveURL(/\/work\/W-1004$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Lagoon Health · Milestone 3 invoice' })).toBeVisible();
  });

  test('pm: exactly four projects, never P-0102; P-0102 opens as no access', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'pm' });
    await page.goto('/projects');
    await listLoaded(page);
    await expect(projectLinks(page)).toHaveCount(4);
    await expect(page.locator('main')).not.toContainText('Harbour Bank');
    await page.goto('/projects/P-0102');
    await expect(page.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeVisible();
    expect(await page.locator('body').innerText()).not.toContain('Harbour Bank');
  });

  test('persona none: no projects request on the list or a journey', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'none' });
    const requests: string[] = [];
    page.on('request', (r) => {
      if (r.url().includes('/api/v1/projects')) requests.push(r.url());
    });
    for (const path of ['/projects', '/projects/P-0101']) {
      await page.goto(path);
      await expect(page.getByText(/isn’t open to your role|No sections are open to your role yet\./)).toBeVisible();
    }
    expect(requests).toEqual([]);
    await expectNoAxeViolations(page);
  });

  test('signed out: 401 on the list and on a journey', async ({ page }) => {
    await page.route('**/api/v1/projects**', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: '{"code":"not_signed_in","message":"Sign in to continue."}' }),
    );
    await page.goto('/projects');
    await expect(page.getByRole('main').getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/accounts/login/?next=%2Fprojects');
    await page.goto('/projects/P-0101');
    await expect(page.getByRole('main').getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/accounts/login/?next=%2Fprojects%2FP-0101');
  });

  test('journey error: 500 then Try again recovers', async ({ page }) => {
    let fail = true;
    await page.route('**/api/v1/projects/P-0101', (route) =>
      fail ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"code":"server_error","message":"x"}' }) : route.continue(),
    );
    await page.goto('/projects/P-0101');
    const card = page.getByRole('main').getByRole('alert');
    await expect(card).toContainText('We couldn’t load this project. Your work is safe; nothing was changed.');
    await expect(card).toContainText('Reference server_error for support.');
    await expectNoAxeViolations(page);
    fail = false;
    await card.getByRole('button', { name: 'Try again' }).click();
    await expect(lineLinks(page)).toHaveCount(12);
  });

  test('keyboard focus is visible on every control', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    for (const target of [
      page.getByRole('searchbox', { name: 'Search projects' }),
      projectLinks(page).first(),
      page.getByRole('radio', { name: '20' }),
      page.getByRole('button', { name: 'Show more' }),
    ]) {
      expect(await keyboardRing(page, target)).toEqual({ style: 'solid', width: '2px' });
    }
    await page.goto('/projects/P-0101');
    await journeyLoaded(page);
    for (const target of [
      page.getByRole('navigation', { name: 'Breadcrumb' }).getByRole('link', { name: 'Projects' }),
      page.getByRole('navigation', { name: 'Project' }).getByRole('link', { name: 'Journey' }),
      lineLinks(page).first(),
    ]) {
      expect(await keyboardRing(page, target)).toEqual({ style: 'solid', width: '2px' });
    }
    await page.goto('/projects/P-0099');
    await expect(page.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeVisible();
    expect(await keyboardRing(page, page.getByRole('link', { name: 'Back to projects' }))).toEqual({ style: 'solid', width: '2px' });
  });
});

test.describe('phone 390 card focus', () => {
  test.use({ viewport: PHONE, hasTouch: true, isMobile: true });

  test('card links and the back link show the focus ring', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    expect(await keyboardRing(page, projectLinks(page).first())).toEqual({ style: 'solid', width: '2px' });
    await page.goto('/projects/P-0101');
    await journeyLoaded(page);
    expect(await keyboardRing(page, page.getByRole('link', { name: '← Projects' }))).toEqual({ style: 'solid', width: '2px' });
  });
});
