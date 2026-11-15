// Opens the SCR-04 state named by FID_STATE on the built /my-work page.
const TITLES = { '': 'Invoice preparation and delivery', validation: 'Invoice preparation and delivery', weekly: 'Reviewed weekly client report', minutes: 'Formal minutes and action handoff', issue: 'Issue investigation and owner follow-up', change: 'Controlled change and signed closure', incident: 'Emergency change for an incident', escalation: 'Escalate and communicate', leadership: 'Leadership report' };
async function pick(page, label, option) {
  const dlg = page.getByRole('dialog');
  await dlg.getByRole('combobox', { name: label }).click();
  await dlg.getByRole('option', { name: new RegExp('^' + option.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).first().click();
}
export default async function (page) {
  const state = process.env.FID_STATE || '';
  const phone = page.viewportSize().width < 720;
  if (phone) await page.getByRole('button', { name: 'Start work' }).last().click();
  else await page.getByRole('button', { name: 'More ways to start' }).click();
  const dlg = page.getByRole('dialog');
  await dlg.getByRole('radio').first().waitFor();
  if (state === 'lines') return;
  await dlg.getByRole('radio', { name: new RegExp('^' + TITLES[state]) }).check();
  await dlg.getByRole('button', { name: 'Next' }).click();
  await dlg.getByRole('button', { name: 'change line' }).waitFor();
  const project = state === 'incident' || state === 'validation' ? 'Harmattan Bank' : 'Lagoon Health';
  if (state !== 'leadership') await pick(page, 'Project', project);
  switch (state) {
    case '': await pick(page, 'Completed milestone', 'Milestone 3'); break;
    case 'validation':
      await dlg.getByRole('button', { name: 'Start the invoice' }).click();
      await dlg.getByRole('alert').waitFor(); break;
    case 'weekly':
      await dlg.getByLabel('From').fill('2026-11-12'); await dlg.getByLabel('To').fill('2026-11-18'); break;
    case 'minutes': await pick(page, 'Meeting', 'Weekly sync'); await dlg.getByRole('radio', { name: 'Client' }).click(); break;
    case 'issue': await pick(page, 'Issue', 'ISS-0233'); break;
    case 'change': await dlg.getByLabel('What the client asked for').fill('Add WhatsApp reminders as well as SMS'); break;
    case 'incident': await pick(page, 'Incident', 'INC-0031'); await dlg.getByLabel('Plan').fill('Disable the new card router; fall back to the old one.'); break;
    case 'escalation': await pick(page, 'From issue', 'ISS-0241'); await dlg.getByRole('radio', { name: 'To the client' }).click(); break;
    case 'leadership': await dlg.getByRole('radio', { name: 'Internal Tuesday' }).click(); await dlg.getByLabel('Period').fill('2026-11-17'); break;
  }
  await page.mouse.move(0, 899);
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
}
