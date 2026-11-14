import { settle } from './act-wait.mjs';
// Board state: Line "Invoice preparation and delivery" and a State applied, then the panel open again.
export default async function (page) {
  await settle(page);
  const open = () => page.locator('button[aria-haspopup="dialog"]').first().click();
  await open();
  const dlg = page.getByRole('dialog', { name: 'Filter' });
  await dlg.getByRole('checkbox', { name: 'Invoice preparation and delivery' }).check();
  await dlg.getByRole('combobox', { name: 'State' }).selectOption('waiting');
  await dlg.getByRole('button', { name: /^Show (\d+\+? items?|results)$/ }).click();
  await page.waitForURL(/line=invoice/);
  await page.waitForTimeout(300);
  await settle(page);
  await open();
  await dlg.waitFor();
  await page.waitForTimeout(600);
}
