// F-49: opens the SCR-23 drawer on the built /my-work page, fills it with the board's values (Stated deadline),
// uploads the board's file (an in-memory buffer of 2.4 MB) and waits for "Uploaded".
const FILES = { desktop: 'Tamarind-Loans-RFP-loan-origination.pdf', mobile: 'Tamarind-Loans-RFP.pdf' };
export default async function (page) {
  const phone = page.viewportSize().width < 720;
  if (phone) await page.getByRole('button', { name: 'Start work' }).last().click();
  else await page.getByRole('button', { name: 'More ways to start' }).click();
  const dlg = page.getByRole('dialog');
  await dlg.getByRole('radio').first().waitFor();
  await dlg.getByRole('radio', { name: /^Log a received RFP/ }).check();
  await dlg.getByRole('button', { name: 'Next' }).click();
  await dlg.getByRole('button', { name: 'change line' }).waitFor();
  await dlg.getByRole('combobox', { name: 'Client or prospect' }).click();
  await dlg.getByRole('option', { name: /^Tamarind Loans Ltd/ }).first().click();
  await dlg.getByLabel('RFP reference').fill('TL-RFP-2026-014');
  await dlg.locator('[data-field="rfp_document"] input[type="file"]').setInputFiles({ name: FILES[phone ? 'mobile' : 'desktop'], mimeType: 'application/pdf', buffer: Buffer.alloc(Math.round(2.4 * 1024 * 1024), 7) });
  await dlg.getByText(/^Uploaded · /).waitFor();
  await dlg.getByLabel('Received').fill('2026-11-12T09:40');
  await dlg.getByRole('radiogroup', { name: 'How the client wants it submitted' }).getByRole('radio', { name: 'Email' }).click();
  await dlg.getByLabel('Submit to (optional)').fill('procurement@tamarindloans.example');
  await dlg.getByRole('radiogroup', { name: 'Submission deadline' }).getByRole('radio', { name: 'Stated', exact: true }).click();
  await dlg.getByLabel('Deadline (optional)').fill('2026-11-28T17:00');
  await dlg.getByLabel('Note (optional)').fill('Received from their procurement lead by email.');
  await page.mouse.move(0, 899);
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
}
