// F-09 board scenarios on the built page, picked by FID_STATE. Board values only: the act script makes the
// choices the boards draw (Approved, 11 Nov 16:20, the board's file, the tick); the page itself never does.
const STATE = process.env.FID_STATE || 'default';
const pdf = (name, size) => ({ name, mimeType: 'application/pdf', buffer: Buffer.alloc(size, 37) });

async function upload(page, file) {
  await page.locator('input[type="file"]').first().setInputFiles(file);
  await page.getByText(file.name).first().waitFor();
  await page.waitForFunction(() => !document.body.textContent.includes('Uploading…'));
}

export default async function act(page) {
  if (STATE === 'reconcile' || STATE === 'waiting') {
    await page.locator('main h1').first().waitFor();
    return;
  }
  if (STATE === 'sow') {
    await page.getByRole('radio', { name: 'Signed' }).check({ force: true });
    await page.getByLabel('When', { exact: true }).fill('2026-12-20T14:10');
    await upload(page, pdf('SOW-0207-v1-signed.pdf', 1153434));
    await page.getByRole('checkbox').check();
    return;
  }
  await page.getByRole('radio', { name: 'Approved' }).check();
  await page.getByLabel('When they responded').fill('2026-11-11T16:20');
  if (STATE === 'validation') return;
  await upload(page, pdf('Lagoon_UAT_signoff_11Nov.pdf', 184 * 1024));
  await page.getByRole('checkbox').check();
  if (STATE === 'success') {
    await page.getByRole('button', { name: 'Record response' }).click();
    await page.getByRole('status').filter({ hasText: 'Response recorded.' }).waitFor();
  }
}
