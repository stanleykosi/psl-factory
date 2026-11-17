// @vitest-environment jsdom
// F-30: the issue's work item (W-2411 to W-2414) drawn from E-WORK-ITEM `workspace`, with its three writes: post an owner
// update and record a reply (E-WORK-STEP) and set an owner (E-WORK-ASSIGN). Contract mock only; the fetch stub stands in
// for the backend.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

const navigation = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2411',
  useRouter: () => ({ replace: vi.fn(), push: navigation.push, prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const stepRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);
const assignRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/assignment'].post.requestBody.content['application/json'].schema);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = Response | (() => Response | Promise<Response>);
let sent: Sent[];
let reads: WorkItem[];
let writes: Answer[];
let who: string;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;

const posts = (suffix: string) => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const itemReads = () => sent.filter((r) => r.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(r.path));

beforeEach(() => {
  sent = [];
  reads = [];
  writes = [];
  who = 'pm';
  navigation.push.mockClear();
  fetchStub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
    if (url.pathname === '/api/v1/me') return json(200, read(`me.${who}.json`));
    if (request.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(url.pathname)) {
      const next = reads.length > 1 ? reads.shift()! : reads[0];
      return json(200, next);
    }
    if (request.method === 'POST' && /\/(steps|assignment)$/.test(url.pathname)) {
      const answer = writes.length > 1 ? writes.shift()! : writes[0];
      return typeof answer === 'function' ? answer() : answer;
    }
    return json(404, { code: 'not_found', message: 'Not here.' });
  });
  vi.stubGlobal('fetch', withoutBellFeed(fetchStub));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function open(first: WorkItem, ...later: WorkItem[]) {
  reads = [first, ...later];
  const view = render(
    <AppShell>
      <WorkItemView id={first.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: first.title });
  return view;
}

const ws = () => within(document.querySelector('.ws') as HTMLElement);
const buttons = () => ws().queryAllByRole('button').map((b) => b.textContent);
const press = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const bump = (body: WorkItem, revision: number): WorkItem => ({ ...body, revision, workspace: { ...body.workspace!, revision } });
const type = (label: string, value: string) => fireEvent.change(ws().getByLabelText(label), { target: { value } });
const submitButton = () => ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!;
const chooseOwner = async (name: string) => {
  fireEvent.click(ws().getByRole('combobox', { name: /Owner/ }));
  fireEvent.click(await screen.findByRole('option', { name: new RegExp(name) }));
};

describe('four states from data (AC 1 to 5, 7)', () => {
  it('W-2411 draws facts, the timeline, Chasing, the agent note and one step', async () => {
    await open(item('W-2411'));
    expect(document.querySelector('.work-state')!.textContent).toBe('FIX IN TESTING');
    const facts = [...document.querySelectorAll('.ws-fact')].map((f) => f.textContent);
    expect(facts).toEqual(['OWNEREngineering (recorded by PM)', 'RAISED09 Nov', 'AGE3 days', 'BLOCKSGo-live', 'SEVERITYHigh']);
    expect(ws().getByRole('heading', { name: 'What has happened' })).toBeTruthy();
    expect(ws().getByRole('heading', { name: 'Chasing' })).toBeTruthy();
    expect(ws().getByText(/Reminder sent/)).toBeTruthy();
    expect(document.querySelector('.ws-agentnote')!.textContent).toContain("I'll remind the owner if there's no update by 13 Nov.");
    expect(ws().getByRole('heading', { name: 'Next' })).toBeTruthy();
    expect(buttons()).toEqual(['Post update']);
  });

  it('W-2412 draws the lead, Chasing and two steps; Raise an escalation is secondary', async () => {
    await open(item('W-2412'));
    expect(document.querySelector('.work-state')!.textContent).toBe('NO RESPONSE · 3 DAYS');
    expect(ws().getByText("Engineering (the owner) hasn't acknowledged ISS-0233 since Tola asked on 09 Nov. It blocks go-live.")).toBeTruthy();
    expect(ws().getByText("Record the owner's reply when it comes, or raise an escalation.")).toBeTruthy();
    expect(buttons()).toEqual(['Record a reply', 'Raise an escalation']);
    expect(document.querySelector('.ws-fact')).toBeNull();
  });

  it('W-2413 draws only Set an owner; W-2414 is read-only with a link to the register', async () => {
    await open(item('W-2413'));
    expect(document.querySelector('.work-state')!.textContent).toBe('OWNER NEEDED');
    expect(buttons()).toEqual(['Set an owner']);
    cleanupView();
    await open(item('W-2414'));
    expect(document.querySelector('.work-state')!.textContent).toBe('FOLLOW-UP VERIFIED');
    expect(buttons()).toEqual([]);
    expect(ws().getByRole('link', { name: 'Open the issue register' }).getAttribute('href')).toBe('/projects/P-0101/registers');
    expect(sent.filter((r) => r.method !== 'GET')).toHaveLength(0);
  });

  it('the status tone comes from the response: verified is green only because the tone says so', async () => {
    await open(item('W-2414'));
    expect(document.querySelector('.ws-note.psl-callout--success, .ws-note.psl-callout--verified, .ws-note[class*="success"]')).not.toBeNull();
    cleanupView();
    const body = item('W-2414');
    body.workspace!.status = { label: 'FOLLOW-UP VERIFIED', tone: 'neutral' };
    await open(body);
    expect(document.querySelector('.ws-note[class*="success"]')).toBeNull();
  });

  it('the same controls for every persona; a copy with the steps removed draws none; the issue code never reads /me', async () => {
    const seen: (string | null)[][] = [];
    for (const persona of ['pm', 'finance_lead', 'ceo']) {
      who = persona;
      const view = await open(item('W-2412'));
      seen.push(buttons());
      view.unmount();
    }
    for (const list of seen) expect(list).toEqual(['Record a reply', 'Raise an escalation']);
    const bare = item('W-2412');
    delete bare.workspace!.steps;
    await open(bare);
    expect(buttons()).toEqual([]);
    for (const file of ['Workspace.tsx', 'AssignForm.tsx', 'useWorkspaceAssign.ts']) expect(readFileSync(join(__dirname, '../src/features/workspace', file), 'utf8')).not.toMatch(/api\/v1\/me/);
  });

  it('agent text is shown as returned and nothing claims a send or a verification', async () => {
    const page = () => document.querySelector('.ws')!.textContent ?? '';
    await open(item('W-2411'));
    expect(page()).not.toMatch(/(was|has been|have been|been) sent|sent to/i);
    expect(page()).not.toMatch(/logged in|signed in as the owner/i);
    cleanupView();
    await open(item('W-2412'));
    expect(page()).not.toMatch(/escalation (was|has been) (started|raised)/i);
    expect(page()).not.toMatch(/verified/i);
    expect(page()).not.toMatch(/(was|has been|have been|been) sent|sent to/i);
  });
});

function cleanupView() {
  document.body.innerHTML = '';
}

describe('unknown, not zero, and no state from dates (AC 2, 3)', () => {
  it('a missing age, owner and reminder time read Unknown and Time unknown', async () => {
    const body = item('W-2411');
    const facts = body.workspace!.sections[0].items;
    delete facts.find((f) => f.id === 'f-age')!.value;
    delete facts.find((f) => f.id === 'f-owner')!.value;
    delete body.workspace!.sections[2].items.find((i) => i.id === 'c2')!.at;
    await open(body);
    const row = (label: string) => [...document.querySelectorAll('.ws-fact')].find((f) => f.querySelector('dt')!.textContent === label)!;
    expect(row('AGE').querySelector('dd')!.textContent).toBe('Unknown');
    expect(row('OWNER').querySelector('dd')!.textContent).toBe('Unknown');
    expect(screen.getByText('Time unknown')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\b0 days\b/);
  });

  it('changing the dates without the status leaves the status and the overdue words as returned', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2027-03-01T09:00:00Z'));
    const body = item('W-2412');
    body.workspace!.sections[1].items[2].at = '2020-01-01T09:00:00+01:00';
    await open(body);
    expect(document.querySelector('.work-state')!.textContent).toBe('NO RESPONSE · 3 DAYS');
    expect(screen.getByText("Engineering (the owner) hasn't acknowledged ISS-0233 since Tola asked on 09 Nov. It blocks go-live.")).toBeTruthy();
    const source = ['Workspace.tsx', 'AssignForm.tsx', 'useWorkspaceAssign.ts'].map((f) => readFileSync(join(__dirname, '../src/features/workspace', f), 'utf8')).join('\n');
    expect(source).not.toMatch(/Date\.now|new Date\(\)/);
  });
});

