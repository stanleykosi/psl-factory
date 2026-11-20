// F-51 round 2: opens the SCR-04 fixed asset schedule or cash forecast drawer on the built /my-work page and fills it with the
// board's values. FID_LINE picks the drawer: ppe or forecast. The phone sheet is captured whole (as F-49's driver).
export default async function (page) {
  const phone = page.viewportSize().width < 720;
  const line = process.env.FID_LINE;
  if (phone) await page.getByRole('button', { name: 'Start work' }).last().click();
  else await page.getByRole('button', { name: 'More ways to start' }).click();
  const dlg = page.getByRole('dialog');
  await dlg.getByRole('radio').first().waitFor();
  await dlg.getByRole('radio', { name: line === 'ppe' ? /^Fixed asset schedule/ : /^Cash forecast/ }).check();
  await dlg.getByRole('button', { name: 'Next' }).click();
  await dlg.getByRole('button', { name: 'change line' }).waitFor();
  if (line === 'ppe') {
    await dlg.locator('[data-field="proof"] input[type="file"]').setInputFiles({ name: 'ppe_register_oct.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.alloc(98304, 7) });
    await dlg.getByText(/^Uploaded · /).waitFor();
    await dlg.getByRole('combobox', { name: /^Prior schedule/ }).click();
    await dlg.getByRole('option', { name: /^PPE-0005/ }).first().click();
  } else {
    await dlg.getByRole('combobox', { name: 'Scenario' }).click();
    await dlg.getByRole('option', { name: /^Base case · v4/ }).first().click();
    const asOf = dlg.getByLabel('As of');
    await asOf.fill('31 Oct 2026');
    await asOf.blur();
    await dlg.getByLabel('Months').fill('6');
    // Audience keeps the option the line's data names (Management), as the board draws it selected
  }
  if (phone) {
    const extra = await dlg.evaluate((el) => { const s = el.querySelector('.cmp-scroll'); return s ? s.scrollHeight - s.clientHeight : 0; });
    await page.setViewportSize({ width: 390, height: 844 + Math.max(0, extra) + 40 });
    await dlg.evaluate((el) => { const s = el.querySelector('.cmp-scroll'); if (s) s.scrollTop = 0; });
  }
  await page.mouse.move(0, 899);
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
}
