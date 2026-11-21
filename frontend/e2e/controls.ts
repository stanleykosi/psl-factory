import type { Locator, Page } from '@playwright/test';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Picks a date and time ("2026-11-11T16:20") in the shared date-and-time dropdown (D-158): open it, move to the
 *  month, choose the day, the hour and the minute, then Done. */
export async function fillWhen(scope: Page | Locator, label: string, value: string) {
  const [day, clock] = value.split('T');
  const [hour, minute] = clock.split(':');
  const [y, m] = day.split('-').map(Number);
  await scope.getByRole('button', { name: new RegExp(`^${escape(label)} `) }).click();
  const panel = scope.getByRole('dialog', { name: 'Choose a date and time' });
  const want = y * 12 + (m - 1);
  for (let step = 0; step < 240; step += 1) {
    const [name, year] = ((await panel.getByRole('grid').getAttribute('aria-label')) ?? '').split(' ');
    const shown = Number(year) * 12 + MONTHS.indexOf(name);
    if (shown === want) break;
    await panel.getByRole('button', { name: shown > want ? 'Previous month' : 'Next month' }).click();
  }
  await panel.locator(`[data-iso="${day}"]`).click();
  await panel.getByRole('listbox', { name: 'Hour' }).locator(`[data-value="${hour}"]`).click();
  await panel.getByRole('listbox', { name: 'Minute' }).locator(`[data-value="${minute}"]`).click();
  await panel.getByRole('button', { name: 'Done' }).click();
}

/** Chooses an option of a shared Select by its visible words. */
export async function choose(scope: Page | Locator, label: string | RegExp, option: string | RegExp) {
  await scope.getByRole('combobox', { name: label }).click();
  await scope.getByRole('option', { name: option }).click();
}
