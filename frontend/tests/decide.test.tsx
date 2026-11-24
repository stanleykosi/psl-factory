// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { StrictMode } from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { LiveHistoryItem, LiveTask, LiveTaskRead, LiveWork } from '@/api/types';
import { DecideView } from '@/features/decide/DecideView';
import { formatAmount } from '@/features/decide/liveFormat';
import { AppShell } from '@/shell/AppShell';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/17/decide',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const me = JSON.parse(readFileSync(join(fixtures, 'me.finance_lead.json'), 'utf8')) as unknown;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const CONFLICT = { code: 'conflict', message: 'This changed while you were reading it.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const SERVER = { code: 'server_error', message: 'Down.' };

const task = (over: Partial<LiveTask> = {}): LiveTask => ({
  id: 41,
  kind: 'invoice_review',
  role: 'finance_reviewer',
  status: 'open',
  revision: 3,
  claimed_by_you: false,
  can_claim: true,
  can_decide: false,
  verdicts: ['approve', 'return', 'reject'],
  url: '/work/17/decide?task=41',
  ...over,
});

const readOf = (taskOver: Partial<LiveTask> = {}, over: Partial<LiveTaskRead> = {}): LiveTaskRead => ({
  task: task(taskOver),
  work_id: 17,
  label: 'Invoice 3 for the Lekki handover',
  invoice_packet: { invoice_id: 9, version: 2, sha256: 'a1b2c3d4'.repeat(8), amount: '4250000.00', currency: 'NGN', recipient: 'Lekki Estates Ltd', preparation_id: 5, basis: 'Milestone 3 certificate', prepared_by: 'Chidi', prepared_at: '2026-11-23T08:00:00Z', sources: [] },
  review_evidence: [
    { id: 88, version: 2, source: 'signed milestone certificate', sha256: 'b'.repeat(64) },
    { id: 91, version: 2, source: 'client email', sha256: 'c'.repeat(64) },
  ],
  decision_hold_code: null,
  review_stations_url: null,
  changes_from_previous: null,
  recipient_change: { earlier: null, current: 'Lekki Estates Ltd' },
  ...over,
});

const workOf = (tasks: LiveTask[] = [task()], over: Partial<LiveWork> = {}): LiveWork => ({
  id: 17,
  case_id: '00000000-0000-4000-8000-000000000017',
  title: 'Lekki handover invoice',
  line: 'finance-ledger/v1',
  state: 'action_needed',
  status_label: 'Needs your decision',
  owner: null,
  sample: false,
  updated_at: '2026-11-23T09:00:00Z',
  django_url: '/work/17/',
  api_url: '/api/v1/work/17',
  revision: 1,
  case_revision: 1,
  next_step: 'A reviewer decides.',
  blocker: '',
  tasks,
  screens: [],
  actions: [],
  progress: null,
  aggregate: null,
  panels: [],
  output_url: null,
  information: [],
  available_control: [],
  reference: null,
  started_at: '2026-11-23T08:00:00Z',
  verified_at: null,
  queue_output_url: null,
  exception_code: null,
  exception_next_step: null,
  exception_started_at: null,
  action_kind: null,
  station: null,
  agent: null,
  tracking_url: null,
  proofs_url: null,
  ...over,
});

type Call = { method: string; path: string; query: string; body: unknown; csrf: string | null };
type Answer = (n: number, call: Call) => Response | Promise<Response>;
let calls: Call[];
let answers: { work: Answer; task: Answer; claim: Answer; decide: Answer; comment: Answer; history: Answer; queue: Answer };

const only = (suffix: string) => calls.filter((c) => c.method === 'POST' && c.path.endsWith(suffix));
const counts = () => ({
  taskReads: calls.filter((c) => c.method === 'GET' && c.path === '/api/v1/tasks/41').length,
  workReads: calls.filter((c) => c.method === 'GET' && c.path === '/api/v1/work/17').length,
  claims: only('/claim'),
  decides: only('/decision'),
  comments: only('/comments'),
  gets: calls.filter((c) => c.method === 'GET' && c.path !== '/api/v1/me').length,
});

const claimed = () => readOf({ claimed_by_you: true, can_claim: false, can_decide: true });

