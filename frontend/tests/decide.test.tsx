// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { StrictMode } from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { TaskDecision, WorkItem } from '@/api/types';
import { DecideView } from '@/features/decide/DecideView';
import { formatAmount } from '@/features/decide/format';
import { AppShell } from '@/shell/AppShell';

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-1201/decide',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = <T,>(name: string): T => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as T;
const item = (name: string): WorkItem => (name === 'W-1001' ? read('E-WORK-ITEM.json') : read(`work/${name}.json`));
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };

type Call = { method: string; path: string; body: unknown; csrf: string | null };
type Answer = (n: number, call: Call) => Response | Promise<Response>;
let calls: Call[];
let answers: { me: string; item: Answer; claim: Answer; decide: Answer };

const counts = () => ({
  gets: calls.filter((c) => c.method === 'GET' && c.path.startsWith('/api/v1/work/')).length,
  claims: calls.filter((c) => c.path.endsWith('/claim')),
  decides: calls.filter((c) => c.path.endsWith('/decision')),
});

beforeEach(() => {
  calls = [];
  answers = {
    me: 'finance_lead',
    item: () => json(200, item('W-1201')),
    claim: (_, c) => json(200, { task_id: c.path.split('/')[4], revision: (c.body as { expected_revision: number }).expected_revision, claimed_by: 'Ada Okafor' }),
    decide: (_, c) => json(200, { task_id: c.path.split('/')[4], verdict: (c.body as { verdict: string }).verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-12T09:47:00Z', work_state: 'ready' }),
  };
  const n = { item: 0, claim: 0, decide: 0 };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const c: Call = { method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') };
      calls.push(c);
      if (url.pathname === '/api/v1/me') return json(200, read(`me.${answers.me}.json`));
      if (url.pathname.endsWith('/claim')) return answers.claim(n.claim++, c);
      if (url.pathname.endsWith('/decision')) return answers.decide(n.decide++, c);
      return answers.item(n.item++, c);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});

async function open(id = 'W-1201', taskId: string | null = 'T-1201', strict = false) {
  const tree = (
    <AppShell>
      <DecideView id={id} taskId={taskId ?? undefined} />
    </AppShell>
  );
  render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
const button = (name: string | RegExp) => screen.getByRole('button', { name });
const ready = () => waitFor(() => expect((button(/^Approve v/) as HTMLButtonElement).disabled).toBe(false));
const text = () => document.body.textContent ?? '';
const decisionControls = () => screen.queryAllByRole('button', { name: /approve|return|reject/i });

describe('default view', () => {
  it('W-1201 shows only the decision values, the chain and the three controls (A-DECIDE)', async () => {
    await open();
    await ready();
    for (const value of [
      'Invoice v2',
      '₦4,250,000.00',
      'Contract stage 2 of 4 · terms v1',
      'accounts@lagoonhealth.example',
      'Changed since Invoice v1',
      'PO number, as you asked',
      'Bisi Ade (Finance)',
      'Chidi',
      'Step 1 of 1',
      'Only a Finance Lead can decide. You are Finance Lead.',
    ]) {
      expect(text(), value).toContain(value);
    }
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Approve invoice v2');
    expect(screen.getByText('FINANCE REVIEW · INV-0412')).toBeTruthy();
    expect(screen.getByText('Lagoon Health · Milestone 2 invoice')).toBeTruthy();
    expect(button('Approve v2')).toBeTruthy();
    expect(button('Return')).toBeTruthy();
    expect(button('Reject')).toBeTruthy();
    expect(screen.getByText(/Approving earns APPROVED only\. Issue is the next station\./)).toBeTruthy();
    expect(screen.getByText('Station 4 of 7 · Finance review · only a Finance Lead can decide')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'See Chidi’s steps' }).getAttribute('href')).toBe('/work/W-1201');
    expect(screen.getByText('Cannot approve, send or pay.')).toBeTruthy();
    const crumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(crumb.textContent).toBe('My work / Prepare an invoice / INV-0412');
    const label = screen.getByLabelText(/^Note/) as HTMLTextAreaElement;
    expect(label.maxLength).toBe(2000);
    expect(screen.getByText('0 / 2000')).toBeTruthy();
  });

  it('formats amounts from the decimal string and never shows unknown as zero (INV-UNKNOWN)', async () => {
    expect(formatAmount({ amount: '4250000.00', currency: 'NGN', unknown: false })).toBe('₦4,250,000.00');
    expect(formatAmount({ amount: '1200.50', currency: 'USD', unknown: false })).toBe('USD 1,200.50');
    expect(formatAmount({ amount: '999.99', currency: 'NGN', unknown: false })).toBe('₦999.99');
    expect(formatAmount({ amount: '-12345678901234567.10', currency: 'NGN', unknown: false })).toBe('-₦12,345,678,901,234,567.10');
    expect(formatAmount({ currency: 'NGN', unknown: true })).toBeNull();
    expect(formatAmount({ amount: '4250000.00', currency: 'NGN', unknown: true })).toBeNull();

    answers.item = () => json(200, item('W-1202'));
    await open('W-1202', 'T-1202');
    const amountRow = screen.getByText('Amount').parentElement!;
    expect(amountRow.querySelector('dd')!.textContent).toBe('Unknown');
    expect(amountRow.querySelector('.psl-unknown')).toBeTruthy();
    expect(text()).not.toMatch(/0\.00|₦0/);
  });

  it('a decision with unknown: true and an amount string still shows Unknown', async () => {
    const crafted = item('W-1201');
    crafted.tasks[0].decision!.amount = { amount: '4250000.00', currency: 'NGN', unknown: true };
    answers.item = () => json(200, crafted);
    await open();
    expect(screen.getByText('Amount').parentElement!.querySelector('dd')!.textContent).toBe('Unknown');
    expect(text()).not.toContain('4,250,000');
  });

  it('W-1208 omits To and Changed since, and shows two earlier approvals with WAT times', async () => {
    answers.item = () => json(200, item('W-1208'));
    await open('W-1208', 'T-1208');
    expect(screen.queryByText('To')).toBeNull();
    expect(text()).not.toContain('Changed since');
    expect(text()).toContain('Step 3 of 3');
    const steps = within(screen.getByRole('region', { name: 'Approval chain' })).getAllByRole('listitem');
    expect(steps.map((li) => li.textContent)).toEqual([
      '1PM · Tunde BelloApproved 12 Nov 09:05',
      '2PMO Lead · Ngozi EzeApproved 12 Nov 09:40',
      '3Finance Lead · Ada Okafor (you)Current',
    ]);
    expect(steps[0].querySelector('time')!.getAttribute('dateTime')).toBe('2026-11-12T08:05:00Z');
  });
});

describe('claim and decide', () => {
  it('claims once on open with the task revision and the CSRF header, also under StrictMode', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const original = answers.claim;
    answers.claim = async (n, c) => {
      await gate;
      return original(n, c);
    };
    await open('W-1201', 'T-1201', true);
    await waitFor(() => expect(counts().claims).toHaveLength(1));
    expect(screen.getByText('Getting this decision ready…')).toBeTruthy();
    for (const name of [/^Approve v2/, 'Return', 'Reject']) expect((button(name) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => release());
    await ready();
    expect(screen.queryByText('Getting this decision ready…')).toBeNull();
    expect(counts().claims).toEqual([
      { method: 'POST', path: '/api/v1/tasks/T-1201/claim', body: { expected_revision: 2 }, csrf: 'mock-csrf-finance_lead' },
    ]);
  });

  it('Approve sends one decide with the claim revision, then shows the done view with the reloaded facts', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1201' : 'W-1201.approve'));
    await open();
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('Invoice v2 is approved');
    expect(counts().decides).toEqual([
      { method: 'POST', path: '/api/v1/tasks/T-1201/decision', body: { expected_revision: 2, verdict: 'approve' }, csrf: 'mock-csrf-finance_lead' },
    ]);
    expect(screen.getByText(/^YOU APPROVED ·/).textContent).toBe('YOU APPROVED · 10:47');
    expect(screen.getByText('Decided by Ada Okafor')).toBeTruthy();
    await screen.findByText('Chidi issues invoice v2 and emails it to Lagoon Health.');
    expect(screen.getByText('Chidi issues invoice v2 and emails it to Lagoon Health.').closest('.psl-callout')!.className).toContain('psl-callout--success');
    const approved = within(screen.getByRole('list', { name: 'Facts' })).getAllByRole('listitem')[2];
    expect(approved.textContent).toBe('APPROVEDEarned12 Nov 10:47');
    expect(screen.getByText('Paid is tracked separately by Finance and is not part of this decision.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open the work item' }).getAttribute('href')).toBe('/work/W-1201');
    expect(screen.getByRole('link', { name: 'Back to my work' }).getAttribute('href')).toBe('/my-work');
    expect(decisionControls()).toHaveLength(0);
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(counts().gets).toBe(2);
  });

  it('the done view keeps its header and warns when the reload fails', async () => {
    answers.item = (n) => (n === 0 ? json(200, item('W-1201')) : json(500, { code: 'server_error', message: 'Down.' }));
    await open();
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('We couldn’t refresh this item. Open the work item to see the latest.');
    expect(screen.getByText('Invoice v2 is approved')).toBeTruthy();
  });

  it('Return or Reject without a note sends nothing and asks for one; a note is sent as typed', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1201' : 'W-1201.return'));
    await open();
    await ready();
    const note = screen.getByLabelText(/^Note/) as HTMLTextAreaElement;
    for (const name of ['Return', 'Reject']) {
      for (const value of ['', '   \n ']) {
        fireEvent.change(note, { target: { value } });
        fireEvent.click(button(name));
        expect(screen.getByText('Add a note to return or reject.')).toBeTruthy();
        expect(note.getAttribute('aria-invalid')).toBe('true');
        const error = screen.getByText('Add a note to return or reject.');
        expect(note.getAttribute('aria-describedby')).toContain(error.id);
        expect(document.activeElement).toBe(note);
      }
    }
    expect(counts().decides).toHaveLength(0);
    fireEvent.change(note, { target: { value: 'Wrong PO' } });
    expect(screen.getByText('8 / 2000')).toBeTruthy();
    expect(note.getAttribute('aria-invalid')).toBeNull();
    fireEvent.click(button('Return'));
    await screen.findByText('Invoice v2 was returned');
    expect(counts().decides.map((c) => c.body)).toEqual([{ expected_revision: 2, verdict: 'return', note: 'Wrong PO' }]);
    expect(screen.getByText(/^YOU RETURNED ·/)).toBeTruthy();
    await screen.findByText('Bisi Ade corrects invoice v2 and resubmits it.');
    expect(screen.getByText('Bisi Ade corrects invoice v2 and resubmits it.').closest('.psl-callout')!.className).toContain('psl-callout--info');
    expect(screen.queryByText(/Paid is tracked separately/)).toBeNull();
  });

  it('a note over 2000 characters is refused before any request; Approve sends a note only when non-blank', async () => {
    await open();
    await ready();
    const note = screen.getByLabelText(/^Note/) as HTMLTextAreaElement;
    fireEvent.change(note, { target: { value: 'x'.repeat(2001) } });
    fireEvent.click(button('Approve v2'));
    expect(screen.getByText('Keep the note to 2000 characters or fewer.')).toBeTruthy();
    expect(counts().decides).toHaveLength(0);
    fireEvent.change(note, { target: { value: '  ' } });
    fireEvent.click(button('Approve v2'));
    await screen.findByText('Invoice v2 is approved');
    expect(counts().decides.map((c) => c.body)).toEqual([{ expected_revision: 2, verdict: 'approve' }]);
  });

  it('a double click sends one decide; while pending all three are disabled and Approve reads Approving…', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const original = answers.decide;
    answers.decide = async (n, c) => {
      await gate;
      return original(n, c);
    };
    await open();
    await ready();
    const approve = button('Approve v2');
    fireEvent.click(approve);
    fireEvent.click(approve);
    await screen.findByText('Approving…');
    expect(counts().decides).toHaveLength(1);
    for (const name of ['Approving…', 'Return', 'Reject']) expect((button(name) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole('region', { name: 'Your decision' }).getAttribute('aria-busy')).toBe('true');
    fireEvent.click(button('Approving…'));
    await act(async () => release());
    await screen.findByText('Invoice v2 is approved');
    expect(counts().decides).toHaveLength(1);
  });
});

