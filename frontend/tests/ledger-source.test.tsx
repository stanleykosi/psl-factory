// @vitest-environment jsdom
// F-45 SCR-58 part 1: the ledger source LED-0052 drawn from E-WORK-ITEM `workspace` (W-4201 to W-4213). The observer records
// what they found with a proof file (E-EVIDENCE-UPLOAD, then E-WORK-STEP through F-17's step form); an independent reviewer
// approves or rejects it in place (E-TASK-CLAIM, E-TASK-DECIDE through F-33's InlineDecide). Contract mock only: the fetch
// stub stands in for the backend. No amount is shown, Unknown is never 0, controls come only from you_can_act,
// disabled_reason and the steps sent, and "Verified" only from the re-read.
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
  usePathname: () => '/work/W-4203',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const decideRequest = ajv.compile(openapi.paths['/api/v1/tasks/{task_id}/decision'].post.requestBody.content['application/json'].schema);
const stepRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);
const uploadRequest = ajv.compile(openapi.paths['/api/v1/cases/{case_id}/evidence'].post.requestBody.content['application/json'].schema);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

const IDS = ['W-4201', 'W-4202', 'W-4203', 'W-4204', 'W-4205', 'W-4206', 'W-4207', 'W-4208', 'W-4209', 'W-4210', 'W-4211', 'W-4212', 'W-4213'];
const SIDECARS = ['W-4202.next', 'W-4203.approve', 'W-4203.reject', 'W-4208.next', 'W-4212.approve', 'W-4212.reject', 'W-4213.next'];

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Body = Record<string, unknown>;
type Handler = (body: Body, path: string) => Response | Promise<Response>;
let sent: Sent[];
let served: WorkItem;
let readAnswer: (() => Response | Promise<Response>) | null;
let who: string;
let onClaim: Handler;
let onDecide: Handler;
let onStep: Handler;
let onUpload: Handler;

