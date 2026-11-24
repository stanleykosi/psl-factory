// @vitest-environment jsdom
// F-91: the station track, six facts, agent card, reference, started line and paged history on the live work item.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { LiveHistoryRow, LiveTracking, LiveWorkItem } from '@/api/types';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { factsOf, historyLine, mergeHistory, stationsOf } from '@/features/work-item/live/model';
import { POLL_MS } from '@/features/work-item/useWorkItem';

// @ts-expect-error plain ESM module without type declarations
import { workLive } from '../mock/work-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/work/4102',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
type Reply = { status: number; body: unknown };
const mock = (path: string): Reply => {
  const [status, body] = workLive({ method: 'get', url: new URL(path, 'http://m.local'), csrfOk: true, persona: 'finance_lead' }) as [number, unknown];
  return { status, body };
};
const tracking = (id: number) => mock(`/api/v1/work/${id}/tracking`).body as LiveTracking;
const work = (id: number) => mock(`/api/v1/work/${id}`).body as LiveWorkItem;

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let answer: (url: URL) => Reply | undefined;
let delay: (url: URL) => Promise<void> | undefined;
const urls = () => fetchStub.mock.calls.map(([request]) => new URL(request.url));
const trackingReads = () => urls().filter((u) => u.pathname.endsWith('/tracking'));
const historyReads = () => urls().filter((u) => u.pathname.endsWith('/history'));

beforeEach(() => {
  answer = (url) => mock(url.pathname + url.search);
  delay = () => undefined;
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] });
    await delay(url);
    const reply = answer(url);
    return reply ? json(reply.status, reply.body) : json(404, { code: 'not_found', message: 'No.' });
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const open = (id: string, tab: 'overview' | 'history' = 'overview') => render(<LiveWorkItemView id={id} tab={tab} />);
const heading = () => screen.findByRole('heading', { level: 1 }, { timeout: 8000 });
const track = () => screen.findByRole('list', { name: 'Stations in order' }, { timeout: 8000 });
const facts = () => screen.getByRole('list', { name: 'Facts' });
const items = (list: HTMLElement) => within(list).getAllByRole('listitem');

describe('the station track and the six facts (AC1 to AC4)', () => {
  it('4102 draws five stations in order with their holders and the execution station as current', async () => {
    open('4102');
    const stations = items(await track());
    expect(stations.map((s) => s.querySelector('strong')?.textContent)).toEqual(['Intake', 'Execution', 'Decision', 'Delivery', 'Verified']);
    expect(stations.map((s) => s.querySelector('span')?.textContent)).toEqual(['Tunde Bello', 'Tola', 'Unassigned', 'Unassigned', 'Unassigned']);
    expect(stations.map((s) => s.getAttribute('aria-current'))).toEqual([null, 'step', null, null, null]);
    expect(stations[1].className).toContain('psl-station--agent');
  });

  it('4102: Drafted reads Unknown, nothing reads No or 0; Not yet boxes are blank for sighted users', async () => {
    open('4102');
    await track();
    const boxes = items(facts());
    expect(boxes).toHaveLength(6);
    expect(boxes[0].textContent).toContain('Unknown');
    expect(boxes[1].textContent).toContain('Not yet');
    expect(within(facts()).queryByText(/^(No|0)$/)).toBeNull();
  });

  it('4103: reviewed null is Unknown; the decision station is a person station held by Ada Okafor', async () => {
    open('4103');
    const stations = items(await track());
    expect(stations[2].textContent).toContain('Ada Okafor');
    expect(stations[2].className).toContain('psl-station--person');
    expect(items(facts())[1].textContent).toContain('Unknown');
  });

  it('4101: only Verified shows a time; the other earned facts say Earned alone; no Paid note', async () => {
    open('4101');
    await track();
    const boxes = items(facts());
    expect(boxes.map((b) => b.querySelector('time') !== null)).toEqual([false, false, false, false, false, true]);
    expect(boxes[0].textContent).toContain('Earned');
    expect(screen.queryByText(/Paid is/)).toBeNull();
  });

  it('4104 (stuck): the current station is stopped and an unknown station reads Unknown, not done', async () => {
    open('4104');
    const stations = items(await track());
    expect(stations[1].className).toContain('psl-station--stopped');
    expect(stations[2].textContent).toContain('Unknown');
    expect(stations[2].className).toContain('psl-station--todo');
  });
});

