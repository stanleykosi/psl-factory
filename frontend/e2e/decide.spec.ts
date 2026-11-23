import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// SCR-03 journeys on the mock's live decision desk (mock/live-decide.mjs): work 17 / task 41 decides, 18 / 42 is not
// yours, 19 / 43 has no invoice packet. Cookie psl_mock_decide=stale redrafts the invoice before the first decision.
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOCK = `http://127.0.0.1:${process.env.MOCK_PORT ?? 3102}`;

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function loaded(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: 'Loading…' })).toHaveCount(0);
  await expect(page.locator('main#main h1').first()).toBeVisible();
}

async function openDecision(page: Page, work = '17', task = '41') {
  await page.goto(`/work/${work}/decide?task=${task}`);
  await loaded(page);
  await expect(page).toHaveTitle('Decision · PSL Factory');
  await expect(page.getByText('Getting this decision ready…')).toHaveCount(0);
}

const cookie = (page: Page, name: string, value: string) => page.context().addCookies([{ name, value, domain: 'localhost', path: '/' }]);
const pick = (page: Page, name = /client email/) => page.getByRole('radio', { name }).check();

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${MOCK}/__mock/reset`)).status()).toBe(204);
});

test('approve: the evidence picker gates the buttons, then the done board names the verdict', async ({ page }) => {
  await openDecision(page);
  await expect(page.getByRole('radio')).toHaveCount(2);
  await expect(page.getByRole('radio', { checked: true })).toHaveCount(0);
  for (const name of [/^Approve v2/, 'Return', 'Reject']) await expect(page.getByRole('button', { name })).toBeDisabled();
  await expect(page.getByText('Choose the evidence you are relying on to turn on these buttons.')).toBeVisible();
  await pick(page);
  await expect(page.getByRole('button', { name: 'Approve v2' })).toBeEnabled();
  await page.getByRole('button', { name: 'Approve v2' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Invoice 3 for the Lekki handover is approved');
  await expect(page.getByText('Approve, with no note')).toBeVisible();
  await expect(page.getByRole('button', { name: /^Approve|Return|Reject/ })).toHaveCount(0);
});

test('return needs a note, then is recorded with it', async ({ page }) => {
  await openDecision(page);
  await pick(page, /signed milestone certificate/);
  await page.getByRole('button', { name: 'Return' }).click();
  await expect(page.getByText('Add a note to return or reject.')).toBeVisible();
  await page.getByLabel(/^Note/).fill('Wrong PO number');
  await page.getByRole('button', { name: 'Return' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Invoice 3 for the Lekki handover was returned');
  await expect(page.getByText('Return, with the note “Wrong PO number”')).toBeVisible();
});

test('reject needs a note, then is recorded with it', async ({ page }) => {
  await openDecision(page);
  await pick(page);
  await page.getByRole('button', { name: 'Reject' }).click();
  await expect(page.getByText('Add a note to return or reject.')).toBeVisible();
  await page.getByLabel(/^Note/).fill('Not our client');
  await page.getByRole('button', { name: 'Reject' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Invoice 3 for the Lekki handover was rejected');
});

test('a redrafted invoice shows the stale board, keeps the note and offers only Review version 3', async ({ page }) => {
  await cookie(page, 'psl_mock_decide', 'stale');
  await openDecision(page);
  await pick(page);
  await page.getByLabel(/^Note/).fill('Looks right');
  await page.getByRole('button', { name: 'Approve v2' }).click();
  await expect(page.getByText('A newer version arrived while you were reading.')).toBeVisible();
  await expect(page.getByText('Your note wasn’t sent: “Looks right”')).toBeVisible();
  await expect(page.getByText('₦4,300,000.00')).toBeVisible();
  await page.getByRole('button', { name: 'Review version 3' }).click();
  await expect(page.getByRole('button', { name: 'Approve v3' })).toBeVisible();
});

test('not yours: read-only with the generic sentence, a comment box and no decision buttons', async ({ page }) => {
  await openDecision(page, '18', '42');
  await expect(page.getByText('NOT YOUR DECISION')).toBeVisible();
  await expect(page.getByRole('button', { name: /^Approve|Return|Reject/ })).toHaveCount(0);
  await page.getByLabel(/^Comment for the finance reviewer/).fill('Please check the PO number.');
  await page.getByRole('button', { name: 'Add comment' }).click();
  await expect(page.getByText('Your comment was added.')).toBeVisible();
});

test('an unknown amount reads Unknown', async ({ page }) => {
  await openDecision(page, '19', '43');
  await expect(page.getByText('Unknown', { exact: true })).toBeVisible();
  await expect(page.locator('main')).not.toContainText('₦0');
});

test('not-open: a task that is not on the work, no task, and a non-numeric id', async ({ page }) => {
  for (const url of ['/work/17/decide?task=99', '/work/17/decide', '/work/W-1201/decide?task=T-1201']) {
    await page.goto(url);
    await loaded(page);
    await expect(page.getByText('This decision isn’t open here')).toBeVisible();
  }
});

test('error states: no access, signed out, and an unconfirmed decision', async ({ page }) => {
  await cookie(page, 'psl_mock_scenario', '404');
  await page.goto('/work/17/decide?task=41');
  await expect(page.getByRole('button', { name: /^Approve|Return|Reject/ })).toHaveCount(0);
  await expect(page.getByText('This decision isn’t open here')).toHaveCount(0);
  await page.context().clearCookies({ name: 'psl_mock_scenario' });
  await cookie(page, 'psl_mock_scenario', '401');
  await page.goto('/work/17/decide?task=41');
  await expect(page.getByText(/signed out/i).first()).toBeVisible();
  await page.context().clearCookies({ name: 'psl_mock_scenario' });
  // the decision fails in the network and the reload fails too: the buttons stay off
  const state = { down: false };
  await page.route('**/api/v1/tasks/41/decision', (route) => {
    state.down = true;
    return route.abort('failed');
  });
  await page.route('**/api/v1/work/17', (route) =>
    state.down ? route.fulfill({ status: 503, contentType: 'application/json', body: '{"code":"server_error","message":"Down."}' }) : route.continue(),
  );
  await openDecision(page);
  await pick(page);
  await page.getByRole('button', { name: 'Approve v2' }).click();
  await expect(page.getByText('We couldn’t confirm whether your decision was recorded.')).toBeVisible();
  for (const name of [/^Approve v2/, 'Return', 'Reject']) await expect(page.getByRole('button', { name })).toBeDisabled();
  await expectNoAxeViolations(page);
});
