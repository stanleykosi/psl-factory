// @vitest-environment jsdom
// F-85: /work/[id] and /work/[id]/history on the live API (GET /work/{id}, /history). Fixtures come from the mock itself.
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { decisionHref, historyCaption, historyLine, isLiveWorkId, lineName, needsPolling, safeHref } from '@/features/work-item/live/model';
import { POLL_MS } from '@/features/work-item/useWorkItem';
import type { LiveWorkItem } from '@/api/types';
import { SIGN_IN_URL } from '@/shell/sample';

// @ts-expect-error plain ESM module without type declarations
import { workLive } from '../mock/work-live.mjs';

// The frame owns the phone's back link; this test is about the page, so the hook is a no-op.
vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/work/4102',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
type Reply = { status: number; body: unknown };
/** What the mock answers for a GET, so the page is tested against the same fixtures the browser sees. */
const mock = (path: string, scenario?: string): Reply => {
  const [status, body] = workLive({ method: 'get', url: new URL(path, 'http://m.local'), scenario, csrfOk: true, persona: 'finance_lead' }) as [number, unknown];
  return { status, body };
};

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let answer: (url: URL) => Reply | undefined;
const urls = () => fetchStub.mock.calls.map(([request]) => new URL(request.url));
const reads = (suffix = '') => urls().filter((u) => /^\/api\/v1\/work\/\d+$/.test(u.pathname) && suffix === '');
const writes = () => fetchStub.mock.calls.filter(([request]) => request.method !== 'GET');

beforeEach(() => {
  answer = (url) => mock(url.pathname + url.search);
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 'fresh', signed_in: true, next_url: '/' });
    const reply = answer(url);
    return reply ? json(reply.status, reply.body) : json(404, { code: 'not_found', message: 'No.' });
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function open(id: string, tab: 'overview' | 'history' = 'overview') {
  return render(<LiveWorkItemView id={id} tab={tab} />);
}
const heading = () => screen.findByRole('heading', { level: 1 }, { timeout: 8000 });

describe('overview on the live item', () => {
  it('4102 shows the title, a Processing tag, the next step and the activity line, and none of the v7 parts (AC1, AC15)', async () => {
    open('4102');
    expect((await heading()).textContent).toBe('Weekly update for Lagoon Health');
    expect(document.querySelector('.work-state')?.textContent).toBe('Processing');
    expect(screen.getByText(/The agent is drafting the update/)).toBeTruthy();
    expect(screen.getByText('Drafting the weekly update')).toBeTruthy();
    expect(document.querySelector('.work-agentsec, .psl-steps')).toBeNull();
    expect(screen.queryByText(/not available/i)).toBeNull();
    expect(screen.queryByRole('button', { name: /resume|cancel|check what happened|release|start|correct/i })).toBeNull();
    expect(writes()).toHaveLength(0);
  });

  it('the owner is shown only when there is one, never "Unassigned" (4104)', async () => {
    open('4104');
    await heading();
    expect(screen.queryByText(/With /)).toBeNull();
    expect(document.querySelector('.work-sub')?.textContent).not.toMatch(/unassigned/i);
    expect(screen.getByText(/A policy value is missing/)).toBeTruthy();
  });

  it('null revisions load the page and are not drawn as 0 (AC11)', async () => {
    open('4104');
    await heading();
    expect(document.body.textContent).not.toMatch(/revision\s*0/i);
    const item = mock('/api/v1/work/4105').body as LiveWorkItem;
    expect(item.revision).toBeNull();
  });

  it('a decision link only for a task that can be decided or claimed; no claim or decide call (AC9)', async () => {
    open('4103');
    await heading();
    const links = screen.getAllByRole('link', { name: 'Open decision' });
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute('href')).toBe('/work/4103/decide?task=9101');
    expect(screen.getByText(/Finance Lead/)).toBeTruthy();
    expect(writes()).toHaveLength(0);
  });

  it('the output link only when output_url is set (AC10)', async () => {
    const first = open('4101');
    await heading();
    expect(screen.getByRole('link', { name: 'Open the output' }).getAttribute('href')).toBe('/api/v1/work/4101/output');
    first.unmount();
    open('4103');
    await heading();
    expect(screen.queryByRole('link', { name: 'Open the output' })).toBeNull();
  });

  it('a panel with no adapter is left out and the page still loads (AC20)', async () => {
    open('4107');
    await heading();
    expect(await screen.findByRole('heading', { name: 'Period' })).toBeTruthy();
    expect(screen.queryByText(/forecast/i)).toBeNull();
  });
});

