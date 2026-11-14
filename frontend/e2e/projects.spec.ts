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
const projectTabs = (page: Page) => page.getByRole('tablist', { name: 'Project' }).getByRole('tab');

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

    test('list default (Active): 20 projects, Filter, Show more, rows per page; tabs, total and note from 720px', async ({ page }) => {
      await page.goto('/projects');
      await listLoaded(page);
      await expect(projectLinks(page)).toHaveCount(20);
      await expect(projectLinks(page).first()).toHaveAttribute('href', '/projects/P-0101');
      await expect(page.getByRole('button', { name: 'Show more' })).toBeVisible();
      await expect(page.getByRole('radiogroup', { name: 'Rows per page' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Filter' })).toBeVisible();
      if (phone) {
        await expect(page.getByRole('table')).toHaveCount(0);
        await expect(page.getByRole('tablist')).toBeHidden();
        await expect(projectLinks(page).first()).toContainText('Release · UAT with client · PM Tunde Bello2 need a person · 1 stopped');
        await expectTouchTargets([
          page.getByRole('searchbox', { name: 'Search' }),
          page.getByRole('button', { name: 'Filter' }),
          ...(await page.getByRole('radio').all()),
          page.getByRole('button', { name: 'Show more' }),
          ...(await projectLinks(page).all()).slice(0, 3),
        ]);
      } else {
        await expect(page.locator('.projects__eyebrow')).toHaveText('PROJECTS');
        await expect(page.getByRole('tab')).toHaveText(['Active22', 'Closed2', 'All I can see24']);
        await expect(page.locator('.psl-resultcount')).toHaveText('22 PROJECTS');
        await expect(page.getByRole('columnheader')).toHaveText(['PROJECT', 'PM', 'WHERE IT IS', 'NEXT MILESTONE', 'NEEDS A PERSON', 'STOPPED']);
        await expect(page.getByText('You see projects your roles cover. Open one for its journey, documents, money and registers.')).toBeVisible();
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

    test('journey default: P-0101 as drawn, every line in order with its tag', async ({ page }) => {
      await page.goto('/projects/P-0101');
      await journeyLoaded(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Lagoon Health · patient app');
      const tabs = projectTabs(page);
      // Phones draw the tabs without counts.
      await expect(tabs).toHaveText(phone ? ['Journey', 'Milestones', 'Documents', 'Money', 'Registers', 'Actions'] : ['Journey', 'Milestones4', 'Documents6', 'Money', 'Registers6', 'Actions9'], {
        useInnerText: phone,
      });
      await expect(tabs.first()).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('.projects__next')).toContainText('What is next');
      await expect(lineLinks(page)).toHaveCount(8);
      await expect(lineLinks(page).nth(6)).toHaveAttribute('href', '/work/W-1001');
      if (phone) {
        await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toBeHidden();
        await expect(page.getByRole('link', { name: '← Projects' })).toBeVisible();
        await expect(page.locator('.projects__phoneline')).toHaveText('8 pieces of work · 2 waiting on people · 1 stopped');
        await expect(page.getByRole('complementary')).toBeHidden();
        // Each line's link covers its whole row.
        await expectTouchTargets([page.getByRole('link', { name: '← Projects' }), tabs.first(), ...(await page.locator('ol.projects__lines > li').all())]);
      } else {
        await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toHaveText('Projects / Lagoon Health');
        await expect(page.getByRole('link', { name: '← Projects' })).toBeHidden();
        await expect(page.locator('.projects__route')).toHaveText('PM Tunde Bello · Route A from RFP-0031 · 8 pieces of work across 6 lines');
        await expect(page.getByRole('region', { name: 'Facts earned' })).toBeVisible();
        await expect(page.getByRole('complementary', { name: "Tola's summary" })).toContainText('Lagoon Health is moving.');
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
      await expect(page.getByRole('tablist', { name: 'Project' })).toBeVisible();
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
      await expect(page.getByRole('tablist', { name: 'Project' })).toHaveCount(0);
      expect(await page.title()).toBe('Project · PSL Factory');
      const text = await page.locator('body').innerText();
      expect(text).not.toContain('P-0099');
      expect(text).not.toContain('We could not find that record.');
      expect(await noHorizontalScroll(page)).toBe(true);
      if (phone) await expectTouchTargets([page.getByRole('link', { name: 'Back to projects' })]);
      await shot(page, `project-no-access-${w}`);
      await expectNoAxeViolations(page);
    });

    test('project tab: Milestones opens a coming-next panel under the same header', async ({ page }) => {
      await page.goto('/projects/P-0101/milestones');
      await journeyLoaded(page);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Lagoon Health · patient app');
      await expect(projectTabs(page).nth(1)).toHaveAttribute('aria-selected', 'true');
      await expect(page.getByRole('heading', { level: 2, name: 'Milestones come next' })).toBeVisible();
      await expect(lineLinks(page)).toHaveCount(0);
      expect(await page.title()).toBe('Project · PSL Factory');
      expect(await noHorizontalScroll(page)).toBe(true);
      await shot(page, `project-milestones-${w}`);
      await expectNoAxeViolations(page);
      await page.getByRole('link', { name: 'Open the journey' }).click();
      await expect(page).toHaveURL(/\/projects\/P-0101$/);
      await expect(lineLinks(page)).toHaveCount(8);
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
    await page.getByRole('searchbox', { name: 'Search' }).fill('lagoon');
    expect(new URL((await request).url()).search).toBe('?limit=20&status=active&q=lagoon');
    await expect(page).toHaveURL(/\/projects\?q=lagoon$/);
    await expect(projectLinks(page)).toHaveText(['Lagoon Health · patient app']);
    await page.getByRole('searchbox', { name: 'Search' }).fill('zzz');
    await expect(page.getByRole('heading', { name: 'No projects match' })).toBeVisible();
    await page.getByRole('button', { name: 'Clear search' }).click();
    await expect(projectLinks(page)).toHaveCount(20);
  });

  test('paging: Show more appends; 10 rows per page is kept across a reload; ?limit=7 falls back to 20', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    const more = page.waitForRequest((r) => r.url().includes('cursor='));
    await page.getByRole('button', { name: 'Show more' }).click();
    expect(new URL((await more).url()).search).toBe('?limit=20&status=active&cursor=o20');
    await expect(projectLinks(page)).toHaveCount(22);
    await expect(projectLinks(page).nth(20)).toBeFocused();
    await expect(page.locator('.psl-showmore')).toContainText('All 22 showing');
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

  test('a journey line opens its work item: Invoice · Milestone 2 is W-1001', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    await projectLinks(page).first().click();
    await expect(page).toHaveURL(/\/projects\/P-0101$/);
    await journeyLoaded(page);
    await lineLinks(page).nth(6).click();
    await expect(page).toHaveURL(/\/work\/W-1001$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Lagoon Health · Milestone 2 invoice' })).toBeVisible();
  });

  test('tabs: Closed and All I can see change the request and the URL; Filter says filters come next', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'pm' });
    await page.goto('/projects');
    await listLoaded(page);
    await expect(projectLinks(page)).toHaveCount(4);
    const closed = page.waitForRequest((r) => r.url().includes('status=closed'));
    await page.getByRole('tab', { name: /Closed/ }).click();
    expect(new URL((await closed).url()).search).toBe('?limit=20&status=closed');
    await expect(page).toHaveURL(/\?status=closed$/);
    await expect(projectLinks(page)).toHaveText(['Sabi Market · web store']);
    await page.getByRole('tab', { name: /Closed/ }).focus();
    await page.keyboard.press('ArrowRight');
    await expect(page).toHaveURL(/\?status=all$/);
    await expect(projectLinks(page)).toHaveCount(5);
    await expect(page.getByRole('tab', { name: /All I can see/ })).toBeFocused();
    await page.getByRole('button', { name: 'Filter' }).click();
    await expect(page.getByRole('dialog', { name: 'Filter projects' })).toContainText('Filters come next');
    await expectNoAxeViolations(page);
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Filter' })).toBeFocused();
  });

  test('an unknown project tab is the not-found page', async ({ page }) => {
    await page.goto('/projects/P-0101/nope');
    await expect(page.getByRole('heading', { name: 'This page doesn’t exist.' })).toBeVisible();
    await expect(page.getByRole('tablist', { name: 'Project' })).toHaveCount(0);
  });

  test('pm: the four active board projects, never P-0104; P-0104 opens as no access', async ({ page, context }) => {
    await setCookies(context, { psl_mock_persona: 'pm' });
    await page.goto('/projects');
    await listLoaded(page);
    await expect(projectLinks(page)).toHaveCount(4);
    await expect(page.locator('main')).not.toContainText('Delta Foods');
    await page.goto('/projects/P-0104');
    await expect(page.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeVisible();
    expect(await page.locator('body').innerText()).not.toContain('Delta Foods');
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
    await expect(lineLinks(page)).toHaveCount(8);
  });

  test('keyboard focus is visible on every control', async ({ page }) => {
    await page.goto('/projects');
    await listLoaded(page);
    for (const target of [
      page.getByRole('tab', { name: /Active/ }),
      page.getByRole('searchbox', { name: 'Search' }),
      page.getByRole('button', { name: 'Filter' }),
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
      projectTabs(page).first(),
      lineLinks(page).first(),
      page.getByRole('link', { name: 'Ask me about this project' }),
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
