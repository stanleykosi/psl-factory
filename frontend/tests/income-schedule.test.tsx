// @vitest-environment jsdom
// F-33: the income schedule's work item (W-2701 to W-2711) drawn from E-WORK-ITEM `workspace`, with its writes: the review
// decided in place (E-TASK-CLAIM, E-TASK-DECIDE through useDecision) and the preparer's correction (E-WORK-STEP). Contract
// mock only; the fetch stub stands in for the backend. Money rules: amounts as returned, nothing computed, Unknown never 0.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2702',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
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

const posts = (suffix: string) => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const taskPosts = () => sent.filter((r) => r.method === 'POST' && r.path.startsWith('/api/v1/tasks/'));
const decided = (verdict: string, task = 'T-2702') => json(200, { task_id: task, verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-13T14:05:00Z', work_state: 'verified' });

beforeEach(() => {
  sent = [];
  readAnswer = null;
  who = 'finance_lead';
  onClaim = (body) => json(200, { task_id: 'T', revision: body.expected_revision, claimed_by: 'Ada Okafor' });
  onDecide = (body) => {
    const next = item(`W-2702.${body.verdict as string}`);
    served = next;
    return decided(body.verdict as string);
  };
  onStep = () => json(200, { work_id: 'W-2703', state: 'action_needed', revision: 5, outcome: 'done' });
  const fetchStub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    const body = text ? JSON.parse(text) : undefined;
    sent.push({ method: request.method, path: url.pathname, body, csrf: request.headers.get('X-CSRFToken') });
    if (url.pathname === '/api/v1/me') return json(200, read(`me.${who}.json`));
    if (request.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(url.pathname)) return readAnswer ? readAnswer() : json(200, served);
    if (request.method === 'POST' && url.pathname.endsWith('/claim')) return onClaim(body);
    if (request.method === 'POST' && url.pathname.endsWith('/decision')) return onDecide(body);
    if (request.method === 'POST' && url.pathname.endsWith('/steps')) return onStep(body);
    return json(404, { code: 'not_found', message: 'Not here.' });
  });
  vi.stubGlobal('fetch', withoutBellFeed(fetchStub));
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

const phone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));

async function open(body: WorkItem) {
  served = body;
  const view = render(
    <AppShell>
      <WorkItemView id={body.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: body.title });
  return view;
}

