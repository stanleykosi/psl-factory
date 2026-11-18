// F-47: opens the SCR-04 proof drawer named by FID_STATE on the built /my-work page, fills it as the spec's Boards
// table says, uploads the board's file (an in-memory buffer at the board's size) and waits for "Uploaded".
const TITLES = { minutes: 'Formal minutes and action handoff', change: 'Controlled change and signed closure', schedules: 'Income detail or schedule inventory', ledger: 'Record a ledger source' };
const FILES = { minutes: ['weekly-sync-notes-17nov.docx', 38912], change: ['client-request-17nov.pdf', 20480], schedules: ['income_detail_oct.xlsx', 53248], ledger: ['qb_export_je7741.pdf', 45056] };
async function pick(page, label, option) {
  const dlg = page.getByRole('dialog');
  await dlg.getByRole('combobox', { name: label }).click();
  await dlg.getByRole('option', { name: new RegExp('^' + option.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).first().click();
}
export default async function (page) {
  const state = process.env.FID_STATE;
  const phone = page.viewportSize().width < 720;
  if (phone) await page.getByRole('button', { name: 'Start work' }).last().click();
  else await page.getByRole('button', { name: 'More ways to start' }).click();
  const dlg = page.getByRole('dialog');
  await dlg.getByRole('radio').first().waitFor();
  await dlg.getByRole('radio', { name: new RegExp('^' + TITLES[state]) }).check();
  await dlg.getByRole('button', { name: 'Next' }).click();
  await dlg.getByRole('button', { name: 'change line' }).waitFor();
  switch (state) {
    case 'minutes': await pick(page, 'Project', 'Lagoon Health'); await pick(page, 'Meeting', 'Weekly sync'); await dlg.getByRole('radio', { name: 'Client' }).click(); break;
    case 'change': await pick(page, 'Project', 'Lagoon Health'); await dlg.getByLabel('What the client asked for').fill('Add WhatsApp reminders as well as SMS'); break;
    case 'schedules': await dlg.getByRole('radio', { name: 'Income detail' }).click(); await dlg.getByLabel('Reference').fill('SCH-INC-2026-10'); await pick(page, 'Mapping note', 'Mapping run MR-0044'); break;
    case 'ledger': await dlg.getByLabel('Key').fill('QB-JE-7741'); break;
  }
  const [name, size] = FILES[state];
  await dlg.locator('[data-field="proof"] input[type="file"]').setInputFiles({ name, mimeType: 'application/octet-stream', buffer: Buffer.alloc(size, 7) });
  await dlg.getByText(/^Uploaded · /).waitFor();
  await page.mouse.move(0, 899);
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
}
