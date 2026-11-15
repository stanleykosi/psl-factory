// Wait until the work item (or the no-access board) has loaded and the network is quiet.
export default async function (page) {
  await page.waitForFunction(() => !document.querySelector('[role=status]') && document.querySelector('main h1'), null, { timeout: 30000 });
  await page.waitForLoadState('networkidle');
}
