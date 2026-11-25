import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// F-137 "Record an issue" on the Registers tab against the contract mock: open the drawer, record, see the new row after the re-read,
// at 1440 and 390, with the one POST counted and axe WCAG 2.2 AA.
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function choose(page: Page, name: RegExp, option: string) {
  await page.getByRole('combobox', { name }).click();
  await page.getByRole('option', { name: option }).click();
}

for (const [label, viewport] of [
  ['desktop 1440', { width: 1440, height: 900 }],
  ['phone 390', { width: 390, height: 844 }],
] as const) {
  test(`record an issue, ${label}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.request.post('/__mock/reset').catch(() => undefined);
    const posts: string[] = [];
    page.on('request', (request) => {
      if (request.method() === 'POST' && /\/issues$/.test(new URL(request.url()).pathname)) posts.push(request.postData() ?? '');
    });
    await page.goto('/projects/P-0101/registers');
    await expect(page.getByRole('button', { name: 'Record an issue' })).toBeVisible();
    await page.getByRole('button', { name: 'Record an issue' }).click();
    const dialog = page.getByRole('dialog', { name: 'Record an issue' });
    await expect(dialog.getByRole('button', { name: 'Record issue' })).toBeVisible();
    await axe(page);

    await dialog.getByRole('button', { name: 'Record issue' }).click();
    await expect(dialog.getByText(/to continue\./).first()).toBeVisible();
    expect(posts).toHaveLength(0);

    await dialog.getByLabel('Reference').fill('ISS-0501');
    await dialog.getByLabel('Title').fill('Appointment emails arrive twice');
    await dialog.getByLabel('Kind').fill('defect');
    await choose(page, /Responsible owner/, 'Kemi Adebayo');
    await dialog.getByLabel('Next action').fill('Check the mail queue');
    await choose(page, /Evidence/, 'test report · version 2 · no. 7902');
    await dialog.getByLabel('Note').fill('Two clients reported it.');
    await choose(page, /Severity/, 'High');
    await dialog.getByRole('button', { name: 'Record issue' }).click();
    await expect(dialog.getByText(/Recorded: ISS-0501/)).toBeVisible();
    expect(posts).toHaveLength(1);
    await axe(page);

    await dialog.getByRole('button', { name: 'Close' }).first().click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByText('ISS-0501').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Record an issue' })).toBeFocused();
  });
}
