// @vitest-environment jsdom
// F-39: the escalation's work item (W-3601 to W-3609) drawn from E-WORK-ITEM `workspace`, with its writes: the PMO Lead's
// decision in place (E-TASK-CLAIM, E-TASK-DECIDE through useDecision) and Send for review (E-WORK-STEP). Contract mock only;
// the fetch stub stands in for the backend. Nothing in part 1 reaches the client, so no page may say it did.
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
  usePathname: () => '/work/W-3602',
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
const decided = (verdict: string, task = 'T-3602') => json(200, { task_id: task, verdict, decided_by: 'Tunde Bello', decided_at: '2026-11-13T14:05:00Z', work_state: 'action_needed' });

beforeEach(() => {
  sent = [];
  readAnswer = null;
  who = 'pm';
  onClaim = (body) => json(200, { task_id: 'T', revision: body.expected_revision, claimed_by: 'Tunde Bello' });
  onDecide = (body) => {
    const next = item(`W-3602.${body.verdict === 'approve' ? 'approve' : 'reject'}`);
    served = next;
    return decided(body.verdict as string);
  };
  onStep = () => {
    served = item('W-3604.next');
    return json(200, { work_id: 'W-3604', state: 'action_needed', revision: 3, outcome: 'done', message: 'Done: Send for review.' });
  };
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
const ready = async () => waitFor(() => expect(ws().getByRole('button', { name: 'Escalate to the client' }).hasAttribute('disabled')).toBe(false));
const click = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const note = () => ws().getByLabelText('Note (needed to reject)') as HTMLTextAreaElement;
/** What the page says about the write: its notices, the status tag and the Decide panel (not the station names or the facts strip). */
const said = () => [document.querySelector('.ws-notices'), status(), document.querySelector('.ws-idecide'), document.querySelector('.ws-side')].map((el) => el?.textContent ?? '').join(' ');
const factValue = (label: string) => [...document.querySelectorAll('.ws-fact')].find((f) => f.querySelector('dt')?.textContent === label)?.querySelector('dd')?.textContent;

const body = () => document.body.textContent ?? '';
const FORBIDDEN = /sent to|was sent|has been sent|delivered|received|This sends to the client/i;
const card = () => document.querySelector('.ws-lineagent');

describe('four states from data (AC 1, 2)', () => {
  it('W-3601 investigating: facts, Tola working with steps and sources, Started, Ask Tola, and no decide control', async () => {
    await open(item('W-3601'));
    expect(status().textContent).toBe('INVESTIGATING');
    expect(status().className).toContain('agent');
    expect(factValue('Raised by')).toBe('You');
    expect(factValue('From issue')).toBe('ISS-0241');
    expect(factValue('Asked for')).toBe('ESCALATE TO THE CLIENT');
    const c = card()!;
    expect(c.textContent).toContain('Tola');
    expect(c.textContent).toContain('WORKING');
    expect(c.textContent).toContain('step 3 of 4');
    for (const source of ['ISS-0241 · 3 WEEKS OPEN', 'ACT-0420 · OVERDUE 15 DAYS', 'MILESTONE 3 · GO-LIVE 4 DEC']) expect(c.textContent).toContain(source);
    expect(c.querySelector('.psl-agent__foot')!.textContent).toMatch(/^Started .+Ask Tola$/);
    expect(ws().getByRole('link', { name: 'Ask Tola' }).getAttribute('href')).toBe('/assistant');
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    await new Promise((r) => setTimeout(r, 50));
    expect(taskPosts()).toHaveLength(0);
  });

  it('W-3602 decide: What Tola found, Decide · PMO Lead with the consequence, both buttons, and no visible agent card', async () => {
    await open(item('W-3602'));
    expect(status().textContent).toBe('YOUR DECISION');
    expect(ws().getByRole('heading', { name: 'What Tola found' })).toBeTruthy();
    expect(factValue('Client test data')).toBe('15 DAYS LATE');
    expect(factValue('Delays')).toBe('MILESTONE 3 · GO-LIVE 4 DEC');
    expect(factValue('Already asked the client')).toBe('3 TIMES');
    const panel = await ws().findByRole('region', { name: 'Decide · PMO Lead' });
    expect(within(panel).getByText("Escalating means a formal message to the client's sponsor, reviewed before it's sent.")).toBeTruthy();
    expect(within(panel).getByLabelText('Note (needed to reject)')).toBeTruthy();
    await ready();
    expect(within(panel).getAllByRole('button').map((b) => b.textContent)).toEqual(['Escalate to the client', "Don't escalate"]);
    expect(card()).toBeNull();
  });

  it('W-3603 not escalated: the quote as returned, Next, Back to the issue to W-3609, no buttons, no visible card', async () => {
    await open(item('W-3603'));
    expect(status().textContent).toBe('NOT ESCALATED');
    expect(ws().getByText('Kemi Adebayo decided not to escalate on 13 Nov: “Their new lead starts Monday. Ask them directly first.”')).toBeTruthy();
    expect(ws().getByRole('heading', { name: 'Next' })).toBeTruthy();
    expect(ws().getByText('The issue stays open with its owner. You can raise the escalation again later.')).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Back to the issue' }).getAttribute('href')).toBe('/work/W-3609');
    expect(buttons()).toEqual([]);
    expect(card()).toBeNull();
  });

  it('W-3604 draft: Message v1 as returned, Tola done with three details, Send for review, no Send/Approve/Edit control', async () => {
    await open(item('W-3604'));
    expect(status().textContent).toBe('MESSAGE DRAFTED');
    expect(ws().getByRole('heading', { name: 'Message v1' })).toBeTruthy();
    expect(ws().getByText("Your team's test data is now 15 days late (asked 22 Oct, 29 Oct, 5 Nov). Go-live on 4 Dec depends on it. Could you confirm a date this week?")).toBeTruthy();
    expect(card()!.textContent).toContain('DONE');
    for (const d of ['ESCALATE · 13 NOV', 'FACTS AND DATES ONLY', 'SPONSOR · PROJECT CONTACT']) expect(card()!.textContent).toContain(d);
    expect(buttons()).toEqual(['Send for review']);
    expect(screen.queryByRole('button', { name: /Approve|Edit|^Send$/ })).toBeNull();
  });

  it('a fixture step source changes only that text; the dates in Message v1 are not reformatted', async () => {
    const w = item('W-3601');
    w.agent.steps![0].source = 'ISS-0241 · 4 WEEKS OPEN';
    await open(w);
    expect(card()!.textContent).toContain('ISS-0241 · 4 WEEKS OPEN');
    expect(card()!.textContent).toContain('ACT-0420 · OVERDUE 15 DAYS');
    cleanup();
    const f = item('W-3602');
    f.workspace!.sections[0].items[2].value = '4 TIMES';
    f.workspace!.sections[0].items[0].value = '16 DAYS LATE';
    await open(f);
    expect(factValue('Already asked the client')).toBe('4 TIMES');
    expect(factValue('Client test data')).toBe('16 DAYS LATE');
    expect(factValue('Delays')).toBe('MILESTONE 3 · GO-LIVE 4 DEC');
  });

  it('no board string is written in src', () => {
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
    // F-16's own eyebrow "NOT YOUR DECISION" contains the board's words, so that one is taken out first
    const own = text.replaceAll('NOT YOUR DECISION', '');
    for (const board of ['INVESTIGATING', 'YOUR DECISION', 'NOT ESCALATED', 'MESSAGE DRAFTED', 'Escalate to the client', "Don't escalate", 'FACTS AND DATES']) expect(own, board).not.toContain(board);
  });
});

describe('round 2: the boards draw no extra card, no empty line and the board tones', () => {
  it('W-3601 and W-3603 draw no "Decide whether to escalate" task card', async () => {
    for (const id of ['W-3601', 'W-3603']) {
      await open(item(id));
      expect(screen.queryByText('Decide whether to escalate')).toBeNull();
      expect(document.querySelector('.work-aside .psl-panel--decide')).toBeNull();
      cleanup();
    }
  });

  it('W-3604 shows the message as the section item, with no empty line and no warning callout', async () => {
    await open(item('W-3604'));
    const section = ws().getByRole('heading', { name: 'Message v1' }).closest('section')!;
    expect(section.textContent).toContain('Could you confirm a date this week?');
    expect(section.textContent).not.toContain('Nothing here yet.');
    expect(section.querySelector('.psl-callout--warning')).toBeNull();
  });

  it('the not-escalated sentence is an info callout, and the status tones are the boards (drafted agent, not escalated neutral)', async () => {
    await open(item('W-3603'));
    expect(document.querySelector('.ws-note.psl-callout--info')?.textContent).toContain('decided not to escalate');
    expect(document.querySelector('.ws-note.psl-callout--warning')).toBeNull();
    expect(status().className).toContain('neutral');
    cleanup();
    await open(item('W-3604'));
    expect(status().className).toContain('agent');
  });
});

describe('unknown, sample and the sent-to-client rule (AC 3, 5, 14)', () => {
  it('W-3606: Delays and Already asked the client read Unknown, never 0, blank or a dash', async () => {
    await open(item('W-3606'));
    expect(factValue('Delays')).toBe('Unknown');
    expect(factValue('Already asked the client')).toBe('Unknown');
    expect(factValue('Client test data')).toBe('15 DAYS LATE');
    for (const dd of document.querySelectorAll('.ws-fact dd')) expect(dd.textContent!.trim()).not.toMatch(/^(0|0 TIMES|-|—|)$/);
  });

  it('every fixture is marked sample because the record says so; a copy with sample false is not', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    for (const id of ['W-3601', 'W-3602', 'W-3603', 'W-3604', 'W-3605', 'W-3606', 'W-3607', 'W-3608', 'W-3609']) {
      await open(item(id));
      expect(document.querySelector('.work-lineend')!.textContent, id).toContain('SAMPLE DATA');
      cleanup();
    }
    await open({ ...item('W-3602'), sample: false });
    expect(document.querySelector('.work-lineend')!.textContent).not.toContain('SAMPLE DATA');
  });

  it('no fixture, sidecar or notice says anything went to the client; no step sets sends', async () => {
    for (const name of readdirSync(join(fixtures, 'work')).filter((n) => /^W-36\d\d(\.[a-z]+)?\.json$/.test(n) && !n.includes('.steps'))) {
      const id = name.replace('.json', '');
      await open({ ...item(id), id: id.slice(0, 6) });
      // the shared uncertain notice says "Nothing was sent again." (F-16, not this feature's text); nothing else may match
      expect(body().replace(/Nothing was sent again\./g, ''), name).not.toMatch(FORBIDDEN);
      cleanup();
    }
  });
});

describe('who may act (AC 6)', () => {
  it('W-3605 not your role: the reason and Kemi Adebayo · PMO Lead from asked, no button, no claim', async () => {
    await open(item('W-3605'));
    expect(await ws().findByText('This decision needs a PMO Lead.')).toBeTruthy();
    expect(ws().getByText('Kemi Adebayo · PMO Lead')).toBeTruthy();
    cleanup();
    const bare = item('W-3605');
    delete (bare.tasks[0] as { asked?: unknown }).asked;
    await open(bare);
    expect(await ws().findByText('This decision needs a PMO Lead.')).toBeTruthy();
    expect(document.body.textContent).not.toContain('Kemi Adebayo');
    expect(buttons()).toEqual([]);
    await new Promise((r) => setTimeout(r, 50));
    expect(taskPosts()).toHaveLength(0);
  });

  it('the controls follow you_can_act only: pm, finance_lead and ceo see the same buttons', async () => {
    for (const persona of ['pm', 'finance_lead', 'ceo']) {
      who = persona;
      await open(item('W-3602'));
      await ready();
      expect(buttons(), persona).toEqual(['Escalate to the client', "Don't escalate"]);
      cleanup();
    }
    for (const dir of ['workspace', 'work-item']) {
      for (const name of readdirSync(join(__dirname, '../src/features', dir)).filter((n) => /\.tsx?$/.test(n))) {
        expect(readFileSync(join(__dirname, '../src/features', dir, name), 'utf8'), name).not.toMatch(/useMe\b/);
      }
    }
  });
});

describe('escalate and don’t escalate (AC 7 to 9)', () => {
  it('claims once, then one decision {verdict approve, expected_revision} with CSRF; a double press sends one; MESSAGE DRAFTED from the re-read', async () => {
    await open(item('W-3602'));
    await ready();
    expect(posts('/api/v1/tasks/T-3602/claim')).toHaveLength(1);
    await act(async () => {
      const go = ws().getByRole('button', { name: 'Escalate to the client' });
      fireEvent.click(go);
      fireEvent.click(go);
    });
    await waitFor(() => expect(status().textContent).toBe('MESSAGE DRAFTED'));
    const [decision] = posts('/api/v1/tasks/T-3602/decision');
    expect(posts('/decision')).toHaveLength(1);
    expect(decision.body).toEqual({ verdict: 'approve', expected_revision: 1 });
    expect(decideRequest(decision.body)).toBe(true);
    expect(decision.csrf).toBe('mock-csrf-pm');
    expect(body()).not.toMatch(FORBIDDEN);
  });

  it('Don’t escalate needs a note: empty, blank and over 2000 send nothing; with a note one reject with the trimmed note, then NOT ESCALATED and the link', async () => {
    await open(item('W-3602'));
    await ready();
    await click("Don't escalate");
    expect(await screen.findByText('Add a note to reject it.')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(note()));
    fireEvent.change(note(), { target: { value: '   ' } });
    await click("Don't escalate");
    fireEvent.change(note(), { target: { value: 'x'.repeat(2001) } });
    await click("Don't escalate");
    expect(await screen.findByText('Keep the note to 2000 characters or fewer.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    fireEvent.change(note(), { target: { value: '  Their new lead starts Monday.  ' } });
    await click("Don't escalate");
    await waitFor(() => expect(status().textContent).toBe('NOT ESCALATED'));
    expect(posts('/decision').map((p) => p.body)).toEqual([{ verdict: 'reject', expected_revision: 1, note: 'Their new lead starts Monday.' }]);
    expect(decideRequest(posts('/decision')[0].body)).toBe(true);
    expect(ws().getByRole('link', { name: 'Back to the issue' }).getAttribute('href')).toBe('/work/W-3609');
  });

  it('the error under the note is announced', async () => {
    await open(item('W-3602'));
    await ready();
    await click("Don't escalate");
    const message = await screen.findByText('Add a note to reject it.');
    expect(note().getAttribute('aria-invalid')).toBe('true');
    expect(note().getAttribute('aria-describedby')).toContain(message.id || message.closest('[id]')!.id);
  });

  it('a 200 whose re-read still serves the decision shows neither MESSAGE DRAFTED, NOT ESCALATED nor "is approved" as a result', async () => {
    onDecide = (b) => decided(b.verdict as string);
    await open(item('W-3602'));
    await ready();
    await click('Escalate to the client');
    await waitFor(() => expect(posts('/decision')).toHaveLength(1));
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3602').length).toBeGreaterThanOrEqual(3));
    expect(status().textContent).toBe('YOUR DECISION');
    expect(body()).not.toMatch(/MESSAGE DRAFTED|NOT ESCALATED/);
  });
});

describe('uncertain and refused decides (AC 10, 11)', () => {
  const uncertain = (): WorkItem => item('W-3607.approve');

  it('W-3607: a 200 with work_state effect_uncertain shows result not confirmed, never escalated or drafted', async () => {
    onDecide = (b) => {
      served = uncertain();
      return json(200, { task_id: 'T-3607', verdict: b.verdict, decided_by: 'Tunde Bello', decided_at: '2026-11-13T14:05:00Z', work_state: 'effect_uncertain' });
    };
    await open(item('W-3607'));
    await ready();
    await click('Escalate to the client');
    expect(await screen.findByText('Escalation ESC-0012: result not confirmed')).toBeTruthy();
    expect(status().textContent).toBe('RESULT NOT CONFIRMED');
    expect(said()).not.toMatch(/is approved|MESSAGE DRAFTED|has been escalated/i);
    expect(posts('/decision')).toHaveLength(1);
  });

  for (const [name, answer] of [
    ['a 500', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
  ] as const) {
    it(`${name} re-reads first, shows the uncertain notice and never sends again by itself`, async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
      onDecide = answer as unknown as Handler;
      await open(item('W-3602'));
      await ready();
      const before = sent.length;
      await click('Escalate to the client');
      expect(await screen.findByText(/We couldn.t confirm your decision/)).toBeTruthy();
      const after = sent.slice(before);
      expect(after[0].path).toBe('/api/v1/tasks/T-3602/decision');
      expect(after[1]).toMatchObject({ method: 'GET', path: '/api/v1/work/W-3602' });
      expect(said()).not.toMatch(/is approved|MESSAGE DRAFTED|NOT ESCALATED/);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(posts('/decision')).toHaveLength(1);
    }, 90_000);
  }

  it('403: the read-only view; 409: the stale view keeps the note and resends only on a new press; 422: the message under the note', async () => {
    onDecide = () => {
      const w = item('W-3602');
      served = { ...w, tasks: [{ ...w.tasks[0], you_can_act: false, cannot_act_reason: 'not_your_role' }] };
      return json(403, { code: 'forbidden', message: 'No.' });
    };
    await open(item('W-3602'));
    await ready();
    await click('Escalate to the client');
    expect(await ws().findByText('This decision needs a PMO Lead.')).toBeTruthy();
    expect(buttons().filter((b) => b === 'Escalate to the client')).toHaveLength(0);
    cleanup();

    sent = [];
    const newer = { ...item('W-3602'), revision: 2, tasks: [{ ...item('W-3602').tasks[0], revision: 2 }] };
    onDecide = () => {
      served = newer;
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-3602'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Wait for Monday.' } });
    await click("Don't escalate");
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(1);
    await click('Review the latest');
    await ready();
    expect(note().value).toBe('Wait for Monday.');
    expect(posts('/decision')).toHaveLength(1);
    cleanup();

    onDecide = () => json(422, { code: 'invalid', message: 'Say why.', fields: [{ name: 'note', message: 'Say why.' }] });
    await open(item('W-3602'));
    await ready();
    fireEvent.change(note(), { target: { value: 'Nope.' } });
    await click("Don't escalate");
    expect(await ws().findByText('Say why.')).toBeTruthy();
  });
});

describe('QA-3-1: another reviewer decided first', () => {
  // Reviewer A's escalate lands before B's don't escalate: the task is decided, so the re-read has no decide steps left.
  const lostRace = () => {
    onDecide = () => {
      served = item('W-3602.approve');
      return json(409, { code: 'stale_revision', message: 'Someone changed this since you opened it.' });
    };
  };

  it('desktop: the 409 re-read shows MESSAGE DRAFTED, the stale sentence and the unsent note', async () => {
    lostRace();
    await open(item('W-3602'));
    await ready();
    fireEvent.change(note(), { target: { value: '  Wait for their reply first.  ' } });
    await click("Don't escalate");
    await waitFor(() => expect(status().textContent).toBe('MESSAGE DRAFTED'));
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(ws().getByText('Your note wasn’t sent: “Wait for their reply first.”')).toBeTruthy();
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(said()).not.toMatch(/NOT ESCALATED|was rejected|is approved/i);
    expect(posts('/decision')).toHaveLength(1);
  });

  it('phone: the note typed in the Drawer is named as not sent once the Drawer and the panel go', async () => {
    phone();
    lostRace();
    await open(item('W-3602'));
    await ready();
    await click("Don't escalate");
    const dialog = await screen.findByRole('dialog', { name: "Don't escalate" });
    fireEvent.change(within(dialog).getByLabelText(/^Note/), { target: { value: 'Wait for their reply first.' } });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: "Don't escalate" }));
    });
    await waitFor(() => expect(status().textContent).toBe('MESSAGE DRAFTED'));
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(ws().getByText('Your note wasn’t sent: “Wait for their reply first.”')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(1);
  });

  it('an escalate that loses the race says nothing was recorded and names no note', async () => {
    onDecide = () => {
      served = item('W-3602.reject');
      return json(409, { code: 'stale_revision', message: 'Someone changed this since you opened it.' });
    };
    await open(item('W-3602'));
    await ready();
    await click('Escalate to the client');
    await waitFor(() => expect(status().textContent).toBe('NOT ESCALATED'));
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(said()).not.toMatch(/note wasn’t sent|MESSAGE DRAFTED/i);
    expect(posts('/decision')).toHaveLength(1);
  });
});