describe('stationsOf and factsOf', () => {
  const base = tracking(4102);
  const item = work(4102);
  const st = (rows: [LiveTracking['stations'][number]['key'], LiveTracking['stations'][number]['status'], string | null][]): LiveTracking => ({
    ...base,
    stations: rows.map(([key, status, owner], i) => ({ key, name: key, position: i + 1, status, owner })),
  });

  it('holders: owner when set; else Unassigned for pending and current, Not recorded for recorded; unknown reads Unknown', () => {
    const out = stationsOf(st([['intake', 'recorded', null], ['execution', 'current', null], ['decision', 'pending', null], ['delivery', 'unknown', 'Someone'], ['verified', 'recorded', 'Ada']]), { ...item, current_activity: undefined });
    expect(out.map((s) => s.text)).toEqual(['Not recorded', 'Unassigned', 'Unassigned', 'Unknown', 'Ada']);
    expect(out.map((s) => s.status)).toEqual(['done', 'waiting', 'todo', 'todo', 'verified']);
  });

  it('is drawn in position order and an empty list draws none', () => {
    const t = st([['decision', 'pending', null], ['intake', 'recorded', null]]);
    t.stations = [{ ...t.stations[0], position: 2 }, { ...t.stations[1], position: 1 }];
    expect(stationsOf(t, item).map((s) => s.name)).toEqual(['intake', 'decision']);
    expect(stationsOf({ ...base, stations: [] }, item)).toEqual([]);
  });

  it('current station kind: person for intake and decision, agent only when watched, stopped for a stuck state', () => {
    const one = (key: 'intake' | 'execution' | 'decision' | 'delivery', patch: Partial<LiveWorkItem>) => stationsOf(st([[key, 'current', 'X']]), { ...item, ...patch })[0].status;
    expect(one('intake', {})).toBe('person');
    expect(one('decision', {})).toBe('person');
    expect(one('execution', { current_activity: { label: 'x', watching: true } })).toBe('agent');
    expect(one('execution', { current_activity: { label: 'x', watching: false } })).toBe('waiting');
    expect(one('delivery', {})).toBe('waiting');
    for (const state of ['action_needed', 'owner_needed', 'setup_needed', 'effect_uncertain', 'awaiting_reconciliation', 'followup_needed', 'cancelled'] as const) {
      expect(one('execution', { state, current_activity: { label: 'x', watching: true } })).toBe('stopped');
    }
  });

  it('facts: true earned, false not yet, null Unknown; only Verified carries the time', () => {
    const out = factsOf({ ...base, verified_at: '2026-11-22T16:40:00Z', facts: { drafted: null, reviewed: false, approved: true, sent: true, receipt: null, verified: true } });
    expect(out.drafted).toEqual({ status: 'unknown' });
    expect(out.reviewed).toEqual({ status: 'not_yet' });
    expect(out.approved).toEqual({ status: 'earned' });
    expect(out.receipt_recorded).toEqual({ status: 'unknown' });
    expect(out.verified).toEqual({ status: 'earned', at: '2026-11-22T16:40:00Z' });
    expect(factsOf({ ...base, facts: { ...base.facts, verified: null } }).verified).toEqual({ status: 'unknown' });
  });
});

describe('header, agent card and missing tracking (AC5, AC6, AC10)', () => {
  it('reference sits beside the id; null reference keeps Work {id} alone; started line from tracking', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    const first = open('4101');
    await heading();
    await track();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('My work / Invoice / Work 4101 · INV-0412');
    expect(document.querySelector('.work-sub')?.textContent).toMatch(/Started by Tunde Bello · /);
    first.unmount();
    open('4104');
    await heading();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('My work / Weekly report / Work 4104');
  });

  it('4105 has no tracking_url: no track, no facts, no started line, no tracking read; the rest loads', async () => {
    open('4105');
    await heading();
    expect(document.querySelector('.psl-track, .psl-facts')).toBeNull();
    expect(document.querySelector('.work-sub')?.textContent).not.toMatch(/Started by/);
    expect(trackingReads()).toHaveLength(0);
    expect(screen.queryByText(/couldn.t load where/i)).toBeNull();
  });

  it('4102 agent card: name, activity line, last activity; no numbered steps', async () => {
    open('4102');
    await track();
    const card = screen.getByRole('region', { name: 'Agent at work' });
    expect(within(card).getByText('Tola')).toBeTruthy();
    expect(within(card).getByText('Drafting the weekly update')).toBeTruthy();
    expect(within(card).getByText(/Last activity: Worker · Drafting/)).toBeTruthy();
    expect(card.querySelector('ol, .psl-steps, .psl-step')).toBeNull();
    expect(document.body.textContent).not.toMatch(/Read:/);
  });

  it('an item with no agent, no activity and no last activity draws no agent area', async () => {
    open('4103');
    await track();
    expect(screen.queryByRole('region', { name: 'Agent at work' })).toBeNull();
  });
});