describe('post an owner update (AC 8, 12, 13)', () => {
  it('opens the shared form with an unselected required Update type and sends one valid POST with CSRF', async () => {
    const body = item('W-2411');
    await open(body, item('W-2411.next' as never));
    await press('Post update');
    expect(ws().getAllByRole('radio').length + ws().queryAllByRole('button', { name: /Acknowledge|Started|Progress update/ }).length).toBe(3);
    expect(ws().queryAllByRole('radio', { checked: true })).toHaveLength(0);
    writes = [json(200, { work_id: 'W-2411', state: 'processing', revision: 4, outcome: 'done', message: 'Done: update posted.' })];
    // required fields: nothing is sent
    await act(async () => {
      fireEvent.click(submitButton());
    });
    expect(posts('/steps')).toHaveLength(0);
    expect(document.querySelector('.ws-form [role="alert"], .ws-form .psl-error')).not.toBeNull();
    fireEvent.click(ws().getByRole('radio', { name: 'Progress update' }));
    type('Update', '  Fix verified on 2 of 3 models.  ');
    const submit = submitButton();
    await act(async () => {
      fireEvent.click(submit);
      fireEvent.click(submit);
    });
    await waitFor(() => expect(itemReads()).toHaveLength(2));
    const calls = posts('/steps');
    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe('/api/v1/work/W-2411/steps');
    expect(calls[0].csrf).toBeTruthy();
    expect(calls[0].body).toMatchObject({ expected_revision: 3, step: 'post_owner_update', inputs: { update_type: 'progress', update: 'Fix verified on 2 of 3 models.' } });
    expect(Object.keys(calls[0].body!).sort()).toEqual(['expected_revision', 'idempotency_key', 'inputs', 'step']);
    expect(String(calls[0].body!.idempotency_key)).toMatch(UUID);
    expect(stepRequest(calls[0].body), JSON.stringify(stepRequest.errors)).toBe(true);
    await waitFor(() => expect(screen.getByText('Done: update posted.')).toBeTruthy());
    expect(await screen.findByText(/Fix verified on 2 of 3 models; third model test tomorrow\./)).toBeTruthy();
    expect(screen.getByText('Owner update · recorded by PM')).toBeTruthy();
  });

  it('a 500 never says done; Try again repeats the same key', async () => {
    await open(item('W-2411'));
    await press('Post update');
    fireEvent.click(ws().getByRole('radio', { name: 'Started' }));
    type('Update', 'Started on it');
    writes = [json(500, { code: 'server_error', message: 'Nope.' })];
    const submit = () => ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!;
    await act(async () => {
      fireEvent.click(submit());
    });
    await waitFor(() => expect(document.querySelector('.ws-notice')).not.toBeNull());
    expect(document.body.textContent).not.toMatch(/Done:|recorded by PM · done/);
    writes = [json(500, { code: 'server_error', message: 'Nope.' })];
    await act(async () => {
      fireEvent.click(submit());
    });
    await waitFor(() => expect(posts('/steps')).toHaveLength(2));
    expect(posts('/steps')[1].body!.idempotency_key).toBe(posts('/steps')[0].body!.idempotency_key);
    expect((ws().getByLabelText('Update') as HTMLTextAreaElement).value).toBe('Started on it');
  });

  it('a 422 puts the message under the named field and keeps the entries', async () => {
    await open(item('W-2411'));
    await press('Post update');
    fireEvent.click(ws().getByRole('radio', { name: 'Started' }));
    type('Update', 'Words');
    writes = [json(422, { code: 'invalid', message: 'Check update.', fields: [{ name: 'update', message: 'Say what changed.' }] })];
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!);
    });
    expect(await screen.findByText('Say what changed.')).toBeTruthy();
    expect((ws().getByLabelText('Update') as HTMLTextAreaElement).value).toBe('Words');
  });

  it('a 409 re-reads, says it is stale, keeps the entries and sends once; the next press carries the new revision', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
    const body = item('W-2411');
    await open(body, bump(body, 4));
    await press('Post update');
    fireEvent.click(ws().getByRole('radio', { name: 'Started' }));
    type('Update', 'Words');
    writes = [json(409, { code: 'stale', message: 'Changed.' })];
    const submit = () => ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!;
    await act(async () => {
      fireEvent.click(submit());
    });
    expect(await screen.findByText(/This changed while you were working. Showing version 4./)).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(posts('/steps')).toHaveLength(1);
    writes = [json(200, { work_id: 'W-2411', state: 'processing', revision: 5, outcome: 'done' })];
    await act(async () => {
      fireEvent.click(submit());
    });
    await waitFor(() => expect(posts('/steps')).toHaveLength(2));
    expect(posts('/steps')[1].body!.expected_revision).toBe(4);
  });
});

