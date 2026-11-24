// @vitest-environment jsdom
// F-87: the work item's own commands (descriptors), the one sender (useWorkCommand) and the controls row on the live page.
import { act, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import type { LiveWorkItem } from '@/api/types';
import { makeCommand, readPanel, registerLineAdapter, type PanelRef, type LineActionsProps, type LineAdapter } from '@/features/workspace/adapter';
import { toFormData, useWorkCommand } from '@/features/workspace/useWorkCommand';
import { workItemCommands } from '@/features/workspace/workItemCommands';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';

// @ts-expect-error plain ESM module without type declarations
import { resetWorkLive, workLive, workLiveLog } from '../mock/work-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/work/4120',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
const item = (id: number): LiveWorkItem => (workLive({ method: 'get', url: new URL(`/api/v1/work/${id}`, 'http://m.local'), csrfOk: true, persona: 'finance_lead' }) as [number, LiveWorkItem])[1];

let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST').map(([r]) => new URL(r.url).pathname);
const sessionReads = () => fetchStub.mock.calls.filter(([r]) => new URL(r.url).pathname === '/api/v1/session').length;

beforeEach(() => {
  resetWorkLive();
  scenario = undefined;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const reply = workLive({ method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes }) as [number | string, unknown];
    if (reply[0] === 'drop') throw new TypeError('network down');
    return json(reply[0] as number, reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('workItemCommands (the table in the spec)', () => {
  it('reconcile: POST /actions, no key, no case_revision', () => {
    const [command] = workItemCommands(item(4120));
    expect(command).toMatchObject({ id: 'work.reconcile', label: 'Check what happened', url: '/api/v1/work/4120/actions', successStatuses: [202], idempotency: { field: null, value: null } });
    expect(command.body({})).toEqual({ action: 'reconcile', expected_revision: 5 });
  });

  it('resume and cancel: POST /control with the item revision', () => {
    const [resume, cancel] = workItemCommands(item(4121));
    expect([resume.id, cancel.id]).toEqual(['work.resume', 'work.cancel']);
    expect(resume.url).toBe('/api/v1/work/4121/control');
    expect(resume.body({})).toEqual({ action: 'resume', expected_revision: 3 });
    expect(cancel.body({})).toEqual({ action: 'cancel', expected_revision: 3 });
    expect(resume.successStatuses).toEqual([200]);
  });

  it('background: pause and continue carry no action; an input cannot flip enabled', () => {
    const [pause, resume] = workItemCommands(item(4122));
    expect(pause.url).toBe('/api/v1/work/4122/background');
    expect(pause.body({})).toEqual({ expected_revision: 7, enabled: false });
    expect(resume.body({})).toEqual({ expected_revision: 7, enabled: true });
    expect(pause.body({ enabled: true })).toEqual({ expected_revision: 7, enabled: false });
    expect(Object.keys(pause.body({}))).not.toContain('action');
    expect(pause.successStatuses).toEqual([202]);
  });

  it('adopt_profile and release_invoice are never built, even when listed', () => {
    expect(item(4123).available_control).toContain('adopt_profile');
    expect(item(4123).actions).toContain('release_invoice');
    expect(workItemCommands(item(4123))).toEqual([]);
  });

  it('nothing listed gives no command', () => {
    expect(workItemCommands(item(4111))).toEqual([]);
  });

  it('a null revision holds every command with the reason, and the body stays null (never 0)', () => {
    const commands = workItemCommands(item(4110));
    expect(commands.map((c) => c.id)).toEqual(['work.reconcile', 'work.cancel']);
    for (const c of commands) {
      expect(c.disabledReason).toBe('We don’t have this item’s current version yet. Reload and try again.');
      expect(c.body({}).expected_revision).toBeNull();
    }
  });
});

/** The hook with a reload that reads the mock item, as the page does. */
function useSender(id: number, onAccessLost?: () => void) {
  const state = { current: item(id) };
  const reload = vi.fn(async (): Promise<LiveWorkItem | null> => {
    state.current = item(id);
    return state.current;
  });
  const useUnderTest = ({ it }: { it: { revision: number | null } }) => useWorkCommand({ item: it, reload, onAccessLost });
  const hook = renderHook(useUnderTest, { initialProps: { it: state.current } });
  return { ...hook, reload, state };
}
const press = async (hook: ReturnType<typeof useSender>, id: string, index = 0) => {
  const command = workItemCommands(hook.state.current).filter((c) => c.id === id)[index];
  await act(async () => {
    await hook.result.current.run(command);
  });
};

describe('useWorkCommand', () => {
  it('reconcile: one POST, then a re-read, and the words come from the re-read', async () => {
    scenario = 'ready';
    const hook = useSender(4120);
    await press(hook, 'work.reconcile');
    expect(posts()).toEqual(['/api/v1/work/4120/actions']);
    expect(hook.reload).toHaveBeenCalledTimes(1);
    expect(hook.result.current.notice).toEqual({ kind: 'success', text: 'Checked. This item is now: Ready to continue.' });
    expect(workLiveLog()[0]).toMatchObject({ route: 'actions', body: { action: 'reconcile', expected_revision: 5 } });
  });

  it('a reload that fails after the send says so and keeps every control locked until a read lands', async () => {
    const hook = useSender(4121);
    hook.reload.mockResolvedValue(null);
    await press(hook, 'work.resume');
    expect(hook.result.current.notice?.text).toBe('Sent. We couldn’t reload the item; reload the page to see its state.');
    expect(hook.result.current.busy).toBe(true);
    await press(hook, 'work.cancel');
    expect(posts()).toHaveLength(1);
    hook.rerender({ it: item(4121) });
    expect(hook.result.current.busy).toBe(false);
  });

  it('a double press sends one request and a second control cannot send while one runs', async () => {
    const hook = useSender(4121);
    const [resume, cancel] = workItemCommands(hook.state.current);
    await act(async () => {
      const first = hook.result.current.run(resume);
      void hook.result.current.run(resume);
      void hook.result.current.run(cancel);
      await first;
    });
    expect(posts()).toHaveLength(1);
  });

  it('409 re-reads, says it changed, and does not repeat the press; the next press carries the new revision', async () => {
    scenario = 'w409';
    const hook = useSender(4121);
    await press(hook, 'work.resume');
    expect(hook.result.current.notice).toMatchObject({ kind: 'error', text: 'This changed while you were working. Showing the latest version.', detail: 'Someone changed this since you opened it.' });
    expect(posts()).toHaveLength(1);
    expect(hook.reload).toHaveBeenCalledTimes(1);
    scenario = undefined;
    hook.rerender({ it: hook.state.current });
    await press(hook, 'work.resume');
    expect(workLiveLog().map((l: { body: { expected_revision: number } }) => l.body.expected_revision)).toEqual([3, 5]);
  });

  it('403 forbidden shows the server message, re-reads and does not retry', async () => {
    scenario = 'w403';
    const hook = useSender(4121);
    await press(hook, 'work.resume');
    expect(hook.result.current.notice).toEqual({ kind: 'error', text: 'You can’t do this.', detail: 'Your role does not allow this.' });
    expect(hook.reload).toHaveBeenCalledTimes(1);
    expect(posts()).toHaveLength(1);
  });

  it('403 csrf_failed refreshes the session once, says press again and sends nothing more', async () => {
    scenario = 'w403csrf';
    const hook = useSender(4121);
    await press(hook, 'work.resume');
    expect(hook.result.current.notice).toEqual({ kind: 'error', text: 'Press the button again.' });
    expect(sessionReads()).toBe(1);
    expect(posts()).toHaveLength(1);
    expect(hook.reload).not.toHaveBeenCalled();
  });

  it('422 shows the server message and the first field message, and re-reads', async () => {
    scenario = 'w422';
    const hook = useSender(4121);
    await press(hook, 'work.resume');
    expect(hook.result.current.notice).toEqual({ kind: 'error', text: 'A policy value is missing.', detail: 'Ask the PMO Lead to set it.' });
    expect(hook.reload).toHaveBeenCalledTimes(1);
  });

  it.each(['w429', 'w503'])('%s says try again shortly and nothing is sent by itself over 30 s', async (name) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    scenario = name;
    const hook = useSender(4121);
    await press(hook, 'work.resume');
    expect(hook.result.current.notice?.text).toBe('Try again shortly.');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(posts()).toHaveLength(1);
    expect(hook.result.current.busy).toBe(false);
  });

  it.each(['w500', 'wdrop'])('%s on cancel is uncertain: re-read, locked with its sentence, nothing sent for 60 s, unlocked only by a new revision', async (name) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    scenario = name;
    const hook = useSender(4121);
    // the 500 did not move the item; the dropped connection did (the write ran)
    const sent = hook.state.current;
    await press(hook, 'work.cancel');
    expect(hook.result.current.notice).toEqual({ kind: 'error', text: 'We couldn’t confirm that this happened. Check the page before trying again.' });
    expect(hook.reload).toHaveBeenCalledTimes(1);
    expect(hook.result.current.lockedReason('work.cancel')).toBe('Check the page before trying again.');
    await press(hook, 'work.cancel');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(posts()).toHaveLength(1);
    // same revision as sent: still locked; a different revision: unlocked
    hook.rerender({ it: { ...sent } });
    expect(hook.result.current.lockedReason('work.cancel')).not.toBeNull();
    hook.rerender({ it: { ...sent, revision: 4 } });
    expect(hook.result.current.lockedReason('work.cancel')).toBeNull();
  });

  it('an unknown result on "Check what happened" shows the same words but does not lock it', async () => {
    scenario = 'w500';
    const hook = useSender(4120);
    await press(hook, 'work.reconcile');
    expect(hook.result.current.notice?.text).toBe('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(hook.result.current.lockedReason('work.reconcile')).toBeNull();
    scenario = 'ready';
    await press(hook, 'work.reconcile');
    expect(posts()).toHaveLength(2);
  });

  it('a null revision sends nothing', async () => {
    const hook = useSender(4110);
    await press(hook, 'work.reconcile');
    expect(fetchStub.mock.calls.filter(([r]) => r.method === 'POST')).toHaveLength(0);
    expect(hook.result.current.notice).toBeNull();
  });

  it('401 and 404 hand the page over instead of drawing a notice', async () => {
    const lost = vi.fn();
    const hook = useSender(4121, lost);
    fetchStub.mockImplementationOnce(async () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }));
    await press(hook, 'work.resume');
    expect(lost.mock.calls[0][0]).toMatchObject({ kind: 'unauthenticated' });
    fetchStub.mockImplementationOnce(async () => json(404, { code: 'not_found', message: 'This record is unavailable.' }));
    await press(hook, 'work.resume');
    expect(lost.mock.calls[1][0]).toMatchObject({ kind: 'not_found' });
    expect(hook.result.current.notice).toBeNull();
  });

  it('a poll landing mid-write does not clear the lock or the notice (deferred POST)', async () => {
    let release: (r: Response) => void = () => undefined;
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => (request.method === 'POST' ? new Promise<Response>((resolve) => (release = resolve)) : base(request)));
    const hook = useSender(4121);
    const [resume, cancel] = workItemCommands(hook.state.current);
    let first: Promise<void> = Promise.resolve();
    await act(async () => {
      first = hook.result.current.run(resume);
    });
    expect(hook.result.current.pending).toBe('work.resume');
    // a poll lands: a new item object, same revision
    hook.rerender({ it: { ...hook.state.current } });
    expect(hook.result.current.pending).toBe('work.resume');
    expect(hook.result.current.busy).toBe(true);
    await act(async () => {
      await hook.result.current.run(cancel);
    });
    expect(posts()).toHaveLength(1);
    // the re-read after the send fails: still locked, and the problem is an error notice
    hook.reload.mockResolvedValue(null);
    await act(async () => {
      release(json(200, { work_id: 4121, state: 'ready', revision: 4 }));
      await first;
    });
    expect(hook.result.current.notice).toMatchObject({ kind: 'error', text: 'Sent. We couldn’t reload the item; reload the page to see its state.' });
    expect(hook.result.current.busy).toBe(true);
  });

  it('refuses a url that is not an API path of this site before any request, and an input cannot add an action to a body that has none', async () => {
    const hook = useSender(4121);
    for (const url of ['https://evil.example/api/v1/x', '//evil.example/api/v1/x', '/api/v1/../admin', '/other/x']) {
      const bad = makeCommand({ id: 'x.y', label: 'Y', url, tokens: { expected_revision: 3 }, successStatuses: [200] });
      await act(async () => {
        await hook.result.current.run(bad);
      });
    }
    expect(fetchStub.mock.calls.filter(([r]) => r.method === 'POST')).toHaveLength(0);
    const none = makeCommand({ id: 'work.background.pause', label: 'P', url: '/api/v1/work/1/background', tokens: { expected_revision: 7 }, action: null, successStatuses: [202] });
    expect(Object.keys(none.body({ action: 'evil', enabled: false }))).toEqual(['enabled', 'expected_revision']);
  });

  it('a multipart command goes through the same sender (lock, re-read) without a JSON content type; JSON stays JSON', async () => {
    const types: (string | null)[] = [];
    fetchStub.mockImplementation(async (request: Request) => {
      const url = new URL(request.url);
      if (request.method === 'POST') {
        types.push(request.headers.get('Content-Type'));
        return json(201, {});
      }
      return json(200, item(Number(url.pathname.split('/')[4])));
    });
    const hook = useSender(4121);
    const upload = makeCommand({ id: 'assets.dates', label: 'Save', url: '/api/v1/work/4121/assets', tokens: { expected_revision: 3, case_revision: null }, contentType: 'multipart/form-data', successStatuses: [201] });
    const plain = makeCommand({ id: 'assets.note', label: 'Note', url: '/api/v1/work/4121/note', tokens: { expected_revision: 3 }, successStatuses: [201] });
    await act(async () => {
      await hook.result.current.run(upload, { proof: new File(['pdf'], 'proof.pdf', { type: 'application/pdf' }) });
    });
    await act(async () => {
      await hook.result.current.run(plain, { note: 'y' });
    });
    expect(types[0]).not.toBe('application/json');
    expect(types[1]).toBe('application/json');
    expect(hook.reload).toHaveBeenCalledTimes(2);
    expect(hook.result.current.notice?.kind).toBe('success');
  });

  it('toFormData: a file is a part, null and undefined are left out, numbers are text, an object is JSON text, and the descriptor wins', () => {
    const upload = makeCommand({ id: 'assets.dates', label: 'Save', url: '/api/v1/work/4121/assets', tokens: { expected_revision: 3, case_revision: null }, contentType: 'multipart/form-data', successStatuses: [201] });
    const form = toFormData(upload.body({ proof: new File(['pdf'], 'proof.pdf'), note: 'x', when: { a: 1 }, gone: undefined, expected_revision: 99 }));
    expect((form.get('proof') as File).name).toBe('proof.pdf');
    expect(form.get('action')).toBe('dates');
    expect(form.get('expected_revision')).toBe('3');
    expect(form.get('note')).toBe('x');
    expect(form.get('when')).toBe('{"a":1}');
    expect(form.has('case_revision')).toBe(false);
    expect(form.has('gone')).toBe(false);
  });
});

