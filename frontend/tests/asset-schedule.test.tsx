// @vitest-environment jsdom
// F-42: the fixed asset schedule's work item (W-3901 to W-3912) drawn from E-WORK-ITEM `workspace`, with its two reviews
// decided in place on one item (E-TASK-CLAIM, E-TASK-DECIDE through F-33's InlineDecide and useDecision). Contract mock only;
// the fetch stub stands in for the backend. Money rules: costs as returned, nothing computed, Unknown never 0.
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
  usePathname: () => '/work/W-3902',
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

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Body = Record<string, unknown>;
type Handler = (body: Body, path: string) => Response | Promise<Response>;
let sent: Sent[];
let served: WorkItem;
let readAnswer: (() => Response) | null;
let who: string;
let onClaim: Handler;
let onDecide: Handler;

const posts = (suffix: string) => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const taskPosts = () => sent.filter((r) => r.method === 'POST' && r.path.startsWith('/api/v1/tasks/'));
const answer = (task: string, verdict: string, workState = 'processing') => json(200, { task_id: task, verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-13T14:05:00Z', work_state: workState });
const taskOf = (path: string) => path.split('/')[4];

beforeEach(() => {
  sent = [];
  readAnswer = null;
  who = 'finance_lead';
  onClaim = (body) => json(200, { task_id: 'T', revision: body.expected_revision, claimed_by: 'Ada Okafor' });
  // the mock's swap: the decided item is <work_id>.<verdict>.json
  onDecide = (body, path) => {
    served = item(`${served.id}.${body.verdict as string}`);
    return answer(taskOf(path), body.verdict as string, served.state);
  };
  const fetchStub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    const body = text ? JSON.parse(text) : undefined;
    sent.push({ method: request.method, path: url.pathname, body, csrf: request.headers.get('X-CSRFToken') });
    if (url.pathname === '/api/v1/me') return json(200, read(`me.${who}.json`));
    if (request.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(url.pathname)) return readAnswer ? readAnswer() : json(200, served);
    if (request.method === 'POST' && url.pathname.endsWith('/claim')) return onClaim(body, url.pathname);
    if (request.method === 'POST' && url.pathname.endsWith('/decision')) return onDecide(body, url.pathname);
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
const ready = async (name: string) => waitFor(() => expect(ws().getByRole('button', { name }).hasAttribute('disabled')).toBe(false));
const click = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const note = () => ws().getByLabelText(/^Note \(needed to/) as HTMLTextAreaElement;
/** What the page says about the write: its notices, the status tag and the side column (not the station names). */
const said = () => [document.querySelector('.ws-notices'), status(), document.querySelector('.ws-side')].map((el) => el?.textContent ?? '').join(' ');
const factValue = (label: string) => [...document.querySelectorAll('.ws-fact')].find((f) => f.querySelector('dt')?.textContent === label)?.querySelector('dd')?.textContent;
const column = (label: string) => [...document.querySelectorAll(`.ws-table td[data-label="${label}"]`)].map((td) => td.textContent);
const settle = () => new Promise((r) => setTimeout(r, 50));

describe('four states from data (AC 1, 8)', () => {
  it('W-3901 investigating: the Register facts and note, Chidi working in the card with steps, sources and Ask Chidi, and no decide control', async () => {
    await open(item('W-3901'));
    expect(status().textContent).toBe('CHIDI INVESTIGATING');
    expect(status().className).toContain('agent');
    expect(ws().getByRole('heading', { name: 'Register' })).toBeTruthy();
    expect(factValue('Assets')).toBe('64');
    expect(factValue('Added since September')).toBe('4');
    expect(factValue('Disposed')).toBe('1');
    expect(factValue('Unclear dates')).toBe('3');
    expect(ws().getByText('Chidi never reads asset values; he checks structure, dates and provenance.')).toBeTruthy();
    const card = document.querySelector('.ws-lineagent')!;
    for (const text of ['WORKING', 'step 3 of 4', 'Read the asset register', 'PPE_REGISTER_OCT.XLSX · 64 ASSETS', 'PPE-0005', 'VALUES NOT READ', 'Hand to register review']) expect(card.textContent, text).toContain(text);
    expect(card.querySelector('.psl-agent__foot')!.textContent).toBe('Started 10:05Ask Chidi');
    expect(ws().getAllByRole('link', { name: 'Ask Chidi' })).toHaveLength(1);
    expect(ws().getByRole('link', { name: 'Ask Chidi' }).getAttribute('href')).toBe('/assistant');
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect([...document.querySelectorAll('.ws-stations .psl-station strong')].map((s) => s.textContent)).toEqual(['Chidi investigates', 'Register review', 'Date review (if unclear)', 'Calculate', 'Schedule review', 'Verified']);
    await settle();
    expect(taskPosts()).toHaveLength(0);
  });

  it('W-3902 register review: the Register changes table and the Decide panel with the backend basis and consequence', async () => {
    await open(item('W-3902'));
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect(ws().getByRole('heading', { name: 'Register changes' })).toBeTruthy();
    expect([...document.querySelectorAll('.ws-table th')].map((th) => th.textContent)).toEqual(['ASSET', 'CHANGE', 'COST']);
    expect(column('ASSET')).toEqual(['Dell server rack · A-0412', 'Toyota Hilux · A-0388', '3 laptops']);
    expect(column('CHANGE')).toEqual(['Added 02 Oct', 'Disposed 20 Oct', 'Added']);
    const panel = await ws().findByRole('region', { name: 'Decide · PPE reviewer' });
    expect(within(panel).getByText('Approve the October register as the source for the schedule.')).toBeTruthy();
    expect(within(panel).getByText('3 assets have unclear dates; they go to a date review next.')).toBeTruthy();
    expect(within(panel).getByLabelText('Note (needed to return or reject)')).toBeTruthy();
    await ready('Approve register');
    expect(within(panel).getAllByRole('button').map((b) => b.textContent)).toEqual(['Approve register', 'Return with a note', 'Reject']);
  });

  it('W-3903 date review: the Unclear dates table, the proof as a cite with its detail, one Decide panel and a claim for T-3903 only', async () => {
    await open(item('W-3903'));
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect([...document.querySelectorAll('.ws-table th')].map((th) => th.textContent)).toEqual(['ASSET', 'REGISTER SAYS', 'EXPLANATION']);
    expect(column('ASSET')).toEqual(['A-0412 server rack', 'A-0415 laptop', 'A-0416 laptop']);
    expect(column('REGISTER SAYS')).toEqual(['"Oct 2026"', 'Blank', '"Q4"']);
    expect(column('EXPLANATION')).toEqual(['Delivered 02 Oct, live 15 Oct', 'Issued 07 Oct', 'Issued 09 Oct']);
    const proof = ws().getByRole('heading', { name: 'Proof' }).closest('section')!;
    expect(proof.textContent).toContain('asset-dates-explanation.pdf');
    expect(proof.textContent).toContain('Uploaded · 64 KB');
    expect(within(proof).queryByRole('link')).toBeNull();
    // UI-1-1: the file name as returned (its own case) comes first in the row, the detail under it
    const row = proof.querySelector('.ws-row')!;
    expect(row.querySelector('.ws-row__end')!.textContent).toBe('asset-dates-explanation.pdf');
    expect(row.querySelector('.ws-row__main')!.textContent).toBe('Uploaded · 64 KB');
    expect(readFileSync(join(__dirname, '../src/features/workspace/workspace.css'), 'utf8')).toMatch(/\.ws\[data-line="fixed_assets"\] \.ws-rows--text \.ws-cite[^{]*\{[^}]*text-transform: none/);
    const panel = await ws().findByRole('region', { name: 'Decide · PPE reviewer' });
    expect(within(panel).getByText('Approve the explained dates. Depreciation starts from these dates.')).toBeTruthy();
    await ready('Approve dates');
    expect(buttons()).toEqual(['Approve dates', 'Return with a note', 'Reject']);
    expect(document.querySelectorAll('.ws-idecide')).toHaveLength(1);
    // the decided register task draws no card, link or claim of its own
    expect(document.querySelector('.work-aside')!.textContent).not.toContain('Review the asset register');
    expect(screen.queryByRole('link', { name: /Open the review|Review/ })).toBeNull();
    expect(posts('/claim').map((p) => p.path)).toEqual(['/api/v1/tasks/T-3903/claim']);
  });

  it('W-3904 calculating: PROCESSING and the Calculation facts as returned, Next as returned, no agent working and no control', async () => {
    await open(item('W-3904'));
    expect(status().textContent).toBe('PROCESSING');
    expect(factValue('Source')).toBe('REGISTER · APPROVED');
    expect(factValue('Dates')).toBe('APPROVED');
    expect(factValue('Rule')).toBe('F07 CALCULATION RULES');
    expect(ws().getByText("The factory calculates the schedule with the approved rules; Chidi doesn't see the values.")).toBeTruthy();
    expect(document.querySelector('.ws-lineagent')).toBeNull();
    expect(document.body.textContent).not.toContain('WORKING');
    expect(document.querySelector('.ws-stations')!.textContent).not.toContain('Agent working');
    expect(buttons()).toEqual([]);
    await settle();
    expect(taskPosts()).toHaveLength(0);
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
    for (const board of ['CHIDI INVESTIGATING', 'AWAITING FINANCE DECISION', 'PPE reviewer', 'never reads asset values', 'VALUES NOT READ', 'Depreciation starts', 'F07', 'PPE_REGISTER', 'asset-dates-explanation', 'every return', 'backend only waits']) expect(text, board).not.toContain(board);
  });
});

describe('costs and counts as returned (AC 2 to 5)', () => {
  it('the costs are the backend decimal strings at desktop and phone, with no short form; a changed amount shows exactly', async () => {
    await open(item('W-3902'));
    expect(column('COST')).toEqual(['₦8,400,000.00', '₦14,000,000.00', '₦3,150,000.00']);
    cleanup();
    phone();
    await open(item('W-3902'));
    expect(column('COST')).toEqual(['₦8,400,000.00', '₦14,000,000.00', '₦3,150,000.00']);
    expect(document.body.textContent).not.toMatch(/14(\.0)?M|8\.4M|3\.2M/);
    cleanup();
    const changed = item('W-3902');
    changed.workspace!.sections[0].items[1].cells![2].money = { amount: '14000000.10', currency: 'NGN', unknown: false };
    await open(changed);
    expect(column('COST')[1]).toBe('₦14,000,000.10');
  });

  it('changing a fact changes only that value; removing a row changes no other text, the consequence included', async () => {
    const facts = item('W-3901');
    facts.workspace!.sections[0].items[0].value = '65';
    await open(facts);
    expect(factValue('Assets')).toBe('65');
    expect(factValue('Added since September')).toBe('4');
    expect(factValue('Unclear dates')).toBe('3');
    cleanup();
    const fewer = item('W-3902');
    fewer.workspace!.sections[0].items.splice(2, 1);
    await open(fewer);
    expect(column('ASSET')).toEqual(['Dell server rack · A-0412', 'Toyota Hilux · A-0388']);
    expect(column('COST')).toEqual(['₦8,400,000.00', '₦14,000,000.00']);
    expect(await ws().findByText('3 assets have unclear dates; they go to a date review next.')).toBeTruthy();
    expect(ws().getByRole('heading', { name: 'Register changes' })).toBeTruthy();
  });

  it('no depreciation, opening, closing or total figure appears on any part 1 page', async () => {
    for (const id of ['W-3901', 'W-3902', 'W-3903', 'W-3904', 'W-3907', 'W-3909']) {
      await open(item(id));
      const text = document.querySelector('main')!.textContent!;
      expect(text, id).not.toMatch(/opening|closing|total|net book|accumulated/i);
      // the date review's basis is the backend's sentence; no other text names depreciation
      expect(text.replace('Approve the explained dates. Depreciation starts from these dates.', ''), id).not.toMatch(/depreciation/i);
      cleanup();
    }
  });

  it('W-3910: the unknown Hilux cost reads Unknown, never 0, blank or a dash', async () => {
    await open(item('W-3910'));
    const cost = column('COST');
    expect(cost).toEqual(['₦8,400,000.00', 'Unknown', '₦3,150,000.00']);
    expect(cost[1]).not.toMatch(/^(|-|—|₦0|0\.00|₦0\.00)$/);
    expect(document.querySelector('.ws')!.textContent).not.toContain('₦0');
  });

  it('every fixture is marked sample because the record says so; a copy with sample false is not (AC 5)', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    for (const id of ['W-3901', 'W-3902', 'W-3903', 'W-3904', 'W-3905', 'W-3906', 'W-3907', 'W-3908', 'W-3909', 'W-3910', 'W-3911', 'W-3912']) {
      await open(item(id));
      expect(document.querySelector('.work-lineend')!.textContent, id).toContain('SAMPLE DATA');
      cleanup();
    }
    await open({ ...item('W-3902'), sample: false });
    expect(document.querySelector('.work-lineend')!.textContent).not.toContain('SAMPLE DATA');
  });
});

describe('the holds and who may act (AC 6, 7, 12)', () => {
  for (const [id, label, sentence] of [
    ['W-3907', 'Who reviews assets', 'An admin sets Who reviews assets in Setup · Finance rules. The register review starts then.'],
    ['W-3908', 'Register rules', 'An admin sets Register rules in Setup · Finance rules. The register review starts then.'],
    ['W-3909', 'Calculation rules', 'An admin sets Calculation rules in Setup · Finance rules. The calculation starts then.'],
  ] as const) {
    it(`${id} (${label} not set): the backend’s hold, no Decide panel, no button, no task write and no reviewer named`, async () => {
      await open(item(id));
      expect(status().textContent).toBe('SETUP NEEDED');
      expect(factValue(label)).toBe('NOT SET');
      expect(ws().getByText(sentence)).toBeTruthy();
      expect(buttons()).toEqual([]);
      expect(document.querySelector('.ws-idecide')).toBeNull();
      expect(document.querySelector('main')!.textContent).not.toContain('Ada Okafor');
      expect(document.body.textContent).not.toContain('PPE reviewer');
      expect(document.body.textContent).not.toContain('PROCESSING');
      expect(document.body.textContent).not.toContain('₦');
      await settle();
      expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
    });
  }

  it('UX-1-1: no hold or uncertain state on this line draws the "See all exceptions" button; another line still does', async () => {
    for (const id of ['W-3907', 'W-3908', 'W-3909', 'W-3911.approve']) {
      await open(item(id));
      expect(screen.queryByRole('link', { name: 'See all exceptions' }), id).toBeNull();
      cleanup();
    }
    await open(item('W-2706'));
    expect(screen.getAllByRole('link', { name: 'See all exceptions' }).length).toBeGreaterThan(0);
  });

  it('TECH-1-1: after both reviews the lifecycle facts stay drafted and reviewed', () => {
    for (const id of ['W-3903.approve', 'W-3904', 'W-3909']) {
      const facts = Object.fromEntries(item(id).facts.map((f) => [f.name, f.status]));
      expect(facts, id).toMatchObject({ drafted: 'earned', reviewed: 'earned' });
    }
  });

  it('W-3909 stops at Calculate: station 4 stopped, no Calculation facts', async () => {
    await open(item('W-3909'));
    const stations = [...document.querySelectorAll('.ws-stations .psl-station')];
    expect(stations[3].className).toContain('psl-station--stopped');
    expect(stations[3].textContent).toContain('Calculate');
    expect(ws().queryByRole('heading', { name: 'Calculation' })).toBeNull();
    expect(factValue('Rule')).toBeUndefined();
  });

  it('W-3905 and W-3912 (you prepared it) and W-3906 (not your role) show the reason, no button and send no claim', async () => {
    await open(item('W-3905'));
    expect(await ws().findByText('You prepared October register, so someone else must review it.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    cleanup();
    await open(item('W-3912'));
    expect(await ws().findByText('You prepared October in-service dates, so someone else must review it.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    cleanup();
    await open(item('W-3906'));
    expect(await ws().findByText('This decision needs a PPE reviewer.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    await settle();
    expect(taskPosts()).toHaveLength(0);
  });

  it('the controls follow you_can_act only: finance_lead, ceo and pm see the same buttons on the same items', async () => {
    for (const persona of ['finance_lead', 'ceo', 'pm']) {
      who = persona;
      await open(item('W-3902'));
      await ready('Approve register');
      expect(buttons(), persona).toEqual(['Approve register', 'Return with a note', 'Reject']);
      cleanup();
      await open(item('W-3903'));
      await ready('Approve dates');
      expect(buttons(), persona).toEqual(['Approve dates', 'Return with a note', 'Reject']);
      cleanup();
      sent = [];
      await open(item('W-3906'));
      expect(await ws().findByText('This decision needs a PPE reviewer.')).toBeTruthy();
      expect(buttons(), persona).toEqual([]);
      await settle();
      expect(taskPosts(), persona).toHaveLength(0);
      cleanup();
    }
    // the line checks read the line key only: no /me call or hook in the changed files
    for (const file of ['../src/features/workspace/Workspace.tsx', '../src/features/workspace/labels.ts', '../src/features/work-item/WorkItemOverview.tsx']) expect(readFileSync(join(__dirname, file), 'utf8'), file).not.toMatch(/useMe\b|api\/v1\/me\b/);
  });

  it('a copy of W-3901 without the section note shows no "never reads" text (the line is data)', async () => {
    const body = item('W-3901');
    delete body.workspace!.sections[0].note;
    await open(body);
    expect(document.body.textContent).not.toContain('never reads');
  });
});

describe('approve, return and reject (AC 9 to 11)', () => {
  it('W-3902: claims once, then one decision with CSRF and {verdict, expected_revision}; a double press sends one; the waiting state only from the re-read', async () => {
    await open(item('W-3902'));
    await ready('Approve register');
    expect(posts('/api/v1/tasks/T-3902/claim')).toHaveLength(1);
    await act(async () => {
      const approve = ws().getByRole('button', { name: 'Approve register' });
      fireEvent.click(approve);
      fireEvent.click(approve);
    });
    await waitFor(() => expect(status().textContent).toBe('WAITING FOR DATE EXPLANATIONS'));
    expect(posts('/decision')).toHaveLength(1);
    const [decision] = posts('/api/v1/tasks/T-3902/decision');
    expect(decision.body).toEqual({ verdict: 'approve', expected_revision: 1 });
    expect(decideRequest(decision.body)).toBe(true);
    expect(decision.csrf).toBe('mock-csrf-finance_lead');
    expect(await screen.findByText('October register is approved')).toBeTruthy();
    expect(ws().getByText('Waiting for someone to explain the 3 unclear in-service dates and attach the proof. The date review starts after that.')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/dates are explained/);
    // no date-review panel and no control on the waiting state
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(buttons()).toEqual([]);
  });

  it('W-3903: Approve dates sends one decision for T-3903; PROCESSING and REGISTER · APPROVED only after the re-read', async () => {
    let decide: () => void = () => {};
    onDecide = (body, path) =>
      new Promise<Response>((resolve) => {
        decide = () => {
          served = item(`W-3903.${body.verdict as string}`);
          resolve(answer(taskOf(path), body.verdict as string));
        };
      });
    await open(item('W-3903'));
    await ready('Approve dates');
    await click('Approve dates');
    await waitFor(() => expect(posts('/decision')).toHaveLength(1));
    expect(said()).not.toMatch(/PROCESSING|APPROVED/);
    await act(async () => decide());
    await waitFor(() => expect(status().textContent).toBe('PROCESSING'));
    expect(factValue('Source')).toBe('REGISTER · APPROVED');
    const [decision] = posts('/api/v1/tasks/T-3903/decision');
    expect(decision.body).toEqual({ verdict: 'approve', expected_revision: 1 });
    expect(decideRequest(decision.body)).toBe(true);
    expect(await screen.findByText('October in-service dates is approved')).toBeTruthy();
    expect(posts('/api/v1/tasks/T-3931/decision')).toHaveLength(0);
  });

  it('a 200 whose re-read still serves the review never says approved, APPROVED or PROCESSING', async () => {
    onDecide = (body, path) => answer(taskOf(path), body.verdict as string);
    await open(item('W-3903'));
    await ready('Approve dates');
    await click('Approve dates');
    await waitFor(() => expect(posts('/decision')).toHaveLength(1));
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3903').length).toBeGreaterThanOrEqual(3));
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect(said()).not.toMatch(/APPROVED|PROCESSING/);
    expect(document.querySelector('main')!.textContent).not.toContain('PROCESSING');
  });

  it('return and reject need a note: empty, blank and over 2000 characters send nothing; with a note one POST with the trimmed note', async () => {
    await open(item('W-3902'));
    await ready('Approve register');
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
    fireEvent.change(note(), { target: { value: '  The Hilux was sold on 21 Oct.  ' } });
    await click('Return with a note');
    await waitFor(() => expect(status().textContent).toBe('RETURNED'));
    expect(posts('/decision').map((p) => p.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'The Hilux was sold on 21 Oct.' }]);
    expect(decideRequest(posts('/decision')[0].body)).toBe(true);
    expect(ws().getByText(/Ada Okafor returned the October register on 13 Nov/)).toBeTruthy();
    expect(buttons()).toEqual([]);
    expect(document.body.textContent).not.toMatch(/every return|backend only waits|Correct and resubmit/i);
    expect(await screen.findByText('October register was returned')).toBeTruthy();
  });

  it('reject with a note on W-3903 shows the rejected state the re-read returns', async () => {
    await open(item('W-3903'));
    await ready('Approve dates');
    fireEvent.change(note(), { target: { value: 'Not for October.' } });
    await click('Reject');
    await waitFor(() => expect(status().textContent).toBe('REJECTED'));
    expect(posts('/api/v1/tasks/T-3903/decision')[0].body).toEqual({ verdict: 'reject', expected_revision: 1, note: 'Not for October.' });
    // The result toast (D-151) can land a tick after the status under a loaded run: wait for it rather than read it at once.
    expect(await screen.findByText('October in-service dates was rejected')).toBeTruthy();
    await waitFor(() => expect(buttons()).toEqual([]));
  });

  it('the error under the note is announced', async () => {
    await open(item('W-3902'));
    await ready('Approve register');
    await click('Reject');
    const message = await screen.findByText('Add a note to reject it.');
    expect(note().getAttribute('aria-invalid')).toBe('true');
    expect(note().getAttribute('aria-describedby')).toContain(message.id || message.closest('[id]')!.id);
  });
});

describe('refusals and uncertain writes (AC 13 to 15)', () => {
  it('403 on decide: read-only from the re-read reason, no approved', async () => {
    onDecide = () => {
      served = { ...item('W-3902'), tasks: [{ ...item('W-3902').tasks[0], you_can_act: false, cannot_act_reason: 'not_your_role' }] };
      return json(403, { code: 'forbidden', message: 'No.' });
    };
    await open(item('W-3902'));
    await ready('Approve register');
    await click('Approve register');
    expect(await ws().findByText('This decision needs a PPE reviewer.')).toBeTruthy();
    expect(said()).not.toMatch(/approved/i);
    expect(buttons().filter((b) => b === 'Approve register')).toHaveLength(0);
  });

  it('409: the stale view keeps the note; a new press after Review the latest carries the new revision', async () => {
    const newer = { ...item('W-3902'), revision: 2, tasks: [{ ...item('W-3902').tasks[0], revision: 2 }] };
    onDecide = () => {
      served = newer;
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-3902'));
    await ready('Approve register');
    fireEvent.change(note(), { target: { value: 'Check the Hilux.' } });
    await click('Return with a note');
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(1);
    await click('Review the latest');
    await ready('Approve register');
    expect(note().value).toBe('Check the Hilux.');
    onDecide = (body, path) => answer(taskOf(path), body.verdict as string);
    await click('Return with a note');
    await waitFor(() => expect(posts('/decision')).toHaveLength(2));
    expect(posts('/decision')[1].body!.expected_revision).toBe(2);
  });

  it('422: the backend message under the note', async () => {
    onDecide = () => json(422, { code: 'invalid', message: 'Say which asset.', fields: [{ name: 'note', message: 'Say which asset.' }] });
    await open(item('W-3902'));
    await ready('Approve register');
    fireEvent.change(note(), { target: { value: 'Fix it.' } });
    await click('Return with a note');
    expect(await ws().findByText('Say which asset.')).toBeTruthy();
  });

  for (const [name, reply] of [
    ['a 500', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
  ] as const) {
    it(`${name} re-reads first, shows the uncertain notice, says nothing was approved and never sends again by itself`, async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
      onDecide = reply as unknown as Handler;
      await open(item('W-3902'));
      await ready('Approve register');
      const before = sent.length;
      await click('Approve register');
      expect(await screen.findByText(/We couldn.t confirm your decision/)).toBeTruthy();
      const after = sent.slice(before);
      expect(after[0].path).toBe('/api/v1/tasks/T-3902/decision');
      expect(after[1]).toMatchObject({ method: 'GET', path: '/api/v1/work/W-3902' });
      expect(said()).not.toMatch(/is approved|was returned|was rejected|APPROVED|PROCESSING/i);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(posts('/decision')).toHaveLength(1);
    }, 90_000);
  }

  it('W-3911: each verdict shows "October register: result not confirmed" and the backend’s DECISION NOT CONFIRMED, before and after a reload', async () => {
    for (const verdict of ['approve', 'return', 'reject'] as const) {
      await open(item('W-3911'));
      await ready('Approve register');
      if (verdict !== 'approve') fireEvent.change(note(), { target: { value: 'Check the Hilux.' } });
      await click(verdict === 'approve' ? 'Approve register' : verdict === 'return' ? 'Return with a note' : 'Reject');
      expect(await screen.findByText('October register: result not confirmed'), verdict).toBeTruthy();
      expect(status().textContent).toBe('DECISION NOT CONFIRMED');
      expect(said(), verdict).not.toMatch(/is approved|was returned|was rejected|APPROVED|PROCESSING/i);
      expect(document.querySelector('.ws-live .psl-callout--success')).toBeNull();
      expect(posts('/decision')).toHaveLength(1);
      cleanup();
      // a reload draws the backend’s uncertain state with no control
      await open(served);
      expect(status().textContent).toBe('DECISION NOT CONFIRMED');
      expect(buttons().filter((b) => /Approve|Return|Reject/.test(b ?? ''))).toEqual([]);
      cleanup();
      sent = [];
    }
  });

  it('a later deliberate decide clears the earlier notice', async () => {
    let first = true;
    onDecide = (body, path) => {
      if (first) {
        first = false;
        return json(409, { code: 'stale', message: 'Changed.' });
      }
      served = item(`W-3902.${body.verdict as string}`);
      return answer(taskOf(path), body.verdict as string, served.state);
    };
    await open(item('W-3902'));
    await ready('Approve register');
    await click('Approve register');
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    await click('Review the latest');
    await ready('Approve register');
    await click('Approve register');
    expect(await screen.findByText('October register is approved')).toBeTruthy();
    expect(screen.queryByText('This review changed while you were reading it, so nothing was recorded.')).toBeNull();
  });

  it('401 on decide shows the signed-out state with next=/work/W-3902', async () => {
    onDecide = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await open(item('W-3902'));
    await ready('Approve register');
    await click('Approve register');
    const link = await screen.findByRole('link', { name: /sign in/i });
    expect(link.getAttribute('href')).toContain('next=%2Fwork%2FW-3902');
  });

  it('401 on read shows the signed-out state with next=/work/W-3903', async () => {
    readAnswer = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    served = item('W-3903');
    render(
      <AppShell>
        <WorkItemView id="W-3903" tab="overview" />
      </AppShell>,
    );
    const link = await screen.findByRole('link', { name: /sign in/i });
    expect(link.getAttribute('href')).toContain('next=%2Fwork%2FW-3903');
  });

  it('403 and 404 on read look the same: no title, cost or fact; persona none gets it with no further call', async () => {
    for (const code of [403, 404]) {
      readAnswer = () => json(code, { code: code === 403 ? 'forbidden' : 'not_found', message: 'No.' });
      served = item('W-3902');
      render(
        <AppShell>
          <WorkItemView id="W-3902" tab="overview" />
        </AppShell>,
      );
      await screen.findByText(/isn.t open to you|can.t open|not open/i);
      expect(document.body.textContent).not.toContain('Fixed asset schedule');
      expect(document.body.textContent).not.toContain('14,000,000');
      expect(document.body.textContent).not.toContain('Toyota Hilux');
      cleanup();
    }
    who = 'none';
    sent = [];
    readAnswer = () => json(403, { code: 'forbidden', message: 'No.' });
    render(
      <AppShell>
        <WorkItemView id="W-3902" tab="overview" />
      </AppShell>,
    );
    await screen.findByText('No sections are open to your role yet.');
    await settle();
    expect(sent.filter((r) => r.path.startsWith('/api/v1/work/'))).toHaveLength(0);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });
});

describe('phone (AC 16)', () => {
  it('the step labels in the pinned bar; Return with a note and Reject open the Drawer with the note; Cancel closes it and returns focus', async () => {
    phone();
    await open(item('W-3903'));
    await ready('Approve dates');
    expect(buttons()).toEqual(['Approve dates', 'Return with a note', 'Reject']);
    expect(document.querySelector('.ws-ministations')!.textContent).toContain('Station 3 of 6 · Date review (if unclear)');
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
    await waitFor(() => expect(document.activeElement?.textContent).toBe('Return with a note'));
  });
});

describe('other lines are unchanged (AC 17)', () => {
  it('W-2701 keeps the income line frame; W-2411 (issue) draws none of the schedule frame', async () => {
    await open(item('W-2701'));
    expect(document.querySelectorAll('.ws-stations .psl-station')).toHaveLength(5);
    expect(document.querySelector('.ws-lineagent')!.textContent).toContain('WORKING');
    cleanup();
    who = 'pm';
    await open(item('W-2411'));
    expect(document.querySelector('.ws-stations, .ws-lineagent, .ws-ministations')).toBeNull();
  });
});