describe('stale (A-STALE)', () => {
  it('a 409 on decide keeps the replaced version, reloads once and compares; Review claims the new revision', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1207' : 'W-1207.next'));
    answers.decide = (n) => (n === 0 ? json(409, STALE) : json(200, { task_id: 'T-1207', verdict: 'approve', decided_by: 'Ada Okafor', decided_at: '2026-11-12T09:50:00Z', work_state: 'waiting' }));
    await open('W-1207', 'T-1207');
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('A newer version arrived while you were reading.');
    expect(counts().decides).toHaveLength(1);
    expect(counts().gets).toBe(2);
    expect(text()).toContain('Version 3 was drafted at 12 Nov 10:46.');
    expect(text()).toContain('Version 2 can no longer be approved.');
    const old = screen.getByRole('region', { name: 'VERSION 2 · REPLACED' });
    const now = screen.getByRole('region', { name: 'VERSION 3 · CURRENT' });
    expect(within(old).getByText('accounts@lagoonhealth.example')).toBeTruthy();
    const nowRows = Object.fromEntries(within(now).getAllByRole('term').map((dt) => [dt.textContent, dt.nextElementSibling!.textContent]));
    expect(nowRows).toEqual({
      Amount: '₦4,250,000.00 · unchanged',
      Basis: 'Contract stage 2 of 4 · terms v1 · unchanged',
      'Send to': 'billing@lagoonhealth.example · changed',
    });
    expect(within(now).getByText('Billing contact changed')).toBeTruthy();
    expect(screen.getByText('Decisions always apply to one exact version, so an approval can never land on the wrong one.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /^Approve/ })).toBeNull();
    expect(counts().claims).toHaveLength(1);

    fireEvent.click(button('Review version 3'));
    await waitFor(() => expect(counts().claims).toHaveLength(2));
    expect(counts().claims[1].body).toEqual({ expected_revision: 5 });
    await ready();
    expect(button('Approve v3')).toBeTruthy();
    expect(counts().decides).toHaveLength(1);
  });

  it('a 409 on claim goes to the same stale view and sends no decide', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1207' : 'W-1207.next'));
    answers.claim = (n, c) => (n === 0 ? json(409, STALE) : json(200, { task_id: 'T-1207', revision: (c.body as { expected_revision: number }).expected_revision, claimed_by: 'Ada Okafor' }));
    await open('W-1207', 'T-1207');
    await screen.findByText('A newer version arrived while you were reading.');
    expect(screen.getByRole('region', { name: 'VERSION 2 · REPLACED' })).toBeTruthy();
    expect(counts().decides).toHaveLength(0);
  });

  it('Review leads to the read-only view when the current version is not yours to decide', async () => {
    const next = item('W-1207.next');
    next.tasks[0] = { ...next.tasks[0], you_can_act: false, cannot_act_reason: 'not_your_role', asked: [] };
    answers.item = (n) => json(200, n === 0 ? item('W-1207') : next);
    answers.decide = () => json(409, STALE);
    await open('W-1207', 'T-1207');
    await ready();
    fireEvent.click(button('Approve v2'));
    fireEvent.click(await screen.findByRole('button', { name: 'Review version 3' }));
    expect(screen.getByText('This decision needs a Finance Lead.')).toBeTruthy();
    expect(decisionControls()).toHaveLength(0);
    expect(counts().claims).toHaveLength(1);
  });
});