describe('the controls row on the live page', () => {
  const open = (id: number) => render(<ToastProvider><LiveWorkItemView id={String(id)} tab="overview" /></ToastProvider>);
  const row = () => screen.queryByRole('group', { name: 'Controls' });
  const buttons = () => within(row()!).getAllByRole('button');

  it('4120 draws "Check what happened" only; 4111 draws no row; 4123 draws none for adopt_profile or release_invoice', async () => {
    open(4120);
    await screen.findByRole('button', { name: 'Check what happened' });
    expect(buttons()).toHaveLength(1);
    expect(screen.queryByRole('radio')).toBeNull();
    expect(fetchStub.mock.calls.filter(([r]) => r.method === 'POST')).toHaveLength(0);
  });

  it.each([4111, 4123])('%i has no controls row and no heading', async (id) => {
    open(id);
    await screen.findByRole('heading', { level: 1 });
    expect(row()).toBeNull();
  });

  it('pressing Check what happened sends one POST with the exact body and shows what the re-read says', async () => {
    scenario = 'ready';
    open(4120);
    fireEvent.click(await screen.findByRole('button', { name: 'Check what happened' }));
    expect((await screen.findByText(/Checked\. This item is now/)).textContent).toContain('Checked. This item is now: Ready to continue.');
    expect(document.querySelector('.work-state')?.textContent).toBe('Ready to continue');
    expect(posts()).toEqual(['/api/v1/work/4120/actions']);
    expect(workLiveLog()).toEqual([{ route: 'actions', work_id: 4120, body: { action: 'reconcile', expected_revision: 5 } }]);
  });

  it('while a command runs every button is disabled and the pressed one says Working', async () => {
    let release: (r: Response) => void = () => undefined;
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => (request.method === 'POST' ? new Promise<Response>((resolve) => (release = resolve)) : base(request)));
    open(4121);
    fireEvent.click(await screen.findByRole('button', { name: 'Resume' }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Working/ })).toBeTruthy());
    expect(buttons().every((b) => (b as HTMLButtonElement).disabled || b.getAttribute('aria-busy') === 'true')).toBe(true);
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /Working/ }));
    expect(posts()).toHaveLength(1);
    release(json(200, { work_id: 4121, state: 'ready', revision: 4 }));
    await waitFor(() => expect(screen.queryByRole('button', { name: /Working/ })).toBeNull());
  });

  it('Resume sends the control body and shows the new state tag from the re-read', async () => {
    open(4121);
    fireEvent.click(await screen.findByRole('button', { name: 'Resume' }));
    await screen.findByText(/This item is now: Ready to continue\./);
    expect(workLiveLog()).toEqual([{ route: 'control', work_id: 4121, body: { action: 'resume', expected_revision: 3 } }]);
    expect(document.querySelector('.work-state')?.textContent).toBe('Ready to continue');
  });

  it('Cancel asks first: nothing is sent by opening or by "Keep it"; "Cancel this work" sends one POST and the tag reads Cancelled', async () => {
    open(4121);
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Cancel this work?' });
    expect(within(dialog).getByText('This stops the work. It can’t be started again from here.')).toBeTruthy();
    expect(posts()).toHaveLength(0);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Keep it' }));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(posts()).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Cancel this work' }));
    await waitFor(() => expect(document.querySelector('.work-state')?.textContent).toBe('Cancelled'));
    expect(workLiveLog()).toEqual([{ route: 'control', work_id: 4121, body: { action: 'cancel', expected_revision: 3 } }]);
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });

  it('4122 draws Pause and Continue; each sends its own body and neither has an action', async () => {
    open(4122);
    fireEvent.click(await screen.findByRole('button', { name: 'Pause background work' }));
    await screen.findByText(/Done\. This item is now: Processing\./);
    fireEvent.click(screen.getByRole('button', { name: 'Continue background work' }));
    await waitFor(() => expect(workLiveLog()).toHaveLength(2));
    expect(workLiveLog().map((l: { body: unknown }) => l.body)).toEqual([
      { expected_revision: 7, enabled: false },
      { expected_revision: 7, enabled: true },
    ]);
  });

  it('4110 (null revision) draws disabled buttons with the reason beside them and sends nothing', async () => {
    open(4110);
    const check = (await screen.findByRole('button', { name: 'Check what happened' })) as HTMLButtonElement;
    expect(check.disabled).toBe(true);
    expect(screen.getAllByText('We don’t have this item’s current version yet. Reload and try again.')).toHaveLength(2);
    fireEvent.click(check);
    expect(posts()).toHaveLength(0);
  });

  it('a dropped connection on Resume locks Resume with its sentence and the page sends no second request', async () => {
    scenario = 'wdrop';
    open(4121);
    fireEvent.click(await screen.findByRole('button', { name: 'Resume' }));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    // the re-read shows the item moved (a new revision), which is the only thing that unlocks it
    await waitFor(() => expect(document.querySelector('.work-state')?.textContent).toBe('Ready to continue'));
    expect(posts()).toHaveLength(1);
  });

  it('after a 500 on Resume the button is disabled with "Check the page before trying again." beside it, and no second request is sent', async () => {
    scenario = 'w500';
    open(4121);
    fireEvent.click(await screen.findByRole('button', { name: 'Resume' }));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    const resume = screen.getByRole('button', { name: 'Resume' }) as HTMLButtonElement;
    expect(resume.disabled).toBe(true);
    expect(within(row()!).getByText('Check the page before trying again.')).toBeTruthy();
    fireEvent.click(resume);
    expect(posts()).toHaveLength(1);
  });

  it('a 404 on the write replaces the page with "This record is unavailable."', async () => {
    open(4121);
    const button = await screen.findByRole('button', { name: 'Resume' });
    fetchStub.mockImplementationOnce(async () => json(404, { code: 'not_found', message: 'This record is unavailable.' }));
    fireEvent.click(button);
    await screen.findByRole('heading', { name: 'This record is unavailable.' });
  });

  it('nothing is written on load or by polling', async () => {
    open(4122);
    await screen.findByRole('button', { name: 'Pause background work' });
    expect(fetchStub.mock.calls.filter(([r]) => r.method !== 'GET')).toHaveLength(0);
  });
});