const ws = () => within(document.querySelector('.ws') as HTMLElement);
const buttons = () => ws().queryAllByRole('button').map((b) => b.textContent);
const status = () => document.querySelector('.work-state')!;
const ready = async () => waitFor(() => expect(ws().getByRole('button', { name: 'Approve schedule' }).hasAttribute('disabled')).toBe(false));
const click = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const note = () => ws().getByLabelText(/^Note \(needed to/) as HTMLTextAreaElement;
/** What the page says about the write: its notices, the status tag and the Decide panel (not the station names or the facts strip). */
const said = () => [document.querySelector('.ws-notices'), status(), document.querySelector('.ws-idecide'), document.querySelector('.ws-side')].map((el) => el?.textContent ?? '').join(' ');
const factValue = (label: string) => [...document.querySelectorAll('.ws-fact')].find((f) => f.querySelector('dt')?.textContent === label)?.querySelector('dd')?.textContent;

describe('four states from data (AC 1, 8)', () => {
  it('W-2701 investigating: the figures, Chidi working with steps and sources, the agent tag, Ask Chidi, and no decide control', async () => {
    await open(item('W-2701'));
    expect(status().textContent).toBe('CHIDI INVESTIGATING');
    expect(status().className).toContain('agent');
    expect(ws().getByRole('heading', { name: 'Income detail · 38 rows' })).toBeTruthy();
    const rows = [...document.querySelectorAll('.ws-rows--figures .ws-row')].map((r) => r.textContent);
    expect(rows).toEqual(['Disaggregation31 ROWS', 'Reclassification5 ROWS', 'Additive2 ROWS', 'Possible duplicates2CHIDI CHECKING']);
    const checking = ws().getByText('CHIDI CHECKING');
    expect(checking.className).toContain('agent');
    expect(document.body.textContent).not.toMatch(/no duplicates|none/i);
    const card = document.querySelector('.ws-lineagent')!;
    expect(card.textContent).toContain('WORKING');
    expect(card.textContent).toContain('INCOME_DETAIL_OCT.XLSX · 38 ROWS');
    expect(card.textContent).toContain('2 ROWS MAY BE DUPLICATES');
    expect(card.textContent).toContain('MAPPING RUN MR-0044');
    expect(card.textContent).toContain('Started 11:20');
    expect(card.querySelector('.psl-agent')).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Ask Chidi' }).getAttribute('href')).toBe('/assistant');
    // UI-2-2: the started time and Ask Chidi are the card's own footer row
    const foot = card.querySelector('.psl-agent__foot')!;
    expect(foot.textContent).toBe('Started 11:20Ask Chidi');
    expect(ws().getAllByRole('link', { name: 'Ask Chidi' })).toHaveLength(1);
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(document.querySelectorAll('.ws-stations .psl-station')).toHaveLength(5);
  });

  it('W-2702 review: the prepared schedule facts and the Decide panel with the backend basis and consequence', async () => {
    await open(item('W-2702'));
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect(ws().getByRole('heading', { name: 'Prepared schedule' })).toBeTruthy();
    expect(factValue('Report line · Service revenue')).toBe('₦12,400,000.00');
    expect(factValue('Detail rows')).toBe('38');
    expect(factValue('Duplicates resolved')).toBe('2 OF 2');
    expect(factValue('Prepared by')).toBe('BISI ADE');
    const panel = await ws().findByRole('region', { name: 'Decide · Schedules reviewer' });
    expect(within(panel).getByText("Approve the income detail for Service revenue, October. You didn't prepare it, so you can review it.")).toBeTruthy();
    expect(within(panel).getByText("Approving doesn't post anything. Exporting it as an accounting adjustment is a separate step with its own approval.")).toBeTruthy();
    expect(within(panel).getByLabelText('Note (needed to return or reject)')).toBeTruthy();
    await ready();
    expect(within(panel).getAllByRole('button').map((b) => b.textContent)).toEqual(['Approve schedule', 'Return with a note', 'Reject']);
  });

  it('W-2703 returned: the reviewer’s words and the step’s consequence as returned, no D-RETURN note of our own (AC 16)', async () => {
    await open(item('W-2703'));
    expect(status().textContent).toBe('RETURNED · CORRECT AND RESUBMIT');
    expect(ws().getByText('Ada Okafor returned it on 13 Nov: “Row 12 is a reclassification, not a disaggregation.”')).toBeTruthy();
    expect(ws().getByText('What happens next: the schedule is prepared again and goes back to Ada Okafor. The returned version stays in the history.')).toBeTruthy();
    expect(buttons()).toEqual(['Correct and resubmit']);
    expect(document.body.textContent).not.toMatch(/every return|backend only waits/i);
  });

  it('W-2704 verified: VERIFIED from the status, the facts as returned, Next as returned, no Export or Withdraw (AC 9)', async () => {
    await open(item('W-2704'));
    expect(status().textContent).toBe('VERIFIED');
    expect(factValue('Approved by')).toBe('ADA OKAFOR · 13 NOV');
    expect(factValue('Verification scope')).toBe('THESE 38 ROWS ONLY');
    expect(factValue('Posted to the ledger')).toBe('NO');
    expect(ws().getByText("Optional: export the 7 additive and reclassification rows as an accounting adjustment for October's accounts.")).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Export|Withdraw/ })).toBeNull();
    expect(screen.queryByText(/can decide/)).toBeNull();
  });

  it('no board string is written in src (AC 1, 16)', () => {
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.(tsx?|css)$/.test(name) && !name.endsWith('schema.d.ts')) files.push(path);
      }
    };
    walk(join(__dirname, '../src'));
    const text = files.map((f) => readFileSync(f, 'utf8')).join('\n');
    for (const board of ['CHIDI INVESTIGATING', 'AWAITING FINANCE DECISION', 'CORRECT AND RESUBMIT', 'THESE 38 ROWS', 'Service revenue', 'backend only waits', 'every return']) expect(text, board).not.toContain(board);
  });
});