describe('send for review (AC 12, 13)', () => {
  it('F-52: W-3602 after approve: Send for review completes and the re-read reads WAITING FOR REVIEW', async () => {
    onStep = () => {
      served = item('W-3602.next.send_for_review');
      return json(200, { work_id: 'W-3602', state: 'action_needed', revision: 3, outcome: 'done', message: 'Done: Send for review.' });
    };
    await open(item('W-3602.approve'));
    await click('Send for review');
    await waitFor(() => expect(status().textContent).toBe('WAITING FOR REVIEW'));
    expect(posts('/api/v1/work/W-3602/steps')).toHaveLength(1);
    expect(buttons()).toEqual([]);
  });

  it('one step with CSRF, expected_revision, inputs {} and a UUID key; a retry after a 500 reuses it; WAITING FOR REVIEW only from the re-read', async () => {
    onStep = () => json(500, { code: 'server_error', message: 'Down.' });
    await open(item('W-3604'));
    await click('Send for review');
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    expect(status().textContent).toBe('MESSAGE DRAFTED');
    expect(body()).not.toMatch(/sent for review/i);
    onStep = () => {
      served = item('W-3604.next');
      return json(200, { work_id: 'W-3604', state: 'action_needed', revision: 3, outcome: 'done', message: 'Done: Send for review.' });
    };
    await act(async () => {
      fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    });
    await waitFor(() => expect(status().textContent).toBe('WAITING FOR REVIEW'));
    const [first, second] = posts('/api/v1/work/W-3604/steps');
    expect(first.body).toMatchObject({ expected_revision: 2, step: 'send_for_review' });
    // the shared step writer sends no `inputs` for a step with no fields; the generated request schema accepts that
    expect(first.body!.inputs ?? {}).toEqual({});
    expect(stepRequest(first.body)).toBe(true);
    expect(first.csrf).toBe('mock-csrf-pm');
    expect(first.body!.idempotency_key).toMatch(UUID);
    expect(second.body!.idempotency_key).toBe(first.body!.idempotency_key);
    expect(buttons()).toEqual([]);
    expect(screen.queryByRole('button', { name: /Approve|Send|Return/ })).toBeNull();
    expect(body()).not.toMatch(FORBIDDEN);
  });

  it('W-3608: Send for review is unavailable with the returned reason, nothing is posted whatever is pressed, no reviewer is named', async () => {
    await open(item('W-3608'));
    const reason = 'No one is set to review client messages yet. An admin sets this in Setup.';
    expect(ws().getByText(reason)).toBeTruthy();
    const button = ws().queryByRole('button', { name: 'Send for review' });
    if (button) fireEvent.click(button);
    await new Promise((r) => setTimeout(r, 50));
    expect(posts('/steps')).toHaveLength(0);
    expect(taskPosts()).toHaveLength(0);
    expect(body()).not.toMatch(/Kemi|Ada Okafor/);
  });
});

