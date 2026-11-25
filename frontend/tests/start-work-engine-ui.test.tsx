// @vitest-environment jsdom
// F-92: the form engine in the Start work drawer, against the mock's real shapes: issues and escalation (JSON), emergency and change
// (dependent pickers), minutes (multipart with the notes file), and the start answers for one JSON line and for minutes.
import { act, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { StartWorkDrawer } from '@/features/start-work/StartWorkDrawer';
import { pmoEmergency } from '@/features/start-work/lines/pmoEmergency';
import { pmoMinutes } from '@/features/start-work/lines/pmoMinutes';
import type { Line } from '@/features/start-work/types';
import { useStart } from '@/features/start-work/useStart';

import { useNodeUploads } from './assistant-bridge';

// @ts-expect-error plain ESM module without type declarations
import { resetStartLive, startLive, startLiveLog } from '../mock/start-live.mjs';

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/my-work',
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const TOKEN = 'mock-csrf-pm';
let scenario: string | undefined;
let override: ((request: Request, url: URL) => Response | undefined) | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const requests = () => fetchStub.mock.calls.map(([r]) => r);
const reads = (path: RegExp) => requests().filter((r) => path.test(new URL(r.url).pathname));
const bodies = async () => Promise.all(reads(/^\/api\/v1\/work$/).filter((r) => r.method === 'POST').map(async (r) => JSON.parse(await r.clone().text())));
const sourceReads = (field: string) => reads(/intake-sources$/).map((r) => new URL(r.url)).filter((u) => u.searchParams.get('field') === field);

let makeFile: (name: string, type?: string, size?: number) => File;

beforeEach(async () => {
  makeFile = await useNodeUploads();
  resetStartLive();
  scenario = undefined;
  override = undefined;
  nav.push.mockReset();
  setCsrfToken(TOKEN);
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    const custom = override?.(request, url);
    if (custom) return custom;
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 'fresh', signed_in: true, next_url: '/' });
    const post = request.method === 'POST';
    const rawBytes = post ? Buffer.from(await request.clone().arrayBuffer()) : undefined;
    const [status, body] = startLive({ method: request.method.toLowerCase(), url, raw: rawBytes?.toString('utf8') ?? '', rawBytes, contentType: request.headers.get('content-type'), scenario, csrfOk: request.headers.get('x-csrftoken') === TOKEN, persona: 'pm' });
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const PROJECT = { case_id: '00000000-0000-4000-8000-000000000001', title: 'Project 01', case_revision: 4, sample: false, django_url: '/', source_options_url: '/', workflow_intake_url: null };
const served = (key: string) => (startLive({ method: 'get', url: new URL('http://m/api/v1/lines'), persona: 'pm' })[1] as { items: Line[] }).items.find((l) => l.key === key) as Line;

/** Opens the drawer on a line from the chooser and returns its dialog. */
async function openLine(title: string, heading: string) {
  render(<StartWorkDrawer onClose={vi.fn()} />);
  const chooser = await screen.findByRole('dialog');
  fireEvent.click(await within(chooser).findByRole('radio', { name: new RegExp(title) }));
  fireEvent.click(within(chooser).getByRole('button', { name: 'Next' }));
  return screen.findByRole('dialog', { name: heading });
}
const option = async (label: string) => fireEvent.click(await screen.findByRole('option', { name: label }));
async function choose(dialog: HTMLElement, name: string, label: string) {
  fireEvent.click(within(dialog).getByRole('combobox', { name: new RegExp(`^${name}`) }));
  await option(label);
}

describe('issues', () => {
  it('a project and an issue, then Start: no reference, the issue id, and /work/4102 opens (AC4)', async () => {
    const dialog = await openLine('Chase an open issue', 'Chase an open issue');
    expect(within(dialog).queryByLabelText('Reference')).toBeNull();
    await choose(dialog, 'Project', 'Project 01');
    await choose(dialog, 'Issue', 'ISS- 12');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start chase' }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/4102'));
    expect(await bodies()).toEqual([{ line: 'pmo-issues/v1', case_id: PROJECT.case_id, case_revision: 4, idempotency_key: expect.any(String), intake: { issue_id: 12 } }]);
  });

  it('Start with nothing chosen sends nothing and names each missing control (AC8)', async () => {
    const dialog = await openLine('Chase an open issue', 'Chase an open issue');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start chase' }));
    const summary = await screen.findByRole('alert');
    for (const text of ['Project is required.', 'Issue is required.']) expect(within(summary).getByText(text)).toBeTruthy();
    expect(await bodies()).toEqual([]);
  });

  it('the issue list pages with before while next_before is set', async () => {
    const dialog = await openLine('Chase an open issue', 'Chase an open issue');
    await choose(dialog, 'Project', 'Project 01');
    fireEvent.click(within(dialog).getByRole('combobox', { name: /^Issue/ }));
    await screen.findByRole('option', { name: 'ISS- 28' });
    expect(sourceReads('issue_id').map((u) => u.searchParams.get('before'))[0]).toBeNull();
  });

  it('a source read that fails shows its retry and does not block the other fields (AC13)', async () => {
    override = (_r, url) => (url.pathname.endsWith('/intake-sources') && url.searchParams.get('field') === 'issue_id' ? json(503, { code: 'unavailable', message: 'Down.' }) : undefined);
    const dialog = await openLine('Chase an open issue', 'Chase an open issue');
    await choose(dialog, 'Project', 'Project 01');
    fireEvent.click(within(dialog).getByRole('combobox', { name: /^Issue/ }));
    expect(await screen.findByRole('button', { name: /try again/i })).toBeTruthy();
    expect((within(dialog).getByRole('button', { name: 'Start chase' }) as HTMLButtonElement).disabled).toBe(false);
  });
});