beforeEach(() => {
  calls = [];
  answers = {
    work: () => json(200, workOf()),
    task: () => json(200, readOf()),
    claim: (_, c) => json(200, { task_id: 41, revision: (c.body as { expected_revision: number }).expected_revision, claimed_by: 'Ada Okafor' }),
    decide: () => json(200, { task_id: 41, review_id: 12, verdict: 'approve', work_state: 'waiting' }),
    comment: () => json(200, { comment_id: 5 }),
    history: () => json(200, { items: [], as_of: '2026-11-23T09:31:00Z' }),
    queue: () => json(200, { items: [], page: 1, next_page: null, as_of: '2026-11-23T09:31:00Z', limited: false, lines: [], evaluated: 0, deferred: [], payroll_questions: [] }),
  };
  const n = { work: 0, task: 0, claim: 0, decide: 0, comment: 0, history: 0, queue: 0 };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const c: Call = { method: request.method, path: url.pathname, query: url.search, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') };
      calls.push(c);
      if (url.pathname === '/api/v1/me') return json(200, me);
      if (url.pathname === '/api/v1/work') return answers.queue(n.queue++, c);
      if (url.pathname.endsWith('/history')) return answers.history(n.history++, c);
      if (url.pathname.endsWith('/claim')) return answers.claim(n.claim++, c);
      if (url.pathname.endsWith('/decision')) return answers.decide(n.decide++, c);
      if (url.pathname.endsWith('/comments')) return answers.comment(n.comment++, c);
      if (url.pathname.startsWith('/api/v1/tasks/')) return answers.task(n.task++, c);
      return answers.work(n.work++, c);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});

async function open(id = '17', taskId: string | null = '41', strict = false) {
  const tree = (
    <AppShell>
      <DecideView id={id} taskId={taskId ?? undefined} />
    </AppShell>
  );
  render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const text = () => document.body.textContent ?? '';
const choose = (name: RegExp | string) => fireEvent.click(screen.getByRole('radio', { name }));
const decisionControls = () => screen.queryAllByRole('button', { name: /approve|return|reject/i });
/** Opened as a person who can claim: the claim has gone out and the board is ready for the evidence choice. */
async function openReady() {
  await open();
  await waitFor(() => expect(screen.queryByText('Getting this decision ready…')).toBeNull());
}

describe('opening the decision (criterion 1)', () => {
  it('reads the task, claims once with the task revision (also under StrictMode) and shows label, version, amount and recipient', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const original = answers.claim;
    answers.claim = async (n, c) => {
      await gate;
      return original(n, c);
    };
    await open('17', '41', true);
    await waitFor(() => expect(counts().claims).toHaveLength(1));
    expect(screen.getByText('Getting this decision ready…')).toBeTruthy();
    for (const name of [/^Approve v2/, 'Return', 'Reject']) expect(button(name).disabled).toBe(true);
    await act(async () => release());
    await waitFor(() => expect(screen.queryByText('Getting this decision ready…')).toBeNull());
    expect(counts().claims).toEqual([{ method: 'POST', path: '/api/v1/tasks/41/claim', query: '', body: { expected_revision: 3 }, csrf: 'mock-csrf-finance_lead' }]);
    expect(counts().taskReads).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Invoice 3 for the Lekki handover');
    for (const value of ['Version 2', '₦4,250,000.00', 'Lekki Estates Ltd', 'Only a finance reviewer can decide.']) expect(text(), value).toContain(value);
    // no person is inferred: the board never says who "you are"
    expect(text()).not.toMatch(/You are/);
  });

  it('a task that is already claimed by the person sends no claim', async () => {
    answers.task = () => json(200, claimed());
    await open();
    expect(counts().claims).toHaveLength(0);
    expect(screen.queryByText('Getting this decision ready…')).toBeNull();
  });

  it('shows the checksum short and secondary, and a recipient change as a visible line', async () => {
    answers.task = () => json(200, readOf({}, { recipient_change: { earlier: 'Old Estates Ltd', current: 'Lekki Estates Ltd' } }));
    await openReady();
    expect(screen.getByText(/checksum a1b2c3d4$/, { selector: '.decide-tech' })).toBeTruthy();
    expect(text()).not.toContain('a1b2c3d4a1b2c3d4');
    expect(screen.getByText(/Recipient changed\. It was Old Estates Ltd\./)).toBeTruthy();
  });

  it('shows no recipient-changed line when the earlier recipient is absent or the same', async () => {
    answers.task = () => json(200, readOf({}, { recipient_change: { earlier: 'Lekki Estates Ltd', current: 'Lekki Estates Ltd' } }));
    await openReady();
    expect(text()).not.toContain('Recipient changed');
  });
});

describe('evidence and the decision body (criteria 2 and 3)', () => {
  it('pre-selects nothing; the three buttons stay off with a visible reason until one item is chosen', async () => {
    await openReady();
    const radios = screen.getAllByRole('radio') as HTMLInputElement[];
    expect(radios.map((r) => r.checked)).toEqual([false, false]);
    for (const name of [/^Approve v2/, 'Return', 'Reject']) {
      expect(button(name).disabled).toBe(true);
      const reason = screen.getByText('Choose the evidence you are relying on to turn on these buttons.');
      expect(button(name).getAttribute('aria-describedby')).toBe(reason.id);
    }
    choose(/client email/);
    for (const name of [/^Approve v2/, 'Return', 'Reject']) expect(button(name).disabled).toBe(false);
    expect(screen.queryByText('Choose the evidence you are relying on to turn on these buttons.')).toBeNull();
  });

  it('Approve sends exactly expected_revision, verdict, the chosen evidence_id and a note key, even when the note is empty', async () => {
    await openReady();
    choose(/signed milestone certificate/);
    fireEvent.click(button('Approve v2'));
    await screen.findByText(/Decision recorded on|is approved/);
    expect(counts().decides).toEqual([
      { method: 'POST', path: '/api/v1/tasks/41/decision', query: '', body: { expected_revision: 3, verdict: 'approve', evidence_id: 88, note: '' }, csrf: 'mock-csrf-finance_lead' },
    ]);
    expect(Object.keys(counts().decides[0].body as object).sort()).toEqual(['evidence_id', 'expected_revision', 'note', 'verdict']);
  });

  it('the decision uses the revision the claim returned', async () => {
    answers.claim = () => json(200, { task_id: 41, revision: 4, claimed_by: 'Ada Okafor' });
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    await screen.findByText(/Decision recorded on|is approved/);
    expect((counts().decides[0].body as { expected_revision: number }).expected_revision).toBe(4);
  });

  it('Return or Reject without a note sends nothing and asks for one; a note is sent as typed with the evidence', async () => {
    await openReady();
    choose(/client email/);
    const note = screen.getByLabelText(/^Note/) as HTMLTextAreaElement;
    for (const name of ['Return', 'Reject']) {
      for (const value of ['', '   \n ']) {
        fireEvent.change(note, { target: { value } });
        fireEvent.click(button(name));
        const error = screen.getByText('Add a note to return or reject.');
        expect(note.getAttribute('aria-invalid')).toBe('true');
        expect(note.getAttribute('aria-describedby')).toContain(error.id);
      }
    }
    expect(counts().decides).toHaveLength(0);
    answers.decide = () => json(200, { task_id: 41, review_id: 13, verdict: 'return', work_state: 'action_needed' });
    fireEvent.change(note, { target: { value: 'Wrong PO' } });
    fireEvent.click(button('Return'));
    await screen.findByText(/Decision recorded on|was returned/);
    expect(counts().decides.map((c) => c.body)).toEqual([{ expected_revision: 3, verdict: 'return', evidence_id: 91, note: 'Wrong PO' }]);
  });

  it('a note over 2000 characters is refused before any request', async () => {
    await openReady();
    choose(/client email/);
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: 'x'.repeat(2001) } });
    fireEvent.click(button('Approve v2'));
    expect(screen.getByText('Keep the note to 2000 characters or fewer.')).toBeTruthy();
    expect(counts().decides).toHaveLength(0);
  });

  it('with no review evidence the buttons stay off and a sentence says why', async () => {
    answers.task = () => json(200, readOf({}, { review_evidence: [] }));
    await openReady();
    expect(screen.queryAllByRole('radio')).toHaveLength(0);
    expect(screen.getByText('There is no evidence to cite yet, so this can’t be decided.')).toBeTruthy();
    for (const name of [/^Approve v2/, 'Return', 'Reject']) expect(button(name).disabled).toBe(true);
  });

  it('a double click sends one decision; the other buttons wait while it is pending', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const original = answers.decide;
    answers.decide = async (n, c) => {
      await gate;
      return original(n, c);
    };
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    fireEvent.click(button('Approving…'));
    await waitFor(() => expect(counts().decides).toHaveLength(1));
    for (const name of ['Return', 'Reject']) expect(button(name).disabled).toBe(true);
    await act(async () => release());
    await screen.findByText(/Decision recorded on|is approved/);
    expect(counts().decides).toHaveLength(1);
  });
});