describe('money and counts as returned (AC 2 to 5)', () => {
  it('the report line is the backend decimal string at desktop and phone; a changed amount shows exactly', async () => {
    await open(item('W-2702'));
    expect(factValue('Report line · Service revenue')).toBe('₦12,400,000.00');
    cleanup();
    phone();
    await open(item('W-2702'));
    expect(factValue('Report line · Service revenue')).toBe('₦12,400,000.00');
    expect(document.body.textContent).not.toContain('12.4M');
    cleanup();
    const changed = item('W-2702');
    changed.workspace!.sections[0].items[0].money = { amount: '12400000.10', currency: 'NGN', unknown: false };
    await open(changed);
    expect(factValue('Report line · Service revenue')).toBe('₦12,400,000.10');
  });

  it('changing a figure or a fact changes only that text; the section title and the other values stay as sent', async () => {
    const figures = item('W-2701');
    figures.workspace!.sections[0].items[0].value = '30 ROWS';
    await open(figures);
    expect(ws().getByRole('heading', { name: 'Income detail · 38 rows' })).toBeTruthy();
    expect(ws().getByText('30 ROWS')).toBeTruthy();
    expect(ws().getByText('5 ROWS')).toBeTruthy();
    cleanup();
    const facts = item('W-2702');
    facts.workspace!.sections[0].items[2].value = '1 OF 2';
    await open(facts);
    expect(factValue('Duplicates resolved')).toBe('1 OF 2');
    expect(factValue('Detail rows')).toBe('38');
    cleanup();
    const next = item('W-2704');
    next.workspace!.next = ['Optional: export the 6 rows.'];
    await open(next);
    expect(ws().getByText('Optional: export the 6 rows.')).toBeTruthy();
    expect(factValue('Verification scope')).toBe('THESE 38 ROWS ONLY');
  });

  it('W-2707: an unknown amount and a missing row count read Unknown, never 0, blank or a dash', async () => {
    await open(item('W-2707'));
    expect(factValue('Report line · Service revenue')).toBe('Unknown');
    expect(factValue('Detail rows')).toBe('Unknown');
    const text = document.querySelector('.ws')!.textContent!;
    expect(text).not.toContain('₦0');
    expect(text).not.toContain('0.00');
    for (const dd of document.querySelectorAll('.ws-fact dd')) expect(dd.textContent!.trim()).not.toMatch(/^(|-|—)$/);
  });

  it('every fixture is marked sample because the record says so; a copy with sample false is not (AC 5)', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    for (const id of ['W-2701', 'W-2702', 'W-2703', 'W-2704', 'W-2705', 'W-2706', 'W-2707', 'W-2708', 'W-2709', 'W-2710', 'W-2711']) {
      await open(item(id));
      expect(document.querySelector('.work-lineend')!.textContent, id).toContain('SAMPLE DATA');
      cleanup();
    }
    await open({ ...item('W-2702'), sample: false });
    expect(document.querySelector('.work-lineend')!.textContent).not.toContain('SAMPLE DATA');
  });
});

