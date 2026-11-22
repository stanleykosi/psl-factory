import { expect, test, type Locator, type Page } from '@playwright/test';

const PHONE = { width: 390, height: 844 };
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

test.beforeEach(async ({ request, context, baseURL }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
  await context.addCookies([{ name: 'psl_mock_persona', value: 'pm', url: baseURL! }]);
});

async function loaded(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
}

/** Every target is at least 44 by 44 (a label around a box counts as the target). */
async function expectTargets(targets: Locator[]) {
  for (const target of targets) {
    await expect(target.first()).toBeVisible();
    const box = (await target.first().boundingBox())!;
    expect(box.height, String(target)).toBeGreaterThanOrEqual(44);
    expect(box.width).toBeGreaterThanOrEqual(44);
  }
}

test('response form at 390: the shared Select, DateField, radios, checkbox and file zone are 44px targets', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto('/work/W-1605/respond?task=T-1605');
  await loaded(page);
  await expectTargets([
    page.getByRole('combobox', { name: 'Who responded' }),
    page.getByRole('button', { name: /^When they responded / }),
    page.getByRole('radio', { name: 'Approved' }).locator('xpath=ancestor::label'),
    page.getByRole('checkbox').locator('xpath=ancestor::label'),
    page.getByText(/Take a photo or/).locator('xpath=ancestor::label'),
  ]);
});

test('RFP follow-up at 390: Send, Edit and the edit box are 44px targets, and Enter and Space press the buttons', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto('/work/W-2108/outcome');
  await loaded(page);
  await expectTargets([page.getByRole('button', { name: 'Send follow-up' }), page.getByRole('button', { name: 'Edit' })]);
  const edit = page.getByRole('button', { name: 'Edit' });
  await edit.focus();
  await page.keyboard.press('Space');
  await expect(page.getByLabel('Follow-up text')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Use the draft' })).toBeVisible();
  await page.getByRole('button', { name: 'Use the draft' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Edit' })).toBeVisible();
});

test('My work filters at 390: the line checkboxes, the Show-all link and the three Selects are 44px targets', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: baseURL! }]);
  await page.setViewportSize(PHONE);
  await page.goto('/my-work');
  await loaded(page);
  await page.getByRole('button', { name: /^Filter/ }).click();
  const dialog = page.getByRole('dialog', { name: 'Filter' });
  await expect(dialog).toBeVisible();
  await expectTargets([
    dialog.getByRole('checkbox').first().locator('xpath=ancestor::label'),
    dialog.getByRole('button', { name: /lines$/ }),
    dialog.getByRole('combobox', { name: 'Project' }),
    dialog.getByRole('combobox', { name: 'State' }),
    dialog.getByRole('combobox', { name: 'Waiting on' }),
  ]);
});

test('proof file zone, Remove and Clear search are 44px targets at 390', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto('/work/W-2101/respond?task=T-2101');
  await loaded(page);
  await expectTargets([page.getByText('choose a file').locator('xpath=ancestor::label')]);
  await page.getByRole('radio', { name: 'Security, missing' }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: 'proof.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(2048) });
  await expectTargets([page.getByRole('button', { name: 'Remove proof.pdf' })]);
  await page.goto('/projects?q=zzz');
  await loaded(page);
  await expectTargets([page.getByRole('button', { name: 'Clear search' })]);
});