describe('tracking errors and polling (AC7 to AC9)', () => {
  it('4107: 503 shows one callout with Try again; Try again reads tracking only', async () => {
    open('4107');
    await heading();
    expect(await screen.findByText(/couldn.t load where this work is held\./i)).toBeTruthy();
    expect(screen.getByText(/Try again shortly\./)).toBeTruthy();
    expect(screen.getByRole('heading', { level: 1 })).toBeTruthy();
    const items = urls().filter((u) => /^\/api\/v1\/work\/4107$/.test(u.pathname)).length;
    expect(trackingReads()).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(trackingReads()).toHaveLength(2));
    expect(urls().filter((u) => /^\/api\/v1\/work\/4107$/.test(u.pathname))).toHaveLength(items);
  });

  const tick = async () => act(async () => void (await vi.advanceTimersByTimeAsync(POLL_MS + 50)));

  it('tracking is read again on each item poll while watched, and once otherwise', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    open('4102');
    await track();
    expect(trackingReads()).toHaveLength(1);
    await tick();
    await waitFor(() => expect(trackingReads()).toHaveLength(2));
    await tick();
    await waitFor(() => expect(trackingReads()).toHaveLength(3));
    cleanup();
    fetchStub.mockClear();
    open('4103');
    await track();
    await tick();
    await tick();
    expect(trackingReads()).toHaveLength(1);
  });

  it('a failed tracking poll keeps the last good track', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    open('4102');
    await track();
    answer = (url) => (url.pathname.endsWith('/tracking') ? { status: 500, body: { code: 'server_error', message: 'x' } } : mock(url.pathname));
    await tick();
    await waitFor(() => expect(trackingReads().length).toBeGreaterThan(1));
    expect(items(screen.getByRole('list', { name: 'Stations in order' }))).toHaveLength(5);
    expect(screen.queryByText(/couldn.t load where/i)).toBeNull();
  });

  it.each([404, 403])('a %i on tracking shows the page-level state and stops polling', async (status) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    answer = (url) => (url.pathname.endsWith('/tracking') ? { status, body: { code: status === 403 ? 'forbidden' : 'not_found', message: 'x' } } : mock(url.pathname));
    open('4102');
    await screen.findByText(status === 404 ? 'This record is unavailable.' : /can.t open this work item/i);
    const count = urls().length;
    await tick();
    expect(urls()).toHaveLength(count);
    if (status === 404) expect(screen.getByRole('heading', { name: 'This record is unavailable.' })).toBeTruthy();
  });

  it('a 401 on tracking shows the signed-out state', async () => {
    answer = (url) => (url.pathname.endsWith('/tracking') ? { status: 401, body: { code: 'not_signed_in', message: 'x' } } : mock(url.pathname));
    open('4102');
    expect(await screen.findByRole('link', { name: 'Sign in' })).toBeTruthy();
  });
});

const row = (entry_id: number, patch: Partial<LiveHistoryRow> = {}): LiveHistoryRow => ({ at: '2026-11-23T08:00:00Z', station: 's', status: 't', actor_kind: 'worker', entry_id, ...patch });