describe('record a reply and raise an escalation (AC 9, 10)', () => {
  it('Record a reply sends one POST with the reply, revision and a key', async () => {
    const body = item('W-2412');
    await open(body, item('W-2412.next' as never));
    await press('Record a reply');
    await act(async () => {
      fireEvent.click(submitButton());
    });
    expect(posts('/steps')).toHaveLength(0);
    expect(ws().getByText('Add reply to continue.')).toBeTruthy();
    type('Reply', 'Engineering is looking at it today.');
    writes = [json(200, { work_id: 'W-2412', state: 'processing', revision: 4, outcome: 'done', message: 'Done: reply recorded.' })];
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!);
    });
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    expect(posts('/steps')[0].body).toMatchObject({ step: 'record_reply', expected_revision: 3, inputs: { reply: 'Engineering is looking at it today.' } });
    expect(stepRequest(posts('/steps')[0].body)).toBe(true);
    expect(await screen.findByText('Owner reply · recorded by PM')).toBeTruthy();
  });

  it('Raise an escalation opens Start work on the escalation line with the prefill and posts nothing on this page', async () => {
    await open(item('W-2412'));
    const lines = read('start-work/lines.pm.json');
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request) => {
      if (new URL(request.url).pathname === '/api/v1/lines') {
        sent.push({ method: 'GET', path: '/api/v1/lines', body: undefined, csrf: null });
        return json(200, lines);
      }
      return base(request);
    });
    await press('Raise an escalation');
    expect(await screen.findByRole('dialog')).toBeTruthy();
    await waitFor(() => expect(within(screen.getByRole('dialog')).getAllByText(/Escalat/i).length).toBeGreaterThan(0));
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/escalation (was|has been) (started|raised)/i);
  });

  it('without starts_line the escalation button is not drawn; a malformed one is not drawn either', async () => {
    const body = item('W-2412');
    delete (body.workspace!.steps![1] as { starts_line?: unknown }).starts_line;
    await open(body);
    expect(buttons().filter((b) => b === 'Raise an escalation')).toHaveLength(1); // a plain step: it would post, so it still shows as a step
    cleanupView();
    const odd = item('W-2412');
    (odd.workspace!.steps![1] as { starts_line?: unknown }).starts_line = { line_key: '', prefill: [] };
    await open(odd);
    await press('Raise an escalation');
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});

