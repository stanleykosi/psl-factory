// @vitest-environment jsdom
// F-35: the leadership report's work item (W-3201 to W-3212) drawn from E-WORK-ITEM `workspace`, with its writes: the
// leadership review decided in place (E-TASK-CLAIM, E-TASK-DECIDE through F-33's InlineDecide over useDecision) and "Send for
// leadership review" (E-WORK-STEP) only where the backend offers it. Contract mock only; the fetch stub stands in for the
// backend. Nothing says sent, delivered or received unless the re-read item says so; the page counts nothing.
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
  usePathname: () => '/work/W-3202',
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
const decided = (verdict: string, task = 'T-3202', state = 'processing') => json(200, { task_id: task, verdict, decided_by: 'Folake Bello', decided_at: '2026-11-03T08:10:00Z', work_state: state });

beforeEach(() => {
  sent = [];
  readAnswer = null;
  who = 'ceo';
  onClaim = (body) => json(200, { task_id: 'T', revision: body.expected_revision, claimed_by: 'Folake Bello' });
  onDecide = (body) => {
    served = item(`W-3202.${body.verdict as string}`);
    return decided(body.verdict as string, 'T-3202', served.state);
  };
  onStep = () => json(200, { work_id: 'W-3205', state: 'action_needed', revision: 4, outcome: 'done' });
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
const ready = async (label = 'Approve and send') => waitFor(() => expect(ws().getByRole('button', { name: label }).hasAttribute('disabled')).toBe(false));
const click = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const note = () => ws().getByLabelText(/^Note \(needed to/) as HTMLTextAreaElement;
const rows = (kind: string) => [...document.querySelectorAll(`.ws-rows--${kind} .ws-row`)].map((r) => r.textContent);
const figure = (label: string) => [...document.querySelectorAll('.ws-rows--figures .ws-row')].find((r) => r.textContent?.startsWith(label));
/** Without the backend's Next lines, which may name what the factory waits for ("before marking it received"). */
const withoutNext = (text: string) => (served.workspace?.next ?? []).reduce((rest, line) => rest.replace(line, ''), text);
/** What the page says about the write: its notices, the status tag and the side column (not the screen-reader facts strip). */
const said = () => withoutNext([document.querySelector('.ws-notices'), status(), document.querySelector('.ws-side')].map((el) => el?.textContent ?? '').join(' '));
/** The words drawn on the page: the status and the workspace (the screen-reader facts and stations carry the line's names). */
const pageWords = (body: WorkItem) => {
  let text = `${status().textContent} ${document.querySelector('.ws')!.textContent}`;
  for (const line of body.workspace?.next ?? []) text = text.replace(line, '');
  return text;
};
const banner = () => [...document.querySelectorAll('.ws-note.psl-callout')].map((el) => [...el.classList].find((c) => c.startsWith('psl-callout--')));
const NO_RESEND = /^(Resend|Send again|Try sending|Confirm what happened)/;

describe('four states from data (AC 1, 7, 8, 10)', () => {
  it('W-3201 drafting: the access note as an information banner, Tola working beside it with steps and sources, no control', async () => {
    await open(item('W-3201'));
    expect(status().textContent).toBe('DRAFTING');
    expect(status().className).toContain('agent');
    expect(ws().getByText("The report only uses records you can see. Projects you can't see are left out and counted as left out, never counted as zero.")).toBeTruthy();
    expect(banner()).toEqual(['psl-callout--info']);
    const card = document.querySelector('.ws-side .ws-lineagent')!;
    expect(card.textContent).toContain('Tola');
    expect(card.textContent).toContain('WORKING');
    expect(card.textContent).toContain('step 3 of 4');
    for (const source of ['5 PROJECTS · 41 MEETINGS · 12 ISSUES', '3 MILESTONES COMPLETE · 2 INVOICES VERIFIED', 'ESC-0011 · ESC-0012']) expect(card.textContent).toContain(source);
    // "Send for leadership review" is Tola's fourth step, not a button
    expect(within(card as HTMLElement).getByText('Send for leadership review').closest('.psl-step')).toBeTruthy();
    expect(card.querySelector('.psl-agent__foot')!.textContent).toBe('Started 01 Nov 08:00Ask Tola');
    expect(ws().getAllByRole('link', { name: 'Ask Tola' }).map((l) => l.getAttribute('href'))).toEqual(['/assistant']);
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide, .ws-stations')).toBeNull();
    expect(document.querySelectorAll('section[aria-label="Agent at work"]')).toHaveLength(1);
    await new Promise((r) => setTimeout(r, 50));
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });

  it('W-3202 review: the report figures as returned and the Decide panel with the basis; no report link', async () => {
    await open(item('W-3202'));
    expect(status().textContent).toBe('YOUR REVIEW');
    expect(ws().getByRole('heading', { name: 'Monthly report v1' })).toBeTruthy();
    expect(rows('figures')).toEqual(['Projects covered5 OF 5', 'Milestones completed3', 'Open escalations2', 'Invoices verified · paid is reported by Finance2']);
    const panel = await ws().findByRole('region', { name: 'Decide · Leadership reviewer' });
    expect(within(panel).getByText('Approving sends this exact version to the audience. Who reviews is set in Setup › Rules.')).toBeTruthy();
    expect(within(panel).getByLabelText('Note (needed to return)')).toBeTruthy();
    await ready();
    expect(within(panel).getAllByRole('button').map((b) => b.textContent)).toEqual(['Approve and send', 'Return with a note']);
    expect(document.body.textContent).not.toMatch(/Open the (full )?report|sends to the client/);
    expect(document.querySelector('a[href^="/reports"]')).toBeNull();
  });

  it('W-3203 tuesday: published without review, one row per recipient, CHECKING amber and never received, Next as returned', async () => {
    const body = item('W-3203');
    await open(body);
    expect(status().textContent).toBe('PUBLISHED · NO REVIEW');
    expect(status().className).toContain('done');
    expect(banner()).toEqual(['psl-callout--success']);
    expect(ws().getByText('Internal Tuesday reports go out without review. Sent to 6 PMO staff on 10 Nov 09:00; 5 deliveries confirmed, 1 still checking.')).toBeTruthy();
    expect(rows('recipients')).toEqual(['5 PMO staffDELIVERED 10 Nov 09:00', 'Sola MartinsCHECKING Time unknown']);
    const checking = ws().getByText('CHECKING');
    expect(checking.className).toContain('waiting');
    expect(ws().getByText('DELIVERED').className).toContain('done');
    expect(ws().getByRole('heading', { name: 'Next' })).toBeTruthy();
    expect(ws().getByText("The factory checks the last delivery before marking it received. It won't resend until it knows.")).toBeTruthy();
    expect(pageWords(body)).not.toMatch(/received/i);
    expect(buttons().filter((b) => NO_RESEND.test(b ?? ''))).toEqual([]);
    expect(buttons()).toEqual([]);
  });

  it('W-3204 received: RECEIVED BY EVERY RECIPIENT from the status, the sentence and Next as returned, no report link', async () => {
    await open(item('W-3204'));
    expect(status().textContent).toBe('RECEIVED BY EVERY RECIPIENT');
    expect(banner()).toEqual(['psl-callout--success']);
    expect(ws().getByText("October's report was approved by Ifeoma Nwosu and delivered to all 4 recipients on 03 Nov, verified.")).toBeTruthy();
    expect(ws().getByText('Read it any time on Overview.')).toBeTruthy();
    expect(screen.queryByRole('link', { name: /Open the (full )?report/ })).toBeNull();
    expect(document.querySelector('a[href^="/reports"]')).toBeNull();
    expect(buttons()).toEqual([]);
  });

  it('RECEIVED BY EVERY RECIPIENT appears only on W-3204; W-3211 and the W-3209 approve sidecar never say received or delivered to all', async () => {
    for (const id of ['W-3201', 'W-3202', 'W-3203', 'W-3205', 'W-3206', 'W-3207', 'W-3208', 'W-3209', 'W-3210', 'W-3211', 'W-3212', 'W-3202.approve', 'W-3209.approve']) {
      const body = item(id);
      await open(body);
      expect(document.body.textContent, id).not.toContain('RECEIVED BY EVERY RECIPIENT');
      if (id === 'W-3211' || id === 'W-3209.approve') {
        expect(pageWords(body), id).not.toMatch(/received|delivered to all/i);
        expect(ws().getByText('CHECKING').className).toContain('waiting');
      }
      cleanup();
    }
  });

  it('no board string is written in src (AC 1)', () => {
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
    for (const board of ['YOUR REVIEW', 'PUBLISHED · NO REVIEW', 'RECEIVED BY EVERY RECIPIENT', 'PMO staff', 'Leadership reviewer', 'paid is reported by Finance', 'Approve and send', 'Send for leadership review']) expect(text, board).not.toContain(board);
  });
});

describe('the page computes nothing (AC 2 to 4)', () => {
  it('changing a figure changes only that value; changing a receipt changes neither the note sentence nor the header', async () => {
    const changed = item('W-3202');
    changed.workspace!.sections[0].items[0].value = '4 OF 5';
    await open(changed);
    expect(rows('figures')).toEqual(['Projects covered4 OF 5', 'Milestones completed3', 'Open escalations2', 'Invoices verified · paid is reported by Finance2']);
    cleanup();
    const tuesday = item('W-3203');
    const row = tuesday.workspace!.sections[1].items[0];
    row.receipt = 'uncertain';
    row.tag = { label: 'CHECKING', tone: 'uncertain' };
    await open(tuesday);
    expect(status().textContent).toBe('PUBLISHED · NO REVIEW');
    expect(ws().getByText('Internal Tuesday reports go out without review. Sent to 6 PMO staff on 10 Nov 09:00; 5 deliveries confirmed, 1 still checking.')).toBeTruthy();
    expect(rows('recipients')).toEqual(['5 PMO staffCHECKING 10 Nov 09:00', 'Sola MartinsCHECKING Time unknown']);
  });

  it('no changed file under src/features/workspace parses numbers or counts', () => {
    for (const name of ['Workspace.tsx', 'Sections.tsx', 'labels.ts']) {
      const source = readFileSync(join(__dirname, '../src/features/workspace', name), 'utf8');
      expect(source, name).not.toMatch(/parseFloat|Number\(|\.reduce\(/);
    }
  });

  it('W-3210: Open escalations reads Unknown (never 0, blank or a dash), the coverage line as returned, 3 OF 5, and no project name', async () => {
    await open(item('W-3210'));
    expect(figure('Open escalations')!.textContent).toBe('Open escalationsUnknown');
    expect(figure('Projects covered')!.textContent).toBe('Projects covered3 OF 5');
    expect(ws().getByText("2 projects are left out because you can't see them.")).toBeTruthy();
    for (const r of document.querySelectorAll('.ws-rows--figures .ws-row')) expect(r.lastElementChild!.textContent!.trim()).not.toMatch(/^(|0|-|—)$/);
    const titles = (read('projects/list.json') as { rows: { item: { title: string } }[] }).rows.map((r) => r.item.title);
    for (const title of titles) expect(document.body.textContent, title).not.toContain(title);
  });

  it('SEC-1-1: W-3210 shows only the visible projects’ records, in the figures and in Tola’s text; the left-out projects are only a count', async () => {
    await open(item('W-3210'));
    const text = document.body.textContent!;
    // the agent card is drawn (screen-reader copy while Tola is done), so its steps and sources are in the page
    expect(text).toContain("Gathered October's records you can see");
    expect(text).toContain('3 PROJECTS · 24 MEETINGS · 7 ISSUES');
    expect(text).toContain('2 MILESTONES COMPLETE · 1 INVOICE VERIFIED');
    // nothing from the full report (all five projects): no five-project source, no meeting or issue totals, no escalation id
    for (const hidden of ['5 PROJECTS', '41 MEETINGS', '12 ISSUES', '3 MILESTONES', '2 INVOICES', 'ESC-0011', 'ESC-0012']) expect(text, hidden).not.toContain(hidden);
    expect(text).not.toMatch(/ESC-\d+/);
    // no project of any kind is named or linked: no title, no case id, no link to a project page
    const projects = (read('projects/list.json') as { rows: { item: { title: string; case_id: string } }[] }).rows.map((r) => r.item);
    for (const { title, case_id: caseId } of projects) {
      expect(text, title).not.toContain(title);
      expect(text, caseId).not.toContain(caseId);
    }
    expect(text).not.toMatch(/\bP-\d{4}\b/);
    expect(document.querySelector('a[href^="/projects/"]')).toBeNull();
    // the left-out projects appear only as the backend's count
    expect(text.match(/left out/g)).toHaveLength(1);
  });

  it('every fixture is marked sample because the record says so; a copy with sample false is not', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    for (const id of ['W-3201', 'W-3202', 'W-3203', 'W-3204', 'W-3205', 'W-3206', 'W-3207', 'W-3208', 'W-3209', 'W-3210', 'W-3211', 'W-3212']) {
      await open(item(id));
      expect(document.querySelector('.work-lineend')!.textContent, id).toContain('SAMPLE DATA');
      cleanup();
    }
    await open({ ...item('W-3202'), sample: false });
    expect(document.querySelector('.work-lineend')!.textContent).not.toContain('SAMPLE DATA');
  });
});

describe('the hold and who may act (AC 5, 6, 13)', () => {
  it('W-3207 reviewer not set: the backend’s hold, no Decide panel, no button, no task write and no reviewer named', async () => {
    await open(item('W-3207'));
    expect(status().textContent).toBe('SETUP NEEDED');
    const fact = [...document.querySelectorAll('.ws-fact')].find((f) => f.querySelector('dt')?.textContent === 'Leadership reviewer');
    expect(fact?.querySelector('dd')?.textContent).toContain('NOT SET');
    expect(ws().getByText('An admin sets who reviews leadership reports in Setup › Rules. The review starts then.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(screen.queryByRole('region', { name: /Leadership reviewer/ })).toBeNull();
    expect(document.querySelector('main')!.textContent).not.toMatch(/Ifeoma|Approve and send/);
    await new Promise((r) => setTimeout(r, 50));
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });

  it('W-3206 (you prepared it) and W-3208 (not your role) show the reason, no button and send no claim', async () => {
    await open(item('W-3206'));
    expect(await ws().findByText('You prepared Monthly report v1, so someone else must review it.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    cleanup();
    await open(item('W-3208'));
    expect(await ws().findByText('This decision needs a Leadership reviewer.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    await new Promise((r) => setTimeout(r, 50));
    expect(taskPosts()).toHaveLength(0);
  });

  it('W-3201, W-3203, W-3204 and W-3211 draw no decide control; W-3211’s decided task opens nothing', async () => {
    for (const id of ['W-3201', 'W-3203', 'W-3204', 'W-3211']) {
      await open(item(id));
      expect(document.querySelector('.ws-idecide'), id).toBeNull();
      expect(screen.queryByRole('button', { name: /Approve|Return/ }), id).toBeNull();
      expect(screen.queryByRole('link', { name: /Open the decision|Open the review/ }), id).toBeNull();
      cleanup();
    }
    expect(taskPosts()).toHaveLength(0);
  });

  it('the controls follow you_can_act only: ceo, pm and finance_lead see the same buttons on the same item', async () => {
    for (const persona of ['ceo', 'pm', 'finance_lead']) {
      who = persona;
      sent = [];
      await open(item('W-3202'));
      await ready();
      expect(buttons(), persona).toEqual(['Approve and send', 'Return with a note']);
      cleanup();
      await open(item('W-3208'));
      expect(await ws().findByText('This decision needs a Leadership reviewer.')).toBeTruthy();
      expect(buttons(), persona).toEqual([]);
      cleanup();
    }
    for (const name of ['Workspace.tsx', 'Sections.tsx', 'labels.ts', 'InlineDecide.tsx']) {
      expect(readFileSync(join(__dirname, '../src/features/workspace', name), 'utf8'), name).not.toMatch(/useMe|api\/v1\/me\b/);
    }
  });
});

describe('approve and return (AC 11, 12)', () => {
  it('claims once, then one decision with CSRF and {verdict, expected_revision}; a double press sends one; the sent state only from the re-read', async () => {
    await open(item('W-3202'));
    await ready();
    expect(posts('/api/v1/tasks/T-3202/claim')).toHaveLength(1);
    await act(async () => {
      const approve = ws().getByRole('button', { name: 'Approve and send' });
      fireEvent.click(approve);
      fireEvent.click(approve);
    });
    await waitFor(() => expect(status().textContent).toBe('SENT · CHECKING DELIVERIES'));
    const [decision] = posts('/api/v1/tasks/T-3202/decision');
    expect(posts('/decision')).toHaveLength(1);
    expect(decision.body).toEqual({ verdict: 'approve', expected_revision: 1 });
    expect(decideRequest(decision.body)).toBe(true);
    expect(decision.csrf).toBe('mock-csrf-ceo');
    expect(await screen.findByText('Monthly report v1 is approved')).toBeTruthy();
    expect(rows('recipients')).toEqual(['CEONot yet', 'CTONot yet', 'PMO LeadNot yet', 'Finance LeadNot yet']);
    expect(ws().getByText('The factory marks it received when every delivery is confirmed.')).toBeTruthy();
    expect(pageWords(served)).not.toMatch(/received|delivered/i);
    expect(buttons().filter((b) => NO_RESEND.test(b ?? ''))).toEqual([]);
    expect(posts('/actions')).toHaveLength(0);
  });

  it('a 200 whose re-read still serves the review says neither sent nor received', async () => {
    onDecide = (body) => decided(body.verdict as string);
    await open(item('W-3202'));
    await ready();
    await click('Approve and send');
    await waitFor(() => expect(posts('/decision')).toHaveLength(1));
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3202').length).toBeGreaterThanOrEqual(3));
    expect(status().textContent).toBe('YOUR REVIEW');
    expect(said()).not.toMatch(/\bsent\b|received|delivered/i);
  });

  it('return needs a note: empty, blank and over 2000 characters send nothing; with a note one POST with the trimmed note', async () => {
    await open(item('W-3202'));
    await ready();
    await click('Return with a note');
    const message = await screen.findByText('Add a note to return it.');
    expect(document.activeElement).toBe(note());
    expect(note().getAttribute('aria-invalid')).toBe('true');
    expect(note().getAttribute('aria-describedby')).toContain(message.id || message.closest('[id]')!.id);
    fireEvent.change(note(), { target: { value: '   ' } });
    await click('Return with a note');
    expect(await screen.findByText('Add a note to return it.')).toBeTruthy();
    fireEvent.change(note(), { target: { value: 'x'.repeat(2001) } });
    await click('Return with a note');
    expect(await screen.findByText('Keep the note to 2000 characters or fewer.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    fireEvent.change(note(), { target: { value: '  Add the Lagoon Health escalation to the summary.  ' } });
    await click('Return with a note');
    await waitFor(() => expect(status().textContent).toBe('DRAFTING · RETURNED'));
    expect(posts('/decision').map((p) => p.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'Add the Lagoon Health escalation to the summary.' }]);
    expect(decideRequest(posts('/decision')[0].body)).toBe(true);
    expect(ws().getByText('Returned on 02 Nov: “Add the Lagoon Health escalation to the summary.”')).toBeTruthy();
    expect(await screen.findByText('Monthly report v1 was returned')).toBeTruthy();
  });
});

describe('refusals and uncertain writes (AC 14, 15, 17)', () => {
  it('403 on decide: read-only from the re-read reason, no approved', async () => {
    onDecide = () => {
      served = { ...item('W-3202'), tasks: [{ ...item('W-3202').tasks[0], you_can_act: false, cannot_act_reason: 'not_your_role' }] };
      return json(403, { code: 'forbidden', message: 'No.' });
    };
    await open(item('W-3202'));
    await ready();
    await click('Approve and send');
    expect(await ws().findByText('This decision needs a Leadership reviewer.')).toBeTruthy();
    expect(said()).not.toMatch(/approved|\bsent\b/i);
    expect(buttons().filter((b) => b === 'Approve and send')).toHaveLength(0);
  });

  it('409: the stale view keeps the note; a new press after Review the latest carries the new revision', async () => {
    const newer = { ...item('W-3202'), revision: 2, tasks: [{ ...item('W-3202').tasks[0], revision: 2 }] };
    onDecide = () => {
      served = newer;
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-3202'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Add the escalation.' } });
    await click('Return with a note');
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(1);
    await click('Review the latest');
    await ready();
    expect(note().value).toBe('Add the escalation.');
    onDecide = (body) => decided(body.verdict as string);
    await click('Return with a note');
    await waitFor(() => expect(posts('/decision')).toHaveLength(2));
    expect(posts('/decision')[1].body!.expected_revision).toBe(2);
  });

  it('422: the backend message under the note', async () => {
    onDecide = () => json(422, { code: 'invalid', message: 'Say which escalation.', fields: [{ name: 'note', message: 'Say which escalation.' }] });
    await open(item('W-3202'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Fix it.' } });
    await click('Return with a note');
    expect(await ws().findByText('Say which escalation.')).toBeTruthy();
  });

  it('W-3209: a decide answering effect_uncertain re-reads and shows "result not confirmed" and the backend’s checking delivery', async () => {
    onDecide = (body) => {
      served = item('W-3209.approve');
      return decided(body.verdict as string, 'T-3209', 'effect_uncertain');
    };
    const body = item('W-3209');
    await open(body);
    await ready();
    await click('Approve and send');
    expect(await screen.findByText('Monthly report v1: result not confirmed')).toBeTruthy();
    expect(status().textContent).toBe('SENT · DELIVERY NOT CONFIRMED');
    expect(rows('recipients').at(-1)).toBe('Finance LeadCHECKING Time unknown');
    expect(said()).not.toMatch(/is approved|received/i);
    expect(document.querySelector('.ws-live .psl-callout--success')).toBeNull();
    expect(buttons().filter((b) => NO_RESEND.test(b ?? ''))).toEqual([]);
    expect(posts('/decision')).toHaveLength(1);
    expect(posts('/actions')).toHaveLength(0);
  });

  for (const [name, answer] of [
    ['a 500', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['a timeout', () => Promise.reject(new DOMException('The operation timed out.', 'TimeoutError'))],
  ] as const) {
    it(`${name} on W-3202 re-reads first, shows the uncertain notice, says nothing was approved and never sends again by itself`, async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
      onDecide = answer as unknown as Handler;
      await open(item('W-3202'));
      await ready();
      const before = sent.length;
      await click('Approve and send');
      expect(await screen.findByText(/We couldn.t confirm your decision/)).toBeTruthy();
      const after = sent.slice(before);
      expect(after[0].path).toBe('/api/v1/tasks/T-3202/decision');
      expect(after[1]).toMatchObject({ method: 'GET', path: '/api/v1/work/W-3202' });
      expect(said()).not.toMatch(/is approved|was returned|\bsent\b|received/i);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(posts('/decision')).toHaveLength(1);
    }, 90_000);
  }

  it('401 on decide shows the signed-out state with next=/work/W-3202', async () => {
    onDecide = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await open(item('W-3202'));
    await ready();
    await click('Approve and send');
    const link = await screen.findByRole('link', { name: /sign in/i });
    expect(link.getAttribute('href')).toContain('next=%2Fwork%2FW-3202');
  });

  it('401 on read shows the signed-out state with next=/work/W-3203', async () => {
    readAnswer = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    served = item('W-3203');
    render(
      <AppShell>
        <WorkItemView id="W-3203" tab="overview" />
      </AppShell>,
    );
    const link = await screen.findByRole('link', { name: /sign in/i });
    expect(link.getAttribute('href')).toContain('next=%2Fwork%2FW-3203');
  });

  it('403 and 404 on read look the same: no title, figure, recipient or sentence; persona none gets it with no further call', async () => {
    for (const code of [403, 404]) {
      readAnswer = () => json(code, { code: code === 403 ? 'forbidden' : 'not_found', message: 'No.' });
      served = item('W-3203');
      render(
        <AppShell>
          <WorkItemView id="W-3203" tab="overview" />
        </AppShell>,
      );
      await screen.findByText(/isn.t open to you|can.t open|not open/i);
      for (const text of ['Tuesday report', 'PMO staff', 'Sola Martins', 'without review', 'CHECKING']) expect(document.body.textContent, `${code} ${text}`).not.toContain(text);
      cleanup();
    }
    who = 'none';
    sent = [];
    readAnswer = () => json(403, { code: 'forbidden', message: 'No.' });
    render(
      <AppShell>
        <WorkItemView id="W-3202" tab="overview" />
      </AppShell>,
    );
    await screen.findByText('No sections are open to your role yet.');
    await new Promise((r) => setTimeout(r, 50));
    expect(sent.filter((r) => r.path.startsWith('/api/v1/work/'))).toHaveLength(0);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });
});

describe('send for leadership review (AC 16)', () => {
  it('W-3205: one step with CSRF, expected_revision, a UUID key and no inputs; a retry after a 500 reuses the key; the re-read is in review', async () => {
    await open(item('W-3205'));
    expect(ws().getByText('It goes to the leadership reviewer set in Setup › Rules.')).toBeTruthy();
    onStep = () => json(500, { code: 'server_error', message: 'Down.' });
    await click('Send for leadership review');
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    expect(await screen.findByText('We couldn’t confirm this step. Check the page before trying again.')).toBeTruthy();
    expect(said()).not.toMatch(/sent for review|\bsent to\b/i);
    onStep = () => {
      served = item('W-3205.next');
      return json(200, { work_id: 'W-3205', state: 'action_needed', revision: 4, outcome: 'done' });
    };
    await click('Try again');
    await waitFor(() => expect(status().textContent).toBe('AWAITING LEADERSHIP REVIEW'));
    const [first, second] = posts('/api/v1/work/W-3205/steps');
    expect(first.body).toEqual({ expected_revision: 3, step: 'send_for_review', idempotency_key: first.body!.idempotency_key });
    expect(stepRequest(first.body)).toBe(true);
    expect(first.csrf).toBe('mock-csrf-ceo');
    expect(first.body!.idempotency_key).toMatch(UUID);
    expect(second.body!.idempotency_key).toBe(first.body!.idempotency_key);
    expect(await ws().findByText('You prepared Monthly report v1, so someone else must review it.')).toBeTruthy();
    expect(said()).not.toMatch(/sent to/i);
    expect(taskPosts()).toHaveLength(0);
  });

  it('W-3212: effect_uncertain shows the uncertain notice after a re-read, never "sent for review", and sends no second step', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
    onStep = () => json(200, { work_id: 'W-3212', state: 'action_needed', revision: 3, outcome: 'effect_uncertain', message: "We couldn't confirm the report reached the reviewer." });
    await open(item('W-3212'));
    const before = sent.length;
    await click('Send for leadership review');
    expect(await screen.findByText('We are checking what happened. Nothing was sent again.')).toBeTruthy();
    expect(screen.getByText("We couldn't confirm the report reached the reviewer.")).toBeTruthy();
    const after = sent.slice(before);
    expect(after[0].path).toBe('/api/v1/work/W-3212/steps');
    expect(after.slice(1).some((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3212')).toBe(true);
    expect(said()).not.toMatch(/sent for review|Done:/i);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(posts('/steps')).toHaveLength(1);
    expect(buttons().filter((b) => NO_RESEND.test(b ?? ''))).toEqual([]);
  }, 90_000);
});

describe('phone (AC 18)', () => {
  it('the Decide bar has both steps; Return opens the Drawer with the note; Cancel closes it and returns focus', async () => {
    phone();
    await open(item('W-3202'));
    await ready();
    expect(buttons()).toEqual(['Approve and send', 'Return with a note']);
    await click('Return with a note');
    const dialog = await screen.findByRole('dialog', { name: 'Return with a note' });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Return with a note' }));
    });
    expect(await within(dialog).findByText('Add a note to return it.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement?.textContent).toBe('Return with a note');
  });

  it('the phone draws the same sections and words as desktop: the access note on W-3201, recipients and Next on W-3203', async () => {
    phone();
    await open(item('W-3201'));
    expect(ws().getByText("The report only uses records you can see. Projects you can't see are left out and counted as left out, never counted as zero.")).toBeTruthy();
    expect(document.querySelector('.ws-lineagent')!.textContent).toContain('Started 01 Nov 08:00');
    cleanup();
    await open(item('W-3203'));
    expect(rows('recipients')).toEqual(['5 PMO staffDELIVERED 10 Nov 09:00', 'Sola MartinsCHECKING Time unknown']);
    expect(ws().getByText("The factory checks the last delivery before marking it received. It won't resend until it knows.")).toBeTruthy();
  });
});

describe('other lines are unchanged by the line sets (AC 24)', () => {
  it('the income line keeps its stations and agent beside; the issue line keeps neither', async () => {
    who = 'finance_lead';
    await open(item('W-2701'));
    expect(document.querySelectorAll('.ws-stations .psl-station')).toHaveLength(5);
    expect(document.querySelector('.ws-lineagent')!.textContent).toContain('Started 11:20');
    cleanup();
    who = 'pm';
    await open(item('W-2411'));
    expect(document.querySelector('.ws-stations, .ws-lineagent, .ws-ministations')).toBeNull();
  });

  it('the leadership report draws no station row, and its banner tone follows the status tone only', async () => {
    await open(item('W-3205'));
    expect(document.querySelector('.ws-stations, .ws-ministations')).toBeNull();
    expect(banner()).toEqual(['psl-callout--warning']);
    cleanup();
    await open(item('W-3202.return'));
    expect(banner()).toEqual(['psl-callout--info']);
    cleanup();
    const stopped = item('W-3201');
    stopped.workspace!.status = { label: 'STOPPED', tone: 'stopped' };
    await open(stopped);
    expect(banner()).toEqual(['psl-callout--problem']);
  });
});