describe('the done board (criterion 4, checklist 2)', () => {
  const historyItem: LiveHistoryItem = { at: '2026-11-23T09:47:00Z', station: 'Finance review', status: 'approve', task_id: 41, actor: 'Chinedu Eze', reason: 'Matches the certificate', evidence_id: 88, actor_kind: 'person', entry_id: 7 };

  async function approve(note = '') {
    await openReady();
    choose(/signed milestone certificate/);
    if (note) fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: note } });
    fireEvent.click(button('Approve v2'));
  }

  it('shows the verdict, label, note and the work state, and "decided by" from the matching history item', async () => {
    answers.history = () => json(200, { items: [{ ...historyItem, task_id: 99, actor: 'Someone Else' }, historyItem], as_of: '2026-11-23T09:48:00Z' });
    answers.work = (n) => json(200, workOf([task()], { state: n === 0 ? 'action_needed' : 'waiting' }));
    await approve('Matches the certificate');
    await screen.findByText('Invoice 3 for the Lekki handover is approved');
    expect(screen.getByText('Approve, with the note “Matches the certificate”')).toBeTruthy();
    expect(screen.getByText('Waiting on others')).toBeTruthy();
    expect(screen.getByText(/by Chinedu Eze$/)).toBeTruthy();
    expect(text()).not.toContain('Someone Else');
    expect(screen.getByText(/^YOU APPROVED ·/).closest('.decide-banner')!.className).toBe('decide-banner decide-banner--success');
    expect(screen.getByText('Paid is tracked separately by Finance and is not part of this decision.')).toBeTruthy();
    expect(decisionControls()).toHaveLength(0);
    expect(calls.some((c) => c.path === '/api/v1/work/17/history' && c.query === '?kind=decision')).toBe(true);
  });

  it('draws no "decided by" line when the history has no item for this task', async () => {
    answers.history = () => json(200, { items: [{ ...historyItem, task_id: 99 }], as_of: '2026-11-23T09:48:00Z' });
    await approve();
    await screen.findByText('Invoice 3 for the Lekki handover is approved');
    expect(screen.queryByText('Decided')).toBeNull();
    expect(text()).not.toContain('Chinedu Eze');
    expect(screen.getByText('Approve, with no note')).toBeTruthy();
  });

  it('never says approved straight after the 200: until the re-read confirms, the board says recorded', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const original = answers.work;
    answers.work = async (n, c) => {
      if (n > 0) await gate;
      return original(n, c);
    };
    await approve();
    await screen.findByText('Decision recorded on Invoice 3 for the Lekki handover');
    expect(text()).not.toMatch(/is approved|YOU APPROVED/);
    expect(document.querySelector('.decide-banner--success')).toBeNull();
    await act(async () => release());
    await screen.findByText('Invoice 3 for the Lekki handover is approved');
  });

  it('a failed re-read keeps what was recorded and says it could not refresh', async () => {
    answers.work = (n) => (n === 0 ? json(200, workOf()) : json(500, SERVER));
    await approve('ok');
    await screen.findByText('We couldn’t refresh this item. Open the work item to see the latest.');
    expect(screen.getByText('Decision recorded on Invoice 3 for the Lekki handover')).toBeTruthy();
    expect(screen.getByText('Approve, with the note “ok”')).toBeTruthy();
  });

  it('a work_state of effect_uncertain shows the uncertain notice, no approved banner and no Paid line', async () => {
    answers.decide = () => json(200, { task_id: 41, review_id: 12, verdict: 'approve', work_state: 'effect_uncertain' });
    await approve();
    await screen.findByText(/We couldn’t confirm your decision\./);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Invoice 3 for the Lekki handover: result not confirmed');
    expect(document.querySelector('.decide-banner--success')).toBeNull();
    expect(text()).not.toMatch(/is approved|YOU APPROVED|Paid is tracked/);
    expect(screen.getByText('Approve, result not confirmed')).toBeTruthy();
  });

  it('an echoed verdict other than the three is never called approved', async () => {
    answers.decide = () => json(200, { task_id: 41, review_id: 12, verdict: 'constructor', work_state: 'waiting' });
    await approve();
    await screen.findByText('Decision recorded on Invoice 3 for the Lekki handover');
    await waitFor(() => expect(counts().workReads).toBeGreaterThan(1));
    expect(text()).not.toMatch(/YOU APPROVED|is approved|Paid is tracked separately/);
  });
});