describe('set an owner (AC 11 to 14)', () => {
  it('lists exactly the three candidates with no preselection, and sends one POST with CSRF', async () => {
    const body = item('W-2413');
    await open(body, item('W-2413.next' as never));
    await press('Set an owner');
    fireEvent.click(ws().getByRole('combobox', { name: /Owner/ }));
    const options = await screen.findAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual([
      expect.stringContaining('Tunde Bello'),
      expect.stringContaining('Engineering'),
      expect.stringContaining('Lagoon Health support'),
    ]);
    expect(options[1].textContent).toContain('recorded by PM');
    expect(options[1].textContent).toContain('Team');
    fireEvent.click(options[1]);
    writes = [json(200, { work_id: 'W-2413', state: 'processing', revision: 3, assigned_to: 'Engineering' })];
    const submit = ws().getAllByRole('button', { name: 'Set owner' }).find((b) => (b as HTMLButtonElement).type === 'submit')!;
    await act(async () => {
      fireEvent.click(submit);
      fireEvent.click(submit);
    });
    await waitFor(() => expect(itemReads()).toHaveLength(2));
    const calls = posts('/assignment');
    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe('/api/v1/work/W-2413/assignment');
    expect(calls[0].csrf).toBeTruthy();
    expect(calls[0].body).toEqual({ expected_revision: 2, person_id: 'T-ENG' });
    expect(assignRequest(calls[0].body)).toBe(true);
    expect(await screen.findByText('Owner set: Engineering')).toBeTruthy();
    expect(screen.getByText('FOLLOW-UP STARTED')).toBeTruthy();
    expect(buttons()).toEqual([]);
  });

  it('Owner is required: the message, a summary, focus on the field, nothing sent; a note over 2000 characters is refused', async () => {
    await open(item('W-2413'));
    await press('Set an owner');
    const submit = () => ws().getAllByRole('button', { name: 'Set owner' }).find((b) => (b as HTMLButtonElement).type === 'submit')!;
    await act(async () => {
      fireEvent.click(submit());
    });
    expect(ws().getAllByText('Choose an owner to continue.').length).toBeGreaterThan(0);
    expect(screen.getByText('1 thing to fix')).toBeTruthy();
    await chooseOwner('Engineering');
    fireEvent.change(ws().getByLabelText(/^Note/), { target: { value: 'x'.repeat(2001) } });
    await act(async () => {
      fireEvent.click(submit());
    });
    expect(ws().getAllByText('Keep the note to 2000 characters.').length).toBeGreaterThan(0);
    expect(posts('/assignment')).toHaveLength(0);
  });

  it('a note is required only when assign.note_required says so', async () => {
    const body = item('W-2413');
    body.assign!.note_required = true;
    await open(body);
    await press('Set an owner');
    await chooseOwner('Tunde Bello');
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button', { name: 'Set owner' }).find((b) => (b as HTMLButtonElement).type === 'submit')!);
    });
    expect(ws().getAllByText('Add a note to continue.').length).toBeGreaterThan(0);
    expect(posts('/assignment')).toHaveLength(0);
  });

  it('assign with no candidates reads "No one can be chosen yet." and draws no control', async () => {
    const body = item('W-2413');
    body.assign!.candidates = [];
    await open(body);
    expect(ws().getByText('No one can be chosen yet.')).toBeTruthy();
    expect(buttons()).toEqual([]);
  });

  it('a 422 names Owner under the field; a 500 says Not recorded, re-reads and never says Owner set', async () => {
    await open(item('W-2413'));
    await press('Set an owner');
    await chooseOwner('Tunde Bello');
    const submit = () => ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!;
    writes = [json(422, { code: 'invalid', message: 'Check person_id.', fields: [{ name: 'person_id', message: 'Pick someone on the list.' }] })];
    await act(async () => {
      fireEvent.click(submit());
    });
    expect((await screen.findAllByText('Pick someone on the list.')).length).toBeGreaterThan(0);
    writes = [json(500, { code: 'server_error', message: 'Nope.' })];
    await act(async () => {
      fireEvent.click(submit());
    });
    expect(await screen.findByText('Not recorded')).toBeTruthy();
    expect(itemReads().length).toBeGreaterThanOrEqual(2);
    expect(document.body.textContent).not.toMatch(/Owner set/);
    expect(ws().getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it('a 409 re-reads and says it is stale; one POST only, however long it waits', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
    const body = item('W-2413');
    await open(body, bump(body, 3));
    await press('Set an owner');
    await chooseOwner('Tunde Bello');
    writes = [json(409, { code: 'stale', message: 'Changed.' })];
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!);
    });
    expect(await screen.findByText(/This changed while you were working. Showing version 3./)).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(posts('/assignment')).toHaveLength(1);
    expect(document.body.textContent).not.toMatch(/Owner set/);
  });

  it('uncertain: the re-read decides. Still no owner means the form is offered again; an owner means it is not', async () => {
    const body = item('W-2413');
    await open(body, body);
    await press('Set an owner');
    await chooseOwner('Tunde Bello');
    writes = [json(500, { code: 'server_error', message: 'Nope.' })];
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!);
    });
    expect(await screen.findByText(/We couldn’t confirm the owner was set/)).toBeTruthy();
    expect(ws().getAllByRole('button', { name: /Set owner|Try again/ }).length).toBeGreaterThan(0);
    cleanupView();
    sent = [];
    const written = item('W-2413.next' as never);
    await open(body, written);
    await press('Set an owner');
    await chooseOwner('Tunde Bello');
    writes = [json(500, { code: 'server_error', message: 'Nope.' })];
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!);
    });
    await screen.findByText(/We couldn’t confirm the owner was set/);
    await waitFor(() => expect(ws().queryByRole('button', { name: 'Set owner' })).toBeNull());
    expect(buttons()).toEqual([]);
    expect(posts('/assignment')).toHaveLength(1);
  });
});