describe('history rows and paging (AC11 to AC18)', () => {
  it('historyLine keeps the actor kind and entry id; unknown stations stay as text', () => {
    expect(historyLine(row(5, { station: 'recheck_queue', actor_kind: 'person', actor: 'Kemi' }))).toMatchObject({ station: 'Recheck queue', actorKind: 'person', entryId: 5, actor: 'Kemi' });
    expect(historyLine(row(6)).actor).toBeNull();
  });

  it('mergeHistory appends older rows and drops an entry id already shown', () => {
    expect(mergeHistory([row(3), row(2)], [row(2), row(1)]).map((r) => r.entry_id)).toEqual([3, 2, 1]);
  });

  it('rows carry PERSON or AGENT tags; a worker with no actor shows the tag alone', async () => {
    open('4101', 'history');
    await screen.findByRole('list', { name: /History/ }, { timeout: 8000 });
    const rows = screen.getAllByRole('listitem').filter((li) => li.className === 'work-hcard');
    expect(rows[0].textContent).toContain('AGENT');
    expect(rows[1].textContent).toContain('PERSON');
    expect(rows[1].textContent).toContain('Kemi Adebayo');
    const alone = rows[2].querySelector('.work-who');
    expect(alone?.textContent).toBe('AGENT');
  });

  it('Older events asks before=<next_before> with the same kind, appends 30 rows once, and goes away at the end', async () => {
    open('4101', 'history');
    await screen.findByRole('list', { name: /History/ }, { timeout: 8000 });
    const rowsOf = () => document.querySelectorAll('.work-hcard').length;
    expect(rowsOf()).toBe(30);
    const first = historyReads()[0];
    expect(first.searchParams.has('before')).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Older events' }));
    await waitFor(() => expect(rowsOf()).toBe(60));
    const second = historyReads()[1];
    expect(second.searchParams.get('before')).toMatch(/^\d+$/);
    expect(second.searchParams.has('kind')).toBe(false);
    expect(screen.queryByRole('button', { name: 'Older events' })).toBeNull();
    expect(screen.getByText(/Showing all changes\./)).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(document.querySelectorAll('.work-hcard')[30]));
  });

  it('a filter change after paging starts again at page one; a slow answer to the earlier page never replaces the rows', async () => {
    const release: (() => void)[] = [];
    delay = (url) => (url.pathname.endsWith('/history') && url.searchParams.has('before') ? new Promise<void>((resolve) => release.push(resolve)) : undefined);
    open('4101', 'history');
    await screen.findByRole('list', { name: /History/ }, { timeout: 8000 });
    fireEvent.click(screen.getByRole('button', { name: 'Older events' }));
    await waitFor(() => expect(release).toHaveLength(1));
    fireEvent.click(screen.getByRole('radio', { name: 'Decisions' }));
    await waitFor(() => expect(historyReads().at(-1)?.searchParams.get('kind')).toBe('decision'));
    await waitFor(() => expect(document.querySelectorAll('.work-hcard').length).toBe(1));
    release[0]();
    await act(async () => void (await new Promise((r) => setTimeout(r, 50))));
    expect(document.querySelectorAll('.work-hcard').length).toBe(1);
    expect(historyReads().at(-1)?.searchParams.has('before')).toBe(false);
  });

  it('a failed Older events keeps the rows, says why, offers Try again and sends no second request by itself', async () => {
    open('4101', 'history');
    await screen.findByRole('list', { name: /History/ }, { timeout: 8000 });
    answer = (url) => (url.searchParams.has('before') ? { status: 503, body: { code: 'busy', message: 'x' } } : mock(url.pathname + url.search));
    fireEvent.click(screen.getByRole('button', { name: 'Older events' }));
    expect(await screen.findByText('Try again shortly.')).toBeTruthy();
    expect(document.querySelectorAll('.work-hcard').length).toBe(30);
    await act(async () => void (await new Promise((r) => setTimeout(r, 100))));
    expect(historyReads().filter((u) => u.searchParams.has('before'))).toHaveLength(1);
    answer = (url) => mock(url.pathname + url.search);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(document.querySelectorAll('.work-hcard').length).toBe(60));
  });

  it('no counts and no version column; a history 404 is unavailable and a 403 csrf_failed is not no-access', async () => {
    answer = (url) => (url.pathname.endsWith('/history') ? { status: 404, body: { code: 'not_found', message: 'x' } } : mock(url.pathname));
    open('4101', 'history');
    expect(await screen.findByRole('heading', { name: 'This record is unavailable.' }, { timeout: 8000 })).toBeTruthy();
    cleanup();
    answer = (url) => (url.pathname.endsWith('/history') ? { status: 403, body: { code: 'csrf_failed', message: 'x' } } : mock(url.pathname));
    open('4101', 'history');
    expect(await screen.findByText('Refresh your session and try again.', {}, { timeout: 8000 })).toBeTruthy();
    expect(screen.queryByText(/can.t open this work item/i)).toBeNull();
  });
});

describe('no writes (AC19)', () => {
  it('opening the page and paging history send only GETs', async () => {
    open('4101', 'history');
    await screen.findByRole('list', { name: /History/ }, { timeout: 8000 });
    fireEvent.click(screen.getByRole('button', { name: 'Older events' }));
    await waitFor(() => expect(document.querySelectorAll('.work-hcard').length).toBe(60));
    expect(fetchStub.mock.calls.filter(([request]) => request.method !== 'GET')).toHaveLength(0);
  });
});