describe('stale (criterion 5, checklist 1)', () => {
  const redrafted = () => readOf({ revision: 4 }, { invoice_packet: { ...readOf().invoice_packet!, version: 3, amount: '4300000.00' } });

  it('a 409 on the decision reloads, shows the replaced version beside the current one, keeps the unsent note and never resends', async () => {
    answers.decide = () => json(409, CONFLICT);
    answers.task = (n) => json(200, n === 0 ? readOf() : redrafted());
    await openReady();
    choose(/client email/);
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: 'Looks right' } });
    fireEvent.click(button('Approve v2'));
    await screen.findByText('A newer version arrived while you were reading.');
    expect(text()).toContain('Version 2 can no longer be approved.');
    expect(text()).toContain('VERSION 2 · REPLACED');
    expect(text()).toContain('VERSION 3 · CURRENT');
    expect(text()).toContain('₦4,250,000.00');
    expect(text()).toContain('₦4,300,000.00');
    expect(text()).toContain('· changed');
    expect(screen.getByText('Your note wasn’t sent: “Looks right”')).toBeTruthy();
    expect(decisionControls()).toHaveLength(0);
    expect(button('Review version 3')).toBeTruthy();
    expect(counts().decides).toHaveLength(1);
  });

  it('desktop: the compare is a real table with the board column headers and the changed row marked (UI-1-1)', async () => {
    answers.decide = () => json(409, CONFLICT);
    answers.task = (n) => json(200, n === 0 ? readOf() : readOf({ revision: 4 }, { invoice_packet: { ...readOf().invoice_packet!, version: 3 }, recipient_change: { earlier: null, current: 'Other Estates Ltd' } }));
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    await screen.findByRole('table');
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Field', 'VERSION 2 · REPLACED', 'VERSION 3 · CURRENT']);
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.map((r) => r.textContent)).toEqual(['Amount₦4,250,000.00₦4,250,000.00 · unchanged', 'Send toLekki Estates LtdOther Estates Ltd · changed']);
    expect(rows[1].className).toContain('decide-table__changed');
    expect(rows[0].className).not.toContain('decide-table__changed');
  });

  it('"Review version 3" shows the current board and claims the new revision once', async () => {
    answers.decide = () => json(409, CONFLICT);
    answers.task = (n) => json(200, n === 0 ? readOf() : redrafted());
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    await screen.findByText('A newer version arrived while you were reading.');
    fireEvent.click(button('Review version 3'));
    await waitFor(() => expect(counts().claims).toHaveLength(2));
    expect(counts().claims[1].body).toEqual({ expected_revision: 4 });
    await waitFor(() => expect(button(/^Approve v3/)).toBeTruthy());
    expect(counts().decides).toHaveLength(1);
  });

  it('two reviewers: when the other one closed the task, the stale board carries no decide buttons and Review lands on read-only', async () => {
    answers.decide = () => json(409, CONFLICT);
    answers.task = (n) => json(200, n === 0 ? readOf() : readOf({ status: 'closed', revision: 4, can_claim: false, can_decide: false, claimed_by_you: false, verdicts: [] }));
    await openReady();
    choose(/client email/);
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: 'Fine by me' } });
    fireEvent.click(button('Approve v2'));
    await screen.findByText('A newer version arrived while you were reading.');
    expect(screen.getByText('Your note wasn’t sent: “Fine by me”')).toBeTruthy();
    expect(decisionControls()).toHaveLength(0);
    fireEvent.click(button('Review version 2'));
    await screen.findByText('NOT YOUR DECISION');
    expect(decisionControls()).toHaveLength(0);
    expect(counts().claims).toHaveLength(1);
    expect(counts().decides).toHaveLength(1);
  });

  it('a 409 on the claim reloads and shows the stale board', async () => {
    answers.claim = () => json(409, CONFLICT);
    answers.task = (n) => json(200, n === 0 ? readOf() : redrafted());
    await open();
    await screen.findByText('A newer version arrived while you were reading.');
    expect(counts().claims).toHaveLength(1);
    expect(counts().decides).toHaveLength(0);
  });
});

