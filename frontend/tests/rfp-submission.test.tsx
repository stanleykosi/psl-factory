// @vitest-environment jsdom
// F-38: the RFP submission work item (W-3501 to W-3509) drawn from E-WORK-ITEM `workspace` inside F-18's RFP frame, with its
// writes: the PM's Send for review and Edit cover letter (E-WORK-STEP), the reviewer's claim and decision in place
// (E-TASK-CLAIM, E-TASK-DECIDE through useDecision) and a reconcile answer (E-WORK-ACTION). Contract mock only: the fetch stub
// stands in for the backend, nothing here is submitted, emailed or delivered, and every "Submitted", "Emailed", "Received"
// and receipt word is fixture text the page shows only as returned.
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
  usePathname: () => '/work/W-3501',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const sidecar = (name: string): WorkItem => read(`response/${name}.json`);
const clone = (name: string): WorkItem => structuredClone(item(name));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const decideRequest = ajv.compile(openapi.paths['/api/v1/tasks/{task_id}/decision'].post.requestBody.content['application/json'].schema);
const stepRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Body = Record<string, unknown>;
type Handler = (body: Body) => Response | Promise<Response>;
let sent: Sent[];
let served: WorkItem;
let readAnswer: (() => Response) | null;
let who: string;
let onClaim: Handler;
let onDecide: Handler;
let onStep: Handler;
let onAction: Handler;
let onDocument: () => Response;

const posts = (suffix: string) => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const writes = () => sent.filter((r) => r.method !== 'GET');
const decided = (verdict: string, task: string, state = 'verified') => json(200, { task_id: task, verdict, decided_by: 'Kemi Adebayo', decided_at: '2026-11-26T13:58:00Z', work_state: state });

beforeEach(() => {
  sent = [];
  readAnswer = null;
  who = 'pm';
  onClaim = (body) => json(200, { task_id: 'T', revision: body.expected_revision, claimed_by: 'Kemi Adebayo' });
  onDecide = (body) => {
    served = item(`W-3502.${body.verdict}`);
    return decided(body.verdict as string, 'T-3502');
  };
  onStep = () => {
    served = item('W-3501.next');
    return json(200, { work_id: 'W-3501', state: 'action_needed', revision: 2, outcome: 'done', message: 'Done: Send for review.' });
  };
  onAction = () => json(200, { work_id: 'W-3505', state: 'verified', revision: 4 });
  onDocument = () => json(200, read('documents/D-3501.1.json'));
  const fetchStub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    const body = text ? JSON.parse(text) : undefined;
    sent.push({ method: request.method, path: url.pathname, body, csrf: request.headers.get('X-CSRFToken') });
    if (url.pathname === '/api/v1/me') return json(200, read(`me.${who}.json`));
    if (request.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(url.pathname)) return readAnswer ? readAnswer() : json(200, served);
    if (request.method === 'GET' && url.pathname.startsWith('/api/v1/documents/')) return onDocument();
    if (request.method === 'POST' && url.pathname.endsWith('/claim')) return onClaim(body);
    if (request.method === 'POST' && url.pathname.endsWith('/decision')) return onDecide(body);
    if (request.method === 'POST' && url.pathname.endsWith('/steps')) return onStep(body);
    if (request.method === 'POST' && url.pathname.endsWith('/actions')) return onAction(body);
    return json(404, { code: 'not_found', message: 'Not here.' });
  });
  vi.stubGlobal('fetch', withoutBellFeed(fetchStub));
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const phone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));

async function open(body: WorkItem, heading: string | RegExp = body.title) {
  served = body;
  const view = render(
    <AppShell>
      <WorkItemView id={body.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1 });
  await screen.findByRole('heading', { name: heading });
  return view;
}

const ws = () => within(document.querySelector('.ws') as HTMLElement);
const FULL_PACK = 'Open the full pack (PDF, 6.1 MB)';
/** The buttons in the workspace, not the full-pack link button. */
const buttons = () => ws().queryAllByRole('button').map((b) => b.textContent).filter((t) => t !== FULL_PACK);
const body = () => document.body.textContent ?? '';
const click = async (name: string | RegExp) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const ready = async (name = 'Approve and submit') => waitFor(() => expect(ws().getByRole('button', { name }).hasAttribute('disabled')).toBe(false));
const note = () => ws().getByLabelText('Note (needed to return or reject)') as HTMLTextAreaElement;
/** The list row that holds this text, in the named section. */
const rowIn = (region: string, text: string) => [...screen.getByRole('region', { name: region }).querySelectorAll('li')].find((li) => li.textContent?.includes(text))!;
const sentTo = () => within(screen.getByRole('region', { name: 'Sent to' }));
const FORBIDDEN_BEFORE_REREAD = /Submitted|Emailed|Receipt confirmed|Received|Delivered|Record the outcome/;
const lockCopy = /send again|resend|submit again/i;
/** No control or link offers a second send (the shared uncertain notice's own sentence says the factory won't resend; that is not a control). */
const noSecondSend = () => expect([...document.querySelectorAll('button, a')].map((el) => el.textContent).filter((t) => lockCopy.test(t ?? ''))).toEqual([]);

