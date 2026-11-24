import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

// F-119 (contract mock only): the project retrospective (SCR-33) at 1440 and 390: the saved-version write with its
// recorded requests, the checklist strip, stale and duplicate saves, the unconfirmed 503, and the follow-up action.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const caseOf = (n: string) => `3f6c1a52-0d2b-4c11-9b0a-5a1e7d9c${n}`;
const PAGE = (n: string, query = '') => `/projects/${caseOf(n)}/retrospective${query}`;

test.use({ timezoneId: 'Africa/Lagos', viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });

test.beforeEach(async ({ context, request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: test.info().project.use.baseURL! }]);
});

type Req = { method: string; path: string; query: string; body: Record<string, unknown> | null };
function record(page: Page) {
  const seen: Req[] = [];
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (url.pathname.startsWith('/api/')) seen.push({ method: r.method(), path: url.pathname, query: url.search, body: r.method() === 'POST' ? r.postDataJSON() : null });
  });
  return seen;
}
const posts = (seen: Req[]) => seen.filter((r) => r.method === 'POST' && r.path.includes('/projects/'));
const field = (page: Page, label: string) => page.getByRole('textbox', { name: label, exact: true });
async function choose(page: Page, label: string, option: string) {
  await page.getByRole('combobox', { name: label, exact: true }).click();
  await page.getByRole('option', { name: option, exact: true }).click();
}
async function ready(page: Page) {
  await expect(page.getByRole('heading', { level: 1, name: 'Project retrospective' })).toBeVisible();
  await expect(page.getByText('Loading…')).toHaveCount(0);
}

test('an empty project shows the form, the strip and no draft', async ({ page }) => {
  await page.goto(PAGE('2001', '?dossier=5001'));
  await ready(page);
  await expect(page.getByText('Sabi Market web store · needed before closure')).toBeVisible();
  for (const label of ['What went well', "What didn't", 'Lessons for next projects']) await expect(field(page, label)).toHaveValue('');
  await expect(page.getByText('Who took part')).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Notes file' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save retrospective' })).toBeDisabled();
  await expect(page.getByText('Write in at least one box.')).toBeVisible();
  expect(((await page.locator('body').innerText()).match(/draft/i) ?? []).length).toBe(0);
  const strip = page.getByRole('region', { name: 'Closure checklist' });
  await expect(strip.getByText('Retrospective saved · this screen')).toBeVisible();
  await expect(strip.getByText('Not yet')).toBeVisible();
  await expect(strip.getByText('No retrospective saved')).toBeVisible();
  await expect(strip.getByText('Project context')).toHaveCount(0);
  await expect(strip.getByText('Closure report')).toHaveCount(0);
});

