export async function settle(page) {
  await page.waitForFunction(() => !document.querySelector('.psl-loading') && document.querySelector('[role=tabpanel]'), null, { timeout: 30000 });
  await page.waitForLoadState('networkidle');
}
export default async function (page) { await settle(page); }