// ---------------------------------------------------------------------------------------------------------------------
describe('draft, from data (AC 3, 6, 7)', () => {
  it('W-3501 at 1440: the frame with Submission current, the pack with its returned tags, the five checks, Tola’s card, Next and the two steps', async () => {
    await open(item('W-3501'), 'Submission pack · v1');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Tamarind Loans · loan origination RFP');
    expect(document.querySelector('.rfp-eyebrow')!.textContent).toContain('Pre-sale / RFP · TL-RFP-2026-014');
    expect(body()).toContain('DEADLINE 28 NOV · 6 DAYS');
    const tabs = within(screen.getByRole('navigation', { name: 'RFP' }));
    const current = document.querySelector('.rfp-tabs [aria-current="page"]')!;
    expect(current.textContent).toContain('Submission');
    expect(current.tagName).toBe('SPAN');
    expect(tabs.getByRole('link', { name: /Team input/ }).getAttribute('href')).toBe('/work/W-2101');
    for (const plain of ['Requirements', 'Pricing', 'Outcome']) expect(tabs.queryByRole('link', { name: plain })).toBeNull();

    const pack = within(screen.getByRole('region', { name: 'What goes to the client' }));
    for (const [text, tag] of [['Response document', 'IN'], ['Commercial proposal', 'IN'], ['Cover letter', 'DRAFT'], ['Company forms', 'TEST TEMPLATE']]) {
      expect(rowIn('What goes to the client', text).textContent).toContain(tag);
    }
    expect(pack.getByText(/64 requirements, v3 approved 18 Nov/)).toBeTruthy();
    const checks = within(screen.getByRole('region', { name: 'Checks' }));
    expect(screen.getByRole('region', { name: 'Checks' }).querySelectorAll('li')).toHaveLength(5);
    expect(checks.getByText('FROM THE RFP, P.2')).toBeTruthy();
    expect(rowIn('Checks', 'Deadline 28 Nov · submit by 26 Nov leaves 2 days')).toBeTruthy();

    const card = document.querySelector('.ws-lineagent')!;
    expect(card.textContent).toContain('Tola');
    expect(card.textContent).toContain('DONE');
    for (const source of ['RESPONSE V3 · APPROVED 18 NOV', 'COSTING V2 · 3 APPROVALS', 'TEST TEMPLATE · UNTIL PSL SUPPLIES THE REAL ONE']) expect(card.textContent).toContain(source);
    expect(ws().getByRole('link', { name: 'Ask Tola' }).getAttribute('href')).toBe('/assistant');
    expect(ws().getByText(/A document reviewer checks the pack/)).toBeTruthy();
    expect(buttons()).toEqual(['Send for review', 'Edit cover letter']);
    expect(body()).not.toMatch(FORBIDDEN_BEFORE_REREAD);
    await new Promise((r) => setTimeout(r, 50));
    expect(writes()).toHaveLength(0);
  });

  it('Tola’s text is never a check result, a decision or a Submitted state, and nothing lets her submit (AC 7)', async () => {
    await open(item('W-3501'), 'Submission pack · v1');
    const checks = document.querySelector('[aria-label="Checks"], .ws-section--checklist:nth-of-type(2)')?.textContent ?? '';
    expect(checks).not.toContain('Tola');
    expect(screen.queryByRole('button', { name: /Tola|submit|approve/i })).toBeNull();
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(body()).not.toMatch(/Submitted/);
  });

  it('no board string is written in src, and src adds no money, date arithmetic, size check, /me read or resend control (AC 3, 5, 8, 14e, 15)', () => {
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.tsx?$/.test(name)) files.push(path);
      }
    };
    walk(join(__dirname, '../src'));
    const text = (path: string) => readFileSync(path, 'utf8');
    for (const pattern of [/procurement@|submit by|TL-SUB|all [34] approvals|Approve and submit/, /Delivered|delivery confirmed|verified as sent/]) {
      expect(files.filter((f) => pattern.test(text(f))).map((f) => f.replace(/.*src\//, '')), String(pattern)).toEqual([]);
    }
    const mine = ['features/rfp/RfpFrame.tsx', 'features/work-item/WorkItemView.tsx', 'features/workspace/InlineDecide.tsx'].map((f) => text(join(__dirname, '../src', f)));
    for (const src of mine) {
      expect(src).not.toMatch(/getTime\(\) *-|Date\.now\(\) *-|differenceIn|20 ?MB/);
      expect(src).not.toMatch(/useMe|\/api\/v1\/me/);
    }
    // InlineDecide's own header comment says "no automatic resend"; the frame and the page carry no such control or word
    for (const src of mine.slice(0, 2)) expect(src).not.toMatch(/send again|resend|submit again/i);
  });
});

describe('the Submission tab and the header are additive (AC 4)', () => {
  const tabsOf = (work_id?: string) => {
    const w = clone('W-3501');
    for (const t of w.rfp!.tabs!) {
      t.current = t.key === 'outcome';
      if (t.key === 'submission') {
        if (work_id) t.work_id = work_id;
        else delete t.work_id;
      }
    }
    return w;
  };
  it('a Submission tab with work_id links to it when it is not current; without work_id it stays plain text', () => {
    const w = tabsOf('W-3501');
    render(<RfpFrame id="W-3501" item={w} rfp={w.rfp!} fallback="x" />);
    expect(screen.getByRole('link', { name: 'Submission' }).getAttribute('href')).toBe('/work/W-3501');
    cleanup();
    const plain = tabsOf();
    render(<RfpFrame id="W-3501" item={plain} rfp={plain.rfp!} fallback="x" />);
    expect(screen.queryByRole('link', { name: 'Submission' })).toBeNull();
    expect(screen.getByText('Submission').className).toContain('is-plain');
  });

  it('Team input and Outcome behave as before on F-18’s W-2101 and W-2104; a workspace item without rfp draws no frame', async () => {
    const old = read('response/work/W-2101.json') as WorkItem;
    old.rfp!.tabs = old.rfp!.tabs!.map((t) => ({ ...t, current: t.key === 'outcome' }));
    render(<RfpFrame id="W-2101" item={old} rfp={old.rfp!} fallback="x" />);
    expect(screen.getByRole('link', { name: /Team input/ }).getAttribute('href')).toBe('/work/W-2101');
    expect(screen.queryByRole('link', { name: 'Submission' })).toBeNull();
    cleanup();
    await open(item('W-3902'));
    expect(screen.queryByRole('navigation', { name: 'RFP' })).toBeNull();
  });
});