describe('phone stale and not-yours (UI-1-2, UI-1-3)', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  });

  it('stale: one grey replaced line, then one current card with the To row and its changed tag', async () => {
    answers.decide = () => json(409, CONFLICT);
    answers.task = (n) => json(200, n === 0 ? readOf() : readOf({ revision: 4 }, { invoice_packet: { ...readOf().invoice_packet!, version: 3 }, recipient_change: { earlier: null, current: 'Other Estates Ltd' } }));
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    const old = await screen.findByRole('region', { name: 'Version 2, no longer current' });
    expect(old.textContent).toBe('Invoice v2 · ₦4,250,000.00REPLACED');
    expect(screen.queryByRole('table')).toBeNull();
    const now = screen.getByRole('region', { name: 'What changed in version 3' });
    expect(now.textContent).toBe('Amount₦4,250,000.00 unchangedToOther Estates Ltd changed');
  });

  it('not-yours: the Waiting cell spans the rest of the strip so no empty cell is left', async () => {
    answers.task = () => json(200, readOf({ can_claim: false, can_decide: false }));
    await open();
    expect(document.querySelectorAll('.decide-strip__box')).toHaveLength(2);
    expect(document.querySelector('.decide-strip__box--waiting')).toBeTruthy();
    const css = readFileSync(join(__dirname, '../src/features/decide/decide.css'), 'utf8');
    expect(css).toMatch(/\.decide-strip__box--waiting \{ grid-column: span 2; \}/);
  });
});

describe('the done board panel (UI-1-4)', () => {
  it('"What happens next" is a complementary landmark', async () => {
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    await screen.findByText(/Decision recorded on|is approved/);
    expect(screen.getByRole('complementary', { name: 'WHAT HAPPENS NEXT' })).toBeTruthy();
  });
});

describe('the title is drawn once (UI-1-5)', () => {
  it('no sub-line when the work title equals the task label; the work title shows when it differs', async () => {
    answers.task = () => json(200, claimed());
    answers.work = () => json(200, workOf([task()], { title: 'Invoice 3 for the Lekki handover' }));
    await open();
    expect(screen.getAllByText('Invoice 3 for the Lekki handover').filter((el) => !el.closest('.cmp-sr') && el.tagName !== 'H1')).toHaveLength(0);
  });
});

