import { expect, test, type Page } from '@playwright/test';

// D-155: the live demo of the mock. These two specs need the dev server the dev script starts (MOCK_DEMO and
// NEXT_PUBLIC_MOCK_DEMO on): the demo bar does not exist in a production build. Run them with E2E_DEMO=1.
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.skip(process.env.E2E_DEMO !== '1', 'needs the dev server with the demo bar (E2E_DEMO=1)');
test.describe.configure({ timeout: 240_000 });

test.beforeEach(async ({ request, context, baseURL }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies(
    [['psl_mock_persona', 'pm'], ['psl_mock_demo', 'on'], ['psl_mock_speed', 'fast']].map(([name, value]) => ({ name, value, url: baseURL! })),
  );
});

async function switchRole(page: Page, role: string) {
  await page.getByRole('complementary', { name: 'Demo controls' }).getByRole('button', { name: 'Demo' }).click();
  await page.getByRole('combobox', { name: 'Role' }).click();
  await Promise.all([page.waitForEvent('load'), page.getByRole('option', { name: role, exact: true }).click()]);
}

test('a line run: pm starts an invoice, the steps tick, the Finance Lead decides from the demo bar, and it ends in Done', async ({ page }) => {
  await page.goto('/my-work');
  await page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Project' }).click();
  await dialog.getByRole('option', { name: 'Lagoon Health · patient app' }).click();
  await dialog.getByRole('combobox', { name: 'Completed milestone' }).click();
  await dialog.getByRole('option', { name: /Milestone 3/ }).click();
  await dialog.getByRole('button', { name: 'Start the invoice' }).click();
  await expect(page).toHaveURL(/\/work\/W-9001$/);

  // the first station is the agent's: its steps appear one after the other
  await expect(page.getByText('Read what “Draft invoice” needs')).toBeVisible();
  await expect(page.getByText('Worked on “Draft invoice”')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Checked the result of “Draft invoice”')).toBeVisible({ timeout: 30_000 });

  // then it waits for a person, who is not the starter
  await expect(page.getByText('A Finance Lead decides “Finance review”.').first()).toBeVisible({ timeout: 30_000 });
  await page.goto('/my-work?queue=waiting_on_others');
  await expect(page.getByRole('link', { name: /Invoice preparation and delivery · Demo 1/ })).toBeVisible();

  await switchRole(page, 'Finance Lead');
  await page.goto('/my-work');
  await page.getByRole('link', { name: /Invoice preparation and delivery · Demo 1/ }).click();
  await page.getByRole('link', { name: 'Open the decision' }).click();
  const approve = page.getByRole('button', { name: /^Approve / });
  await expect(approve).toBeEnabled();
  await approve.click();

  // the remaining stations run, and the item ends verified, in Done, for the starter
  await switchRole(page, 'PM');
  await page.goto('/my-work?queue=done');
  // My work reads again every 15 s, so the item turns up by itself
  await expect(page.getByRole('link', { name: /Invoice preparation and delivery · Demo 1/ })).toBeVisible({ timeout: 120_000 });
  await page.getByRole('link', { name: /Invoice preparation and delivery · Demo 1/ }).click();
  await expect(page.getByText('Done. Every step is in the history.').first()).toBeVisible();
});

test('a won RFP creates a project: it shows in the Projects list, its page and the Start work picker', async ({ page, request, context, baseURL }) => {
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pmo_lead', url: baseURL! }]);
  const cookie = 'psl_mock_persona=pmo_lead; psl_mock_demo=on; psl_mock_speed=fast';
  const send = async (method: 'get' | 'post', path: string, data?: object) => {
    const response = await request[method](`${MOCK}${path}`, { headers: { Cookie: cookie, 'X-CSRFToken': 'mock-csrf-pmo_lead' }, ...(data ? { data } : {}) });
    return response.json();
  };
  // log an RFP as the PMO Lead through the mock, as the page's form would
  const revision = (await send('get', '/api/v1/lines')).items.find((l: { key: string }) => l.key === 'rfp_intake').case_revision;
  const proof = await send('post', '/api/v1/cases/C-RFP-INTAKE/evidence', { kind: 'rfp_document', filename: 'rfp.pdf', content_base64: Buffer.from('rfp').toString('base64'), case_revision: revision });
  const { work_id: id } = await send('post', '/api/v1/work', {
    line: 'rfp_intake', case_id: 'C-RFP-INTAKE', case_revision: proof.case_revision, idempotency_key: 'e2e-rfp',
    intake: { client: 'CL-3506', rfp_reference: 'E2E-RFP-1', rfp_document: proof.evidence_id, received_at: '2026-11-12T08:40:00.000Z', submission_method: 'email', deadline_status: 'unknown' },
  });

  // the PMO Lead assigns a PM when the run waits, then the run verifies
  await expect.poll(async () => (await send('get', `/api/v1/work/${id}`)).tasks?.length ?? 0, { timeout: 60_000 }).toBe(1);
  const task = (await send('get', `/api/v1/work/${id}`)).tasks[0];
  await send('post', `/api/v1/tasks/${task.id}/decision`, { expected_revision: task.revision, verdict: 'approve' });
  await expect.poll(async () => (await send('get', `/api/v1/work/${id}`)).state, { timeout: 60_000 }).toBe('verified');

  await page.goto('/projects');
  const link = page.getByRole('link', { name: /Tamarind Loans Ltd · new engagement/ });
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(/\/projects\/00000000-0000-4000-8000-000000009001$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Tamarind Loans Ltd · new engagement' })).toBeVisible();

  await page.goto('/my-work');
  await page.locator('nav.psl-nav').getByRole('button', { name: 'Start work' }).click();
  await page.getByRole('dialog').getByRole('combobox', { name: 'Project' }).click();
  await expect(page.getByRole('option', { name: 'Tamarind Loans Ltd · new engagement' })).toBeVisible();
});

test('an assistant run: the steps appear one at a time, then the answer, its sources and the card', async ({ page }) => {
  await page.goto('/assistant');
  await page.getByRole('textbox', { name: 'Message Tola' }).fill('How are my projects doing?');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page).toHaveURL(/\/assistant\/CV-N1$/);
  await expect(page.getByText('Read your request')).toBeVisible();
  await expect(page.getByText('Looked up the projects and milestones you can see')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Sample answer from Tola in the live demo.')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Sample project plan')).toBeVisible();
  await expect(page.getByText('Sample status note')).toBeVisible();
});