describe('cannot act (A-NOT-YOURS)', () => {
  it.each([
    ['W-1203', 'T-1203'],
    ['W-1204', 'T-1204'],
    ['W-1205', 'T-1205'],
    ['W-1206', 'T-1206'],
  ])('%s renders no note and no decision buttons and sends only GETs', async (id, task) => {
    answers.item = () => json(200, item(id));
    await open(id, task);
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(document.querySelector('textarea')).toBeNull();
    expect(decisionControls()).toHaveLength(0);
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
    expect(screen.getByRole('link', { name: 'Open the work item' }).getAttribute('href')).toBe(`/work/${id}`);
  });

  it('copy follows cannot_act_reason, with who was asked', async () => {
    const cases: [string, string[]][] = [
      ['W-1203', ['NOT YOUR DECISION', 'This decision needs a Finance Lead.', 'You can read it, but you can’t approve, return or reject it.', 'Ada Okafor (Finance Lead) was alerted at 12 Nov 10:42 by WhatsApp and email', 'Waiting for Finance Lead', 'SOW v2 stage 2']],
      ['W-1204', ['WAITING FOR REVIEW', 'You prepared Invoice v2, so someone else must review it.', 'Ada Okafor (Finance Lead) was alerted at 12 Nov 10:20']],
      ['W-1205', ['ALREADY DECIDED', 'This decision has already been made.', 'Nothing more is needed from you here.', 'Nobody has been asked yet.']],
      ['W-1206', ['NOT YOUR TURN YET', 'This needs PMO Lead first.', 'You’ll be asked when it’s your turn.', 'Step 3 of 3', 'Ngozi Eze (PMO Lead) has been asked.', 'Waiting for CEO']],
    ];
    for (const [id, expected] of cases) {
      answers.item = () => json(200, item(id));
      const { unmount } = render(
        <AppShell>
          <DecideView id={id} taskId={`T-${id.slice(2)}`} />
        </AppShell>,
      );
      await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
      for (const value of expected) expect(text(), `${id}: ${value}`).toContain(value);
      expect(text()).not.toContain('was alerted at 12 Nov 10:20 by');
      unmount();
    }
  });

  it('not_your_turn without a current step, and no reason at all, use their fallback copy', async () => {
    const turn = item('W-1206');
    const steps = turn.tasks[0].decision!.chain.steps;
    turn.tasks[0].decision!.chain.steps = steps.map((s) => (s.status === 'current' ? { ...s, status: 'not_yet' as const } : s));
    answers.item = () => json(200, turn);
    const first = render(
      <AppShell>
        <DecideView id="W-1206" taskId="T-1206" />
      </AppShell>,
    );
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    expect(text()).toContain('This needs earlier approvals first.');
    first.unmount();

    const plain = item('W-1203');
    delete plain.tasks[0].cannot_act_reason;
    delete plain.tasks[0].asked;
    answers.item = () => json(200, plain);
    await open('W-1203', 'T-1203');
    expect(text()).toContain('NOT YOUR DECISION');
    expect(text()).toContain('You can’t approve, return or reject it.');
    expect(text()).toContain('Nobody has been asked yet.');
  });

  it('eligibility comes from the task, never from /me', async () => {
    answers.item = () => json(200, item('W-1203'));
    const first = render(
      <AppShell>
        <DecideView id="W-1203" taskId="T-1203" />
      </AppShell>,
    );
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    expect(decisionControls()).toHaveLength(0);
    first.unmount();

    answers.me = 'pm';
    answers.item = () => json(200, item('W-1201'));
    await open();
    await ready();
    expect(button('Approve v2')).toBeTruthy();
    expect(counts().claims.at(-1)!.csrf).toBe('mock-csrf-pm');
  });
});