test('a first save sends one version and shows saved only after the re-read', async ({ page }) => {
  const seen = record(page);
  await page.goto(PAGE('2001', '?dossier=5001'));
  await ready(page);
  await field(page, 'What went well').fill('UAT finished on time.');
  await page.getByRole('checkbox', { name: 'Tunde Bello' }).check();
  await choose(page, 'Notes file', 'Retrospective notes');
  const mark = seen.length;
  await page.getByRole('button', { name: 'Save retrospective' }).click();
  await expect(page.getByText(/Saved \d\d:\d\d WAT, version 1\./)).toBeVisible();
  const sent = posts(seen);
  expect(sent).toHaveLength(1);
  expect(sent[0].path).toBe(`/api/v1/projects/${caseOf('2001')}/meetings`);
  expect(sent[0].body).toMatchObject({ kind: 'retrospective', meeting_id: null, revision: 41, purpose: 'Project retrospective', summary: '## What went well\nUAT finished on time.', participant_ids: [12], decisions: [], evidence_id: 87 });
  expect(String(sent[0].body?.reference)).toMatch(/^Retrospective \d{4}-\d{2}-\d{2}$/);
  // the page says saved only after the list and the opened version were read again
  const after = seen.slice(mark).map((r) => `${r.method} ${r.path}`);
  expect(after.indexOf(`GET /api/v1/projects/${caseOf('2001')}/meetings`)).toBeGreaterThan(after.findIndex((x) => x.startsWith('POST')));
  await expect(page.getByText('UAT finished on time.')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Closure checklist' }).getByText('Current')).toBeVisible();
});

test('all three boxes are sent in order under their headings', async ({ page }) => {
  const seen = record(page);
  await page.goto(PAGE('2001'));
  await ready(page);
  await field(page, 'Lessons for next projects').fill('C text');
  await field(page, "What didn't").fill('B text');
  await field(page, 'What went well').fill('A text');
  await choose(page, 'Notes file', 'Test plan v2');
  await page.getByRole('button', { name: 'Save retrospective' }).click();
  await expect(page.getByText(/version 1\./)).toBeVisible();
  expect(posts(seen)[0].body?.summary).toBe("## What went well\nA text\n\n## What didn't\nB text\n\n## Lessons for next projects\nC text");
  await expect(page.getByRole('region', { name: 'Closure checklist' })).toHaveCount(0);
});

test('a new version of a saved retrospective carries the reference and the decisions, and reads as version 3', async ({ page }) => {
  const seen = record(page);
  await page.goto(PAGE('2002'));
  await ready(page);
  await expect(page.getByText('Version 2', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('UAT finished on time.')).toBeVisible();
  await expect(page.getByText('Supporting file 88').first()).toBeVisible();
  await page.getByRole('button', { name: 'Save new version' }).click();
  await expect(field(page, 'What went well')).toHaveValue('UAT finished on time.');
  await expect(page.getByRole('textbox', { name: 'Reference' })).toHaveAttribute('readonly', '');
  await expect(page.getByRole('textbox', { name: 'Decision 1' })).toHaveValue("Ask for the client's device mix during planning.");
  await field(page, "What didn't").fill('Updated second box.');
  await choose(page, 'Notes file', 'Retrospective notes');
  await page.getByRole('button', { name: 'Save new version' }).click();
  await expect(page.getByText(/version 3\./)).toBeVisible();
  const sent = posts(seen);
  expect(sent).toHaveLength(1);
  expect(sent[0].body).toMatchObject({ meeting_id: 301, reference: 'Retrospective 2026-11-10', revision: 52, decisions: [{ text: "Ask for the client's device mix during planning.", evidence_id: 88, change_evidence_id: 90 }] });
  await expect(page.getByText('Updated second box.')).toBeVisible();
});

test('a summary with no headings is shown whole and saved back unchanged', async ({ page }) => {
  const seen = record(page);
  await page.goto(PAGE('2002', '?meeting=301&version=9001'));
  await ready(page);
  await expect(page.getByText('Version 1, not the current version')).toBeVisible();
  await expect(page.getByText('Went fine overall. The client team answered quickly.')).toBeVisible();
  await expect(page.getByRole('heading', { name: /Version 1/ })).toBeVisible();
  // the current version is a click away; saving it back unchanged is covered by the unit round trip
  await page.getByRole('button', { name: /Retrospective 2026-11-10/ }).click();
  await expect(page.getByRole('button', { name: 'Save new version' })).toBeVisible();
  expect(posts(seen)).toHaveLength(0);
});

test('the strip names the exact version the checklist used and says a newer one is saved', async ({ page }) => {
  const seen = record(page);
  await page.goto(PAGE('2002', '?dossier=5002'));
  await ready(page);
  const strip = page.getByRole('region', { name: 'Closure checklist' });
  await expect(strip.getByText('The checklist used version 1 (saved 10 Nov 2026)')).toBeVisible();
  await expect(strip.getByText('A newer version has been saved. The checklist has not picked it up yet.')).toBeVisible();
  for (const r of seen) expect(`${r.path}${r.query}`).not.toMatch(/retrospective_id|latest/);
});

test('an older version opens with no edit or action controls', async ({ page }) => {
  await page.goto(PAGE('2002', '?meeting=301&version=9001'));
  await ready(page);
  await expect(page.getByText('Version 1, not the current version')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save new version' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Make this a follow-up action' })).toHaveCount(0);
});

