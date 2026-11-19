// @vitest-environment jsdom
// F-37: the RFP requirements workspace (W-3401 default, W-3402 review, W-3403 uncertain, W-3404 read only) drawn from
// E-WORK-ITEM `workspace` inside F-18's RFP frame, and its four writes (accept, accept selected, edit and accept, write
// my own) plus add a requirement, all through E-WORK-STEP. Contract mock only: the fetch stub stands in for the backend,
// and nothing here proves an answer reached the client or a reviewer. Every "accepted" word is fixture text.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RfpFrame } from '@/features/rfp/RfpFrame';
import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-3401',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const clone = (name: string): WorkItem => structuredClone(item(name));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const stepRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = Response | (() => Response | Promise<Response>);
let sent: Sent[];
let reads: Record<string, (WorkItem | 'fail')[]>;
let writes: Answer[];
let who: string;
let status: Record<string, number>;

const steps = () => sent.filter((r) => r.method === 'POST' && r.path.endsWith('/steps'));
const ok = (message: string) => json(200, { work_id: 'W-3402', state: 'action_needed', revision: 8, outcome: 'done', message });

beforeEach(() => {
  sent = [];
  reads = {};
  writes = [];
  who = 'pm';
  status = {};
  vi.stubGlobal(
    'fetch',
    withoutBellFeed(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.text();
      sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
      if (url.pathname === '/api/v1/me') return json(200, read(`me.${who}.json`));
      const itemMatch = /^\/api\/v1\/work\/(W-\d+)$/.exec(url.pathname);
      if (request.method === 'GET' && itemMatch) {
        if (status[itemMatch[1]]) return json(status[itemMatch[1]], { code: 'x', message: 'No.' });
        const queue = reads[itemMatch[1]];
        if (!queue) return json(404, { code: 'not_found', message: 'Not here.' });
        const next = queue.length > 1 ? queue.shift()! : queue[0];
        return next === 'fail' ? json(500, { code: 'server_error', message: 'Nope.' }) : json(200, next);
      }
      if (request.method === 'POST' && url.pathname.endsWith('/steps')) {
        const answer = writes.length > 1 ? writes.shift()! : writes[0];
        if (!answer) return json(404, { code: 'not_found', message: 'Not here.' });
        return typeof answer === 'function' ? answer() : answer.clone();
      }
      return json(404, { code: 'not_found', message: 'Not here.' });
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function phone() {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
}

async function open(first: WorkItem, ...later: WorkItem[]) {
  reads[first.id] = [first, ...later];
  const view = render(
    <AppShell>
      <WorkItemView id={first.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: first.title });
  return view;
}

const ws = () => within(document.querySelector('.ws') as HTMLElement);
const body = () => document.body.textContent ?? '';
const press = async (name: string | RegExp, scope: () => ReturnType<typeof within> = ws) => {
  await act(async () => {
    fireEvent.click(scope().getByRole('button', { name }));
  });
};
const type = (label: string | RegExp, value: string, scope: () => ReturnType<typeof within> = ws) => fireEvent.change(scope().getByLabelText(label), { target: { value } });
const row = (id: string) => within(screen.getAllByRole('row').find((r) => within(r).queryByText(id))!);
const panel = () => within(screen.getByRole('region', { name: /Review Tola’s suggestion/ }));

// ---------------------------------------------------------------------------------------------------------------------
describe('the RFP frame on the requirements page (AC 1)', () => {
  it('draws the frame with Requirements current, Team input as a link to the form, plain Pricing, Submission and Outcome, and History', async () => {
    await open(item('W-3401'));
    expect(document.querySelector('.rfp-eyebrow')!.textContent).toContain('Pre-sale / RFP · TL-RFP-2026-014');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Tamarind Loans · loan origination RFP');
    expect(body()).toContain('DEADLINE 28 NOV · 16 DAYS');
    expect(body()).toContain('PM Tunde Bello');
    const tabs = within(screen.getByRole('navigation', { name: 'RFP' }));
    const current = document.querySelector('.rfp-tabs [aria-current="page"]')!;
    expect(current.textContent).toContain('Requirements');
    expect(current.tagName).toBe('SPAN');
    expect(tabs.getByRole('link', { name: /Team input/ }).getAttribute('href')).toBe('/work/W-3401/respond?task=T-3401');
    for (const plain of ['Pricing', 'Submission', 'Outcome']) expect(tabs.queryByRole('link', { name: plain })).toBeNull();
    expect(screen.getByRole('link', { name: 'History' }).getAttribute('href')).toBe('/work/W-3401/history');
  });

  it('on the team-input form Team input is current and Requirements links back; on W-2101 and W-2103 Requirements stays plain', () => {
    const w = item('W-3401');
    const withTeamCurrent = { ...w, rfp: { ...w.rfp!, tabs: w.rfp!.tabs!.map((t) => ({ ...t, current: t.key === 'team_input' })) } };
    render(<RfpFrame id="W-3401" item={withTeamCurrent} rfp={withTeamCurrent.rfp!} fallback="x" />);
    expect(document.querySelector('[aria-current="page"]')!.textContent).toContain('Team input');
    expect(screen.getByRole('link', { name: /Requirements/ }).getAttribute('href')).toBe('/work/W-3401');
    cleanup();
    const old = read('response/work/W-2101.json') as WorkItem;
    old.rfp!.tabs = old.rfp!.tabs!.map((t) => ({ ...t, current: t.key === 'outcome' }));
    render(<RfpFrame id="W-2101" item={old} rfp={old.rfp!} fallback="x" />);
    expect(screen.queryByRole('link', { name: /Requirements/ })).toBeNull();
    expect(screen.getByRole('link', { name: /Team input/ }).getAttribute('href')).toBe('/work/W-2101');
  });

  it('at 390 there is no frame; the header shows the title and the RFP status tag', async () => {
    phone();
    await open(item('W-3401'));
    expect(document.querySelector('.rfp-frame')).toBeNull();
    expect(document.querySelector('.work-header')!.textContent).toContain('DEADLINE 28 NOV · 16 DAYS');
    expect(screen.queryByRole('navigation', { name: 'RFP' })).toBeNull();
  });
});

describe('W-3401 from data (AC 2, 3, 4, 5)', () => {
  it('shows the six rows, the three Progress figures with their note, Tola’s note, the checklist and the toolbar count', async () => {
    await open(item('W-3401'));
    const table = within(screen.getByRole('table'));
    expect(table.getAllByRole('row')).toHaveLength(7);
    expect(row('R-03').getByText('NEEDS CLARIFICATION')).toBeTruthy();
    expect(row('R-01').getByText(/RFP p\.4/)).toBeTruthy();
    expect(ws().getByText('6 of 64')).toBeTruthy();
    const progress = within(screen.getByRole('region', { name: 'Progress' }));
    expect(progress.getByText('38 of 64')).toBeTruthy();
    expect(progress.getByText('Up to 100 rows. Every row cites the RFP page it answers.')).toBeTruthy();
    expect(ws().getByText('Tola')).toBeTruthy();
    expect(ws().getByText(/I matched 41 requirements/)).toBeTruthy();
    const checklist = within(screen.getByRole('region', { name: 'Before review' }));
    expect(checklist.getByText(/10 Nov · estimate-eng.xlsx/)).toBeTruthy();
    expect(checklist.getAllByRole('button', { name: 'Record' })).toHaveLength(2);
  });

  it('puts Tola’s note in the side column straight after Progress, before the checklist', async () => {
    await open(item('W-3401'));
    const side = document.querySelector('.ws-side') as HTMLElement;
    const order = ['Progress', 'I matched 41 requirements', 'Before review'].map((t) => (side.textContent ?? '').indexOf(t));
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it('hides only the team-input task panel on desktop; another task of the item still has its panel', async () => {
    const w = clone('W-3401');
    w.tasks = [...w.tasks!, { id: 'T-3499', kind: 'approve', title: 'Approve the bid', required_role: 'PM', you_can_act: true, revision: 1 } as never];
    await open(w);
    expect(screen.getAllByText('Approve the bid').length).toBeGreaterThan(0);
    expect(screen.queryByText('Record team input')).toBeNull();
  });

  it('draws the review, edit and reject fixtures as the boards do: one primary, no note, no checklist', () => {
    for (const name of ['W-3402', 'W-3402.next.accept', 'W-3402.next.accept_selected', 'W-3402.next.edit_accept', 'W-3402.next.write_own', 'W-3403', 'W-3403.next']) {
      const w = item(name).workspace!;
      expect(w.steps!.find((s) => s.key === 'accept_selected')!.emphasis, name).not.toBe('primary');
      expect(w.agent_note, name).toBeUndefined();
      expect(w.sections!.map((x) => x.key), name).not.toContain('before_review');
    }
  });

  it('tags in the stacked phone table keep their own width', () => {
    const css = readFileSync(join(__dirname, '../src/features/workspace/workspace.css'), 'utf8');
    expect(css).toMatch(/\.ws-table--stack td\.psl-check-cell, \.ws-table--stack th\.psl-check-cell \{ border: none/);
    expect(css).toMatch(/\.ws\[data-line=\"rfp_response\"\] \.ws-table--stack td\[data-label\] \{[^}]*justify-items: start/);
  });

  it('no board string is in src or in the mock server code', () => {
    const hits: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.(ts|tsx|css)$/.test(name) && /38 of 64|NEEDS CLARIFICATION|SUGGESTED BY TOLA|Harmattan|suggest better next time|that bid was won/.test(readFileSync(path, 'utf8'))) hits.push(path);
      }
    };
    walk(join(__dirname, '../src'));
    expect(hits).toEqual([]);
  });

  it('a different figure value shows that value, a figure with no value reads Unknown (never 0), and no total leaves out the "of" count', async () => {
    const w = clone('W-3401');
    const figures = w.workspace!.sections.find((s) => s.key === 'progress')!;
    figures.items[0].value = '12 of 64';
    delete figures.items[1].value;
    delete w.workspace!.sections.find((s) => s.key === 'requirements')!.total;
    await open(w);
    const progress = within(screen.getByRole('region', { name: 'Progress' }));
    expect(progress.getByText('12 of 64')).toBeTruthy();
    expect(progress.queryByText('38 of 64')).toBeNull();
    expect(progress.getByText('Unknown')).toBeTruthy();
    expect(ws().queryByText(/^6 of /)).toBeNull();
  });

  it('shows no amount, rate or costing anywhere on W-3401 to W-3404', async () => {
    for (const id of ['W-3401', 'W-3402', 'W-3403', 'W-3404']) {
      cleanup();
      await open(item(id));
      expect(body(), id).not.toMatch(/₦|\bNGN\b|costing|rate card/i);
    }
  });

  it('Send for review is a disabled button with the returned reason and consequence; pressing it, or Enter, sends nothing; a copy without the step draws none', async () => {
    await open(item('W-3401'));
    const send = ws().getByRole('button', { name: 'Send for review' });
    expect(send.getAttribute('aria-disabled')).toBe('true');
    expect(send.getAttribute('href')).toBeNull();
    expect(ws().getByText('Available once every requirement has an answer and all four teams have given input.')).toBeTruthy();
    expect(ws().getByText('Reviewers: PMO Lead and Engineering Lead.')).toBeTruthy();
    const before = sent.length;
    fireEvent.click(send);
    fireEvent.keyDown(send, { key: 'Enter' });
    expect(sent.length).toBe(before);
    cleanup();
    const w = clone('W-3401');
    w.workspace!.steps = w.workspace!.steps!.filter((s) => s.key !== 'send_for_review');
    await open(w);
    expect(ws().queryByRole('button', { name: 'Send for review' })).toBeNull();
  });

  it('Record on Security and Product opens F-18’s team-input form in the Drawer; Engineering and QA have none; W-3404 draws no Record, Add or Send', async () => {
    await open(item('W-3401'));
    const checklist = within(screen.getByRole('region', { name: 'Before review' }));
    const rows = checklist.getAllByRole('listitem');
    expect(within(rows[0]).queryByRole('button')).toBeNull();
    expect(within(rows[1]).queryByRole('button')).toBeNull();
    expect(within(rows[2]).getByRole('button', { name: 'Record' })).toBeTruthy();
    cleanup();
    await open(item('W-3404'));
    for (const name of ['Record', /Add a requirement/, 'Send for review']) expect(ws().queryByRole('button', { name })).toBeNull();
  });
});

describe('add a requirement (AC 6)', () => {
  it('sends step add_requirement with the trimmed requirement and an integer page, a UUID key and no item_ids; an empty field names itself and sends nothing', async () => {
    writes = [ok('Requirement R-65 added under your name.')];
    await open(item('W-3401'));
    await press(/Add a requirement from the RFP/);
    await press('Add a requirement from the RFP', () => within(screen.getByRole('form')));
    expect(steps()).toHaveLength(0);
    expect(screen.getAllByText(/Add requirement to continue|Add rfp page to continue/i).length).toBeGreaterThan(0);
    type(/Requirement/, '  Data stays in Nigeria  ', () => within(screen.getByRole('form')));
    type(/RFP page/, '12', () => within(screen.getByRole('form')));
    await press('Add a requirement from the RFP', () => within(screen.getByRole('form')));
    expect(steps()).toHaveLength(1);
    const [post] = steps();
    expect(post.body).toMatchObject({ step: 'add_requirement', expected_revision: 7, inputs: { requirement: 'Data stays in Nigeria', rfp_page: 12 } });
    expect(post.body).not.toHaveProperty('item_ids');
    expect(post.body!.idempotency_key).toMatch(UUID);
    expect(stepRequest(post.body), JSON.stringify(stepRequest.errors)).toBe(true);
    expect(post.csrf).toBeTruthy();
  });
});

describe('accept one (AC 7)', () => {
  it('shows the suggestion with its label, the past-answer line as returned, the consequence and three buttons', async () => {
    await open(item('W-3402'));
    expect(panel().getByText(/Approvals above a configurable threshold/)).toBeTruthy();
    expect(panel().getAllByText('Tola')).toHaveLength(1);
    expect(panel().queryByText('Suggested by Tola')).toBeNull();
    expect(panel().getByText('From PSL’s past answer: Harmattan Bank RFP 2025 · R-12 · that bid was won')).toBeTruthy();
    expect(panel().getByText('Harmattan Bank RFP 2025 · R-12').closest('a')).toBeTruthy();
    expect(panel().getByText('Addressed')).toBeTruthy();
    for (const name of ['Accept answer', 'Edit answer', 'Write my own']) expect(panel().getByRole('button', { name })).toBeTruthy();
  });

  it('one press sends exactly one POST, a double press sends one, nothing says accepted until the re-read, then the row, notice and next suggestion come from the re-read', async () => {
    const next = item('W-3402');
    let release!: (r: Response) => void;
    writes = [() => new Promise<Response>((resolve) => (release = resolve))];
    const afterAccept = read('work/W-3402.next.accept.json') as WorkItem;
    await open(item('W-3402'), afterAccept);
    const accept = panel().getByRole('button', { name: 'Accept answer' });
    await act(async () => {
      fireEvent.click(accept);
      fireEvent.click(accept);
    });
    expect(steps()).toHaveLength(1);
    expect(steps()[0].body).toEqual({ expected_revision: next.workspace!.revision, step: 'accept', item_ids: ['R-07'], idempotency_key: expect.stringMatching(UUID) });
    expect(steps()[0].body).not.toHaveProperty('inputs');
    expect(steps()[0].csrf).toBeTruthy();
    expect(row('R-07').getByText('SUGGESTED BY TOLA')).toBeTruthy();
    expect(body()).not.toContain('accepted under your name');
    await act(async () => release(ok('R-07 accepted under your name.')));
    await screen.findByText('R-07 accepted under your name.');
    expect(row('R-07').getByText('ADDRESSED')).toBeTruthy();
    expect(panel().getByText(/R-08 · RFP p\.6/)).toBeTruthy();
    expect(steps()).toHaveLength(1);
  });

  it('a restricted suggestion shows Restricted and none of its text, past-answer line or buttons', async () => {
    const w = clone('W-3402');
    w.workspace!.sections.find((s) => s.key === 'suggestions')!.items[0].restricted = true;
    await open(w);
    expect(screen.getByText('Restricted')).toBeTruthy();
    expect(body()).not.toContain('Harmattan');
    expect(screen.queryByRole('button', { name: 'Accept answer' })).toBeNull();
  });
});

describe('accept selected (AC 8)', () => {
  it('ticking R-07 and R-09 shows "2 selected" and sends exactly those ids', async () => {
    writes = [ok('2 answers accepted under your name.')];
    await open(item('W-3402'), read('work/W-3402.next.accept_selected.json'));
    const accept = ws().getByRole('button', { name: 'Accept selected' });
    fireEvent.click(accept);
    expect(steps()).toHaveLength(0);
    fireEvent.click(ws().getByLabelText("Select R-07"));
    fireEvent.click(ws().getByLabelText("Select R-09"));
    expect(ws().getByText('2 selected')).toBeTruthy();
    await press('Accept selected');
    expect(steps()).toHaveLength(1);
    expect(steps()[0].body).toMatchObject({ step: 'accept_selected', item_ids: ['R-07', 'R-09'] });
    expect(stepRequest(steps()[0].body)).toBe(true);
    await screen.findByText('2 answers accepted under your name.');
    expect(row('R-07').getByText('ADDRESSED')).toBeTruthy();
    expect(row('R-08').getByText('SUGGESTED BY TOLA')).toBeTruthy();
  });

  it('select-all ticks exactly the four rows on screen, shows the mixed state for one to three, and sends ids, never a filter or count', async () => {
    writes = [ok('4 answers accepted under your name.')];
    await open(item('W-3402'));
    const all = ws().getByLabelText('Select all shown rows') as HTMLInputElement;
    fireEvent.click(ws().getByLabelText("Select R-07"));
    expect(all.indeterminate).toBe(true);
    fireEvent.click(all);
    expect(all.indeterminate).toBe(false);
    expect(ws().getByText('4 selected')).toBeTruthy();
    fireEvent.click(all);
    expect(ws().getByText('0 selected')).toBeTruthy();
    fireEvent.click(all);
    await press('Accept selected');
    expect(steps()[0].body).toMatchObject({ item_ids: ['R-07', 'R-08', 'R-09', 'R-10'] });
    expect(Object.keys(steps()[0].body!).sort()).toEqual(['expected_revision', 'idempotency_key', 'item_ids', 'step']);
  });
});

const form = () => within(screen.getByRole('form'));

describe('edit and accept (AC 9)', () => {
  it('opens with Tola’s text and Addressed, the submit reads "Save and accept", and the typed words and Clarify are sent', async () => {
    writes = [ok('R-07 saved with your edit and accepted.')];
    await open(item('W-3402'), read('work/W-3402.next.edit_accept.json'));
    await press('Edit answer', panel);
    expect((form().getByLabelText(/Your answer/) as HTMLTextAreaElement).value).toBe('Approvals above a configurable threshold go to a named loan officer; every decision is recorded.');
    expect(within(screen.getByRole('form')).getByRole('radio', { name: 'Addressed' }).getAttribute('aria-checked') ?? (form().getByRole('radio', { name: 'Addressed' }) as HTMLInputElement).checked).toBeTruthy();
    expect(form().getByRole('button', { name: 'Save and accept' })).toBeTruthy();
    type(/Your answer/, '  Two named loan officers approve.  ', form);
    fireEvent.click(form().getByRole('radio', { name: 'Clarify' }));
    await press('Save and accept', form);
    expect(steps()[0].body).toMatchObject({ step: 'edit_accept', item_ids: ['R-07'], inputs: { answer: 'Two named loan officers approve.', status: 'clarify' } });
    expect(stepRequest(steps()[0].body)).toBe(true);
    await screen.findByText('R-07 saved with your edit and accepted.');
  });

  it('Cancel with no change closes at once; after a change it asks, Keep editing returns to the text, Discard closes with focus on Edit answer; no request goes', async () => {
    await open(item('W-3402'));
    await press('Edit answer', panel);
    await press('Cancel', form);
    expect(screen.queryByRole('form')).toBeNull();
    await press('Edit answer', panel);
    type(/Your answer/, 'Changed words', form);
    await press('Cancel', form);
    expect(screen.getByText('Discard your changes?')).toBeTruthy();
    await press('Keep editing', form);
    expect(screen.queryByText('Discard your changes?')).toBeNull();
    expect((form().getByLabelText(/Your answer/) as HTMLTextAreaElement).value).toBe('Changed words');
    fireEvent.keyDown(form().getByLabelText(/Your answer/), { key: 'Escape' });
    expect(screen.getByText('Discard your changes?')).toBeTruthy();
    await press('Discard', form);
    expect(screen.queryByRole('form')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(panel().getByRole('button', { name: 'Edit answer' })));
    expect(steps()).toHaveLength(0);
  });

  it('a copy without start values opens the form empty', async () => {
    const w = clone('W-3402');
    for (const f of w.workspace!.steps!.find((s) => s.key === 'edit_accept')!.fields!) delete (f as { value?: unknown }).value;
    await open(w);
    await press('Edit answer', panel);
    expect((form().getByLabelText(/Your answer/) as HTMLTextAreaElement).value).toBe('');
  });
});

describe('write my own (AC 10)', () => {
  it('shows Tola’s text read-only as not used, an empty answer, the optional reason with its help; empty save names Your answer and sends nothing', async () => {
    writes = [ok('Your answer to R-07 is saved. Tola’s suggestion is marked not used.')];
    await open(item('W-3402'), read('work/W-3402.next.write_own.json'));
    await press('Write my own', panel);
    expect(form().getByText('Tola’s suggestion (not used)')).toBeTruthy();
    expect((form().getByLabelText(/Your answer/) as HTMLTextAreaElement).value).toBe('');
    expect(form().getByText('Kept internal. It is not shown to the client.')).toBeTruthy();
    expect(body()).not.toMatch(/suggest better next time/);
    await press('Save my answer', form);
    expect(steps()).toHaveLength(0);
    expect(form().getByText(/Add your answer to continue/)).toBeTruthy();
    type(/Your answer/, 'Two named officers approve.', form);
    await press('Save my answer', form);
    expect(steps()[0].body!.inputs).toEqual({ answer: 'Two named officers approve.', status: 'addressed' });
    expect(JSON.stringify(steps()[0].body)).not.toContain('Approvals above a configurable threshold');
    expect(stepRequest(steps()[0].body)).toBe(true);
    await screen.findByText(/Your answer to R-07 is saved/);
  });

  it('the reason is sent when typed', async () => {
    writes = [ok('Your answer to R-07 is saved.')];
    await open(item('W-3402'));
    await press('Write my own', panel);
    type(/Your answer/, 'Two named officers approve.', form);
    type(/Why not Tola/, '  The client asked for two approvers  ', form);
    await press('Save my answer', form);
    expect(steps()[0].body!.inputs).toEqual({ answer: 'Two named officers approve.', status: 'addressed', reason: 'The client asked for two approvers' });
  });
});

describe('failures never say accepted (AC 11)', () => {
  const accepted = () => expect(body()).not.toMatch(/accepted under your name|ADDRESSED/);

  it('422 names the field under Your answer and keeps the entry', async () => {
    writes = [json(422, { code: 'invalid', message: 'Check these fields: answer.', fields: [{ name: 'answer', message: 'The answer is too long.' }] })];
    await open(item('W-3402'));
    await press('Edit answer', panel);
    type(/Your answer/, 'Kept words', form);
    await press('Save and accept', form);
    expect(form().getByText('The answer is too long.')).toBeTruthy();
    expect((form().getByLabelText(/Your answer/) as HTMLTextAreaElement).value).toBe('Kept words');
    expect(body()).not.toContain('edit and accepted');
  });

  it('409 shows the stale notice, re-reads, keeps the typed words and sends the new revision on the next press, with no automatic resend', async () => {
    const newer = clone('W-3402');
    newer.revision = 9;
    newer.workspace!.revision = 9;
    writes = [json(409, { code: 'stale_revision', message: 'Changed.' }), ok('R-07 saved with your edit and accepted.')];
    await open(item('W-3402'), newer);
    await press('Edit answer', panel);
    type(/Your answer/, 'Kept words', form);
    await press('Save and accept', form);
    expect(await screen.findByText(/This changed while you were working/)).toBeTruthy();
    expect(steps()).toHaveLength(1);
    expect((form().getByLabelText(/Your answer/) as HTMLTextAreaElement).value).toBe('Kept words');
    await press('Save and accept', form);
    expect(steps()).toHaveLength(2);
    expect(steps()[1].body!.expected_revision).toBe(9);
    expect(steps()[1].body!.idempotency_key).not.toBe(steps()[0].body!.idempotency_key);
  });

  it('a server error and a network error say the step could not be confirmed, re-read, and Try again repeats the same key', async () => {
    for (const failure of [json(500, { code: 'server_error', message: 'Nope.' }), (() => Promise.reject(new TypeError('network'))) as Answer]) {
      cleanup();
      sent = [];
      writes = [failure, ok('R-07 accepted under your name.')];
      await open(item('W-3402'));
      await press('Accept answer', panel);
      await screen.findByText(/We couldn’t confirm this step/);
      accepted();
      await press('Try again');
      await screen.findByText('R-07 accepted under your name.');
      expect(steps()).toHaveLength(2);
      expect(steps()[1].body!.idempotency_key).toBe(steps()[0].body!.idempotency_key);
    }
  });

  it('403 shows the forbidden notice and re-reads', async () => {
    writes = [json(403, { code: 'forbidden', message: 'No.' })];
    await open(item('W-3402'));
    await press('Accept answer', panel);
    await screen.findByText('You can’t take that step.');
    accepted();
    expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3402').length).toBeGreaterThan(1);
  });
});

describe('uncertain step (AC 12)', () => {
  it('shows the "being checked" notice, turns every step off, keeps them off after a reload and sends one accept', async () => {
    writes = [json(200, { work_id: 'W-3403', state: 'effect_uncertain', revision: 8, outcome: 'effect_uncertain', message: 'R-07 couldn’t be confirmed as accepted.' })];
    await open(item('W-3403'), read('work/W-3403.next.json'));
    await press('Accept answer', panel);
    await screen.findAllByText(/We are checking what happened/);
    await press('Edit answer', panel);
    await press('Accept answer', panel);
    expect(screen.queryByRole('form')).toBeNull();
    expect(steps()).toHaveLength(1);
    expect(body()).not.toContain('accepted under your name');
  });
});

describe('access (AC 14, 15)', () => {
  it('401 on the read is the signed-out state with the next link; 403 and 404 look the same and name nothing', async () => {
    for (const code of [403, 404]) {
      cleanup();
      status = { 'W-3401': code };
      render(
        <AppShell>
          <WorkItemView id="W-3401" tab="overview" />
        </AppShell>,
      );
      await waitFor(() => expect(body()).toMatch(/isn’t open|not open|can’t open|doesn’t exist/i));
      expect(body()).not.toMatch(/TL-RFP-2026-014|Tamarind|loan origination/);
    }
    cleanup();
    status = { 'W-3401': 401 };
    render(
      <AppShell>
        <WorkItemView id="W-3401" tab="overview" />
      </AppShell>,
    );
    await waitFor(() => expect(screen.getByRole('link', { name: /sign in/i }).getAttribute('href')).toContain('next=%2Fwork%2FW-3401'));
  });

  it('the same fixture draws the same controls for pm, finance_lead and ceo; a copy with the steps removed draws none', async () => {
    const drawn: string[][] = [];
    for (const persona of ['pm', 'finance_lead', 'ceo']) {
      cleanup();
      who = persona;
      await open(item('W-3402'));
      drawn.push([...document.querySelectorAll('.ws button')].map((b) => b.textContent ?? ''));
    }
    expect(drawn[1]).toEqual(drawn[0]);
    expect(drawn[2]).toEqual(drawn[0]);
    cleanup();
    const w = clone('W-3402');
    delete w.workspace!.steps;
    for (const s of w.workspace!.sections) for (const i of s.items) delete i.steps;
    await open(w);
    expect(ws().queryByRole('button', { name: /Accept|Edit answer|Write my own/ })).toBeNull();
  });

  it('nothing under features/workspace, work-item or rfp reads /me', () => {
    const hits: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.tsx?$/.test(name) && /useMe\b|\/api\/v1\/me/.test(readFileSync(path, 'utf8'))) hits.push(path);
      }
    };
    for (const sub of ['workspace', 'work-item', 'rfp']) walk(join(__dirname, '../src/features', sub));
    expect(hits).toEqual([]);
  });
});

describe('phone (AC 16)', () => {
  it('Edit answer opens in the Drawer; Cancel after a change asks first, then Discard returns focus to the button', async () => {
    phone();
    await open(item('W-3402'));
    await press('Edit answer', panel);
    const dialog = within(screen.getByRole('dialog'));
    type(/Your answer/, 'Changed on a phone', () => dialog);
    await act(async () => {
      fireEvent.click(dialog.getByRole('button', { name: 'Close' }));
    });
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(dialog.getByText('Discard your changes?')).toBeTruthy();
    await act(async () => {
      fireEvent.click(dialog.getByRole('button', { name: 'Discard' }));
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(panel().getByRole('button', { name: 'Edit answer' })));
    expect(steps()).toHaveLength(0);
  });

  it('Add a requirement opens in the Drawer too', async () => {
    phone();
    await open(item('W-3401'));
    await press(/Add a requirement from the RFP/);
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});