describe('access and frame (AC 15, 16)', () => {
  it('401 on decide shows signed out with next=/work/W-3602', async () => {
    onDecide = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await open(item('W-3602'));
    await ready();
    await click('Escalate to the client');
    const link = await screen.findByRole('link', { name: /sign in/i });
    expect(link.getAttribute('href')).toContain('next=%2Fwork%2FW-3602');
  });

  it('403 and 404 on read look the same: no title, fact, quote or message', async () => {
    for (const code of [403, 404]) {
      readAnswer = () => json(code, { code: code === 403 ? 'forbidden' : 'not_found', message: 'No.' });
      served = item('W-3604');
      render(
        <AppShell>
          <WorkItemView id="W-3604" tab="overview" />
        </AppShell>,
      );
      await screen.findByText(/isn.t open to you|can.t open|not open/i);
      expect(body()).not.toContain('Client test data');
      expect(body()).not.toContain('Your team');
      cleanup();
    }
  });

  it('the crumbs read as returned and the project tab bar marks none current; the phone bar goes back to the project with ESC-0012', async () => {
    await open(item('W-3604'));
    const crumbs = document.querySelector('.ws-crumbs, nav[aria-label*="readcrumb" i]')?.textContent ?? body();
    expect(crumbs.replace(/\s+/g, ' ')).toMatch(/Projects.*Lagoon Health.*Registers.*Escalations.*ESC-0012/i);
    expect(document.querySelectorAll('[aria-current="page"]').length).toBe(0);
    cleanup();
    phone();
    await open(item('W-3604'));
    expect(document.body.innerHTML).toContain('/projects/P-0101');
    expect(body()).toContain('ESC-0012');
  });
});

describe('phone (AC 8, 17)', () => {
  it('Don’t escalate opens the Drawer with the note; Cancel closes it and returns focus', async () => {
    phone();
    await open(item('W-3602'));
    await ready();
    expect(buttons()).toEqual(['Escalate to the client', "Don't escalate"]);
    await click("Don't escalate");
    const dialog = await screen.findByRole('dialog', { name: "Don't escalate" });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: "Don't escalate" }));
    });
    expect(await within(dialog).findByText('Add a note to reject it.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement?.textContent).toBe("Don't escalate"));
  });
});

describe('other lines are unchanged by the escalation edits', () => {
  it('the issue page W-3609 and F-30’s W-2411 draw no visible agent card; the income page still draws its own', async () => {
    await open(item('W-3609'));
    expect(card()).toBeNull();
    expect(status().textContent).toBe('NO RESPONSE · 15 DAYS');
    cleanup();
    await open(item('W-2411'));
    expect(card()).toBeNull();
    cleanup();
    who = 'finance_lead';
    await open(item('W-2701'));
    expect(card()!.textContent).toContain('WORKING');
  });
});