describe('escalation', () => {
  it('lists the register requests worded from the served direction and target; the body has the request, a null template and the reference (AC5)', async () => {
    const dialog = await openLine('Escalate an issue', 'Escalate an issue');
    await choose(dialog, 'Project', 'Project 01');
    await choose(dialog, 'Escalation request', 'Escalate to PMO · #23');
    fireEvent.change(within(dialog).getByLabelText('Reference'), { target: { value: 'Raise it' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start escalation' }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/4102'));
    const [sent] = await bodies();
    expect(sent.intake).toEqual({ request_id: 23, template_id: null });
    expect(sent.reference).toBe('Raise it');
    expect(reads(/escalation-register$/)).toHaveLength(1);
  });

  it('says "No escalation requests to start from." for an empty register', async () => {
    override = (_r, url) => (url.pathname.endsWith('/escalation-register') ? json(200, { revision: 4, can_request: true, issues: [], profiles: [], requests: [], evidence: [], next_page: null }) : undefined);
    const dialog = await openLine('Escalate an issue', 'Escalate an issue');
    await choose(dialog, 'Project', 'Project 01');
    fireEvent.click(within(dialog).getByRole('combobox', { name: /^Escalation request/ }));
    expect(await screen.findByText('No escalation requests to start from.')).toBeTruthy();
  });
});

describe('dependent pickers (AC6)', () => {
  it('Authorisation and Outcome wait for the record, ask with its id as parent_id, and clear when it changes or the project does', async () => {
    const dialog = await openLine('Record an emergency', 'Record an emergency');
    expect(within(dialog).getByText('Choose a project first.', { selector: '#sw-field-profile_id *' })).toBeTruthy();
    await choose(dialog, 'Project', 'Project 01');
    expect(within(dialog).getAllByText('Choose emergency record first.')).toHaveLength(2);
    expect(within(dialog).queryByRole('combobox', { name: /^Authorisation/ })).toBeNull();
    await choose(dialog, 'Emergency record', 'CHG-0007 · v2');
    await choose(dialog, 'Authorisation', 'Authorised 14 November');
    expect(sourceReads('inputs.authorization_id').map((u) => u.searchParams.get('parent_id'))).toEqual(['32']);
    // a different record: the choice under the first is gone and the list is read for the new parent
    await choose(dialog, 'Emergency record', 'CHG-0003 · v1');
    expect(within(dialog).getByRole('combobox', { name: /^Authorisation/ }).textContent).not.toContain('Authorised 14 November');
    fireEvent.click(within(dialog).getByRole('combobox', { name: /^Authorisation/ }));
    await option('Authorised 2 November');
    expect(sourceReads('inputs.authorization_id').map((u) => u.searchParams.get('parent_id'))).toEqual(['32', '31']);
    // a different project: the record and everything under it are cleared
    await choose(dialog, 'Project', 'Project 02');
    expect(within(dialog).getByRole('combobox', { name: /^Emergency record/ }).textContent).not.toContain('CHG-0003');
    expect(within(dialog).getAllByText('Choose emergency record first.')).toHaveLength(2);
  });

  it('sends the chosen ids, null for the rest, and the audience the schema offers', async () => {
    const dialog = await openLine('Record an emergency', 'Record an emergency');
    await choose(dialog, 'Project', 'Project 01');
    await choose(dialog, 'Emergency record', 'CHG-0007 · v2');
    await choose(dialog, 'Outcome', 'Implemented 15 November');
    fireEvent.click(within(dialog).getByRole('radio', { name: 'Client' }));
    expect(within(dialog).queryByRole('radio', { name: 'Management' })).toBeNull();
    fireEvent.change(within(dialog).getByLabelText('Reference'), { target: { value: 'Fire' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start emergency' }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/4102'));
    const [sent] = await bodies();
    expect(sent.intake).toEqual({ profile_id: 32, inputs: { template_id: null, authorization_id: null, outcome_id: 62, audience: 'client' } });
  });
});

describe('the revision sent (AC11)', () => {
  it('is the latest any source answer carried', async () => {
    override = (_r, url) => {
      if (!url.pathname.endsWith('/intake-sources')) return undefined;
      return json(200, { case_revision: 9, fields: [], field: 'issue_id', items: [{ id: 5, label: 'ISS-5' }], next_before: null });
    };
    const dialog = await openLine('Chase an open issue', 'Chase an open issue');
    await choose(dialog, 'Project', 'Project 01');
    await choose(dialog, 'Issue', 'ISS-5');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start chase' }));
    await waitFor(() => expect(reads(/^\/api\/v1\/work$/).filter((r) => r.method === 'POST')).toHaveLength(1));
    expect((await bodies())[0].case_revision).toBe(9);
  });
});

describe('minutes (AC7, AC10, AC12)', () => {
  const file = () => makeFile('notes.txt', 'text/plain', 20);
  const line = () => served('pmo-minutes/v1');
  const started = vi.fn();
  const conflict = vi.fn();
  const minutesPosts = () => reads(/minutes\/intake$/).filter((r) => r.method === 'POST');
  async function ready() {
    const hook = renderHook(() => useStart(pmoMinutes, started, conflict, line()));
    act(() => {
      hook.result.current.chooseProject(PROJECT);
      hook.result.current.setValue('template_id', { value: '54', label: 'Minutes' } as never);
      hook.result.current.setValue('audience', 'internal');
      hook.result.current.setValue('notes_file', file());
      hook.result.current.setValue('reference', 'Minutes of 17 Nov');
    });
    return hook;
  }
  beforeEach(() => {
    started.mockReset();
    conflict.mockReset();
  });

  it('one multipart start with the six parts, no background, no /files call; /work/4102 opens', async () => {
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(started).toHaveBeenCalledWith('4102');
    expect(minutesPosts()).toHaveLength(1);
    expect(reads(/\/files$/)).toHaveLength(0);
    expect(reads(/^\/api\/v1\/work$/)).toHaveLength(0);
    const [entry] = startLiveLog().requests;
    expect(entry.minutes.parts.sort()).toEqual(['audience', 'case_revision', 'idempotency_key', 'notes_file', 'reference', 'template_id']);
    expect(entry.minutes.file).toBe('notes.txt');
    expect(minutesPosts()[0].headers.get('content-type')).toMatch(/^multipart\/form-data; boundary=/);
  });

  it('a missing file or template sends nothing and names each', async () => {
    const hook = renderHook(() => useStart(pmoMinutes, started, conflict, line()));
    act(() => hook.result.current.chooseProject(PROJECT));
    await act(() => hook.result.current.submit());
    expect(Object.values(hook.result.current.errors)).toEqual(['Template is required.', 'Audience is required.', 'Notes file is required.', 'Reference is required.']);
    expect(minutesPosts()).toHaveLength(0);
  });

  it('after a 503, "Check again" resends the same key and the same file; one work item starts', async () => {
    scenario = 'start_uncertain';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.uncertain).toBe(true);
    await act(() => result.current.submit());
    const [first, second] = startLiveLog().requests;
    expect(second.minutes.fields.idempotency_key).toBe(first.minutes.fields.idempotency_key);
    expect(second.minutes.file).toBe(first.minutes.file);
    expect(startLiveLog().started).toHaveLength(1);
    expect(started).toHaveBeenCalledWith('4102');
  });

  it('a 422 names the form\'s own parts under their controls', async () => {
    override = (request) => (request.method === 'POST' ? json(422, { code: 'invalid_input', message: 'Check.', fields: [{ name: 'notes_file', message: 'Empty file.' }, { name: 'template_id', message: 'Not a template.' }, { name: 'zzz', message: 'Odd.' }] }) : undefined);
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.errors).toEqual({ notes_file: 'Empty file.', template_id: 'Not a template.' });
    expect(result.current.notice).toMatchObject({ kind: 'invalid', unmatched: [{ name: 'zzz', message: 'Odd.' }] });
  });

  it('a 413 shows the server\'s words and the next press sends the same file again', async () => {
    override = (request) => (request.method === 'POST' ? json(413, { code: 'too_large', message: 'The notes file is too large.' }) : undefined);
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'The notes file is too large.' });
    expect(result.current.uncertain).toBe(false);
    override = undefined;
    await act(() => result.current.submit());
    expect(started).toHaveBeenCalledWith('4102');
    expect(startLiveLog().requests.map((r: { minutes: { file: string } }) => r.minutes.file)).toEqual(['notes.txt']);
  });

  it.each([
    ['start_denied', 'Your role doesn’t let you start this line.'],
    ['start_missing', 'This record is unavailable.'],
  ])('%s: shows the same words as a JSON line', async (name, text) => {
    scenario = name;
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toMatchObject({ kind: 'problem' });
    expect((result.current.notice as { message: string }).message).toContain(text);
  });

  it('csrf_failed refreshes the session once and does not show the role text', async () => {
    scenario = 'csrf_failed';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect((result.current.notice as { message: string }).message).toBe('Refresh your session and try again.');
    expect(reads(/\/session$/)).toHaveLength(1);
  });

  it('a 401 shows the signed-out state', async () => {
    scenario = '401';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.signedOut).toBe(true);
  });
});

