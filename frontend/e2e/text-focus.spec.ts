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
  const composer = page.locator('.cmp-composer__box');
  const before = await look(composer);
  expect(before.border).toBe(INK);
  await input.focus();
  await page.keyboard.press('Tab');
  const send = page.locator('.cmp-composer__send, .cmp-composer__mic').first();
  await expect(send).toBeFocused();
  const after = await look(composer);
  expect(after.border).toBe(INK);
  expect(after.ring).toBe('none');
  expect(await send.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none');
});