describe('errors (AC5 to AC8)', () => {
  it('404 says one thing, "This record is unavailable."', async () => {
    open('4106');
    expect(await screen.findByRole('heading', { name: 'This record is unavailable.' })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/4106|permission|access to/i);
  });

  it('403 forbidden shows no access; 403 csrf_failed does not, and refreshes the session', async () => {
    answer = () => ({ status: 403, body: { code: 'forbidden', message: 'No.' } });
    const first = open('4102');
    expect(await screen.findByText(/can.t open this work item/i)).toBeTruthy();
    first.unmount();
    answer = () => ({ status: 403, body: { code: 'csrf_failed', message: 'x' } });
    open('4102');
    expect(await screen.findByText('Refresh your session and try again.')).toBeTruthy();
    expect(screen.queryByText(/can.t open this work item|can.t use PSL Factory/i)).toBeNull();
    await waitFor(() => expect(urls().some((u) => u.pathname === '/api/v1/session')).toBe(true));
  });

  it('401 shows the signed-out state with a sign-in link back to this page', async () => {
    answer = () => ({ status: 401, body: { code: 'not_signed_in', message: 'x' } });
    open('4102');
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(link.getAttribute('href')).toBe(`${SIGN_IN_URL}?next=%2Fwork%2F4102`);
  });

  it.each([
    [429, 'Try again shortly.'],
    [503, 'Try again shortly.'],
  ])('%i says "Try again shortly." with Try again', async (status, words) => {
    answer = () => ({ status, body: { code: 'busy', message: 'x' } });
    open('4102');
    expect(await screen.findByText(words)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it('a dropped network says so, with Try again', async () => {
    fetchStub.mockImplementation(async () => {
      throw new TypeError('network');
    });
    open('4102');
    expect(await screen.findByText(/could not reach PSL Factory/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });
});

describe('polling (AC4, AC5)', () => {
  async function opened(id: string) {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    open(id);
    await heading();
  }
  const tick = async () => act(async () => void (await vi.advanceTimersByTimeAsync(POLL_MS + 50)));

  it('a watched item is read again every 5 s', async () => {
    await opened('4102');
    expect(reads()).toHaveLength(1);
    await tick();
    expect(reads()).toHaveLength(2);
    await tick();
    expect(reads()).toHaveLength(3);
  });

  it('an item that is not watched and not processing is read once', async () => {
    await opened('4103');
    await tick();
    await tick();
    expect(reads()).toHaveLength(1);
  });

  it('a failed poll keeps the last good item and says it could not refresh; the next poll recovers', async () => {
    await opened('4102');
    answer = () => ({ status: 500, body: { code: 'server_error', message: 'x' } });
    await tick();
    expect(await screen.findByText(/couldn.t refresh this item/i)).toBeTruthy();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Weekly update for Lagoon Health');
    answer = (url) => mock(url.pathname);
    await tick();
    await waitFor(() => expect(screen.queryByText(/couldn.t refresh this item/i)).toBeNull());
  });

  it.each([401, 403, 404])('a %i on a poll replaces the page and stops polling', async (status) => {
    await opened('4102');
    answer = () => ({ status, body: { code: status === 403 ? 'forbidden' : 'x', message: 'x' } });
    await tick();
    await waitFor(() => expect(screen.queryByText('Drafting the weekly update')).toBeNull());
    const count = reads().length;
    await tick();
    expect(reads()).toHaveLength(count);
  });

  it('a hidden tab pauses reads', async () => {
    await opened('4102');
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    const count = reads().length;
    await tick();
    expect(reads()).toHaveLength(count);
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
  });
});

describe('history (AC12 to AC14)', () => {
  const historyCalls = () => urls().filter((u) => u.pathname.endsWith('/history'));

  it('lists rows, asks for each tab with its kind, and draws no counts and no Show more', async () => {
    open('4101', 'history');
    await screen.findByRole('list', { name: /History/ }, { timeout: 8000 });
    expect(historyCalls()[0].searchParams.has('kind')).toBe(false);
    for (const [tab, kind] of [['Decisions', 'decision'], ['Agent work', 'worker'], ['Evidence', 'evidence']] as const) {
      fireEvent.click(screen.getByRole('radio', { name: tab }));
      await waitFor(() => expect(historyCalls().at(-1)?.searchParams.get('kind')).toBe(kind));
    }
    expect(screen.queryByText(/show more/i)).toBeNull();
    expect(screen.getByText(/Showing all changes\./)).toBeTruthy();
  });

  it('unknown station and status stay as text; no actor, no evidence link when absent (AC13)', async () => {
    open('4101', 'history');
    await screen.findByText('Odd station', {}, { timeout: 8000 });
    expect(screen.getByText('Odd status', { exact: false })).toBeTruthy();
    expect(screen.getAllByText(/^Evidence \d+$/)).toHaveLength(1);
  });

  it('a first page with older events says "Showing the latest 30 changes."; a last page says all', async () => {
    open('4101', 'history');
    expect(await screen.findByText(/Showing the latest 30 changes\./, {}, { timeout: 8000 })).toBeTruthy();
    cleanup();
    open('4108', 'history');
    expect(await screen.findByText(/Showing all changes\./, {}, { timeout: 8000 })).toBeTruthy();
  });

  it('empty says "No changes recorded yet."', async () => {
    answer = (url) => (url.pathname.endsWith('/history') ? { status: 200, body: { items: [], as_of: '2026-11-23T09:00:00Z', next_before: null } } : mock(url.pathname));
    open('4101', 'history');
    expect(await screen.findByText('No changes recorded yet.', {}, { timeout: 8000 })).toBeTruthy();
  });

  it('an error keeps the chosen tab and offers Try again', async () => {
    answer = (url) => (url.pathname.endsWith('/history') && url.searchParams.get('kind') === 'worker' ? { status: 503, body: { code: 'busy', message: 'x' } } : mock(url.pathname + url.search));
    open('4101', 'history');
    await screen.findByRole('list', { name: /History/ }, { timeout: 8000 });
    fireEvent.click(screen.getByRole('radio', { name: 'Agent work' }));
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeTruthy();
    expect(screen.getByRole('radio', { name: 'Agent work' }).getAttribute('aria-checked')).toBe('true');
    answer = (url) => mock(url.pathname + url.search);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('list', { name: /History/ });
    expect(historyCalls().at(-1)?.searchParams.get('kind')).toBe('worker');
  });
});

describe('the mappers', () => {
  it('id, polling, decision link and history rows', () => {
    expect(isLiveWorkId('4102')).toBe(true);
    expect(isLiveWorkId('W-1003')).toBe(false);
    expect(isLiveWorkId('41x')).toBe(false);
    const item = (patch: Partial<LiveWorkItem>) => ({ ...(mock('/api/v1/work/4103').body as LiveWorkItem), ...patch });
    expect(needsPolling(item({ state: 'processing' }))).toBe(true);
    expect(needsPolling(item({ state: 'waiting', current_activity: { label: 'x', watching: true } }))).toBe(true);
    expect(needsPolling(item({ state: 'waiting', current_activity: { label: 'x', watching: false } }))).toBe(false);
    const task = (mock('/api/v1/work/4103').body as LiveWorkItem).tasks;
    expect(decisionHref(4103, task[0])).toBe('/work/4103/decide?task=9101');
    expect(decisionHref(4103, task[1])).toBeNull();
    expect(decisionHref(4103, { ...task[1], can_claim: true })).toBe('/work/4103/decide?task=9102');
    expect(historyLine({ at: 'a', station: 'zz_odd', status: 'weird', actor_kind: 'worker', entry_id: 1 })).toEqual({ at: 'a', station: 'Zz odd', status: 'Weird', actorKind: 'worker', entryId: 1, actor: null, reason: null, evidenceId: null });
    expect(historyLine({ at: 'a', station: 's', status: 't', actor_kind: 'person', entry_id: 2, evidence_id: null }).evidenceId).toBeNull();
    expect(historyCaption(30, true)).toBe('Showing the latest 30 changes.');
    expect(historyCaption(30, false)).toBe('Showing all changes.');
  });
});

describe('F-85 carried fixes', () => {
  it('safeHref allows http(s) and same-site paths only', () => {
    expect(safeHref('/api/v1/work/4101/output')).toBe('/api/v1/work/4101/output');
    expect(safeHref('https://files.example/a.pdf')).toBe('https://files.example/a.pdf');
    expect(safeHref('http://files.example/a.pdf')).toBe('http://files.example/a.pdf');
    for (const bad of ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', ' javascript:alert(1)', 'data:text/html,x', 'vbscript:x', 'file:///etc/passwd', '//evil.example/x', '/\\evil.example/x', 'relative/path', 'mailto:a@b.c', '', null, undefined]) {
      expect(safeHref(bad)).toBeNull();
    }
  });

  it('an output_url that is not http(s) or a site path draws no link', async () => {
    const base = mock('/api/v1/work/4101').body as LiveWorkItem;
    answer = (url) => (url.pathname === '/api/v1/work/4101' ? { status: 200, body: { ...base, output_url: 'javascript:alert(1)' } } : mock(url.pathname + url.search));
    open('4101');
    await heading();
    expect(screen.queryByRole('link', { name: 'Open the output' })).toBeNull();
  });

  it('lineName gives the live lines their plain names and any other key as words, without the version', () => {
    expect(lineName('pmo-weekly-report/v1')).toBe('Weekly client report');
    expect(lineName('pmo-finance/v1')).toBe('Invoice');
    expect(lineName('weekly_report')).toBe('Weekly report');
    expect(lineName('some-new-line/v2')).toBe('Some new line');
  });

  it('the breadcrumb names the line in plain words, never the key', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    open('4102');
    await heading();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('My work / Weekly report / Work 4102');
    expect(document.body.textContent).not.toMatch(/weekly_report|WEEKLY_REPORT/);
  });
});