describe('uncertain effects (criterion 6)', () => {
  for (const [name, reply] of [
    ['a network failure', () => Promise.reject(new TypeError('network'))],
    ['a 5xx', () => json(500, SERVER)],
  ] as const) {
    it(`${name} on the decision reloads once, never resends, and shows the uncertain notice`, async () => {
      answers.decide = reply as Answer;
      await openReady();
      choose(/client email/);
      const before = counts();
      fireEvent.click(button('Approve v2'));
      await screen.findByText(/We couldn’t confirm your decision\./);
      expect(counts().decides).toHaveLength(1);
      expect(counts().workReads).toBe(before.workReads + 1);
      expect(counts().taskReads).toBe(before.taskReads + 1);
    });
  }

  it('when the reload fails too, the buttons stay off and Try again only issues GETs', async () => {
    answers.decide = () => json(500, SERVER);
    await openReady();
    choose(/client email/);
    answers.work = () => json(500, SERVER);
    fireEvent.click(button('Approve v2'));
    await screen.findByText(/We couldn’t confirm whether your decision was recorded\./);
    for (const name of [/^Approve v2/, 'Return', 'Reject']) expect(button(name).disabled).toBe(true);
    const posts = calls.filter((c) => c.method === 'POST').length;
    fireEvent.click(button('Try again'));
    await waitFor(() => expect(button('Try again')).toBeTruthy());
    expect(calls.filter((c) => c.method === 'POST').length).toBe(posts);
  });
});

describe('who can act (criterion 7)', () => {
  it('can_decide false and can_claim false is read-only: no claim, no decision controls, the generic sentence and no specific reason', async () => {
    answers.task = () => json(200, readOf({ can_claim: false, can_decide: false }));
    await open();
    expect(screen.getByText('NOT YOUR DECISION')).toBeTruthy();
    expect(screen.getByText('This decision needs a finance reviewer.')).toBeTruthy();
    expect(screen.getByText('You can’t approve, return or reject it.')).toBeTruthy();
    expect(text()).not.toMatch(/prepared by you|not your turn|You hold|was alerted|Basis/i);
    expect(decisionControls()).toHaveLength(0);
    expect(screen.queryAllByRole('radio')).toHaveLength(0);
    expect(counts().claims).toHaveLength(0);
    expect(text()).toContain('₦4,250,000.00');
  });

  it('a 404 on the work read shows the no-access state', async () => {
    answers.work = () => json(404, { code: 'not_found', message: 'We could not find that record.' });
    await open();
    expect(text()).toMatch(/can.t open this|don.t have access|no access|isn.t available|couldn.t find/i);
    expect(decisionControls()).toHaveLength(0);
  });

  it('a 404 on the task read shows the no-access state', async () => {
    answers.task = () => json(404, { code: 'not_found', message: 'We could not find that record.' });
    await open();
    expect(decisionControls()).toHaveLength(0);
    expect(counts().claims).toHaveLength(0);
  });

  it('a 401 shows the signed-out state', async () => {
    answers.work = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    expect(screen.getByText(/You’re signed out\./)).toBeTruthy();
  });

  it('a 403 on the decision reloads and turns the page read-only', async () => {
    answers.decide = () => json(403, FORBIDDEN);
    answers.task = (n) => json(200, n === 0 ? readOf() : readOf({ can_claim: false, can_decide: false, claimed_by_you: false }));
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    await screen.findByText('NOT YOUR DECISION');
    expect(decisionControls()).toHaveLength(0);
    expect(counts().decides).toHaveLength(1);
  });

  it('a failed claim shows a retry that claims again', async () => {
    answers.claim = (n) => (n === 0 ? json(500, SERVER) : json(200, { task_id: 41, revision: 3, claimed_by: 'Ada Okafor' }));
    await open();
    await screen.findByText(/We couldn’t get this decision ready\./);
    fireEvent.click(button('Try again'));
    await waitFor(() => expect(counts().claims).toHaveLength(2));
    await waitFor(() => expect(screen.queryByText(/We couldn’t get this decision ready\./)).toBeNull());
  });

  it('a work with no ?task, a task that is not on it, or a non-numeric id shows the not-open state; non-numeric ids send nothing', async () => {
    await open('17', null);
    expect(screen.getByText('This decision isn’t open here')).toBeTruthy();
    expect(counts().taskReads).toBe(0);
  });

  it('the work lists other tasks only: not open, and no task read', async () => {
    answers.work = () => json(200, workOf([task({ id: 50 })]));
    await open();
    expect(screen.getByText('This decision isn’t open here')).toBeTruthy();
    expect(counts().taskReads).toBe(0);
    expect(counts().claims).toHaveLength(0);
  });

  for (const [id, taskId] of [['W-1201', '41'], ['17', 'T-1201'], ['17x', '41'], ['-1', '41'], ['17', '1.5'], ['17', '0']] as const) {
    it(`route ids ${id} / ${taskId} are not integers: not open, no request`, async () => {
      await open(id, taskId);
      expect(screen.getByText('This decision isn’t open here')).toBeTruthy();
      expect(calls.filter((c) => c.path !== '/api/v1/me')).toHaveLength(0);
    });
  }
});