const posts = (suffix = '') => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const taskPosts = () => sent.filter((r) => r.method === 'POST' && r.path.startsWith('/api/v1/tasks/'));
const answer = (task: string, verdict: string, workState: string) => json(200, { task_id: task, verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-14T15:30:00Z', work_state: workState });
const taskOf = (path: string) => path.split('/')[4];
const stepDone = (message?: string) => json(200, { work_id: served.id, state: served.state, revision: served.workspace?.revision ?? served.revision, outcome: 'done', ...(message ? { message } : {}) });

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
  // the mock's step: <work_id>.next.json, with the script's message
  onStep = () => {
    served = item(`${served.id}.next`);
    return stepDone('Observation recorded.');
  };
  onUpload = (body) => json(200, { evidence_id: 'EV-C-LED-0052-1', sha256: 'a'.repeat(64), case_revision: (body.case_revision as number) + 1 });
  const fetchStub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    const body = text ? JSON.parse(text) : undefined;
    sent.push({ method: request.method, path: url.pathname, body, csrf: request.headers.get('X-CSRFToken') });
    if (url.pathname === '/api/v1/me') return json(200, read(`me.${who}.json`));
    if (request.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(url.pathname)) return readAnswer ? readAnswer() : json(200, served);
    if (request.method === 'POST' && url.pathname.endsWith('/claim')) return onClaim(body, url.pathname);
    if (request.method === 'POST' && url.pathname.endsWith('/decision')) return onDecide(body, url.pathname);
    if (request.method === 'POST' && url.pathname.endsWith('/steps')) return onStep(body, url.pathname);
    if (request.method === 'POST' && url.pathname.endsWith('/evidence')) return onUpload(body, url.pathname);
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
const ready = async (name = 'Approve reference') => waitFor(() => expect(ws().getByRole('button', { name }).hasAttribute('disabled')).toBe(false));
const click = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const note = () => ws().getByLabelText(/^Note \(needed to/) as HTMLTextAreaElement;
/** What the page says about the write: its notices, the status tag and the side column (not the station names). */
const said = () => [document.querySelector('.ws-notices'), status(), document.querySelector('.ws-side')].map((el) => el?.textContent ?? '').join(' ');
const notices = () => document.querySelector('.ws-notices')?.textContent ?? '';
const factValue = (label: string) => [...document.querySelectorAll('.ws-fact')].find((f) => f.querySelector('dt')?.textContent === label)?.querySelector('dd')?.textContent;
const stationNames = () => [...document.querySelectorAll('.ws-stations .psl-station strong')].map((s) => s.textContent);
const settle = () => new Promise((r) => setTimeout(r, 50));
const reads = (id: string) => sent.filter((r) => r.method === 'GET' && r.path === `/api/v1/work/${id}`).length;

// the observation form
const form = (scope = ws()) => scope.getByRole('form');
/** "What you found" is the shared Select (a combobox button and its listbox), as IntakeField draws a choice of more than three. */
const found = (scope = ws()) => scope.getByRole('combobox', { name: /What you found/ });
const LABELS: Record<string, string> = { found: 'Found', not_found: 'Not found', unknown: 'Unknown', more_than_one: 'More than one' };
const choose = (value: string, scope = ws()) => {
  fireEvent.click(found(scope));
  fireEvent.click(screen.getByRole('option', { name: LABELS[value] }));
};
/** A field's error is announced through the focused control: aria-invalid and aria-describedby naming the message. */
const describedBy = (control: Element) => (control.getAttribute('aria-describedby') ?? '').split(' ').map((ref) => document.getElementById(ref)?.textContent ?? '').join(' ');
const png = () => new File([new Uint8Array(1024)], 'qb-screenshot-je7741.png', { type: 'image/png' });
async function upload(scope: HTMLElement = document.querySelector('.ws') as HTMLElement, count = 1) {
  const input = scope.querySelector('input[type="file"]') as HTMLInputElement;
  await act(async () => {
    fireEvent.change(input, { target: { files: [png()] } });
  });
  await waitFor(() => expect(posts('/evidence')).toHaveLength(count));
  await waitFor(() => expect(screen.queryByText(/Uploading…/)).toBeNull());
}
const submit = async (scope = ws()) => {
  await act(async () => {
    fireEvent.submit(form(scope));
  });
};

describe('four states from data (AC 1, 8)', () => {
  it('W-4201 investigating: the Source facts, Chidi working in the side card with steps, sources and Ask Chidi, and no step or decide control', async () => {
    await open(item('W-4201'));
    expect(status().textContent).toBe('CHIDI INVESTIGATING');
    expect(status().className).toContain('agent');
    expect(document.querySelector('.work-crumbs, .psl-crumbs, nav[aria-label="Breadcrumb"]')?.textContent ?? document.body.textContent).toMatch(/FINANCE.*LEDGER SOURCES.*LED-0052/);
    expect(ws().getByRole('heading', { name: 'Source' })).toBeTruthy();
    expect(factValue('Provider')).toBe('QUICKBOOKS');
    expect(factValue('Reference')).toBe('JE-7741');
    expect(factValue('Treatment')).toBe('ACCRUAL REVERSAL');
    expect(stationNames()).toEqual(['Chidi investigates', 'Capture lineage', 'Record what was found', 'Independent review', 'Verified']);
    const card = document.querySelector('.ws-side .ws-lineagent')!;
    for (const text of ['WORKING', 'Read the ledger source file', 'QB_EXPORT_JE7741.PDF', 'Checked date and period', '28 OCT · 2026-10', 'Checked where it came from', 'QUICKBOOKS · REALM PSL-NG', 'Capture the lineage']) expect(card.textContent, text).toContain(text);
    expect(card.querySelector('.psl-agent__foot')!.textContent).toBe('Started 15:12Ask Chidi');
    expect(ws().getAllByRole('link', { name: 'Ask Chidi' })).toHaveLength(1);
    expect(ws().getByRole('link', { name: 'Ask Chidi' }).getAttribute('href')).toBe('/assistant');
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    // agent work is not an observation, a decision or a verified result
    expect(said()).not.toMatch(/\bfound\b|verified|approved/i);
    await settle();
    expect(posts()).toHaveLength(0);
  });

  it('W-4202 observe: RECORD WHAT YOU FOUND, stations 1-2 done and 3 current, one Record observation step with its consequence; the form is closed', async () => {
    await open(item('W-4202'));
    expect(status().textContent).toBe('RECORD WHAT YOU FOUND');
    expect(status().className).toContain('person');
    expect([...document.querySelectorAll('.ws-stations .psl-station')].map((s) => s.className.match(/psl-station--(\w+)/)?.[1]).slice(0, 3)).toEqual(['done', 'done', 'person']);
    expect(buttons()).toEqual(['Record observation']);
    expect(ws().getByText(/an independent reviewer \(not Bisi, who captured it, and not you\) decides\./)).toBeTruthy();
    expect(ws().queryByRole('form')).toBeNull();
    expect(document.querySelector('.ws-idecide')).toBeNull();
  });

  it('W-4203 review: the Evidence facts and the Decide · Ledger reviewer panel with the basis and the approve consequence as returned', async () => {
    await open(item('W-4203'));
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect(ws().getByRole('heading', { name: 'Evidence' })).toBeTruthy();
    expect(factValue('Captured by')).toBe('BISI ADE');
    expect(factValue('Observed by')).toBe('CHUKA EZE · FOUND');
    expect(factValue('Lineage')).toBe('NEW · NO PREDECESSOR');
    const panel = await ws().findByRole('region', { name: 'Decide · Ledger reviewer' });
    expect(within(panel).getByText('Approve JE-7741 as a supplied reference. You captured nothing and observed nothing here, so you can review.')).toBeTruthy();
    expect(within(panel).getByText('Ledger review is approve or reject only. Approving records a reference; nothing is posted and authenticity isn’t certified.')).toBeTruthy();
    await ready();
    expect(buttons()).toEqual(['Approve reference', 'Reject']);
    expect(ws().getByLabelText('Note (needed to reject)')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Return/ })).toBeNull();
  });

  it('W-4204 verified: VERIFIED from the status, the Recorded facts and the re-check sentence as returned, and no step or button (AC 9)', async () => {
    await open(item('W-4204'));
    expect(status().textContent).toBe('VERIFIED');
    expect(ws().getByRole('heading', { name: 'Recorded' })).toBeTruthy();
    expect(factValue('Posting performed')).toBe('NO');
    expect(factValue('Authenticity certified')).toBe('NO');
    expect(factValue('Completeness certified')).toBe('NO');
    expect(factValue('Reference recorded')).toBe('YES · 14 NOV');
    expect(ws().getByText('A reference only. If the source changes later, a re-check reopens it.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    // the decided task has nothing left to open on this line
    expect(document.querySelector('.work-aside')!.textContent).not.toMatch(/already been made/);
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
    for (const board of ['CHIDI INVESTIGATING', 'RECORD WHAT YOU FOUND', 'JE-7741', 'NO PREDECESSOR', 'Ledger reviewer', 're-check reopens', 'CHECK HELD', 'QuickBooks']) expect(text, board).not.toContain(board);
  });
});

describe('no amount, Unknown and sample (AC 2 to 4)', () => {
  it('no page or sidecar shows a currency sign or an amount', async () => {
    for (const name of [...IDS, ...SIDECARS]) {
      await open(item(name));
      const text = document.body.textContent ?? '';
      expect(text, name).not.toMatch(/₦|NGN|\d{1,3}(,\d{3})+(\.\d+)?|\d+\.\d{2}\b/);
      cleanup();
    }
  });

  it('changing a fact value in a fixture copy changes only that text', async () => {
    const body = item('W-4201');
    body.workspace!.sections[0].items[0].value = 'XERO';
    await open(body);
    expect(factValue('Provider')).toBe('XERO');
    expect(factValue('Reference')).toBe('JE-7741');
    expect(factValue('Treatment')).toBe('ACCRUAL REVERSAL');
    expect(ws().getByRole('heading', { name: 'Source' })).toBeTruthy();
  });

  it('W-4211: Treatment reads Unknown (never empty, 0 or a dash) and the third agent step draws no invented source', async () => {
    await open(item('W-4211'));
    const treatment = factValue('Treatment');
    expect(treatment).toBe('Unknown');
    expect(['', '0', '-', '—']).not.toContain(treatment);
    const steps = [...document.querySelectorAll('.ws-lineagent li')];
    const third = steps.find((li) => li.textContent?.includes('Checked where it came from'))!;
    expect(third.textContent).toBe('✓Done: Checked where it came from');
    expect(document.querySelector('.ws-lineagent')!.textContent).not.toContain('QUICKBOOKS · REALM PSL-NG');
  });

  it('every fixture page shows SAMPLE DATA because the record says so; a copy with sample false does not', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    for (const id of IDS) {
      await open(item(id));
      expect(document.querySelector('.work-lineend')!.textContent, id).toContain('SAMPLE DATA');
      cleanup();
    }
    await open({ ...item('W-4203'), sample: false });
    expect(document.querySelector('.work-lineend')!.textContent).not.toContain('SAMPLE DATA');
  });
});

describe('holds (AC 5, 6)', () => {
  it('W-4205 reviewer not set: the backend’s status, fact and next; no Decide panel, no button, no POST and no reviewer named', async () => {
    await open(item('W-4205'));
    expect(status().textContent).toBe('SETUP NEEDED');
    expect(factValue('Who reviews ledger sources')).toContain('NOT SET');
    expect(ws().getByText('An admin sets Who reviews ledger sources in Setup · Finance rules. The review starts then.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.work-overview')!.querySelectorAll('button, a.psl-btn, a[href^="/setup"], a[href="/exceptions"]')).toHaveLength(0);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    // the signed-in name is the shell's; the page names no reviewer or role
    expect(document.querySelector('main')!.textContent).not.toContain('Ada Okafor');
    expect(document.body.textContent).not.toContain('Ledger reviewer');
    await settle();
    expect(posts()).toHaveLength(0);
  });

  it('no page draws a control for the three ledger setup keys', async () => {
    for (const id of IDS) {
      await open(item(id));
      const overview = document.querySelector('.work-overview')!;
      expect(overview.querySelectorAll('a[href^="/setup"]'), id).toHaveLength(0);
      expect([...overview.querySelectorAll('button')].map((b) => b.textContent).join(' '), id).not.toMatch(/Setup|rules|reviewer/i);
      cleanup();
    }
  });

  it('W-4208: Unknown with proof sends one step with inputs.found unknown; the re-read draws the CHECK HELD hold with no step and no Decide panel', async () => {
    await open(item('W-4208'));
    await click('Record observation');
    choose('unknown');
    await upload();
    await submit();
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    expect(posts('/steps')[0].body!.inputs).toEqual({ found: 'unknown' });
    await waitFor(() => expect(status().textContent).toBe('CHECK HELD'));
    expect(document.querySelectorAll('.ws-stations .psl-station')[2].className).toContain('stopped');
    expect(factValue('What was found')).toContain('UNKNOWN');
    expect(factValue('Verification rules')).toContain('NOT SET');
    expect(ws().getByText('The check stays held. What happens next depends on Verification rules, which an admin sets in Setup · Finance rules.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide')).toBeNull();
  });

  it('the hold comes only from the re-read: a re-read that still serves the observe state shows no hold', async () => {
    onStep = () => stepDone();
    await open(item('W-4208'));
    await click('Record observation');
    choose('more_than_one');
    await upload();
    await submit();
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    expect(posts('/steps')[0].body!.inputs).toEqual({ found: 'more_than_one' });
    await waitFor(() => expect(reads('W-4208')).toBeGreaterThan(1));
    await settle();
    expect(status().textContent).toBe('RECORD WHAT YOU FOUND');
    expect(document.body.textContent).not.toContain('CHECK HELD');
  });

  it('W-4209 held: the status, station 3 stopped, the facts and next, and no control', async () => {
    await open(item('W-4209'));
    expect(status().textContent).toBe('CHECK HELD');
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.work-overview')!.querySelectorAll('a[href="/exceptions"]')).toHaveLength(0);
  });
});

describe('who may act (AC 7, 13)', () => {
  it('W-4206 (took part) and W-4207 (not the role) show the backend’s reason, no button and send no claim', async () => {
    await open(item('W-4206'));
    expect(await ws().findByText('You prepared LED-0052 v1, so someone else must review it.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    cleanup();
    await open(item('W-4207'));
    expect(await ws().findByText('This decision needs a Ledger reviewer.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    await settle();
    expect(posts()).toHaveLength(0);
  });

  it('W-4210: Record observation is drawn inert with its reason; pressing it opens no form and sends nothing', async () => {
    await open(item('W-4210'));
    expect(ws().getByText('You captured this source, so someone else must look it up.')).toBeTruthy();
    const step = ws().getByRole('button', { name: 'Record observation' });
    expect(step.getAttribute('aria-disabled') === 'true' || step.hasAttribute('disabled')).toBe(true);
    await act(async () => {
      fireEvent.click(step);
    });
    expect(ws().queryByRole('form')).toBeNull();
    await settle();
    expect(posts()).toHaveLength(0);
  });

  it('finance_lead, ceo and pm see the same controls on every fixture; the new code reads no /me', async () => {
    const seen: Record<string, string[][]> = {};
    for (const persona of ['finance_lead', 'ceo', 'pm']) {
      who = persona;
      seen[persona] = [];
      for (const id of IDS) {
        await open(item(id));
        if (id === 'W-4203' || id === 'W-4212') await ready();
        else await settle();
        seen[persona].push(buttons() as string[]);
        cleanup();
      }
    }
    expect(seen.ceo).toEqual(seen.finance_lead);
    expect(seen.pm).toEqual(seen.finance_lead);
    for (const file of ['features/workspace/InlineDecide.tsx', 'features/workspace/Workspace.tsx', 'features/workspace/labels.ts']) {
      expect(readFileSync(join(__dirname, '../src', file), 'utf8'), file).not.toMatch(/useMe\b|\/api\/v1\/me\b|is_you|prepared_by/);
    }
  });
});

describe('record what you found (AC 10, 11)', () => {
  it('opens the step form: a required choice of four with nothing selected and a required Proof; empty sends nothing and focuses the first problem', async () => {
    await open(item('W-4202'));
    await click('Record observation');
    const select = found();
    expect(select.textContent).toBe('Choose…');
    fireEvent.click(select);
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Found', 'Not found', 'Unknown', 'More than one']);
    expect(screen.getAllByRole('option').every((o) => o.getAttribute('aria-selected') !== 'true')).toBe(true);
    fireEvent.click(select);
    expect(ws().getByText('Recording what you saw isn’t an approval. “Unknown” or “More than one” holds the check.')).toBeTruthy();
    expect(ws().getByText('Proof')).toBeTruthy();
    await submit();
    expect(posts()).toHaveLength(0);
    expect(await ws().findByText('Add what you found to continue.')).toBeTruthy();
    expect(document.activeElement).toBe(found());
    expect(found().getAttribute('aria-invalid')).toBe('true');
    expect(describedBy(found())).toContain('Add what you found to continue.');
    expect(ws().getByText('Add proof to continue.').closest('[role="alert"]')).toBeTruthy();
    choose('found');
    await submit();
    expect(posts()).toHaveLength(0);
    expect(ws().getByText('Add proof to continue.')).toBeTruthy();
  });

  it('uploads once with kind ledger_observation, case_revision 4 and CSRF, then sends exactly one step; the re-read is the review with the prepared_by_you copy', async () => {
    await open(item('W-4202'));
    await click('Record observation');
    choose('found');
    await upload();
    const [proof] = posts('/evidence');
    expect(proof.path).toBe('/api/v1/cases/C-LED-0052/evidence');
    expect(proof.body).toMatchObject({ kind: 'ledger_observation', filename: 'qb-screenshot-je7741.png', case_revision: 4 });
    expect(uploadRequest(proof.body)).toBe(true);
    expect(proof.csrf).toBe('mock-csrf-finance_lead');
    expect(posts('/steps')).toHaveLength(0);
    await act(async () => {
      fireEvent.submit(form());
      fireEvent.submit(form());
    });
    await waitFor(() => expect(status().textContent).toBe('AWAITING FINANCE DECISION'));
    expect(posts('/steps')).toHaveLength(1);
    const [step] = posts('/steps');
    expect(step.path).toBe('/api/v1/work/W-4202/steps');
    expect(Object.keys(step.body!).sort()).toEqual(['evidence_ids', 'expected_revision', 'idempotency_key', 'inputs', 'step']);
    expect(step.body).toMatchObject({ expected_revision: 2, step: 'record_observation', inputs: { found: 'found' }, evidence_ids: ['EV-C-LED-0052-1'] });
    expect(step.body!.idempotency_key).toMatch(UUID);
    expect(stepRequest(step.body)).toBe(true);
    expect(step.csrf).toBe('mock-csrf-finance_lead');
    expect(await ws().findByText('You prepared LED-0052 v1, so someone else must review it.')).toBeTruthy();
    expect(buttons().filter((b) => b === 'Approve reference')).toHaveLength(0);
    expect(taskPosts()).toHaveLength(0);
  });

  it('never says recorded before the re-read: with the re-read pending after a 200, no notice; once it lands the review and the notice appear together', async () => {
    let release!: (response: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      release = resolve;
    });
    onStep = () => stepDone('Observation recorded.');
    await open(item('W-4202'));
    readAnswer = () => (posts('/steps').length > 0 ? pending : json(200, served));
    await click('Record observation');
    choose('found');
    await upload();
    await submit();
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    await settle();
    expect(notices()).not.toMatch(/recorded|Done:/i);
    expect(status().textContent).toBe('RECORD WHAT YOU FOUND');
    await act(async () => {
      release(json(200, item('W-4202.next')));
    });
    await waitFor(() => expect(status().textContent).toBe('AWAITING FINANCE DECISION'));
    expect(notices()).toContain('Observation recorded.');
  });

  it('a 5xx on the upload shows the proof problem and sends no step', async () => {
    onUpload = () => json(500, { code: 'server_error', message: 'Down.' });
    await open(item('W-4202'));
    await click('Record observation');
    choose('found');
    await upload();
    expect(ws().getByText('Couldn’t upload. Try again.')).toBeTruthy();
    await submit();
    expect(posts('/steps')).toHaveLength(0);
  });

  it('a 409 on the upload re-reads the case revision and the next upload carries the re-read value', async () => {
    let first = true;
    onUpload = (body) => {
      if (first) {
        first = false;
        served = { ...served, case_revision: 6 };
        return json(409, { code: 'stale', message: 'Changed.' });
      }
      return json(200, { evidence_id: 'EV-C-LED-0052-1', sha256: 'a'.repeat(64), case_revision: (body.case_revision as number) + 1 });
    };
    await open(item('W-4202'));
    await click('Record observation');
    await upload();
    expect(await ws().findByText('This item changed. Add the file again.')).toBeTruthy();
    await waitFor(() => expect(reads('W-4202')).toBeGreaterThan(1));
    expect(posts('/evidence')).toHaveLength(1);
    await upload(undefined, 2);
    expect(posts('/evidence')[1].body!.case_revision).toBe(6);
  });

  it('removing the file with × leaves Proof empty, and submitting then sends nothing', async () => {
    await open(item('W-4202'));
    await click('Record observation');
    choose('found');
    await upload();
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Remove qb-screenshot-je7741.png' }));
    });
    expect(ws().queryByText(/qb-screenshot-je7741\.png/)).toBeNull();
    expect(document.body.textContent).not.toMatch(/deleted/i);
    await submit();
    expect(posts('/steps')).toHaveLength(0);
    expect(ws().getByText('Add proof to continue.')).toBeTruthy();
  });

  it('a 403 on the upload says so and sends no step', async () => {
    onUpload = () => json(403, { code: 'forbidden', message: 'No.' });
    await open(item('W-4202'));
    await click('Record observation');
    choose('found');
    await upload();
    expect(ws().getByText('You can’t add proof to this item.')).toBeTruthy();
    await submit();
    expect(posts('/steps')).toHaveLength(0);
  });
});

describe('approve and reject (AC 9, 12)', () => {
  it('Approve claims once, then sends {verdict: approve, expected_revision: 1} with CSRF and no note; Verified only after the re-read', async () => {
    await open(item('W-4203'));
    await ready();
    expect(posts('/api/v1/tasks/T-4203/claim')).toHaveLength(1);
    expect(said()).not.toMatch(/verified/i);
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Approve reference' }));
      fireEvent.click(ws().getByRole('button', { name: 'Approve reference' }));
    });
    await waitFor(() => expect(status().textContent).toBe('VERIFIED'));
    expect(posts('/api/v1/tasks/T-4203/claim')).toHaveLength(1);
    expect(posts('/decision')).toHaveLength(1);
    const [decision] = posts('/decision');
    expect(decision.path).toBe('/api/v1/tasks/T-4203/decision');
    expect(decision.body).toEqual({ verdict: 'approve', expected_revision: 1 });
    expect(decideRequest(decision.body)).toBe(true);
    expect(decision.csrf).toBe('mock-csrf-finance_lead');
    expect(factValue('Reference recorded')).toBe('YES · 14 NOV');
    expect(buttons()).toEqual([]);
  });

  it('a 200 whose re-read still serves the review never says Verified; the panel’s notice is F-33’s decision notice only', async () => {
    onDecide = (body, path) => answer(taskOf(path), body.verdict as string, 'verified');
    await open(item('W-4203'));
    await ready();
    await click('Approve reference');
    await waitFor(() => expect(posts('/decision')).toHaveLength(1));
    await waitFor(() => expect(reads('W-4203')).toBeGreaterThan(1));
    await settle();
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect(said()).not.toMatch(/verified/i);
    // merged F-33 behaviour (spec difference, build.md): a confirmed 200 with a re-read says the decision is recorded
    expect(said()).toContain('LED-0052 v1 is approved');
    expect(factValue('Reference recorded')).toBeUndefined();
  });

  it('Reject needs a note: empty and blank send nothing and focus the note with the announced message; over 2000 characters is refused', async () => {
    await open(item('W-4203'));
    await ready();
    await click('Reject');
    expect(posts('/decision')).toHaveLength(0);
    expect(ws().getByText('Add a note to reject it.')).toBeTruthy();
    expect(document.activeElement).toBe(note());
    expect(note().getAttribute('aria-invalid')).toBe('true');
    expect(describedBy(note())).toContain('Add a note to reject it.');
    fireEvent.change(note(), { target: { value: '   ' } });
    await click('Reject');
    expect(posts('/decision')).toHaveLength(0);
    expect(ws().getByText('Add a note to reject it.')).toBeTruthy();
    fireEvent.change(note(), { target: { value: 'x'.repeat(2001) } });
    await click('Reject');
    expect(posts('/decision')).toHaveLength(0);
    expect(ws().getByText('Keep the note to 2000 characters or fewer.')).toBeTruthy();
  });

  it('with a note one POST with the trimmed note; the re-read shows REJECTED read-only with no Correct step', async () => {
    await open(item('W-4203'));
    await ready();
    fireEvent.change(note(), { target: { value: '  Wrong journal: JE-7714 was meant.  ' } });
    await click('Reject');
    await waitFor(() => expect(status().textContent).toBe('REJECTED'));
    expect(posts('/decision').map((p) => p.body)).toEqual([{ verdict: 'reject', note: 'Wrong journal: JE-7714 was meant.', expected_revision: 1 }]);
    expect(buttons()).toEqual([]);
    expect(screen.queryByRole('button', { name: /Correct/ })).toBeNull();
  });
});

describe('refusals (AC 14)', () => {
  it('403 on decide: the read-only view from the re-read reason, and no approved', async () => {
    onDecide = () => {
      served = { ...item('W-4203'), tasks: [{ ...item('W-4203').tasks[0], you_can_act: false, cannot_act_reason: 'prepared_by_you' }] };
      return json(403, { code: 'forbidden', message: 'No.' });
    };
    await open(item('W-4203'));
    await ready();
    await click('Approve reference');
    expect(await ws().findByText('You prepared LED-0052 v1, so someone else must review it.')).toBeTruthy();
    expect(said()).not.toMatch(/approved|verified/i);
    expect(buttons()).toEqual([]);
  });

  it('403 on the step: “You can’t take that step.”', async () => {
    onStep = () => json(403, { code: 'forbidden', message: 'No.' });
    await open(item('W-4202'));
    await click('Record observation');
    choose('found');
    await upload();
    await submit();
    expect(await screen.findByText('You can’t take that step.')).toBeTruthy();
    expect(notices()).not.toMatch(/recorded/i);
  });

  it('409 on decide: the stale view keeps the note and sends again only on a new press with the new revision', async () => {
    const newer = { ...item('W-4203'), revision: 4, tasks: [{ ...item('W-4203').tasks[0], revision: 2 }] };
    newer.workspace = { ...newer.workspace!, revision: 4 };
    onDecide = () => {
      served = newer;
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-4203'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Wrong period.' } });
    await click('Reject');
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    await settle();
    expect(posts('/decision')).toHaveLength(1);
    await click('Review the latest');
    await ready();
    expect(note().value).toBe('Wrong period.');
    onDecide = (body, path) => answer(taskOf(path), body.verdict as string, 'cancelled');
    await click('Reject');
    await waitFor(() => expect(posts('/decision')).toHaveLength(2));
    expect(posts('/decision')[1].body).toEqual({ verdict: 'reject', note: 'Wrong period.', expected_revision: 2 });
  });

  it('409 on decide after another reviewer decided: the re-read shows their outcome, the stale sentence and the unsent note stay on the page', async () => {
    onDecide = () => {
      served = item('W-4203.approve');
      return json(409, { code: 'stale', message: 'Someone changed this since you opened it.' });
    };
    await open(item('W-4203'));
    await ready();
    fireEvent.change(note(), { target: { value: '  Stale tab note  ' } });
    await click('Reject');
    await waitFor(() => expect(status().textContent).toBe('VERIFIED'));
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(ws().getByText('Your note wasn’t sent: “Stale tab note”')).toBeTruthy();
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(notices()).not.toMatch(/is approved|was rejected/);
    expect(posts('/decision')).toHaveLength(1);
  });

  it('an approve that loses the race says nothing was recorded and names no note', async () => {
    onDecide = () => {
      served = item('W-4203.reject');
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-4203'));
    await ready();
    await click('Approve reference');
    await waitFor(() => expect(status().textContent).toBe('REJECTED'));
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(notices()).not.toMatch(/note wasn’t sent|is approved/);
    expect(posts('/decision')).toHaveLength(1);
  });

  it('409 on the step re-reads, keeps the choice and the uploaded proof, and sends nothing on its own', async () => {
    onStep = () => {
      served = { ...item('W-4202'), revision: 3, workspace: { ...item('W-4202').workspace!, revision: 3 } };
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-4202'));
    await click('Record observation');
    choose('not_found');
    await upload();
    await submit();
    expect(await screen.findByText('This changed while you were working. Showing version 3.')).toBeTruthy();
    expect(found().textContent).toBe('Not found');
    expect(ws().getByText(/qb-screenshot-je7741\.png/)).toBeTruthy();
    await settle();
    expect(posts('/steps')).toHaveLength(1);
    expect(posts('/evidence')).toHaveLength(1);
  });

  it('422 shows the backend message under the field, and under the note', async () => {
    onStep = () => json(422, { code: 'invalid', message: 'Check these fields: found.', fields: [{ name: 'found', message: 'Pick one of the four answers.' }] });
    await open(item('W-4202'));
    await click('Record observation');
    choose('found');
    await upload();
    await submit();
    expect(await ws().findByText('Pick one of the four answers.')).toBeTruthy();
    cleanup();
    onDecide = () => json(422, { code: 'invalid', message: 'Say which journal.', fields: [{ name: 'note', message: 'Say which journal.' }] });
    await open(item('W-4203'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Wrong.' } });
    await click('Reject');
    expect(await ws().findByText('Say which journal.')).toBeTruthy();
  });
});

describe('uncertain writes (AC 15, 16)', () => {
  it('W-4212: approve and reject answer effect_uncertain; the page shows the re-read CHECKING, never Verified, approved or rejected', async () => {
    for (const verdict of ['approve', 'reject'] as const) {
      await open(item('W-4212'));
      await ready();
      if (verdict === 'reject') fireEvent.change(note(), { target: { value: 'Wrong period.' } });
      await click(verdict === 'approve' ? 'Approve reference' : 'Reject');
      await waitFor(() => expect(status().textContent).toBe('CHECKING'));
      expect(await screen.findByText('LED-0052 v1: result not confirmed')).toBeTruthy();
      expect(said()).not.toMatch(/verified|is approved|was rejected/i);
      cleanup();
      sent = [];
    }
  });

  for (const [name, reply] of [
    ['a 500', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
  ] as const) {
    it(`W-4203: ${name} on decide re-reads first, shows the uncertain notice and never sends again by itself`, async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
      onDecide = reply as unknown as Handler;
      await open(item('W-4203'));
      await ready();
      const before = sent.length;
      await click('Approve reference');
      expect(await screen.findByText(/We couldn.t confirm your decision/)).toBeTruthy();
      const after = sent.slice(before);
      expect(after[0].path).toBe('/api/v1/tasks/T-4203/decision');
      expect(after[1]).toMatchObject({ method: 'GET', path: '/api/v1/work/W-4203' });
      expect(said()).not.toMatch(/is approved|was rejected|verified/i);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(posts('/decision')).toHaveLength(1);
    }, 90_000);
  }

  it('W-4213: the step is written and answers 500; the page re-reads first, draws the review and says it could not confirm, never “Observation recorded.”', async () => {
    onStep = () => {
      served = item('W-4213.next');
      return json(500, { code: 'server_error', message: 'Down.' });
    };
    await open(item('W-4213'));
    await click('Record observation');
    choose('found');
    await upload();
    const before = sent.length;
    await submit();
    expect(await screen.findByText('We couldn’t confirm this step. Check the page before trying again.')).toBeTruthy();
    const after = sent.slice(before);
    expect(after[0]).toMatchObject({ method: 'POST', path: '/api/v1/work/W-4213/steps' });
    expect(after[1]).toMatchObject({ method: 'GET', path: '/api/v1/work/W-4213' });
    await waitFor(() => expect(status().textContent).toBe('AWAITING FINANCE DECISION'));
    expect(document.body.textContent).not.toContain('Observation recorded.');
    // the re-read offers no observation step, so there is nothing to try again; one step was sent
    const retry = ws().queryAllByRole('button').find((b) => b.textContent === 'Try again');
    if (retry) {
      await act(async () => {
        fireEvent.click(retry);
      });
      expect(posts('/steps').every((p) => p.body!.idempotency_key === posts('/steps')[0].body!.idempotency_key)).toBe(true);
    } else expect(posts('/steps')).toHaveLength(1);
  });

  it('a 500 before the write keeps the form; Try again reuses the same idempotency key', async () => {
    let calls = 0;
    onStep = () => {
      calls += 1;
      if (calls === 1) return json(500, { code: 'server_error', message: 'Down.' });
      served = item('W-4202.next');
      return stepDone('Observation recorded.');
    };
    await open(item('W-4202'));
    await click('Record observation');
    choose('found');
    await upload();
    await submit();
    expect(await screen.findByText('We couldn’t confirm this step. Check the page before trying again.')).toBeTruthy();
    await submit();
    await waitFor(() => expect(posts('/steps')).toHaveLength(2));
    expect(posts('/steps')[1].body!.idempotency_key).toBe(posts('/steps')[0].body!.idempotency_key);
    await waitFor(() => expect(status().textContent).toBe('AWAITING FINANCE DECISION'));
  });
});

describe('access (AC 17)', () => {
  it('401 on read shows the signed-out state with next=/work/W-4203', async () => {
    readAnswer = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    served = item('W-4203');
    render(
      <AppShell>
        <WorkItemView id="W-4203" tab="overview" />
      </AppShell>,
    );
    const link = await screen.findByRole('link', { name: /sign in/i });
    expect(link.getAttribute('href')).toContain('next=%2Fwork%2FW-4203');
  });

  it('401 on decide and on the step show the signed-out state', async () => {
    onDecide = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await open(item('W-4203'));
    await ready();
    await click('Approve reference');
    expect((await screen.findByRole('link', { name: /sign in/i })).getAttribute('href')).toContain('next=%2Fwork%2FW-4203');
    cleanup();
    onStep = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await open(item('W-4202'));
    await click('Record observation');
    choose('found');
    await upload();
    await submit();
    expect((await screen.findByRole('link', { name: /sign in/i })).getAttribute('href')).toContain('next=%2Fwork%2FW-4202');
  });

  it('403 and 404 on read look the same: no title, fact or agent step; persona none gets it with no further call', async () => {
    const texts: string[] = [];
    for (const code of [403, 404]) {
      readAnswer = () => json(code, { code: code === 403 ? 'forbidden' : 'not_found', message: 'No.' });
      served = item('W-4201');
      render(
        <AppShell>
          <WorkItemView id="W-4201" tab="overview" />
        </AppShell>,
      );
      await screen.findByText(/isn.t open to you|can.t open|not open/i);
      const main = document.querySelector('main')!.textContent ?? '';
      for (const text of ['QuickBooks journal', 'JE-7741', 'QUICKBOOKS', 'Read the ledger source file']) expect(main, text).not.toContain(text);
      texts.push(main);
      cleanup();
    }
    expect(texts[0]).toBe(texts[1]);
    who = 'none';
    sent = [];
    readAnswer = () => json(403, { code: 'forbidden', message: 'No.' });
    render(
      <AppShell>
        <WorkItemView id="W-4201" tab="overview" />
      </AppShell>,
    );
    await screen.findByText('No sections are open to your role yet.');
    await settle();
    expect(sent.filter((r) => r.path.startsWith('/api/v1/work/'))).toHaveLength(0);
    expect(posts()).toHaveLength(0);
  });
});

describe('phone (AC 18)', () => {
  it('Record observation opens the full-height Drawer with the Select and the Proof; Cancel closes it and returns focus', async () => {
    phone();
    await open(item('W-4202'));
    await click('Record observation');
    const dialog = await screen.findByRole('dialog', { name: 'Record observation' });
    expect(within(dialog).getByRole('combobox', { name: /What you found/ })).toBeTruthy();
    expect(dialog.querySelector('input[type="file"]')).toBeTruthy();
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement?.textContent).toBe('Record observation');
  });

  it('in the Drawer the observation sends one upload and one step', async () => {
    phone();
    await open(item('W-4202'));
    await click('Record observation');
    const dialog = await screen.findByRole('dialog', { name: 'Record observation' });
    choose('found', within(dialog));
    await upload(dialog);
    await submit(within(dialog));
    await waitFor(() => expect(status().textContent).toBe('AWAITING FINANCE DECISION'));
    expect(posts('/steps')).toHaveLength(1);
    expect(posts('/steps')[0].body).toMatchObject({ inputs: { found: 'found' }, evidence_ids: ['EV-C-LED-0052-1'] });
  });

  it('the pinned Decide bar has Approve reference and Reject; Reject opens the Drawer with the Note; Escape closes it and returns focus', async () => {
    phone();
    await open(item('W-4203'));
    await ready();
    expect(buttons()).toEqual(['Approve reference', 'Reject']);
    await click('Reject');
    const dialog = await screen.findByRole('dialog', { name: 'Reject' });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));
    });
    expect(await within(dialog).findByText('Add a note to reject it.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    await act(async () => {
      fireEvent.keyDown(dialog, { key: 'Escape' });
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement?.textContent).toBe('Reject');
  });

  it('a stale reject from the Drawer keeps the stale sentence and the unsent note once the panel has gone', async () => {
    phone();
    onDecide = () => {
      served = item('W-4203.approve');
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-4203'));
    await ready();
    await click('Reject');
    const dialog = await screen.findByRole('dialog', { name: 'Reject' });
    fireEvent.change(within(dialog).getByLabelText(/^Note/), { target: { value: 'Phone note' } });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));
    });
    await waitFor(() => expect(status().textContent).toBe('VERIFIED'));
    expect(await screen.findByText('Your note wasn’t sent: “Phone note”')).toBeTruthy();
    expect(screen.getByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
  });
});