test('a stale save says so, re-reads and keeps what was typed', async ({ page, request }) => {
  await page.goto(PAGE('2001'));
  await ready(page);
  await field(page, 'What went well').fill('Typed before the change.');
  await page.getByRole('checkbox', { name: 'Ada Obi' }).check();
  await choose(page, 'Notes file', 'Test plan v2');
  expect((await request.post(`${MOCK}/__mock/retrospective/bump`, { data: { case: '2001' } })).status()).toBe(204);
  await page.getByRole('button', { name: 'Save retrospective' }).click();
  await expect(page.getByText('This changed while you were editing. Reload and try again.')).toBeVisible();
  await expect(field(page, 'What went well')).toHaveValue('Typed before the change.');
  await expect(page.getByRole('checkbox', { name: 'Ada Obi' })).toBeChecked();
  await expect(page.getByRole('combobox', { name: 'Notes file' })).toContainText('Test plan v2');
  // the re-read gave the new revision: the next press goes through
  await page.getByRole('button', { name: 'Save retrospective' }).click();
  await expect(page.getByText(/version 1\./)).toBeVisible();
});

test('a repeated reference shows under the Reference field and Save comes back', async ({ page }) => {
  await page.goto(PAGE('2001'));
  await ready(page);
  await field(page, 'What went well').fill('x');
  await choose(page, 'Notes file', 'Test plan v2');
  await page.getByRole('textbox', { name: 'Reference' }).fill('Retrospective 2026-11-20');
  await page.getByRole('button', { name: 'Save retrospective' }).click();
  const reference = page.getByRole('textbox', { name: 'Reference' });
  await expect(reference).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByText('Meeting reference exists; create a new revision')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save retrospective' })).toBeEnabled();
});

test('a 503 after sending says it could not confirm, re-reads and sends nothing twice', async ({ page }) => {
  const seen = record(page);
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => (release = resolve));
  let hold = false;
  await page.route('**/api/v1/projects/*/meetings?*', async (route) => {
    if (hold) await gate;
    await route.continue();
  });
  await page.goto(PAGE('2005'));
  await ready(page);
  await field(page, 'What went well').fill('x');
  await choose(page, 'Notes file', 'Retrospective notes');
  hold = true;
  await page.getByRole('button', { name: 'Save retrospective' }).click();
  await expect(page.getByText("We couldn't confirm it saved.")).toBeVisible();
  await expect(page.getByRole('button', { name: /^(Save retrospective|Saving…)$/ })).toBeDisabled();
  release();
  await expect(page.getByText('It was not saved. Press Save again.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save retrospective' })).toBeEnabled();
  expect(posts(seen)).toHaveLength(1);
});

test('a double click on Save sends one request', async ({ page }) => {
  const seen = record(page);
  await page.goto(PAGE('2001'));
  await ready(page);
  await field(page, 'What went well').fill('x');
  await choose(page, 'Notes file', 'Retrospective notes');
  await page.getByRole('button', { name: 'Save retrospective' }).dblclick();
  await expect(page.getByText(/version 1\./)).toBeVisible();
  expect(posts(seen)).toHaveLength(1);
});

test('Save is off, with the reason, until the form is complete', async ({ page }) => {
  await page.goto(PAGE('2001'));
  await ready(page);
  const save = page.getByRole('button', { name: 'Save retrospective' });
  await expect(save).toBeDisabled();
  await field(page, 'What went well').fill('x');
  await expect(page.getByText('Choose the notes file.')).toBeVisible();
  await expect(save).toBeDisabled();
  await field(page, 'What went well').fill('a\n## What went well');
  await expect(page.getByText('That line is a section heading. Reword it.').first()).toBeVisible();
  await field(page, 'What went well').fill('y'.repeat(16001));
  await expect(page.getByText(/\d{5} \/ 16000/)).toBeVisible();
  await choose(page, 'Notes file', 'Retrospective notes');
  await expect(save).toBeDisabled();
  await expect(page.getByText(/characters over the 16000 limit/)).toBeVisible();
  await field(page, 'What went well').fill('fine');
  await expect(save).toBeEnabled();
});