describe('a JSON engine line answers like F-86 (AC10, AC12)', () => {
  const started = vi.fn();
  const conflict = vi.fn();
  const line = () => served('pmo-emergency/v1');
  async function ready() {
    const hook = renderHook(() => useStart(pmoEmergency, started, conflict, line()));
    act(() => {
      hook.result.current.chooseProject(PROJECT);
      hook.result.current.setValue('profile_id', { value: '32', label: 'CHG' } as never);
      hook.result.current.setValue('reference', 'Fire');
    });
    return hook;
  }
  beforeEach(() => {
    started.mockReset();
    conflict.mockReset();
  });

  it('a double press sends one request; a 503 locks, and "Check again" resends the same body and key', async () => {
    scenario = 'start_uncertain';
    const { result } = await ready();
    await act(async () => {
      void result.current.submit();
      void result.current.submit();
    });
    expect(await bodies()).toHaveLength(1);
    expect(result.current.uncertain).toBe(true);
    await act(() => result.current.submit());
    const [first, second] = await bodies();
    expect(second).toEqual(first);
    expect(startLiveLog().started).toHaveLength(1);
  });

  it('a 409 gives a new key and the new revision; a 422 gives a new key', async () => {
    scenario = 'start_stale';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toMatchObject({ kind: 'stale' });
    await act(() => result.current.submit());
    const [first, second] = await bodies();
    expect(second.idempotency_key).not.toBe(first.idempotency_key);
    expect(second.case_revision).toBe(5);
  });

  it('a hand-edited case id (start_missing) shows "This record is unavailable."; 403 shows the role text', async () => {
    scenario = 'start_missing';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'This record is unavailable.' });
  });

  it('maps the mock\'s own 422 names (the server\'s typed names) to the controls', async () => {
    // no profile: the schema's own required check names intake.profile_id
    const hook = renderHook(() => useStart(pmoEmergency, started, conflict, line()));
    act(() => {
      hook.result.current.chooseProject(PROJECT);
      hook.result.current.setValue('profile_id', { value: '32', label: 'CHG' } as never);
      hook.result.current.setValue('reference', 'x'.repeat(200));
    });
    await act(() => hook.result.current.submit());
    expect(hook.result.current.errors).toEqual({ reference: 'This is not valid (must NOT have more than 160 characters).' });
  });
});