describe('the page computes nothing (AC 5)', () => {
  it('a changed check sentence, deadline label and approvals text change only that text', async () => {
    const w = clone('W-3501');
    const checks = w.workspace!.sections.find((s) => s.key === 'checks')!;
    checks.items[2].text = "Client's format: one PDF, under 25 MB";
    checks.items[4].text = 'Deadline 30 Nov · submit by 27 Nov leaves 3 days';
    w.workspace!.sections.find((s) => s.key === 'pack')!.items[1].detail = 'costing v9, all 7 approvals';
    w.rfp!.status.label = 'DEADLINE 30 NOV · 9 DAYS';
    await open(w, 'Submission pack · v1');
    expect(body()).toContain('under 25 MB');
    expect(body()).toContain('Deadline 30 Nov · submit by 27 Nov leaves 3 days');
    expect(body()).toContain('costing v9, all 7 approvals');
    expect(body()).toContain('DEADLINE 30 NOV · 9 DAYS');
    expect(body()).not.toMatch(/under 20 MB|26 Nov leaves 2 days|6 DAYS|3 approvals/);
  });
});

describe('unknown is never 0 (AC 6)', () => {
  it('W-3509: the deadline check reads Unknown, the forms detail is absent, and no amount appears', async () => {
    await open(item('W-3509'), 'Submission pack · v1');
    const checks = within(screen.getByRole('region', { name: 'Checks' }));
    expect(checks.getByText('Deadline')).toBeTruthy();
    expect(rowIn('Checks', 'Deadline').textContent).toContain('Unknown');
    expect(rowIn('What goes to the client', 'Company forms').textContent?.trim()).toBe('Company forms TEST TEMPLATE');
    expect(body()).not.toMatch(/₦|\b0\.00\b/);
    for (const name of ['W-3501', 'W-3502', 'W-3503', 'W-3504', 'W-3505', 'W-3506', 'W-3507', 'W-3508', 'W-3509']) expect(JSON.stringify(item(name))).not.toMatch(/₦|"amount"|NGN/);
  });
});

describe('controls only from you_can_act and the steps sent (AC 8)', () => {
  it('W-3502 shows the three buttons, the version, the consequence and where it goes; the claim is sent once', async () => {
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    expect(screen.getByRole('heading', { name: 'Decide · document reviewer' })).toBeTruthy();
    expect(buttons()).toEqual(['Approve and submit', 'Return', 'Reject']);
    expect(ws().getByText('Approving lets the factory submit this exact pack. If anything in it changes, it comes back to you.', { exact: false })).toBeTruthy();
    expect(ws().getByText('Goes to procurement@tamarindloans.example')).toBeTruthy();
    expect(document.querySelector('.ws-idecide')!.textContent).toContain('Submission pack v1');
    expect(posts('/api/v1/tasks/T-3502/claim')).toHaveLength(1);
    expect(screen.queryByRole('navigation', { name: 'RFP' })).toBeNull();
    expect(document.querySelector('.work-crumbrow')!.textContent).toContain('DECISION');
  });

  it('W-3501 in review (prepared by you), W-3509 (not your role) and the submitted items offer no decide button and send no claim', async () => {
    for (const [name, copy] of [
      ['W-3501.next', /You prepared Submission pack v1, so someone else must review it\./],
      ['W-3509', /This decision needs a document reviewer\./],
    ] as const) {
      const w = item(name);
      await open({ ...w, id: w.id }, /Submission pack/);
      expect(ws().getByText(copy)).toBeTruthy();
      expect(buttons()).toEqual([]);
      await new Promise((r) => setTimeout(r, 30));
      expect(posts('/claim')).toHaveLength(0);
      cleanup();
    }
    for (const name of ['W-3503', 'W-3504']) {
      await open(item(name));
      expect(buttons()).toEqual([]);
      expect(posts('/claim')).toHaveLength(0);
      cleanup();
    }
  });

  it('W-3508 draws Approve and submit disabled with the returned reason and Return and Reject live; W-3507 draws Edit cover letter disabled with Not available yet', async () => {
    await open(item('W-3508'), 'Submission pack · v1');
    await waitFor(() => expect(ws().getByRole('button', { name: 'Return' }).hasAttribute('disabled')).toBe(false));
    const approve = ws().getByRole('button', { name: 'Approve and submit' });
    expect(approve.getAttribute('aria-disabled') === 'true' || approve.hasAttribute('disabled')).toBe(true);
    expect(ws().getByText('A part still uses a test template.')).toBeTruthy();
    fireEvent.click(approve);
    await new Promise((r) => setTimeout(r, 30));
    expect(posts('/decision')).toHaveLength(0);
    cleanup();
    await open(item('W-3507'), 'Submission pack · v1');
    const edit = ws().getByRole('button', { name: 'Edit cover letter' });
    expect(edit.getAttribute('aria-disabled') === 'true' || edit.hasAttribute('disabled')).toBe(true);
    expect(ws().getByText('Not available yet')).toBeTruthy();
    fireEvent.click(edit);
    expect(screen.queryByRole('form')).toBeNull();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(posts('/steps')).toHaveLength(0);
  });

  it('personas pm, ceo and finance_lead see the same controls for the same fixture', async () => {
    const seen: string[][] = [];
    for (const persona of ['pm', 'ceo', 'finance_lead']) {
      who = persona;
      await open(item('W-3502'), 'Review the submission pack · v1');
      await ready();
      seen.push(buttons() as string[]);
      cleanup();
    }
    expect(seen[1]).toEqual(seen[0]);
    expect(seen[2]).toEqual(seen[0]);
  });
});