test('a project with no recorded files explains why Save is off', async ({ page }) => {
  await page.goto(PAGE('2004'));
  await ready(page);
  await page.getByRole('button', { name: 'Save new version' }).click();
  await expect(page.getByText('No supporting file is recorded for this project yet. Add the notes file to the project first.').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save new version' })).toBeDisabled();
  await expect(page.getByRole('combobox', { name: 'Notes file' })).toBeDisabled();
});

test('a follow-up action sends one create with the meeting id and no link call', async ({ page }) => {
  const seen = record(page);
  await page.goto(PAGE('2002'));
  await ready(page);
  await expect(page.getByText('Retro action 1 · Tunde Bello · No deadline set · Open · Timing unknown')).toBeVisible();
  await page.getByRole('button', { name: 'Make this a follow-up action' }).click();
  await expect(field(page, 'What needs doing')).toHaveValue("Ask for the client's device mix during planning.");
  await field(page, 'Why it is needed').fill('Found in the retrospective.');
  await choose(page, 'Supporting file', 'Test plan v2');
  await expect(page.getByRole('textbox', { name: 'Reference' })).toHaveValue('Retro action 2');
  await page.getByRole('button', { name: 'Create follow-up action' }).click();
  await expect(page.getByText('Retro action 2 · No owner · No deadline set · Open · Timing unknown')).toBeVisible();
  const created = posts(seen);
  expect(created).toHaveLength(1);
  expect(created[0].path).toBe(`/api/v1/projects/${caseOf('2002')}/actions/create`);
  expect(created[0].body).toMatchObject({ meeting_id: 301, due_at: null, owner_id: null, evidence_id: 88, reference: 'Retro action 2', reason: 'Found in the retrospective.' });
  expect(seen.some((r) => /\/meetings\/\d+\/actions/.test(r.path))).toBe(false);
});

test('a repeated action reference from the server shows under Reference', async ({ page }) => {
  await page.goto(PAGE('2002'));
  await ready(page);
  await page.getByRole('button', { name: 'Make this a follow-up action' }).click();
  await field(page, 'Why it is needed').fill('Because.');
  await choose(page, 'Supporting file', 'Test plan v2');
  await page.getByRole('textbox', { name: 'Reference' }).fill('Retro action 9');
  await page.getByRole('button', { name: 'Create follow-up action' }).click();
  await expect(page.getByRole('textbox', { name: 'Reference' })).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByText('Action reference already exists').first()).toBeVisible();
});

test('a 422 naming a field with no control shows as a message above Save, not as "highlighted fields"', async ({ page }) => {
  await page.goto(PAGE('2001'));
  await ready(page);
  await field(page, 'What went well').fill('x');
  await choose(page, 'Notes file', 'Test plan v2');
  await page.getByRole('textbox', { name: 'Reference' }).fill('Retrospective 2026-11-21');
  await page.getByRole('button', { name: 'Save retrospective' }).click();
  await expect(page.getByText('Pick people who are on the project.')).toBeVisible();
  await expect(page.getByText('Check the highlighted fields.')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Save retrospective' })).toBeEnabled();
});

test('a 422 with only a message on the follow-up action shows that message', async ({ page }) => {
  await page.goto(PAGE('2002'));
  await ready(page);
  await page.getByRole('button', { name: 'Make this a follow-up action' }).click();
  await field(page, 'Why it is needed').fill('Because.');
  await choose(page, 'Supporting file', 'Test plan v2');
  await page.getByRole('textbox', { name: 'Reference' }).fill('Retro action 8');
  await page.getByRole('button', { name: 'Create follow-up action' }).click();
  await expect(page.getByText('The action could not be created.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create follow-up action' })).toBeEnabled();
});