describe('invalid input (criterion 8)', () => {
  it('a 422 shows the server message and field messages, keeps the board, the chosen evidence and the note', async () => {
    answers.decide = () => json(422, { code: 'invalid_input', message: 'Check the details and try again.', fields: [{ name: 'note', message: 'The note is too short for a return.' }, { name: 'evidence_id', message: 'That evidence is not on this review.' }] });
    await openReady();
    choose(/client email/);
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: 'ok' } });
    fireEvent.click(button('Approve v2'));
    await screen.findByText('Check the details and try again.');
    expect(screen.getByText('The note is too short for a return.')).toBeTruthy();
    expect(screen.getByText('That evidence is not on this review.')).toBeTruthy();
    expect((screen.getByRole('radio', { name: /client email/ }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText(/^Note/) as HTMLTextAreaElement).value).toBe('ok');
    expect(button('Approve v2').disabled).toBe(false);
    expect(counts().decides).toHaveLength(1);
  });

  it('a 400 is treated like a 422: the board stays', async () => {
    answers.decide = () => json(400, { code: 'bad_request', message: 'Bad.' });
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    await screen.findByText(/We could not read that request/);
    expect(button('Approve v2').disabled).toBe(false);
  });
});

describe('unknown amount (criterion 9)', () => {
  it('formatAmount reads the decimal string, never a float, and unknown is null', () => {
    expect(formatAmount({ amount: '4250000.00', currency: 'NGN' })).toBe('₦4,250,000.00');
    expect(formatAmount({ amount: '1200.50', currency: 'USD' })).toBe('USD 1,200.50');
    expect(formatAmount({ amount: '999.99', currency: 'NGN' })).toBe('₦999.99');
    expect(formatAmount({ amount: '-12345678901234567.10', currency: 'NGN' })).toBe('-₦12,345,678,901,234,567.10');
    expect(formatAmount(null)).toBeNull();
    expect(formatAmount(undefined)).toBeNull();
    expect(formatAmount({ amount: '', currency: 'NGN' })).toBeNull();
    expect(formatAmount({ amount: '4250000', currency: 'NGN' })).toBeNull();
    expect(formatAmount({ amount: 'abc', currency: 'NGN' })).toBeNull();
  });

  for (const [name, packet] of [
    ['a null packet', null],
    ['an empty amount', { ...readOf().invoice_packet!, amount: '' }],
  ] as const) {
    it(`${name} shows Unknown, never 0`, async () => {
      answers.task = () => json(200, readOf({}, { invoice_packet: packet }));
      await openReady();
      const row = screen.getByText('Amount').parentElement!;
      expect(row.querySelector('dd')!.textContent).toBe('Unknown');
      expect(row.querySelector('.psl-unknown')).toBeTruthy();
      expect(text()).not.toMatch(/0\.00|₦0/);
    });
  }
});