describe('errors', () => {
  it('decide 403 shows the generic read-only view after a reload, with no buttons', async () => {
    answers.item = () => json(200, item('W-1201'));
    answers.decide = () => json(403, FORBIDDEN);
    await open();
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('This decision needs a Finance Lead.');
    expect(text()).toContain('You can’t approve, return or reject it.');
    expect(decisionControls()).toHaveLength(0);
    expect(counts().gets).toBe(2);
    expect(counts().decides).toHaveLength(1);
  });

  it('a 403 on claim prefers the reloaded reason', async () => {
    answers.item = (n) => json(200, n === 0 ? item('W-1201') : item('W-1201.approve'));
    answers.claim = () => json(403, FORBIDDEN);
    await open();
    await screen.findByText('This decision has already been made.');
    expect(decisionControls()).toHaveLength(0);
  });

  it('decide 422 shows the server message, keeps the note and sends nothing more', async () => {
    answers.decide = () => json(422, { code: 'invalid', message: 'Check these fields: note.' });
    await open();
    await ready();
    const note = screen.getByLabelText(/^Note/) as HTMLTextAreaElement;
    fireEvent.change(note, { target: { value: 'Wrong PO' } });
    fireEvent.click(button('Reject'));
    const callout = await screen.findByText('Check these fields: note.');
    expect(callout.closest('.psl-callout')!.className).toContain('psl-callout--problem');
    expect(note.value).toBe('Wrong PO');
    expect(counts().decides).toHaveLength(1);
    expect((button('Reject') as HTMLButtonElement).disabled).toBe(false);
  });

  it('claim 422 shows the message and keeps the controls disabled', async () => {
    answers.claim = () => json(422, { code: 'invalid', message: 'Check these fields: expected_revision.' });
    await open();
    await screen.findByText('Check these fields: expected_revision.');
    expect((button('Approve v2') as HTMLButtonElement).disabled).toBe(true);
  });

  it('claim network error offers Try again, which claims again', async () => {
    answers.claim = (n, c) => (n === 0 ? Promise.reject(new TypeError('offline')) : json(200, { task_id: 'T-1201', revision: (c.body as { expected_revision: number }).expected_revision, claimed_by: 'Ada Okafor' }));
    await open();
    await screen.findByText('We couldn’t get this decision ready. Try again.');
    expect((button('Approve v2') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(button('Try again'));
    await ready();
    expect(counts().claims).toHaveLength(2);
  });

  it('decide network error is an uncertain effect: one reload, no resend, and the controls come back at the same revision', async () => {
    answers.decide = () => Promise.reject(new TypeError('offline'));
    await open();
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText(/We couldn’t confirm your decision\./);
    expect(text()).toContain('We’ve reloaded this item so you can see whether it was recorded.');
    await ready();
    expect(counts().gets).toBe(2);
    expect(counts().decides).toHaveLength(1);
    expect(counts().claims).toHaveLength(1);
  });

  it('decide 500 then a reload that shows it was recorded gives the already-decided view', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1201' : 'W-1201.approve'));
    answers.decide = () => json(500, { code: 'server_error', message: 'Down.' });
    await open();
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('This decision has already been made.');
    expect(text()).toContain('We couldn’t confirm your decision.');
    expect(decisionControls()).toHaveLength(0);
    expect(counts().decides).toHaveLength(1);
  });

  it('item 404 shows the no-access view without the id or title', async () => {
    answers.item = () => json(404, { code: 'not_found', message: 'We could not find that record.' });
    await open();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this work item');
    expect(text()).not.toContain('W-1201');
    expect(text()).not.toContain('Lagoon');
  });

  it('item 401 links to sign in with next set to this decision', async () => {
    answers.item = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    const href = screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')!;
    expect(new URL(href, 'http://x').searchParams.get('next')).toBe('/work/W-1201/decide?task=T-1201');
  });

  it('item 500 shows the error card; Try again re-fetches', async () => {
    answers.item = (n) => (n === 0 ? json(500, { code: 'server_error', message: 'Down.' }) : json(200, item('W-1201')));
    await open();
    const card = screen.getByRole('alert');
    expect(card.textContent).toContain('ERROR · COULDN’T LOAD');
    expect(card.textContent).toContain('We couldn’t load this decision. Your work is safe; nothing was changed.');
    expect(card.textContent).toContain('Reference server_error for support.');
    fireEvent.click(within(card).getByRole('button', { name: 'Try again' }));
    await ready();
    expect(counts().gets).toBe(2);
  });

  it.each([
    ['a missing task parameter', 'W-1201', null],
    ['an unknown task', 'W-1201', 'T-9999'],
    ['W-1001 / T-2001 without a decision', 'W-1001', 'T-2001'],
  ])('%s shows "This decision isn’t open here" with no controls', async (_, id, task) => {
    answers.item = () => json(200, item(id));
    await open(id, task);
    expect(screen.getByRole('heading', { name: 'This decision isn’t open here' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open the work item' }).getAttribute('href')).toBe(`/work/${id}`);
    expect(decisionControls()).toHaveLength(0);
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
  });
});

it('the decision fixture types line up with the contract', () => {
  const decision: TaskDecision = item('W-1201').tasks[0].decision!;
  expect(decision.chain.steps).toHaveLength(1);
});