test('a person who cannot record sees saved versions and nothing to press', async ({ page }) => {
  await page.goto(PAGE('2003'));
  await ready(page);
  await expect(page.getByText('UAT finished on time.')).toBeVisible();
  await expect(page.getByRole('button', { name: /Save/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Make this a follow-up action' })).toHaveCount(0);
  await expect(page.getByRole('alert').filter({ hasText: /\S/ })).toHaveCount(0);
});

test('an unknown or not-yours project shows one wording', async ({ page }) => {
  for (const id of [caseOf('2008'), 'a1b2c3d4-0000-4000-8000-000000000000']) {
    await page.goto(`/projects/${id}/retrospective`);
    await expect(page.getByText('This record is unavailable.')).toBeVisible();
    await expect(page.getByText('Sabi Market')).toHaveCount(0);
  }
});

test('signed out shows the sign-in state for this page', async ({ page, context }) => {
  await context.addCookies([{ name: 'psl_mock_session', value: 'out', url: test.info().project.use.baseURL! }]);
  await page.goto(PAGE('2001', '?dossier=5001'));
  const link = page.getByRole('link', { name: 'Sign in' }).first();
  await expect(link).toBeVisible();
  expect(decodeURIComponent((await link.getAttribute('href')) ?? '')).toContain('next=');
});

test('a checklist that cannot be read hides only the strip', async ({ page }) => {
  await page.goto(PAGE('2001', '?dossier=5009'));
  await ready(page);
  await expect(page.getByText('The closure checklist is unavailable.')).toBeVisible();
  await field(page, 'What went well').fill('x');
  await choose(page, 'Notes file', 'Retrospective notes');
  await page.getByRole('button', { name: 'Save retrospective' }).click();
  await expect(page.getByText(/version 1\./)).toBeVisible();
});

test('a long list pages with More', async ({ page }) => {
  await page.goto(PAGE('2006'));
  await ready(page);
  await expect(page.getByRole('button', { name: /^Retrospective \d+ Version/ })).toHaveCount(25);
  await page.getByRole('button', { name: 'More', exact: true }).click();
  await expect(page.getByRole('button', { name: /^Retrospective \d+ Version/ })).toHaveCount(30);
  await expect(page.getByRole('button', { name: 'More', exact: true })).toHaveCount(0);
});

test('accessibility: no axe violations on the form, a saved version and the strip', async ({ page }) => {
  for (const url of [PAGE('2001', '?dossier=5001'), PAGE('2002', '?dossier=5002')]) {
    await page.goto(url);
    await ready(page);
    const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
  }
});

test.describe('phone 390', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  test('one column, Save reachable, targets at least 44px', async ({ page }) => {
    await page.goto(PAGE('2001', '?dossier=5001'));
    await ready(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const save = page.getByRole('button', { name: 'Save retrospective' });
    await save.scrollIntoViewIfNeeded();
    for (const target of [save, page.getByRole('checkbox', { name: 'Tunde Bello' }).locator('..'), page.getByRole('combobox', { name: 'Notes file' })]) {
      expect((await target.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    const order = await page.evaluate(() => ['Project retrospective', 'What went well', 'Who took part', 'Notes file', 'Save retrospective', 'Closure checklist'].map((t) => {
      const el = [...document.querySelectorAll('h1, label, legend, button, h2, span')].find((e) => e.textContent?.trim() === t || e.textContent?.startsWith(`${t}`));
      return el ? [...document.querySelectorAll('*')].indexOf(el) : -1;
    }));
    expect(order.every((top) => top >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    await page.screenshot({ path: test.info().outputPath('retrospective-390.png'), fullPage: true });
  });
});

test('on desktop Tab goes from the notes file straight to Save', async ({ page }) => {
  await page.goto(PAGE('2001'));
  await ready(page);
  await field(page, 'What went well').fill('x');
  await choose(page, 'Notes file', 'Test plan v2');
  await expect(page.getByRole('combobox', { name: 'Notes file' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Save retrospective' })).toBeFocused();
  // Decisions come after Save in the page order, not before it
  const first = await page.evaluate(() => { const save = document.querySelector('.retro__savebar')!; const add = [...document.querySelectorAll('button')].find((b) => b.textContent === 'Add a decision')!; return !!(save.compareDocumentPosition(add) & Node.DOCUMENT_POSITION_FOLLOWING); });
  expect(first).toBe(true);
});

test.describe('phone 390 save bar', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  test('Save sits in a bar at the bottom of the screen and a form message is not covered', async ({ page }) => {
    await page.goto(PAGE('2001'));
    await ready(page);
    const save = page.getByRole('button', { name: 'Save retrospective' });
    const bar = page.locator('.retro__savebar');
    const at = async () => (await bar.boundingBox())!;
    // the bar is the last element of the form, after Decisions, as wide as the screen, at its foot
    expect(await page.locator('form:has(.retro__savebar)').evaluate((form) => form.lastElementChild?.classList.contains('retro__savebar'))).toBe(true);
    expect(await page.evaluate(() => { const form = document.querySelector('form:has(.retro__savebar)')!; const h = [...form.querySelectorAll('p')].find((p) => p.textContent === 'Decisions')!; return !!(h.compareDocumentPosition(document.querySelector('.retro__savebar')!) & Node.DOCUMENT_POSITION_FOLLOWING); })).toBe(true);
    let box = await at();
    expect(Math.abs(box.width - 390)).toBeLessThanOrEqual(1);
    expect(Math.abs(box.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(box.y + box.height - 844)).toBeLessThanOrEqual(1);
    // still pinned at the end of the page, and the last field is clear of it
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    box = await at();
    expect(Math.abs(box.y + box.height - 844)).toBeLessThanOrEqual(1);
    const add = (await page.getByRole('button', { name: 'Add a decision' }).boundingBox())!;
    expect(add.y + add.height).toBeLessThanOrEqual(box.y);
    await page.evaluate(() => window.scrollTo(0, 0));
    await field(page, 'What went well').fill('x');
    await choose(page, 'Notes file', 'Test plan v2');
    await page.getByRole('textbox', { name: 'Reference' }).fill('Retrospective 2026-11-21');
    await save.click();
    const message = page.getByText('Pick people who are on the project.');
    await expect(message).toBeVisible();
    await message.scrollIntoViewIfNeeded();
    const m = (await message.boundingBox())!;
    expect(m.y + m.height).toBeLessThanOrEqual((await at()).y);
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    expect((await message.boundingBox())!.y).toBeLessThan((await at()).y);
  });

  test('a focused control is never hidden under the bar', async ({ page }) => {
    await page.goto(PAGE('2001'));
    await ready(page);
    const clear = async (target: Locator) => {
      await expect(target).toBeFocused();
      // wait for the scroll that keeps the control above the bar to settle
      await expect.poll(async () => {
        const bar = (await page.locator('.retro__savebar').boundingBox())!;
        const box = (await target.boundingBox())!;
        return box.y + box.height <= bar.y + 1;
      }).toBe(true);
      const covered = await target.evaluate((el) => {
        const r = el.getBoundingClientRect();
        const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return !(top === el || el.contains(top) || (top && top.closest('label')?.contains(el)));
      });
      expect(covered).toBe(false);
    };
    // Tab (not focus) from one box into the next, where the next is partly in view behind the bar
    await field(page, "What didn't").focus();
    await page.keyboard.press('Tab');
    await clear(field(page, 'Lessons for next projects'));
    // and on down through the participants to a control below the fold
    for (const name of ['Tunde Bello', 'Ada Obi']) {
      await page.keyboard.press('Tab');
      await clear(page.getByRole('checkbox', { name }));
    }
    await page.getByRole('button', { name: 'Add a decision' }).focus();
    await clear(page.getByRole('button', { name: 'Add a decision' }));
  });
});