describe('verdicts and revoke (criterion 10)', () => {
  it('draws only the verdicts the task lists', async () => {
    answers.task = () => json(200, readOf({ verdicts: ['approve', 'return'] }));
    await openReady();
    expect(button('Approve v2')).toBeTruthy();
    expect(button('Return')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Reject' })).toBeNull();
    answers.task = () => json(200, readOf({ verdicts: ['reject'] }));
  });

  it('a task that lists only reject draws no approve line', async () => {
    answers.task = () => json(200, readOf({ verdicts: ['reject'] }));
    await openReady();
    expect(screen.queryByRole('button', { name: /^Approve/ })).toBeNull();
    expect(screen.queryByText(/Approving earns/)).toBeNull();
    expect(button('Reject')).toBeTruthy();
  });

  it('no revoke path exists in the decide feature or in InlineDecide', () => {
    const files = ['decide/DecideView.tsx', 'decide/DecidePanel.tsx', 'decide/LiveStates.tsx', 'decide/LiveContent.tsx', 'decide/useLiveDecision.ts', 'decide/liveFormat.ts', 'workspace/InlineDecide.tsx'];
    for (const file of files) expect(readFileSync(join(__dirname, '../src/features', file), 'utf8').toLowerCase(), file).not.toContain('revoke');
    for (const file of files.filter((f) => f.startsWith('decide/'))) expect(readFileSync(join(__dirname, '../src/features', file), 'utf8'), file).not.toMatch(/\bapi\.(GET|POST)/);
  });
});

describe('the pager (criterion 11)', () => {
  const listed = (ids: number[]) => ({ items: ids.map((id) => ({ id, case_id: `00000000-0000-4000-8000-0000000000${id}`, title: `Work ${id}`, line: 'finance-ledger/v1', state: 'action_needed', status_label: 'Needs you', owner: null, sample: false, updated_at: '2026-11-23T09:00:00Z', django_url: `/work/${id}/`, api_url: `/api/v1/work/${id}` })), page: 1, next_page: null, as_of: '2026-11-23T09:00:00Z', limited: false, lines: [], evaluated: ids.length, deferred: [], payroll_questions: [] });

  it('draws "2 of 3" only when the live list holds this work', async () => {
    answers.queue = () => json(200, listed([12, 17, 20]));
    await openReady();
    await waitFor(() => expect(text()).toContain('2 of 3'));
    expect(calls.some((c) => c.path === '/api/v1/work' && c.query === '?queue=decisions')).toBe(true);
  });

  it('draws no pager when the list does not hold this work', async () => {
    answers.queue = () => json(200, listed([12, 20]));
    await openReady();
    await waitFor(() => expect(calls.some((c) => c.path === '/api/v1/work')).toBe(true));
    expect(text()).not.toMatch(/\d of \d/);
  });

  it('with the list failing the rest of the page still works and no count is drawn', async () => {
    answers.queue = () => json(500, SERVER);
    await openReady();
    await waitFor(() => expect(calls.some((c) => c.path === '/api/v1/work')).toBe(true));
    choose(/client email/);
    expect(button('Approve v2').disabled).toBe(false);
    expect(text()).not.toMatch(/\d of \d/);
  });

  it('the done board lists the other waiting decisions from the live list and links to the next one', async () => {
    answers.queue = () => json(200, listed([17, 20, 21]));
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    await screen.findByText('STILL WAITING ON YOU · 2');
    expect(screen.getByRole('link', { name: 'Next decision · 1 of 2' }).getAttribute('href')).toBe('/work/20');
    expect(screen.getByRole('link', { name: 'Work 21' }).getAttribute('href')).toBe('/work/21');
  });

  it('the done board hides the list and the next link when the list read fails', async () => {
    answers.queue = () => json(500, SERVER);
    await openReady();
    choose(/client email/);
    fireEvent.click(button('Approve v2'));
    await screen.findByText(/Decision recorded on|is approved/);
    expect(screen.queryByText(/STILL WAITING|ALL CAUGHT UP/)).toBeNull();
    expect(screen.queryByRole('link', { name: /Next decision/ })).toBeNull();
  });
});

describe('comment on the not-yours board (criterion 12)', () => {
  beforeEach(() => {
    answers.task = () => json(200, readOf({ can_claim: false, can_decide: false }));
  });
  const box = () => screen.getByLabelText(/^Comment for the finance reviewer/) as HTMLTextAreaElement;

  it('sends {revision, body}, requires a body and clears the box once sent', async () => {
    await open();
    fireEvent.click(button('Add comment'));
    expect(screen.getByText('Write a comment first.')).toBeTruthy();
    expect(counts().comments).toHaveLength(0);
    fireEvent.change(box(), { target: { value: 'Please check the PO number.' } });
    fireEvent.click(button('Add comment'));
    await screen.findByText('Your comment was added.');
    expect(counts().comments).toEqual([{ method: 'POST', path: '/api/v1/tasks/41/comments', query: '', body: { revision: 3, body: 'Please check the PO number.' }, csrf: 'mock-csrf-finance_lead' }]);
    expect(box().value).toBe('');
  });

  it('does not send twice for one tap', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    answers.comment = async () => {
      await gate;
      return json(200, { comment_id: 5 });
    };
    await open();
    fireEvent.change(box(), { target: { value: 'One note' } });
    fireEvent.click(button('Add comment'));
    fireEvent.click(screen.getByRole('button', { name: /Adding…/ }));
    await act(async () => release());
    await screen.findByText('Your comment was added.');
    expect(counts().comments).toHaveLength(1);
  });

  it('a 403 shows the server message and takes the box away', async () => {
    answers.comment = () => json(403, FORBIDDEN);
    await open();
    fireEvent.change(box(), { target: { value: 'Hello' } });
    fireEvent.click(button('Add comment'));
    await screen.findByText('Your role does not allow this.');
    expect(screen.queryByRole('button', { name: 'Add comment' })).toBeNull();
  });

  it('a 422 shows the server message and keeps the text', async () => {
    answers.comment = () => json(422, { code: 'invalid_input', message: 'Check the details and try again.', fields: [{ name: 'body', message: 'Too long.' }] });
    await open();
    fireEvent.change(box(), { target: { value: 'Hello' } });
    fireEvent.click(button('Add comment'));
    await screen.findByText('Check the details and try again. Too long.');
    expect(box().value).toBe('Hello');
  });

  it('a 409 shows the server message and reloads the task without resending', async () => {
    answers.comment = () => json(409, CONFLICT);
    await open();
    fireEvent.change(box(), { target: { value: 'Hello' } });
    const before = counts().taskReads;
    fireEvent.click(button('Add comment'));
    await screen.findByText('This changed while you were reading it.');
    await waitFor(() => expect(counts().taskReads).toBe(before + 1));
    expect(counts().comments).toHaveLength(1);
  });

  it('an uncertain failure reloads once and says to check before sending again', async () => {
    answers.comment = () => json(500, SERVER);
    await open();
    fireEvent.change(box(), { target: { value: 'Hello' } });
    const before = counts().taskReads;
    fireEvent.click(button('Add comment'));
    await screen.findByText(/Check whether it was added before you send it again\./);
    await waitFor(() => expect(counts().taskReads).toBe(before + 1));
    expect(counts().comments).toHaveLength(1);
  });

  it('the deciding board has no comment box', async () => {
    answers.task = () => json(200, claimed());
    await open();
    expect(screen.queryByRole('button', { name: 'Add comment' })).toBeNull();
  });
});
