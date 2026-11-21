import { expect, test, type Locator, type Page } from '@playwright/test';

// D-143: a text field shows focus by changing its own border in place: no outer ring, no offset, no layout shift.
const FOCUS = 'rgb(36, 89, 214)';
const INK = 'rgb(31, 36, 39)';

const look = (loc: Locator) =>
  loc.evaluate((el) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return { ring: s.outlineStyle, border: s.borderTopColor, width: s.borderTopWidth, box: [r.x, r.y, r.width, r.height] };
  });

async function checkField(page: Page, field: Locator, box: Locator) {
  await page.mouse.click(2, 2);
  const before = await look(box);
  await field.focus();
  const after = await look(box);
  expect(after.ring).toBe('none');
  expect(after.border).toBe(FOCUS);
  expect(after.width).toBe(before.width);
  expect(after.box).toEqual(before.box);
}

test.beforeEach(async ({ context, baseURL }) => {
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
});

test('a form field, the search and the composer show focus on their own border', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/clients/CL-3501');
  await expect(page.getByLabel('Billing contact name')).toBeVisible();
  const name = page.getByLabel('Billing contact name');
  await checkField(page, name, name);
  await page.screenshot({ path: test.info().outputPath('focus-field.png') });

  await page.goto('/my-work');
  const search = page.getByRole('searchbox', { name: 'Search' });
  await expect(search).toBeVisible();
  await checkField(page, search, search);
  await page.screenshot({ path: test.info().outputPath('focus-search.png') });

  await page.goto('/assistant');
  const input = page.getByRole('textbox', { name: /^Message / });
  await expect(input).toBeVisible();
  const composer = page.locator('.cmp-composer__box');
  await checkField(page, input, composer);
  await page.screenshot({ path: test.info().outputPath('focus-composer.png') });
});

test('the composer box keeps its border when a button inside it has focus; the button keeps its own ring', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/assistant');
  const input = page.getByRole('textbox', { name: /^Message / });
  await input.fill('Hello');
  await page.mouse.click(2, 2);
  const composer = page.locator('.cmp-composer__box');
  const before = await look(composer);
  expect(before.border).toBe(INK);
  await input.focus();
  await page.keyboard.press('Tab');
  const button = page.locator('.cmp-composer__box button:focus');
  await expect(button).toHaveCount(1);
  const after = await look(composer);
  expect(after.border).toBe(INK);
  expect(after.ring).toBe('none');
  // the button inside shows its own edge, with no outline
  expect(await button.evaluate((el) => ({ ring: getComputedStyle(el).outlineStyle, shadow: getComputedStyle(el).boxShadow }))).toEqual({ ring: 'none', shadow: expect.stringContaining('rgb(36, 89, 214)') });
});

// D-144: every focusable control changes its own edge; none draws an outline. Screenshots go to the test output.
test('keyboard focus on a button, a tab, a checkbox, a table row link and a link is an edge in the focus colour, with no outline', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const edge = (loc: Locator) =>
    loc.evaluate((el) => {
      const s = getComputedStyle(el);
      return { ring: s.outlineStyle, shadow: s.boxShadow, underline: `${s.textDecorationLine} ${s.textDecorationColor}`, border: s.borderTopColor, offset: s.outlineOffset };
    });
  await page.goto('/my-work');
  await expect(page.getByRole('tab').first()).toBeVisible();
  await page.keyboard.press('Tab');

  const button = page.getByRole('button', { name: /^Filter/ });
  await button.focus();
  let e = await edge(button);
  expect(e.ring).toBe('none');
  // a filled dark button shows its edge in the on-strong colour (a blue edge on a dark fill cannot be seen)
  expect(e.shadow).toMatch(/rgb\(36, 89, 214\)|rgb\(255, 255, 255\)/);
  await page.screenshot({ path: test.info().outputPath('focus-button.png') });

  const tab = page.getByRole('tab').nth(1);
  await tab.focus();
  e = await edge(tab);
  expect(e.ring).toBe('none');
  expect(e.shadow).toMatch(/rgb\(36, 89, 214\)|rgb\(255, 255, 255\)/);
  await page.screenshot({ path: test.info().outputPath('focus-tab.png') });

  const rowLink = page.locator('tbody tr [data-work-link]').first();
  await rowLink.focus();
  e = await edge(rowLink);
  expect(e.ring).toBe('none');
  expect(e.shadow).toContain('rgb(36, 89, 214)');
  await page.screenshot({ path: test.info().outputPath('focus-table-row.png') });

  await button.click();
  const checkbox = page.getByRole('dialog').getByRole('checkbox').first();
  await page.keyboard.press('Shift'); // keyboard modality after the click, so focus() is a keyboard focus
  await checkbox.focus();
  e = await edge(checkbox);
  expect(e.ring).toBe('none');
  expect(e.border).toBe('rgb(36, 89, 214)');
  await page.screenshot({ path: test.info().outputPath('focus-checkbox.png') });
  await page.keyboard.press('Escape');

  await page.goto('/work/W-1408');
  const crumb = page.getByRole('navigation', { name: 'Breadcrumb' }).getByRole('link').first();
  await expect(crumb).toBeVisible();
  await crumb.focus();
  e = await edge(crumb);
  expect(e.ring).toBe('none');
  expect(e.underline).toContain('rgb(36, 89, 214)');
  await page.screenshot({ path: test.info().outputPath('focus-link.png') });
});