describe('the line write-form slot (Actions)', () => {
  const key = 'f87-slot';
  const seen: LineActionsProps[] = [];
  const adapter = (withActions: boolean): LineAdapter<{ n: number }> => ({
    key,
    read: async () => ({ n: 1 }),
    sections: () => [{ key: 's', kind: 'text', title: 'Slot panel', items: [{ id: 'a', text: 'Panel text' }] }],
    commands: (_r, c) => [makeCommand({ id: 'slot.go', label: 'Go', url: `/api/v1/work/${c.workId}/slot`, tokens: { expected_revision: c.revision }, successStatuses: [200] })],
    ...(withActions
      ? {
          Actions: (props: LineActionsProps<{ n: number }>) => {
            seen.push(props as LineActionsProps);
            return <p>Line actions for {props.ctx.state}</p>;
          },
        }
      : {}),
  });
  const withPanel = (id: number) => {
    const base = item(id);
    const answer = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => {
      const url = new URL(request.url);
      if (request.method === 'GET' && url.pathname === `/api/v1/work/${id}`) return json(200, { ...base, panels: [{ key, url: `/api/v1/work/${id}/slot`, contract_path: null }] });
      if (url.pathname === `/api/v1/work/${id}/slot`) return json(200, { n: 1 });
      return answer(request);
    });
  };

  it('a registered Actions renders under the panel with readback, ctx (with state), commands and reload', async () => {
    registerLineAdapter(adapter(true) as LineAdapter);
    withPanel(4121);
    render(<ToastProvider><LiveWorkItemView id="4121" tab="overview" /></ToastProvider>);
    await screen.findByText('Line actions for action_needed');
    expect(screen.getByText('Panel text')).toBeTruthy();
    const props = seen.at(-1)!;
    expect(props.readback).toEqual({ n: 1 });
    expect(props.ctx).toMatchObject({ workId: 4121, revision: 3, caseRevision: 7, state: 'action_needed' });
    expect(props.commands.map((c) => c.id)).toEqual(['slot.go']);
    expect(typeof props.onAccessLost).toBe('function');
    await act(async () => {
      await expect(props.reload()).resolves.toMatchObject({ id: 4121 });
    });
  });

  it('a line command that timed out stays locked when the panel re-read fails and Try again is pressed (no second send)', async () => {
    const Form = ({ commands, reload, ctx, onAccessLost }: LineActionsProps) => {
      const send = useWorkCommand({ item: ctx, reload, onAccessLost });
      const go = commands[0];
      return (
        <div>
          <button type="button" disabled={send.busy || send.lockedReason(go.id) !== null} onClick={() => void send.run(go)}>
            Go
          </button>
          {send.lockedReason(go.id)}
        </div>
      );
    };
    registerLineAdapter({ ...adapter(false), read: (ref: PanelRef) => readPanel<{ n: number }>(ref), Actions: Form } as LineAdapter);
    withPanel(4121);
    let panelOk = true;
    let slotPosts = 0;
    const wrapped = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/work/4121/slot' && request.method === 'GET' && !panelOk) return json(500, { code: 'server_error', message: 'Broke.' });
      if (url.pathname === '/api/v1/work/4121/slot' && request.method === 'POST') {
        slotPosts += 1;
        panelOk = false;
        return json(500, { code: 'server_error', message: 'Broke.' });
      }
      return wrapped(request);
    });
    render(<ToastProvider><LiveWorkItemView id="4121" tab="overview" /></ToastProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'Go' }));
    // the uncertain branch re-reads; the panel read fails; the form stays mounted on the last good readback
    await screen.findByText(/We couldn’t load this part of the page/);
    expect((screen.getByRole('button', { name: 'Go' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText(/We couldn’t load this part of the page/);
    const go = screen.getByRole('button', { name: 'Go' }) as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    expect(screen.getByText('Check the page before trying again.')).toBeTruthy();
    fireEvent.click(go);
    // and once the panel reads again, the revision is the same, so it is still locked
    panelOk = true;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.queryByText(/We couldn’t load this part of the page/)).toBeNull());
    expect((screen.getByRole('button', { name: 'Go' }) as HTMLButtonElement).disabled).toBe(true);
    expect(slotPosts).toBe(1);
  });

  it('without Actions the panel draws as before and nothing extra', async () => {
    registerLineAdapter(adapter(false) as LineAdapter);
    withPanel(4121);
    render(<ToastProvider><LiveWorkItemView id="4121" tab="overview" /></ToastProvider>);
    await screen.findByText('Panel text');
    expect(screen.queryByText(/Line actions/)).toBeNull();
  });

  it('a form that throws takes only itself down', async () => {
    registerLineAdapter({ ...adapter(false), Actions: () => { throw new Error('boom'); } } as LineAdapter);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    withPanel(4121);
    render(<ToastProvider><LiveWorkItemView id="4121" tab="overview" /></ToastProvider>);
    await screen.findByText(/We couldn’t show these controls/);
    expect(screen.getByText('Panel text')).toBeTruthy();
  });
});