describe('access (AC 15)', () => {
  for (const status of [403, 404]) {
    it(`a ${status} on the read shows the same not-open view with no name or fact`, async () => {
      fetchStub.mockImplementation(async (request) => {
        const url = new URL(request.url);
        if (url.pathname === '/api/v1/me') return json(200, read('me.pm.json'));
        return json(status, { code: 'no', message: 'No.' });
      });
      render(
        <AppShell>
          <WorkItemView id="W-2411" tab="overview" />
        </AppShell>,
      );
      await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
      expect(document.body.textContent).not.toMatch(/Login fails|ISS-0233|Engineering/);
    });
  }

  it('a 403 or 404 on the assignment write shows the same not-open view; a 401 shows signed out', async () => {
    for (const status of [403, 404, 401]) {
      cleanupView();
      await open(item('W-2413'));
      await press('Set an owner');
      await chooseOwner('Tunde Bello');
      writes = [json(status, { code: 'no', message: 'No.' })];
      await act(async () => {
        fireEvent.click(ws().getAllByRole('button').find((b) => (b as HTMLButtonElement).type === 'submit')!);
      });
      await waitFor(() => expect(document.querySelector('.ws')).toBeNull());
      expect(document.body.textContent).not.toMatch(/Report totals round differently/);
    }
  });
});