describe('send for review (AC 9)', () => {
  it('one POST with CSRF, expected_revision, step, inputs and a UUID key; a double press sends one; nothing says it was sent for review until the re-read', async () => {
    await open(item('W-3501'), 'Submission pack · v1');
    expect(body()).not.toMatch(/IN REVIEW/);
    await act(async () => {
      const go = ws().getByRole('button', { name: 'Send for review' });
      fireEvent.click(go);
      fireEvent.click(go);
    });
    await waitFor(() => expect(body()).toContain('IN REVIEW'));
    const [step] = posts('/api/v1/work/W-3501/steps');
    expect(posts('/steps')).toHaveLength(1);
    expect(step.body).toMatchObject({ expected_revision: 1, step: 'send_for_review' });
    expect(step.body!.inputs ?? {}).toEqual({});
    expect(stepRequest(step.body)).toBe(true);
    expect(step.csrf).toBe('mock-csrf-pm');
    expect(step.body!.idempotency_key).toMatch(UUID);
    expect(buttons()).toEqual([]);
  });

  it('a 500 shows the shared not-confirmed notice and Try again reuses the key; a 409 re-reads and says it changed', async () => {
    onStep = () => json(500, { code: 'server_error', message: 'Down.' });
    await open(item('W-3501'), 'Submission pack · v1');
    await click('Send for review');
    expect(await screen.findByText(/We couldn.t confirm this step/)).toBeTruthy();
    expect(screen.queryByText('Not recorded')).toBeNull();
    expect(body()).not.toContain('IN REVIEW');
    onStep = () => {
      served = item('W-3501.next');
      return json(200, { work_id: 'W-3501', state: 'action_needed', revision: 2, outcome: 'done' });
    };
    await act(async () => {
      fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    });
    await waitFor(() => expect(body()).toContain('IN REVIEW'));
    const [first, second] = posts('/steps');
    expect(second.body!.idempotency_key).toBe(first.body!.idempotency_key);
    cleanup();

    sent = [];
    onStep = () => {
      served = { ...item('W-3501'), revision: 2, workspace: { ...item('W-3501').workspace!, revision: 2 } };
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-3501'), 'Submission pack · v1');
    await click('Send for review');
    expect(await screen.findByText(/This changed while you were working\. Showing version 2\./)).toBeTruthy();
    expect(posts('/steps')).toHaveLength(1);
  });
});

describe('edit cover letter (AC 10)', () => {
  it('opens with the current letter, sends one POST with the edited text, and refuses a blank letter before sending', async () => {
    onStep = () => json(200, { work_id: 'W-3501', state: 'action_needed', revision: 2, outcome: 'done', message: 'Cover letter saved.' });
    await open(item('W-3501'), 'Submission pack · v1');
    await click('Edit cover letter');
    const form = within(screen.getByRole('form'));
    const letter = form.getByLabelText(/Cover letter/) as HTMLTextAreaElement;
    expect(letter.value).toBe(read('work/W-3501.json').workspace.steps[1].fields[0].value);
    fireEvent.change(letter, { target: { value: '   ' } });
    await act(async () => {
      fireEvent.click(form.getByRole('button', { name: /Edit cover letter|Save/ }));
    });
    expect(posts('/steps')).toHaveLength(0);
    await waitFor(() => expect(document.activeElement).toBe(letter));
    fireEvent.change(letter, { target: { value: '  Dear team, our response is attached.  ' } });
    await act(async () => {
      fireEvent.click(form.getByRole('button', { name: /Edit cover letter|Save/ }));
    });
    const [step] = posts('/steps');
    expect(step.body).toMatchObject({ expected_revision: 1, step: 'edit_cover_letter', inputs: { cover_letter: 'Dear team, our response is attached.' } });
    expect(stepRequest(step.body)).toBe(true);
    expect(step.body!.idempotency_key).toMatch(UUID);
    expect(await screen.findByText('Cover letter saved.')).toBeTruthy();
  });

  it('a 422 lands under the field and keeps the text', async () => {
    onStep = () => json(422, { code: 'invalid', message: 'Check.', fields: [{ name: 'cover_letter', message: 'Say who to contact.' }] });
    await open(item('W-3501'), 'Submission pack · v1');
    await click('Edit cover letter');
    const form = within(screen.getByRole('form'));
    fireEvent.change(form.getByLabelText(/Cover letter/), { target: { value: 'Short.' } });
    await act(async () => {
      fireEvent.click(form.getByRole('button', { name: /Edit cover letter|Save/ }));
    });
    expect(await screen.findByText('Say who to contact.')).toBeTruthy();
    expect((within(screen.getByRole('form')).getByLabelText(/Cover letter/) as HTMLTextAreaElement).value).toBe('Short.');
  });

  it('on a phone the form opens in the Drawer', async () => {
    phone();
    await open(item('W-3501'), 'Submission pack · v1');
    await click('Edit cover letter');
    const dialog = await screen.findByRole('dialog');
    expect((within(dialog).getByLabelText(/Cover letter/) as HTMLTextAreaElement).value).toContain('Dear Tamarind Loans procurement team');
  });
});

describe('approve (AC 11)', () => {
  it('claims once, sends one decision {verdict approve, expected_revision 1} with CSRF; a double press sends one; Submitted only from the re-read', async () => {
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    await act(async () => {
      const go = ws().getByRole('button', { name: 'Approve and submit' });
      fireEvent.click(go);
      fireEvent.click(go);
    });
    await waitFor(() => expect(body()).toContain('Submitted · delivery confirmed'));
    expect(posts('/claim')).toHaveLength(1);
    expect(posts('/decision')).toHaveLength(1);
    const [decision] = posts('/decision');
    expect(decision.path).toBe('/api/v1/tasks/T-3502/decision');
    expect(decision.body).toEqual({ verdict: 'approve', expected_revision: 1 });
    expect(decideRequest(decision.body)).toBe(true);
    expect(decision.csrf).toBe('mock-csrf-pm');
    expect(screen.getByRole('heading', { name: 'What happened' })).toBeTruthy();
    expect(sentTo().getByText(/Received/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Record the outcome' }).getAttribute('href')).toBe('/work/W-3502/outcome');
  });

  it('a 200 whose re-read still serves the review shows none of Submitted, What happened, Sent to or Record the outcome', async () => {
    onDecide = (b) => decided(b.verdict as string, 'T-3502');
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    await click('Approve and submit');
    await waitFor(() => expect(posts('/decision')).toHaveLength(1));
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3502').length).toBeGreaterThanOrEqual(3));
    expect(body()).not.toMatch(/Submitted|What happened|Sent to|Record the outcome|Approved by/);
  });
});

describe('return and reject need a note (AC 12)', () => {
  it('empty, blank and over 2000 send nothing and focus the note; with a note one POST with the trimmed note; RETURNED TO PM, never Submitted', async () => {
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    await click('Return');
    const message = await screen.findByText('Add a note to return it.');
    await waitFor(() => expect(document.activeElement).toBe(note()));
    expect(note().getAttribute('aria-invalid')).toBe('true');
    expect(note().getAttribute('aria-describedby')).toContain(message.id || message.closest('[id]')!.id);
    fireEvent.change(note(), { target: { value: '   ' } });
    await click('Reject');
    expect(await screen.findByText('Add a note to reject it.')).toBeTruthy();
    fireEvent.change(note(), { target: { value: 'x'.repeat(2001) } });
    await click('Return');
    expect(await screen.findByText('Keep the note to 2000 characters or fewer.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    fireEvent.change(note(), { target: { value: '  Name the contact for the forms.  ' } });
    await click('Return');
    await waitFor(() => expect(body()).toContain('RETURNED TO PM'));
    expect(posts('/decision').map((p) => p.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'Name the contact for the forms.' }]);
    expect(decideRequest(posts('/decision')[0].body)).toBe(true);
    expect(body()).not.toMatch(/Submitted|Record the outcome/);
  });

  it('Reject with a note re-reads to REJECTED', async () => {
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    fireEvent.change(note(), { target: { value: 'Costing is out of date.' } });
    await click('Reject');
    await waitFor(() => expect(body()).toContain('REJECTED'));
    expect(posts('/decision')[0].body).toEqual({ verdict: 'reject', expected_revision: 1, note: 'Costing is out of date.' });
    expect(body()).not.toMatch(/Submitted/);
  });

  it('on a phone Return opens the Drawer with the note; Cancel closes it and returns focus', async () => {
    phone();
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    expect(buttons()).toEqual(['Approve and submit', 'Return', 'Reject']);
    await click('Return');
    const dialog = await screen.findByRole('dialog', { name: 'Return' });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Return' }));
    });
    expect(await within(dialog).findByText('Add a note to return it.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement?.textContent).toBe('Return'));
  });
});

describe('the pack changed (AC 13) and another reviewer decided first (checklist 1)', () => {
  it('W-3506: the first approve answers 409; the page shows v2, no approved text and no second decision; a new press sends expected_revision 2', async () => {
    onDecide = () => {
      served = item('W-3506.next');
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-3506'), 'Submission pack · v1');
    await ready();
    await click('Approve and submit');
    expect(await screen.findByText('Submission pack · v2')).toBeTruthy();
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(body()).toContain('edited by Tunde Bello');
    expect(body()).not.toMatch(/Submitted|approved by|Decision recorded/i);
    expect(posts('/decision')).toHaveLength(1);
    onDecide = () => decided('approve', 'T-3506');
    await click('Review the latest');
    await ready();
    expect(document.querySelector('.ws-idecide')!.textContent).toContain('Submission pack v2');
    await click('Approve and submit');
    await waitFor(() => expect(posts('/decision')).toHaveLength(2));
    expect(posts('/decision')[1].body).toEqual({ verdict: 'approve', expected_revision: 2 });
  });

  it('the real two-reviewer sequence: the task closed meanwhile, so a lasting notice and the unsent note show with no decide buttons', async () => {
    const closed = { ...item('W-3502.return'), id: 'W-3502' };
    onDecide = () => {
      served = closed;
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    fireEvent.change(note(), { target: { value: 'Wait for the forms.' } });
    await click('Reject');
    expect(await screen.findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(await screen.findByText(/Your note wasn.t sent: .Wait for the forms\..*/)).toBeTruthy();
    expect(buttons()).not.toContain('Approve and submit');
    expect(posts('/decision')).toHaveLength(1);
  });
});

describe('the facts and next step match the state (UX-1-1, UX-1-2)', () => {
  const approved = '2026-11-26T13:58:00Z';
  const timeOf = (w: WorkItem, name: string) => w.facts.find((f) => f.name === name);
  it('submitted pages carry the timeline times, never the draft time', () => {
    for (const w of [item('W-3502.approve'), item('W-3503'), item('W-3504'), sidecar('W-3505.delivered')]) {
      expect(timeOf(w, 'approved')?.at).toBe(approved);
      expect(timeOf(w, 'sent')?.at).toBe('2026-11-26T14:42:00Z');
      expect(timeOf(w, 'receipt_recorded')?.at).toBe('2026-11-26T14:43:00Z');
      expect(timeOf(w, 'verified')?.at).toBe('2026-11-26T14:43:00Z');
    }
  });
  it('uncertain and not-delivered pages say the review is done: approved earned, no review pending', () => {
    for (const w of [item('W-3505.approve'), sidecar('W-3505.not_delivered'), sidecar('W-3505.unknown')]) {
      expect(timeOf(w, 'approved')?.status).toBe('earned');
      expect(timeOf(w, 'reviewed')?.status).toBe('earned');
      expect(timeOf(w, 'sent')?.status).not.toBe('earned');
      expect(w.stations.find((s) => s.name === 'Document review')?.status).toBe('done');
      expect(w.next_step).not.toMatch(/approves, returns or rejects/);
    }
  });
});

describe('uncertain paths (AC 14)', () => {
  const uncertain = (): WorkItem => item('W-3505.approve');

  it('(a) the decide answers effect_uncertain: Effect uncertain, Sent to Uncertain, the reconcile panel, never Submitted or Record the outcome', async () => {
    onDecide = (b) => {
      served = uncertain();
      return decided(b.verdict as string, 'T-3505', 'effect_uncertain');
    };
    await open(item('W-3505'), 'Submission pack · v1');
    await ready();
    await click('Approve and submit');
    expect(await screen.findByText('Submission pack v1 · delivery not confirmed')).toBeTruthy();
    expect(body()).toContain('Effect uncertain');
    expect(sentTo().getByText(/Uncertain/)).toBeTruthy();
    expect(screen.getByRole('radiogroup')).toBeTruthy();
    expect(await screen.findByText(/Decision recorded on Submission pack v1: result not confirmed|result not confirmed/)).toBeTruthy();
    expect(body()).not.toMatch(/Submitted|Delivered|Received|Record the outcome/);
    noSecondSend();
    expect(posts('/decision')).toHaveLength(1);
  });

  for (const [name, answer] of [
    ['a 500', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
  ] as const) {
    it(`(b) ${name} on the decide re-reads first, then shows the uncertain notice, with one POST after 60 s`, async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
      onDecide = answer as unknown as Handler;
      await open(item('W-3502'), 'Review the submission pack · v1');
      await ready();
      const before = sent.length;
      await click('Approve and submit');
      expect(await screen.findByText(/We couldn.t confirm your decision/)).toBeTruthy();
      const after = sent.slice(before);
      expect(after[0].path).toBe('/api/v1/tasks/T-3502/decision');
      expect(after[1]).toMatchObject({ method: 'GET', path: '/api/v1/work/W-3502' });
      expect(body()).not.toMatch(/Submitted|Decision recorded on|Approved by/);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(posts('/decision')).toHaveLength(1);
    }, 90_000);
  }

  it('(c) a step that answers outcome uncertain goes to the reconcile path, never "sent for review"', async () => {
    onStep = () => {
      served = { ...uncertain(), id: 'W-3501' };
      return json(200, { work_id: 'W-3501', state: 'effect_uncertain', revision: 2, outcome: 'uncertain', message: 'We could not confirm it was recorded.' });
    };
    await open(item('W-3501'), 'Submission pack · v1');
    await click('Send for review');
    expect(await screen.findByText('We could not confirm it was recorded.')).toBeTruthy();
    expect(screen.getByRole('radiogroup')).toBeTruthy();
    expect(body()).not.toMatch(/sent for review|Done: Send for review/i);
  });

  it('(d) not_delivered re-reads to Not delivered with the backend’s next and no button; unknown keeps the lock; a 5xx on the reconcile shows the panel’s uncertain state with no retry', async () => {
    onAction = () => {
      served = sidecar('W-3505.not_delivered');
      return json(200, { work_id: 'W-3505', state: 'action_needed', revision: 4 });
    };
    await open(uncertain(), 'Submission pack v1 · delivery not confirmed');
    fireEvent.click(screen.getByRole('radio', { name: /It didn.t arrive/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    expect(posts('/actions')[0].body).toEqual({ expected_revision: 2, action: 'reconcile', outcome: 'not_delivered' });
    // the panel asks the browser to reload the work item (jsdom cannot); the re-read serves the sidecar
    expect(await screen.findByText(/Recorded\. Reloading the work item/)).toBeTruthy();
    cleanup();
    await open(served, 'Submission pack v1 · not delivered');
    expect(body()).toContain('Not delivered');
    expect(body()).toContain('Someone checks with Tamarind Loans before anything is sent again.');
    expect(buttons()).toEqual([]);
    expect(screen.queryByRole('radiogroup')).toBeNull();
    expect(rowIn('Sent to', 'procurement@').textContent).toContain('Failed');
    expect(posts('/decision')).toHaveLength(0);
    expect(posts('/steps')).toHaveLength(0);
    cleanup();

    sent = [];
    onAction = () => {
      served = sidecar('W-3505.unknown');
      return json(200, { work_id: 'W-3505', state: 'effect_uncertain', revision: 4 });
    };
    await open(uncertain(), 'Submission pack v1 · delivery not confirmed');
    fireEvent.click(screen.getByRole('radio', { name: /I can.t tell yet/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    expect(await screen.findByText(/Recorded\. Reloading the work item/)).toBeTruthy();
    cleanup();
    await open(served, 'Submission pack v1 · delivery not confirmed');
    expect(screen.getByRole('radiogroup')).toBeTruthy();
    expect(body()).toContain('Effect uncertain');
    cleanup();

    sent = [];
    onAction = () => json(500, { code: 'server_error', message: 'Down.' });
    await open(uncertain(), 'Submission pack v1 · delivery not confirmed');
    fireEvent.click(screen.getByRole('radio', { name: /I can.t tell yet/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    expect(await screen.findByText(/We couldn.t confirm your answer/)).toBeTruthy();
    expect(posts('/actions')).toHaveLength(1);
    expect(body()).not.toMatch(/Submitted|Delivered/);
  });

  it('(d) the delivered answer re-reads to the submitted content with Record the outcome', async () => {
    await open(sidecar('W-3505.delivered'), 'Submitted · delivery confirmed');
    expect(sentTo().getByText(/Received/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Record the outcome' }).getAttribute('href')).toBe('/work/W-3505/outcome');
  });

  it('(e) while reconcile is present every step and decide control is off and one reconcile press sends one POST to /actions only; the same after a reload', async () => {
    const locked = clone('W-3501');
    Object.assign(locked, { state: 'effect_uncertain', reconcile: uncertain().reconcile, allowed_actions: ['reconcile'] });
    await open(locked, 'Submission pack · v1');
    for (const name of ['Send for review', 'Edit cover letter']) {
      const b = ws().getByRole('button', { name });
      expect(b.getAttribute('aria-disabled') === 'true' || b.hasAttribute('disabled'), name).toBe(true);
      fireEvent.click(b);
    }
    expect(screen.queryByRole('form')).toBeNull();
    expect(posts('/steps')).toHaveLength(0);
    cleanup();
    await open(locked, 'Submission pack · v1');
    expect(ws().getByRole('button', { name: 'Send for review' }).getAttribute('aria-disabled') === 'true' || ws().getByRole('button', { name: 'Send for review' }).hasAttribute('disabled')).toBe(true);
    fireEvent.click(screen.getByRole('radio', { name: /I can.t tell yet/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    expect(posts('/actions')).toHaveLength(1);
    expect(posts('/steps')).toHaveLength(0);
    expect(posts('/claim')).toHaveLength(0);
    expect(posts('/decision')).toHaveLength(0);
    noSecondSend();
    cleanup();

    const lockedReview = { ...uncertain(), tasks: [{ ...item('W-3502').tasks[0], id: 'T-3505' }], workspace: { ...item('W-3505').workspace!, steps: item('W-3505').workspace!.steps } };
    sent = [];
    await open({ ...lockedReview, state: 'effect_uncertain', reconcile: uncertain().reconcile, allowed_actions: ['reconcile'] }, /Submission pack/);
    await new Promise((r) => setTimeout(r, 30));
    expect(posts('/decision')).toHaveLength(0);
    for (const b of ws().queryAllByRole('button', { name: /Approve and submit|Return|Reject/ })) expect(b.getAttribute('aria-disabled') === 'true' || b.hasAttribute('disabled')).toBe(true);
  });
});

describe('receipts only as returned (AC 15)', () => {
  it('W-3503 and W-3504: Received with its time only because receipt is received; the banner tag keeps the returned tone', async () => {
    for (const [name, to] of [['W-3503', 'procurement@tamarindloans.example'], ['W-3504', "Client's procurement portal"]] as const) {
      await open(item(name));
      expect(rowIn('Sent to', to).textContent).toMatch(/Received.*26 Nov 15:43/);
      expect(document.querySelector('.ws-section--text .psl-tag')!.textContent).toBe('Receipt confirmed');
      expect(document.querySelector('.ws-section--text .psl-tag')!.className).toContain('done');
      cleanup();
    }
  });

  for (const [receipt, word] of [['not_yet', 'Not yet'], ['uncertain', 'Uncertain'], ['failed', 'Failed'], ['unknown', 'Unknown'], [undefined, 'Unknown']] as const) {
    it(`a recipient with receipt ${receipt ?? 'absent'} reads ${word}, never Received, Sent or Delivered`, async () => {
      const w = clone('W-3503');
      const row = w.workspace!.sections.find((s) => s.key === 'sent_to')!.items[0];
      if (receipt) row.receipt = receipt;
      else delete row.receipt;
      delete row.at;
      w.workspace!.sections = w.workspace!.sections.filter((s) => s.key === 'sent_to');
      await open(w);
      const text = rowIn('Sent to', 'procurement@tamarindloans.example').textContent!;
      expect(text).toContain(word);
      expect(text).not.toMatch(/Received|Delivered|Sent\b/);
    });
  }
});

describe('Record the outcome (AC 16)', () => {
  it('shows only on items that return rfp_outcome, linking to the F-18 outcome form', async () => {
    for (const [w, has] of [[item('W-3503'), true], [item('W-3504'), true], [sidecar('W-3505.delivered'), true], [item('W-3501'), false], [item('W-3502'), false], [item('W-3505.approve'), false], [sidecar('W-3505.not_delivered'), false]] as const) {
      await open(w, w.workspace!.title);
      const link = screen.queryByRole('link', { name: 'Record the outcome' });
      expect(Boolean(link), w.id).toBe(has);
      if (has) expect(link!.getAttribute('href')).toBe(`/work/${w.id}/outcome`);
      cleanup();
    }
    expect(item('W-3503').rfp_outcome!.submission.label).toBe('Submission pack v1');
  });
});

describe('open the full pack (AC 17)', () => {
  it('sends one GET and shows the title, version and Test template; a 404 shows the gone line with no title', async () => {
    await open(item('W-3502'), 'Review the submission pack · v1');
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Open the full pack (PDF, 6.1 MB)' }));
    });
    expect(await screen.findByText('Submission pack · Tamarind Loans')).toBeTruthy();
    expect(sent.filter((r) => r.path === '/api/v1/documents/D-3501/versions/1')).toHaveLength(1);
    expect(body()).toContain('Test template');
    cleanup();

    sent = [];
    onDocument = () => json(404, { code: 'not_found', message: 'No.' });
    await open(item('W-3502'), 'Review the submission pack · v1');
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Open the full pack (PDF, 6.1 MB)' }));
    });
    expect(await screen.findByText('You can’t open this document.')).toBeTruthy();
    expect(body()).not.toContain('Submission pack · Tamarind Loans');
  });
});

describe('access (AC 18)', () => {
  it('401 on the decide shows signed out with next=/work/W-3502', async () => {
    onDecide = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    await click('Approve and submit');
    const link = await screen.findByRole('link', { name: /sign in/i });
    expect(link.getAttribute('href')).toContain('next=%2Fwork%2FW-3502');
  });

  it('403 on the decide shows the read-only view and no approved text', async () => {
    onDecide = () => {
      served = { ...item('W-3502'), tasks: [{ ...item('W-3502').tasks[0], you_can_act: false, cannot_act_reason: 'not_your_role' }] };
      return json(403, { code: 'forbidden', message: 'No.' });
    };
    await open(item('W-3502'), 'Review the submission pack · v1');
    await ready();
    await click('Approve and submit');
    expect(await ws().findByText('This decision needs a document reviewer.')).toBeTruthy();
    expect(buttons()).not.toContain('Approve and submit');
    expect(body()).not.toMatch(/Submitted|Decision recorded on|Approved by/);
  });

  it('403 and 404 on the read look the same, with nothing of the RFP in the page', async () => {
    for (const name of ['W-3502', 'W-3503']) {
      for (const code of [403, 404]) {
        readAnswer = () => json(code, { code: code === 403 ? 'forbidden' : 'not_found', message: 'No.' });
        served = item(name);
        render(
          <AppShell>
            <WorkItemView id={name} tab="overview" />
          </AppShell>,
        );
        await screen.findByText(/isn.t open to you|can.t open|not open/i);
        for (const secret of ['Tamarind', 'TL-RFP-2026-014', 'procurement@', 'Submission pack']) expect(body()).not.toContain(secret);
        cleanup();
      }
    }
  });
});

describe('nothing on load or on a timer (AC 19)', () => {
  it('loading every W-35xx item sends only GETs, and 60 s of fake time sends no POST', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
    for (const name of ['W-3501', 'W-3501.next', 'W-3502', 'W-3503', 'W-3504', 'W-3505.approve', 'W-3506', 'W-3507', 'W-3508', 'W-3509']) {
      const w = item(name);
      served = w;
      render(
        <AppShell>
          <WorkItemView id={w.id} tab="overview" />
        </AppShell>,
      );
      await screen.findByRole('heading', { level: 1 });
      cleanup();
    }
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    // a reviewer who can act is claimed on load (F-16, one claim per task revision); that is the only non-GET and it is not a decision
    expect(writes().filter((r) => !r.path.endsWith('/claim'))).toEqual([]);
    expect(posts('/decision')).toHaveLength(0);
    expect(posts('/steps')).toHaveLength(0);
  });
});

describe('phone (AC 20)', () => {
  it('draws no frame, goes back to the RFP (W-2101) on framed items and to the queue on W-3502, and keeps the same sections and words', async () => {
    phone();
    await open(item('W-3501'));
    expect(screen.queryByRole('navigation', { name: 'RFP' })).toBeNull();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect([...document.querySelectorAll('a')].find((a) => a.textContent?.includes('←'))).toMatchObject({ textContent: expect.stringContaining('RFP') });
    expect(document.querySelector('a[href="/work/W-2101"]')).toBeTruthy();
    expect(screen.getByRole('region', { name: 'What goes to the client' })).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Checks' })).toBeTruthy();
    expect(buttons()).toEqual(expect.arrayContaining(['Send for review', 'Edit cover letter']));
    cleanup();
    await open(item('W-3502'));
    expect([...document.querySelectorAll('a')].find((a) => a.textContent?.includes('←'))!.textContent).toContain('Queue');
    expect(body()).toContain('Goes to procurement@tamarindloans.example');
    cleanup();
    await open(item('W-3505.approve'));
    expect(document.querySelector('.work-state')!.textContent).toBe('Effect uncertain');
  });
});