describe('the hold and who may act (AC 6, 7, 12)', () => {
  it('W-2706 reviewer not set: the backend’s hold, no Decide panel, no button, no task write and no reviewer named', async () => {
    await open(item('W-2706'));
    expect(status().textContent).toBe('SETUP NEEDED');
    expect(factValue('Who reviews schedules')).toBe('NOT SET');
    expect(ws().getByText('An admin sets Who reviews schedules in Setup · Finance rules. The review starts then.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(document.querySelector('main')!.textContent).not.toContain('Ada Okafor');
    expect(document.body.textContent).not.toContain('Schedules reviewer');
    await new Promise((r) => setTimeout(r, 50));
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });

  it('W-2709 offers only Approve and Return; W-2711 draws neither the revoke nor the post step; W-2710 keeps the decision-page link', async () => {
    await open(item('W-2709'));
    await ready();
    expect(buttons()).toEqual(['Approve schedule', 'Return with a note']);
    expect(ws().getByLabelText('Note (needed to return)')).toBeTruthy();
    cleanup();
    await open(item('W-2711'));
    expect(buttons()).toEqual([]);
    expect(screen.queryByText('Withdraw approval')).toBeNull();
    expect(screen.queryByText('Post to the ledger')).toBeNull();
    cleanup();
    sent = [];
    await open(item('W-2710'));
    expect(ws().getByRole('link', { name: 'Open the review' }).getAttribute('href')).toBe('/work/W-2710/decide?task=T-2710');
    expect(buttons()).toEqual([]);
    expect(taskPosts()).toHaveLength(0);
  });

  it('W-2705 (you prepared it) and W-2708 (not your role) show the reason, no button and send no claim', async () => {
    await open(item('W-2705'));
    expect(await ws().findByText('You prepared Schedule v1, so someone else must review it.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    cleanup();
    await open(item('W-2708'));
    expect(await ws().findByText('This decision needs a Schedules reviewer.')).toBeTruthy();
    expect(ws().getByText('You can read it, but you can’t approve, return or reject it.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    await new Promise((r) => setTimeout(r, 50));
    expect(taskPosts()).toHaveLength(0);
  });

  it('the controls follow you_can_act only: finance_lead, ceo and pm see the same buttons on the same item', async () => {
    for (const persona of ['finance_lead', 'ceo', 'pm']) {
      who = persona;
      sent = [];
      await open(item('W-2702'));
      await ready();
      expect(buttons(), persona).toEqual(['Approve schedule', 'Return with a note', 'Reject']);
      cleanup();
      await open(item('W-2708'));
      expect(await ws().findByText('This decision needs a Schedules reviewer.')).toBeTruthy();
      expect(buttons(), persona).toEqual([]);
      cleanup();
    }
    const source = readFileSync(join(__dirname, '../src/features/workspace/InlineDecide.tsx'), 'utf8');
    expect(source).not.toMatch(/useMe|\/me\b/);
  });
});

describe('approve, return and reject (AC 9 to 11)', () => {
  it('claims once, then one decision with CSRF and {verdict, expected_revision}; a double press sends one; Verified only from the re-read', async () => {
    await open(item('W-2702'));
    await ready();
    expect(posts('/api/v1/tasks/T-2702/claim')).toHaveLength(1);
    await act(async () => {
      const approve = ws().getByRole('button', { name: 'Approve schedule' });
      fireEvent.click(approve);
      fireEvent.click(approve);
    });
    await waitFor(() => expect(status().textContent).toBe('VERIFIED'));
    const [decision] = posts('/api/v1/tasks/T-2702/decision');
    expect(posts('/decision')).toHaveLength(1);
    expect(decision.body).toEqual({ verdict: 'approve', expected_revision: 1 });
    expect(decideRequest(decision.body)).toBe(true);
    expect(decision.csrf).toBe('mock-csrf-finance_lead');
    expect(screen.getByText('Schedule v1 is approved')).toBeTruthy();
    expect(factValue('Posted to the ledger')).toBe('NO');
  });

  it('a 200 whose re-read still serves the review never says Verified', async () => {
    onDecide = (body) => decided(body.verdict as string);
    await open(item('W-2702'));
    await ready();
    await click('Approve schedule');
    await waitFor(() => expect(posts('/decision')).toHaveLength(1));
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-2702').length).toBeGreaterThanOrEqual(3));
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect(said()).not.toMatch(/verified/i);
    expect(said()).toContain('Schedule v1 is approved');
  });

  it('return and reject need a note: empty, blank and over 2000 characters send nothing; with a note one POST with the trimmed note', async () => {
    await open(item('W-2702'));
    await ready();
    await click('Return with a note');
    expect(await screen.findByText('Add a note to return it.')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(note()));
    fireEvent.change(note(), { target: { value: '   ' } });
    await click('Reject');
    expect(await screen.findByText('Add a note to reject it.')).toBeTruthy();
    fireEvent.change(note(), { target: { value: 'x'.repeat(2001) } });
    await click('Return with a note');
    expect(await screen.findByText('Keep the note to 2000 characters or fewer.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    fireEvent.change(note(), { target: { value: '  Row 12 is a reclassification.  ' } });
    await click('Return with a note');
    await waitFor(() => expect(status().textContent).toBe('RETURNED · CORRECT AND RESUBMIT'));
    expect(posts('/decision').map((p) => p.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'Row 12 is a reclassification.' }]);
    expect(decideRequest(posts('/decision')[0].body)).toBe(true);
  });

  it('reject with a note shows the rejected state the re-read returns', async () => {
    await open(item('W-2702'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Not for October.' } });
    await click('Reject');
    await waitFor(() => expect(status().textContent).toBe('REJECTED'));
    expect(posts('/decision')[0].body).toEqual({ verdict: 'reject', expected_revision: 1, note: 'Not for October.' });
    expect(screen.getByText('Schedule v1 was rejected')).toBeTruthy();
  });

  it('the error under the note is announced', async () => {
    await open(item('W-2702'));
    await ready();
    await click('Reject');
    const message = await screen.findByText('Add a note to reject it.');
    expect(note().getAttribute('aria-invalid')).toBe('true');
    expect(note().getAttribute('aria-describedby')).toContain(message.id || message.closest('[id]')!.id);
  });
});

describe('refusals and uncertain writes (AC 13, 14, 17)', () => {
  it('403 on decide: read-only from the re-read reason, no approved', async () => {
    onDecide = () => {
      served = { ...item('W-2702'), tasks: [{ ...item('W-2702').tasks[0], you_can_act: false, cannot_act_reason: 'not_your_role' }] };
      return json(403, { code: 'forbidden', message: 'No.' });
    };
    await open(item('W-2702'));
    await ready();
    await click('Approve schedule');
    expect(await ws().findByText('This decision needs a Schedules reviewer.')).toBeTruthy();
    expect(said()).not.toMatch(/approved/i);
    expect(buttons().filter((b) => b === 'Approve schedule')).toHaveLength(0);
  });

  it('409: the stale view keeps the note; a new press after Review the latest carries the new revision', async () => {
    const newer = { ...item('W-2702'), revision: 2, tasks: [{ ...item('W-2702').tasks[0], revision: 2 }] };
    onDecide = () => {
      served = newer;
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-2702'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Check row 12.' } });
    await click('Return with a note');
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(1);
    await click('Review the latest');
    await ready();
    expect(note().value).toBe('Check row 12.');
    onDecide = (body) => decided(body.verdict as string);
    await click('Return with a note');
    await waitFor(() => expect(posts('/decision')).toHaveLength(2));
    expect(posts('/decision')[1].body!.expected_revision).toBe(2);
  });

  it('422: the backend message under the note', async () => {
    onDecide = () => json(422, { code: 'invalid', message: 'Say which row.', fields: [{ name: 'note', message: 'Say which row.' }] });
    await open(item('W-2702'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Fix it.' } });
    await click('Return with a note');
    expect(await ws().findByText('Say which row.')).toBeTruthy();
  });

  for (const [name, answer] of [
    ['a 500', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
  ] as const) {
    it(`${name} re-reads first, shows the uncertain notice, says nothing was approved and never sends again by itself`, async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
      onDecide = answer as unknown as Handler;
      await open(item('W-2702'));
      await ready();
      const before = sent.length;
      await click('Approve schedule');
      expect(await screen.findByText(/We couldn.t confirm your decision/)).toBeTruthy();
      const after = sent.slice(before);
      expect(after[0].path).toBe('/api/v1/tasks/T-2702/decision');
      expect(after[1]).toMatchObject({ method: 'GET', path: '/api/v1/work/W-2702' });
      expect(said()).not.toMatch(/is approved|was returned|was rejected|verified/i);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(posts('/decision')).toHaveLength(1);
    }, 90_000);
  }

  it('401 on decide shows the signed-out state with next=/work/W-2702', async () => {
    onDecide = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await open(item('W-2702'));
    await ready();
    await click('Approve schedule');
    const link = await screen.findByRole('link', { name: /sign in/i });
    expect(link.getAttribute('href')).toContain('next=%2Fwork%2FW-2702');
  });

  it('403 and 404 on read look the same: no title, amount or fact; persona none gets it with no further call', async () => {
    for (const code of [403, 404]) {
      readAnswer = () => json(code, { code: code === 403 ? 'forbidden' : 'not_found', message: 'No.' });
      served = item('W-2702');
      render(
        <AppShell>
          <WorkItemView id="W-2702" tab="overview" />
        </AppShell>,
      );
      await screen.findByText(/isn.t open to you|can.t open|not open/i);
      expect(document.body.textContent).not.toContain('Income detail');
      expect(document.body.textContent).not.toContain('12,400,000');
      cleanup();
    }
    who = 'none';
    sent = [];
    readAnswer = () => json(403, { code: 'forbidden', message: 'No.' });
    render(
      <AppShell>
        <WorkItemView id="W-2702" tab="overview" />
      </AppShell>,
    );
    await screen.findByText('No sections are open to your role yet.');
    await new Promise((r) => setTimeout(r, 50));
    expect(sent.filter((r) => r.path.startsWith('/api/v1/work/'))).toHaveLength(0);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });
});

describe('correct and resubmit (AC 15)', () => {
  it('opens the required choice with nothing selected; sends one step with a UUID key; a retry after a 500 reuses it; the re-read is back in review', async () => {
    await open(item('W-2703'));
    await click('Correct and resubmit');
    const group = ws().getByRole('radiogroup', { name: /Row 12 relationship/ });
    const options = within(group).getAllByRole('radio');
    expect(options.map((o) => o.textContent)).toEqual(['Disaggregation', 'Reclassification', 'Additive']);
    expect(options.every((o) => o.getAttribute('aria-checked') !== 'true' && !(o as HTMLInputElement).checked)).toBe(true);
    const submit = () => ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!;
    await act(async () => {
      fireEvent.click(submit());
    });
    expect(posts('/steps')).toHaveLength(0);
    fireEvent.click(within(group).getByRole('radio', { name: 'Reclassification' }));
    onStep = () => json(500, { code: 'server_error', message: 'Down.' });
    await act(async () => {
      fireEvent.click(submit());
    });
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    expect(document.body.textContent).not.toMatch(/resubmitted/i);
    onStep = () => {
      served = item('W-2703.next');
      return json(200, { work_id: 'W-2703', state: 'action_needed', revision: 5, outcome: 'done', message: 'Sent back for review.' });
    };
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button').find((b) => b.textContent === 'Try again' && (b as HTMLButtonElement).type === 'submit') ?? submit());
    });
    await waitFor(() => expect(status().textContent).toBe('AWAITING FINANCE DECISION'));
    const [first, second] = posts('/api/v1/work/W-2703/steps');
    expect(first.body).toMatchObject({ expected_revision: 4, step: 'correct_and_resubmit', inputs: { row_12_relationship: 'reclassification' } });
    expect(stepRequest(first.body)).toBe(true);
    expect(first.csrf).toBe('mock-csrf-finance_lead');
    expect(first.body!.idempotency_key).toMatch(UUID);
    expect(second.body!.idempotency_key).toBe(first.body!.idempotency_key);
    expect(await ws().findByText('You prepared Schedule v1, so someone else must review it.')).toBeTruthy();
    expect(buttons().filter((b) => b === 'Approve schedule')).toHaveLength(0);
    expect(taskPosts()).toHaveLength(0);
  });

  it('after a return on W-2702 the correction step opens the same form', async () => {
    await open(item('W-2702.return'));
    await click('Correct and resubmit');
    expect(ws().getByRole('radiogroup', { name: /Row 12 relationship/ })).toBeTruthy();
  });
});

describe('phone (AC 18)', () => {
  it('Return with a note and Reject open the Drawer with the note; Cancel closes it and returns focus', async () => {
    phone();
    await open(item('W-2702'));
    await ready();
    expect(buttons()).toEqual(['Approve schedule', 'Return with a note', 'Reject']);
    await click('Reject');
    const dialog = await screen.findByRole('dialog', { name: 'Reject' });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));
    });
    expect(await within(dialog).findByText('Add a note to reject it.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement?.textContent).toBe('Reject'));
  });
});

describe('round 2: an unsettled effect is never an outcome (TECH-1-1)', () => {
  const uncertainItem = (): WorkItem => {
    const body = item('W-2702');
    return { ...body, state: 'effect_uncertain', revision: 2, tasks: [{ ...body.tasks[0], you_can_act: false, cannot_act_reason: 'already_decided', revision: 2 }], workspace: { ...body.workspace!, revision: 2, steps: [] } };
  };
  for (const verdict of ['approve', 'return', 'reject'] as const) {
    it(`${verdict}: a 200 with work_state effect_uncertain shows "result not confirmed", never the outcome`, async () => {
      onDecide = (body) => {
        served = uncertainItem();
        return json(200, { task_id: 'T-2702', verdict: body.verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-13T14:05:00Z', work_state: 'effect_uncertain' });
      };
      await open(item('W-2702'));
      await ready();
      if (verdict !== 'approve') fireEvent.change(note(), { target: { value: 'Check row 12.' } });
      await click(verdict === 'approve' ? 'Approve schedule' : verdict === 'return' ? 'Return with a note' : 'Reject');
      expect(await screen.findByText('Schedule v1: result not confirmed')).toBeTruthy();
      expect(screen.getByText('We are checking what happened. Nothing was sent again.')).toBeTruthy();
      expect(said()).not.toMatch(/is approved|was returned|was rejected|verified/i);
      expect(document.querySelector('.ws-live .psl-callout--success, .ws-live [class*="success"]')).toBeNull();
      expect(posts('/decision')).toHaveLength(1);
    });
  }

  it('a 200 saying verified whose re-read is effect_uncertain with a reconcile is not confirmed either', async () => {
    onDecide = (body) => {
      served = { ...uncertainItem(), reconcile: { question: 'Was it recorded?' } } as unknown as WorkItem;
      return decided(body.verdict as string);
    };
    await open(item('W-2702'));
    await ready();
    await click('Approve schedule');
    expect(await screen.findByText('Schedule v1: result not confirmed')).toBeTruthy();
    expect(said()).not.toMatch(/is approved|verified/i);
  });
});

describe('round 2: the decision notice goes when the item moves on (TECH-1-3)', () => {
  it('after Return, Correct and resubmit leaves no "was returned" notice', async () => {
    await open(item('W-2702'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Row 12.' } });
    await click('Return with a note');
    expect(await screen.findByText('Schedule v1 was returned')).toBeTruthy();
    await click('Correct and resubmit');
    fireEvent.click(ws().getByRole('radio', { name: 'Reclassification' }));
    onStep = () => {
      served = { ...item('W-2703.next'), id: 'W-2702' };
      return json(200, { work_id: 'W-2702', state: 'action_needed', revision: 5, outcome: 'done' });
    };
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!);
    });
    await waitFor(() => expect(status().textContent).toBe('AWAITING FINANCE DECISION'));
    expect(screen.queryByText('Schedule v1 was returned')).toBeNull();
  });
});

describe('round 2: one page re-read after an uncertain decide (TECH-1-4)', () => {
  it('a 500 is followed by exactly two reads of the item: the reconcile, then the page', async () => {
    // the item reads after the decision answer slowly, so a page re-read sent while the reconcile is still reading shows up
    onDecide = () => {
      readAnswer = slow as unknown as () => Response;
      return json(500, { code: 'server_error', message: 'Down.' });
    };
    await open(item('W-2702'));
    await ready();
    const slow = vi.fn(async () => {
      await new Promise((r) => setTimeout(r, 80));
      return json(200, served);
    });
    const before = sent.length;
    await click('Approve schedule');
    expect(await screen.findByText(/We couldn.t confirm your decision/)).toBeTruthy();
    await new Promise((r) => setTimeout(r, 400));
    const reads = sent.slice(before).filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-2702');
    expect(reads).toHaveLength(2);
  });
});

describe('round 2: the read-only branch keeps the income stations and agent (TECH-1-2)', () => {
  it('W-2701 without a workspace revision still draws the five stations and Chidi’s card', async () => {
    const body = item('W-2701');
    delete (body.workspace as { revision?: number }).revision;
    await open(body);
    expect(document.querySelectorAll('.ws-stations .psl-station')).toHaveLength(5);
    expect(document.querySelector('.ws-lineagent')!.textContent).toContain('WORKING');
    expect(document.querySelectorAll('section[aria-label="Agent at work"]')).toHaveLength(1);
    expect(document.querySelectorAll('section[aria-label="Stations"]')).toHaveLength(1);
  });
});

describe('round 2: other lines are unchanged by the income-line frame edits (TECH-1-5)', () => {
  it('W-2304 decided (minutes) still draws its decided-task card and its screen-reader station track', async () => {
    await open(item('W-2304.approve'));
    expect(screen.getByText('Only a PMO Lead can decide.')).toBeTruthy();
    expect(document.querySelector('.cmp-sr section[aria-label="Stations"]')).toBeTruthy();
    expect(document.querySelector('.ws-stations')).toBeNull();
  });

  it('W-2411 (issue) keeps its screen-reader station track and agent card, and draws none of the income line’s', async () => {
    await open(item('W-2411'));
    expect(document.querySelector('.cmp-sr section[aria-label="Stations"]')).toBeTruthy();
    expect(document.querySelector('.cmp-sr section[aria-label="Agent at work"]')).toBeTruthy();
    expect(document.querySelector('.ws-stations, .ws-lineagent, .ws-ministations')).toBeNull();
  });
});

describe('round 3: banner tone, panel type, notices and the uncertain fixture', () => {
  const banner = () => [...document.querySelectorAll('.ws-note.psl-callout')].map((el) => [...el.classList].find((c) => c.startsWith('psl-callout--')));

  it('UI-2-1: the returned and rejected quotes are the problem callout, from the stopped station and status tone', async () => {
    await open(item('W-2703'));
    expect(banner()).toEqual(['psl-callout--problem']);
    cleanup();
    await open(item('W-2702.reject'));
    expect(banner()).toEqual(['psl-callout--problem']);
    cleanup();
    await open(item('W-2704'));
    expect(banner()).toEqual([]);
  });

  it('UI-2-1: every other line keeps its banner exactly as before (weekly W-2209, issue W-2412 and W-2414, minutes W-2304, document review W-2901)', async () => {
    for (const [id, expected] of [
      ['W-2209', ['psl-callout--warning']],
      ['W-2412', ['psl-callout--problem']],
      ['W-2414', ['psl-callout--success']],
      ['W-2304', []],
      ['W-2901', []],
    ] as const) {
      who = id === 'W-2209' ? 'pm' : id.startsWith('W-24') || id === 'W-2304' || id === 'W-2901' ? 'pm' : who;
      await open(item(id));
      expect(banner(), id).toEqual(expected);
      cleanup();
    }
  });

  it('UI-2-3: the note label is "Note" with the muted parenthetical; the consequences are the panel’s small print', async () => {
    await open(item('W-2702'));
    await ready();
    const label = document.querySelector('.ws-idecide .psl-label')!;
    expect(label.textContent).toBe('Note (needed to return or reject)');
    expect(label.querySelector('.psl-opt')!.textContent).toBe('(needed to return or reject)');
    const after = [...document.querySelectorAll('.ws-idecide__after .ws-consequence')].map((p) => p.textContent);
    expect(after).toEqual(["Approving doesn't post anything. Exporting it as an accounting adjustment is a separate step with its own approval.", "Rejecting stops this schedule: it isn't used for October's accounts."]);
  });

  it('UX-2-2: the Reject consequence is the step’s returned text; a step without one draws none', async () => {
    const body = item('W-2702');
    delete body.workspace!.steps![2].consequence;
    await open(body);
    await ready();
    expect([...document.querySelectorAll('.ws-idecide__after .ws-consequence')]).toHaveLength(1);
    expect(screen.queryByText(/Rejecting stops this schedule/)).toBeNull();
  });

  it('TECH-2-1: a decide after a step’s done notice shows its own outcome', async () => {
    const body = item('W-2702');
    body.workspace!.steps = [...body.workspace!.steps!, { key: 'refresh_figures', label: 'Refresh figures', emphasis: 'secondary', applies_to: 'workspace' }];
    onStep = () => json(200, { work_id: 'W-2702', state: 'action_needed', revision: 1, outcome: 'done', message: 'Figures refreshed.' });
    await open(body);
    await ready();
    await click('Refresh figures');
    expect(await screen.findByText('Figures refreshed.')).toBeTruthy();
    await click('Approve schedule');
    expect(await screen.findByText('Schedule v1 is approved')).toBeTruthy();
    expect(screen.queryByText('Figures refreshed.')).toBeNull();
  });

  it('TECH-2-1: a decide after a step notice whose effect is unsettled shows "result not confirmed"', async () => {
    const body = item('W-2712');
    body.workspace!.steps = [...body.workspace!.steps!, { key: 'refresh_figures', label: 'Refresh figures', emphasis: 'secondary', applies_to: 'workspace' }];
    onStep = () => json(200, { work_id: 'W-2712', state: 'action_needed', revision: 1, outcome: 'done', message: 'Figures refreshed.' });
    onDecide = (b) => {
      served = item(`W-2712.${b.verdict as string}`);
      return json(200, { task_id: 'T-2712', verdict: b.verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-13T14:05:00Z', work_state: served.state });
    };
    await open(body);
    await ready();
    await click('Refresh figures');
    expect(await screen.findByText('Figures refreshed.')).toBeTruthy();
    await click('Approve schedule');
    expect(await screen.findByText('Schedule v1: result not confirmed')).toBeTruthy();
    expect(said()).not.toMatch(/is approved|verified/i);
  });

  it('W-2712 sidecars: approve, return and reject each come back effect_uncertain and are never worded as an outcome', async () => {
    for (const verdict of ['approve', 'return', 'reject'] as const) {
      onDecide = (b) => {
        served = item(`W-2712.${b.verdict as string}`);
        return json(200, { task_id: 'T-2712', verdict: b.verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-13T14:05:00Z', work_state: served.state });
      };
      await open(item('W-2712'));
      await ready();
      if (verdict !== 'approve') fireEvent.change(note(), { target: { value: 'Check row 12.' } });
      await click(verdict === 'approve' ? 'Approve schedule' : verdict === 'return' ? 'Return with a note' : 'Reject');
      expect(await screen.findByText('Schedule v1: result not confirmed'), verdict).toBeTruthy();
      expect(status().textContent).toBe('DECISION NOT CONFIRMED');
      expect(said(), verdict).not.toMatch(/is approved|was returned|was rejected|verified/i);
      cleanup();
    }
  });
});