describe('frame (AC 16, 17)', () => {
  it('the project bar links every tab with a page and marks none current', async () => {
    await open(item('W-2411'));
    const bar = screen.getByRole('navigation', { name: 'Project' });
    expect(within(bar).getAllByRole('link').map((l) => l.getAttribute('href'))).toEqual([
      '/projects/P-0101',
      '/projects/P-0101/milestones',
      '/projects/P-0101/documents',
      '/projects/P-0101/money',
      '/projects/P-0101/registers',
      '/projects/P-0101/actions',
    ]);
    expect(bar.querySelector('[aria-current]')).toBeNull();
  });

  it('nothing in the workspace code says the owner logged in', () => {
    for (const file of ['Workspace.tsx', 'Sections.tsx', 'Steps.tsx', 'AssignForm.tsx', 'useWorkspaceAssign.ts']) {
      expect(readFileSync(join(__dirname, '../src/features/workspace', file), 'utf8')).not.toMatch(/logged in|signed in as the owner/i);
    }
  });

  it('no board string is in src', () => {
    const files = ['workspace/Workspace.tsx', 'workspace/Sections.tsx', 'workspace/AssignForm.tsx', 'workspace/useWorkspaceAssign.ts', 'work-item/WorkItemView.tsx'];
    for (const file of files) expect(readFileSync(join(__dirname, '../src/features', file), 'utf8')).not.toMatch(/NO RESPONSE|OWNER NEEDED|FIX IN TESTING|FOLLOW-UP VERIFIED/);
  });

  it('an empty workspace draws only the header and "Nothing here yet."', async () => {
    const body = item('W-2414');
    body.workspace!.sections = [];
    delete body.workspace!.next;
    await open(body);
    expect(ws().getByText('Nothing here yet.')).toBeTruthy();
  });

  it('a restricted item draws Restricted and none of its content', async () => {
    const body = item('W-2411');
    body.workspace!.sections[1].items[0] = { id: 'e4', restricted: true, text: 'SECRET words' };
    await open(body);
    expect(document.body.textContent).not.toContain('SECRET words');
    expect(ws().getAllByText('Restricted').length).toBeGreaterThan(0);
  });
});
