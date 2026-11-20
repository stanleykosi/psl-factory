import type { Locator, Page } from '@playwright/test';

/** Fills a date-and-time field ("2026-11-11T16:20"): the date as 11/11/2026 then the time beside it. */
export async function fillWhen(scope: Page | Locator, label: string, value: string) {
  const [day, time] = value.split('T');
  const [y, m, d] = day.split('-');
  const date = scope.getByLabel(label, { exact: true });
  await date.fill(`${d}/${m}/${y}`);
  await date.blur();
  await scope.getByLabel(`${label}, time`, { exact: true }).fill(time);
}

/** Chooses an option of a shared Select by its visible words. */
export async function choose(scope: Page | Locator, label: string | RegExp, option: string | RegExp) {
  await scope.getByRole('combobox', { name: label }).click();
  await scope.getByRole('option', { name: option }).click();
}
