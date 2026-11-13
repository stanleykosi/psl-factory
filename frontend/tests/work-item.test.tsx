// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { STATE_TAGS, type HistoryEntry, type WorkHistory, type WorkItem, type WorkState } from '@/features/work-item/labels';
import { FactsStrip, StationTrack } from '@/features/work-item/WorkItemOverview';
import { WorkItemView } from '@/features/work-item/WorkItemView';

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-1001',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
/** The item the mock serves for an id: work/<id>.json, else the default fixture. */
const item = (id: string): WorkItem => (id === 'W-1001' ? read('E-WORK-ITEM.json') : read(`work/${id}.json`));
/** A history fixture as the API returns it: the mock-only `_kind` removed. */
function history(id: string): WorkHistory {
  const raw = read(`work/${id}.history.json`) as { items: (HistoryEntry & { _kind?: string })[]; as_of: string };
  return { as_of: raw.as_of, items: raw.items.map(({ _kind, ...entry }) => (void _kind, entry)) };
}
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Handler = (url: URL) => Response | Promise<Response>;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const urls = () => fetchStub.mock.calls.map(([request]) => new URL(request.url));
const historyUrls = () => urls().filter((u) => u.pathname.endsWith('/history'));
const itemUrls = () => urls().filter((u) => !u.pathname.endsWith('/history'));

/** Routes fetch by path: the item answer and the history answer, each built fresh per call. */
function serve(itemAnswer: Handler, historyAnswer: Handler = () => json(200, { items: [], as_of: '2026-11-12T15:45:00Z' })) {
  fetchStub.mockImplementation(async (request) => {
    const url = new URL(request.url);
    return url.pathname.endsWith('/history') ? historyAnswer(url) : itemAnswer(url);
  });
}

beforeEach(() => {
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

async function open(id: string, tab: 'overview' | 'history' = 'overview') {
  const view = render(<WorkItemView id={id} tab={tab} />);
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
  return view;
}

const facts = () => within(screen.getByRole('list', { name: 'Facts' })).getAllByRole('listitem');
const agentCard = () => screen.getByRole('region', { name: 'Agent at work' });

describe('overview', () => {
  it('W-1004 (A-WORKITEM) shows six separate facts, Unknown for the receipt, and the Paid note', async () => {
    serve(() => json(200, item('W-1004')));
    await open('W-1004');
    expect(fetchStub).toHaveBeenCalledTimes(1);
    expect(itemUrls()[0].pathname).toBe('/api/v1/work/W-1004');
    const boxes = facts();
    expect(boxes.map((li) => li.textContent)).toEqual([
      'DRAFTEDEarned12 Nov 10:58',
      'REVIEWEDEarned12 Nov 16:12',
      'APPROVEDEarned12 Nov 16:40',
      'SENT—Not yet',
      'RECEIPT RECORDEDUnknown',
      'VERIFIED—Not yet',
    ]);
    expect(boxes.map((li) => li.className)).toEqual([
      'psl-fact psl-fact--earned',
      'psl-fact psl-fact--earned',
      'psl-fact psl-fact--earned',
      'psl-fact',
      'psl-fact psl-fact--unknown',
      'psl-fact',
    ]);
    expect(boxes[2].querySelector('time')!.getAttribute('dateTime')).toBe('2026-11-12T15:40:00Z');
    for (const box of boxes) {
      const value = box.querySelector('strong')!.textContent!;
      expect(value).not.toMatch(/^$|^0$/);
    }
    expect(screen.getByText('Paid is a separate Finance fact and is not part of this line.')).toBeTruthy();
  });

  it('header: breadcrumb, title with the state tag, revision and tabs', async () => {
    serve(() => json(200, item('W-1004')));
    await open('W-1004');
    const crumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(crumb.textContent).toBe('My work / Prepare an invoice / INV-0419');
    expect(within(crumb).getByRole('link', { name: 'My work' }).getAttribute('href')).toBe('/my-work');
    expect(crumb.querySelector('.psl-mono')!.textContent).toBe('INV-0419');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · Milestone 3 invoice');
    expect(screen.getByText('Ready to continue').className).toBe('psl-tag psl-tag--person work-state');
    expect(screen.getByText('revision 4')).toBeTruthy();
    const tabs = within(screen.getByRole('navigation', { name: 'Work item' })).getAllByRole('link');
    expect(tabs.map((a) => [a.textContent, a.getAttribute('href'), a.getAttribute('aria-current')])).toEqual([
      ['Overview', '/work/W-1004', 'page'],
      ['History', '/work/W-1004/history', null],
    ]);
  });

  it('every fact unknown, or a missing fact, reads Unknown and never 0, No or blank', () => {
    const names = ['drafted', 'reviewed', 'approved', 'sent', 'receipt_recorded', 'verified'] as const;
    const { unmount } = render(<FactsStrip facts={names.map((name) => ({ name, status: 'unknown' }))} />);
    expect(facts().map((li) => li.querySelector('strong')!.textContent)).toEqual(Array(6).fill('Unknown'));
    unmount();
    render(<FactsStrip facts={item('W-1004').facts.filter((f) => f.name !== 'sent')} />);
    const sent = facts()[3];
    expect(sent.textContent).toBe('SENTUnknown');
    expect(sent.className).toBe('psl-fact psl-fact--unknown');
    for (const li of facts()) expect(li.querySelector('strong')!.textContent).not.toMatch(/^$|^0$|^No$/);
  });

  it('a verified fact that is earned uses the verified look', () => {
    render(<FactsStrip facts={item('W-1006').facts} />);
    expect(facts().map((li) => li.className)).toEqual([
      ...Array(5).fill('psl-fact psl-fact--earned'),
      'psl-fact psl-fact--verified',
    ]);
  });

  const STATES: [WorkState, string, string][] = [
    ['ready', 'Ready to continue', 'person'],
    ['processing', 'Processing', 'agent'],
    ['waiting', 'Waiting', 'waiting'],
    ['owner_needed', 'Owner needed', 'person'],
    ['setup_needed', 'Setup needed', 'person'],
    ['action_needed', 'Action needed', 'person'],
    ['effect_uncertain', 'Effect uncertain', 'waiting'],
    ['awaiting_reconciliation', 'Awaiting reconciliation', 'waiting'],
    ['verified', 'Verified', 'done'],
    ['cancelled', 'Cancelled', 'neutral'],
    ['followup_needed', 'Stopped: invoice follow-up needed', 'person'],
  ];

  it('covers all 11 contract states', () => {
    expect(Object.keys(STATE_TAGS).sort()).toEqual(STATES.map(([s]) => s).sort());
  });

  it.each(STATES)('state %s shows "%s" with psl-tag--%s', async (state, text, tone) => {
    serve(() => json(200, { ...item('W-1001'), state }));
    await open('W-1001');
    const tag = screen.getByRole('heading', { level: 1 }).parentElement!.querySelector('.psl-tag')!;
    expect(tag.textContent).toBe(text);
    expect(tag.classList.contains(`psl-tag--${tone}`)).toBe(true);
  });

  it('the station track maps all 7 statuses, numbers them and marks the current one', () => {
    const statuses = ['done', 'verified', 'current_agent', 'current_person', 'waiting', 'stopped', 'not_started'] as const;
    render(<StationTrack stations={statuses.map((status, i) => ({ name: `Station ${i + 1}`, status }))} />);
    const stations = within(screen.getByRole('region', { name: 'Stations' })).getAllByRole('listitem');
    expect(stations.map((li) => [li.className, li.textContent])).toEqual([
      ['psl-station psl-station--done', '01Station 1Done'],
      ['psl-station psl-station--verified', '02Station 2Verified'],
      ['psl-station psl-station--agent', '03Station 3Agent working'],
      ['psl-station psl-station--person', '04Station 4Needs a person'],
      ['psl-station psl-station--waiting', '05Station 5Waiting'],
      ['psl-station psl-station--stopped', '06Station 6Stopped'],
      ['psl-station psl-station--todo', '07Station 7Not started'],
    ]);
    expect(stations.map((li) => li.getAttribute('aria-current'))).toEqual([null, null, 'step', null, null, null, null]);
  });

  it('W-1003: the working agent shows its steps and sources and offers no decision', async () => {
    serve(() => json(200, item('W-1003')));
    await open('W-1003');
    const card = agentCard();
    expect(within(card).getByText('Tola')).toBeTruthy();
    expect(within(card).getByText('WORKING').className).toBe('psl-tag psl-tag--agent');
    expect(within(card).getByText('step 3 of 4')).toBeTruthy();
    expect(within(card).getByText('Cannot approve, send or pay.')).toBeTruthy();
    const steps = within(card).getAllByRole('listitem');
    expect(steps.map((li) => li.className)).toEqual([
      'psl-step psl-step--done',
      'psl-step psl-step--done',
      'psl-step psl-step--now',
      'psl-step psl-step--next',
    ]);
    expect(steps[2].querySelector('.psl-step__box')!.classList.contains('psl-now')).toBe(true);
    const sources = [...card.querySelectorAll('.psl-mono')].map((el) => el.textContent);
    expect(sources).toEqual(['Read: Minutes · 10 Nov', 'Read: Issue register · 4 open']);
    expect(within(card).queryAllByRole('button')).toEqual([]);
    expect(within(card).queryAllByRole('link')).toEqual([]);
    const decisive = [...card.querySelectorAll('*')].filter(
      (el) => /approve|send|pay/i.test(el.textContent ?? '') && el.children.length === 0 && el.textContent !== 'Cannot approve, send or pay.',
    );
    expect(decisive).toEqual([]);
    expect(screen.queryByRole('region', { name: 'Current human task' })).toBeNull();
  });

  it('W-1002: no agent work, and a task for another role has no link or button', async () => {
    serve(() => json(200, item('W-1002')));
    await open('W-1002');
    expect(within(agentCard()).getByText('No agent work on this item.')).toBeTruthy();
    const task = screen.getByRole('region', { name: 'Current human task' });
    expect(within(task).getByText('Only a Finance Officer can decide.')).toBeTruthy();
    expect(within(task).queryByText(/You are/)).toBeNull();
    expect(within(task).queryAllByRole('link')).toEqual([]);
    expect(within(task).queryAllByRole('button')).toEqual([]);
    expect(screen.getByText('Action needed')).toBeTruthy();
  });

  it('W-1001: the person who can act gets "Open the decision"', async () => {
    serve(() => json(200, item('W-1001')));
    await open('W-1001');
    const task = screen.getByRole('region', { name: 'Current human task' });
    expect(within(task).getByRole('heading', { level: 2 }).textContent).toBe('Decide invoice v2');
    expect(within(task).getByText('Only a Finance Lead can decide.')).toBeTruthy();
    expect(within(task).getByText('You are Finance Lead.')).toBeTruthy();
    expect(within(task).getByRole('link', { name: 'Open the decision' }).getAttribute('href')).toBe('/work/W-1001/decide?task=T-2001');
  });

  it('W-1005 effect uncertain: warning next step, SENT Unknown and no action button anywhere', async () => {
    serve(() => json(200, item('W-1005')));
    await open('W-1005');
    const next = screen.getByText('Next step.').closest('.psl-callout')!;
    expect(next.className).toBe('psl-callout psl-callout--warning work-next');
    expect(next.textContent).toContain('Nothing has been resent.');
    expect(facts()[3].textContent).toBe('SENTUnknown');
    expect(screen.queryAllByRole('button')).toEqual([]);
    const stations = within(screen.getByRole('region', { name: 'Stations' })).getAllByRole('listitem');
    expect(stations[5].getAttribute('aria-current')).toBe('step');
    expect(stations[5].className).toBe('psl-station psl-station--waiting');
  });

  it.each([
    ['W-1006', 'success'],
    ['W-1003', 'info'],
    ['W-1002', 'warning'],
  ])('%s next step uses the %s callout', async (id, kind) => {
    serve(() => json(200, item(id)));
    await open(id);
    expect(screen.getByText('Next step.').closest('.psl-callout')!.classList.contains(`psl-callout--${kind}`)).toBe(true);
  });

  it('shows SAMPLE DATA from the record even when the build says the API is live', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_MODE', 'live');
    serve(() => json(200, item('W-1004')));
    await open('W-1004');
    expect(document.querySelector('.work-sub .psl-sample')!.textContent).toBe('SAMPLE DATA');
  });
});

describe('item states', () => {
  it.each([403, 404])('%s shows the no-access board and nothing about the item', async (status) => {
    serve(() => json(status, { code: status === 403 ? 'forbidden' : 'not_found', message: 'x' }));
    await open('W-1099');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this work item');
    expect(screen.getByText('NO ACCESS').className).toContain('psl-tag psl-tag--neutral');
    expect(screen.getByText(/Nothing about it is shown here, not even its name or amount\./)).toBeTruthy();
    expect(screen.getByText(/ask the PMO Lead for access to the project\. If someone sent you this link/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Back to my queue' }).getAttribute('href')).toBe('/my-work');
    expect(screen.getByRole('link', { name: 'Back to my queue' }).className).toBe('psl-btn psl-btn--dark psl-btn--lg');
    expect(document.body.textContent).not.toContain('W-1099');
    expect(document.body.innerHTML).not.toContain('W-1099');
    expect(screen.queryByRole('navigation', { name: 'Work item' })).toBeNull();
  });

  it('401 shows the signed-out callout with next=/work/W-1001', async () => {
    serve(() => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }));
    await open('W-1001');
    expect(screen.getByText('You’re signed out.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fwork%2FW-1001');
  });

  it('a server error shows the work-item error card; Try again re-reads and shows the item', async () => {
    let calls = 0;
    serve(() => (++calls === 1 ? new Response('<html></html>', { status: 500 }) : json(200, item('W-1001'))));
    await open('W-1001');
    const card = screen.getByRole('alert');
    expect(card.className).toBe('shell-errorcard');
    expect([...card.children].map((el) => el.textContent)).toEqual([
      'ERROR · COULDN’T LOAD',
      'We couldn’t load this work item. Your work is safe; nothing was changed.',
      'Reference unexpected_response for support.',
      'Try again',
    ]);
    fireEvent.click(within(card).getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · Milestone 2 invoice'));
    expect(fetchStub).toHaveBeenCalledTimes(2);
  });

  it('a network error shows the same card with its reference', async () => {
    fetchStub.mockRejectedValue(new TypeError('Failed to fetch'));
    await open('W-1001');
    expect(within(screen.getByRole('alert')).getByText('Reference network_error for support.')).toBeTruthy();
  });
});

describe('history', () => {
  const rows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1);

  it('W-1004 lists rows in the order returned, with WAT times, actor tags, actors and events', async () => {
    const page = history('W-1004');
    serve(
      () => json(200, item('W-1004')),
      () => json(200, page),
    );
    await open('W-1004', 'history');
    await waitFor(() => expect(screen.getByRole('table')).toBeTruthy());
    expect(historyUrls()[0].search).toBe('?kind=all&limit=20');
    const shown = rows();
    expect(shown).toHaveLength(12);
    expect(shown.map((tr) => tr.querySelector('time')!.getAttribute('dateTime'))).toEqual(page.items.map((e) => e.at));
    expect(shown[0].querySelector('time')!.textContent).toBe('12 Nov 16:40');
    expect(shown[0].textContent).toBe('12 Nov 16:40PERSON Ada Okafor · Finance LeadApproved invoice v2Note: "Matches SOW-0198 stage 3."Version: v2');
    expect(shown.map((tr) => tr.querySelector('.psl-tag')!.textContent)).toEqual(page.items.map((e) => e.actor_kind.toUpperCase()));
    expect(shown[0].querySelector('.psl-tag')!.className).toBe('psl-tag psl-tag--neutral');
    expect(shown[3].querySelector('.psl-tag')!.className).toBe('psl-tag psl-tag--agent');
    expect(shown[11].querySelector('.psl-tag')!.className).toBe('psl-tag work-tag--outline');
    const events = shown.map((tr) => tr.querySelector('.work-event')!.textContent);
    expect(events).toContain('Returned v1');
    expect(events).toContain('Approved invoice v2');
    expect(screen.getByText('As of 12 Nov 16:45')).toBeTruthy();
    expect(screen.getByText(/Nothing can be edited or deleted/)).toBeTruthy();
    expect(screen.queryByText(/CSV/)).toBeNull();
    expect(screen.getByRole('link', { name: 'History' }).getAttribute('aria-current')).toBe('page');
  });

  it('a restricted row shows only when, actor kind, actor and "Restricted"', async () => {
    const secret: HistoryEntry = {
      at: '2026-11-12T14:20:00Z',
      actor_kind: 'person',
      actor: 'Bisi Ade · Finance',
      event: 'Viewed payroll line SECRET-EVENT',
      detail: 'SECRET-DETAIL',
      version: 'SECRET-VERSION',
      restricted: true,
    };
    serve(
      () => json(200, item('W-1004')),
      () => json(200, { items: [secret], as_of: '2026-11-12T15:45:00Z' }),
    );
    await open('W-1004', 'history');
    await waitFor(() => expect(screen.getByRole('table')).toBeTruthy());
    expect(rows()[0].textContent).toBe('12 Nov 15:20PERSON Bisi Ade · FinanceRestrictedVersion: —');
    expect(document.body.innerHTML).not.toMatch(/SECRET-EVENT|SECRET-DETAIL|SECRET-VERSION|payroll/);
  });

  it('is read-only: its only controls are the filter, rows per page, Show more and Try again', async () => {
    serve(
      () => json(200, item('W-1004')),
      () => json(200, { ...history('W-1004'), next_cursor: 'o:12' }),
    );
    await open('W-1004', 'history');
    await waitFor(() => expect(screen.getByRole('table')).toBeTruthy());
    const controls = [...document.querySelectorAll('button, input, select, textarea, [contenteditable]')];
    expect(controls.map((el) => [el.tagName, el.getAttribute('role'), el.textContent])).toEqual([
      ['BUTTON', 'radio', 'All'],
      ['BUTTON', 'radio', 'Decisions'],
      ['BUTTON', 'radio', 'Agent work'],
      ['BUTTON', 'radio', 'Evidence'],
      ['SELECT', null, '102050'],
      ['BUTTON', null, 'Show more'],
    ]);
    expect(within(screen.getByRole('table')).queryAllByRole('link')).toEqual([]);
  });

  it('a history error keeps the header and tabs and shows the error card in the history area', async () => {
    let calls = 0;
    serve(
      () => json(200, item('W-1004')),
      () => (++calls === 1 ? json(503, { code: 'unavailable', message: 'Down' }) : json(200, history('W-1004'))),
    );
    await open('W-1004', 'history');
    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · Milestone 3 invoice');
    expect(screen.getByRole('navigation', { name: 'Work item' })).toBeTruthy();
    expect(screen.getByText('Reference unavailable for support.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(rows()).toHaveLength(12));
  });

  it('filter, rows per page and Show more send kind, limit and cursor; Show more appends and then goes', async () => {
    const all = history('W-1004').items;
    serve(
      () => json(200, item('W-1004')),
      (url) => {
        const limit = Number(url.searchParams.get('limit'));
        const offset = url.searchParams.get('cursor') ? 10 : 0;
        const items = all.slice(offset, offset + limit);
        return json(200, { items, as_of: '2026-11-12T15:45:00Z', ...(offset + limit < all.length ? { next_cursor: 'o:10' } : {}) });
      },
    );
    await open('W-1004', 'history');
    await waitFor(() => expect(screen.getByRole('table')).toBeTruthy());
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();

    fireEvent.click(screen.getByRole('radio', { name: 'Decisions' }));
    await waitFor(() => expect(historyUrls()).toHaveLength(2));
    expect(historyUrls()[1].search).toBe('?kind=decisions&limit=20');
    expect(screen.getByRole('radio', { name: 'Decisions' }).getAttribute('aria-checked')).toBe('true');

    fireEvent.click(screen.getByRole('radio', { name: 'All' }));
    await waitFor(() => expect(historyUrls()).toHaveLength(3));
    fireEvent.change(screen.getByRole('combobox', { name: 'Rows per page' }), { target: { value: '10' } });
    await waitFor(() => expect(historyUrls()).toHaveLength(4));
    expect(historyUrls()[3].search).toBe('?kind=all&limit=10');
    await waitFor(() => expect(rows()).toHaveLength(10));

    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(rows()).toHaveLength(12));
    expect(historyUrls()[4].search).toBe('?kind=all&limit=10&cursor=o%3A10');
    expect(rows().map((tr) => tr.querySelector('time')!.getAttribute('dateTime'))).toEqual(all.map((e) => e.at));
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('arrow keys move through the filter and choose', async () => {
    serve(() => json(200, item('W-1004')));
    await open('W-1004', 'history');
    const allOption = screen.getByRole('radio', { name: 'All' });
    expect(allOption.tabIndex).toBe(0);
    expect(screen.getByRole('radio', { name: 'Evidence' }).tabIndex).toBe(-1);
    fireEvent.keyDown(allOption, { key: 'ArrowLeft' });
    await waitFor(() => expect(screen.getByRole('radio', { name: 'Evidence' }).getAttribute('aria-checked')).toBe('true'));
    expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Evidence' }));
    await waitFor(() => expect(historyUrls().at(-1)!.search).toBe('?kind=evidence&limit=20'));
  });

  it('an empty filter says nothing is recorded yet', async () => {
    serve(() => json(200, item('W-1004')));
    await open('W-1004', 'history');
    await waitFor(() => expect(screen.getByText('Nothing recorded for this filter yet.')).toBeTruthy());
    expect(screen.getByText('Nothing recorded for this filter yet.').closest('.psl-empty')).toBeTruthy();
  });
});

describe('updates (D-UPDATES r2)', () => {
  let visibility: DocumentVisibilityState;
  beforeEach(() => {
    visibility = 'visible';
    vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => visibility);
    vi.useFakeTimers();
  });
  afterEach(() => vi.restoreAllMocks());

  const settle = () => act(() => vi.advanceTimersByTimeAsync(0));
  const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
  async function openWithFakeTimers(id: string, tab: 'overview' | 'history' = 'overview') {
    render(<WorkItemView id={id} tab={tab} />);
    await settle();
    await settle();
  }

  it('re-reads a working item every 5 s', async () => {
    serve(() => json(200, item('W-1003')));
    await openWithFakeTimers('W-1003');
    expect(itemUrls()).toHaveLength(1);
    await advance(4999);
    expect(itemUrls()).toHaveLength(1);
    await advance(1);
    expect(itemUrls()).toHaveLength(2);
    await advance(5000);
    expect(itemUrls()).toHaveLength(3);
  });

  it('never polls when the agent is not working', async () => {
    serve(() => json(200, item('W-1001')));
    await openWithFakeTimers('W-1001');
    await advance(30000);
    expect(itemUrls()).toHaveLength(1);
  });

  it('stops when the agent finishes', async () => {
    let calls = 0;
    serve(() => json(200, ++calls === 1 ? item('W-1003') : { ...item('W-1003'), agent: { ...item('W-1003').agent, status: 'done' } }));
    await openWithFakeTimers('W-1003');
    await advance(5000);
    expect(itemUrls()).toHaveLength(2);
    await advance(30000);
    expect(itemUrls()).toHaveLength(2);
    expect(screen.getByText('DONE')).toBeTruthy();
  });

  it('stops while the page is hidden and resumes when it is visible again', async () => {
    serve(() => json(200, item('W-1003')));
    await openWithFakeTimers('W-1003');
    visibility = 'hidden';
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await advance(30000);
    expect(itemUrls()).toHaveLength(1);
    visibility = 'visible';
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await advance(5000);
    expect(itemUrls()).toHaveLength(2);
  });

  it('a failed poll keeps the item on screen with a warning, and the next poll tries again', async () => {
    let calls = 0;
    serve(() => (++calls === 2 ? json(503, { code: 'unavailable', message: 'Down' }) : json(200, item('W-1003'))));
    await openWithFakeTimers('W-1003');
    await advance(5000);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Delta Foods · Weekly client update');
    expect(screen.getByText(/We couldn’t refresh this item\. Showing what we had at \d+ \w{3} \d\d:\d\d\./)).toBeTruthy();
    await advance(5000);
    expect(itemUrls()).toHaveLength(3);
    expect(screen.queryByText(/We couldn’t refresh this item/)).toBeNull();
  });

  it('a poll that loses access replaces the item with the no-access or signed-out state and stops', async () => {
    for (const [status, text] of [
      [403, 'You can’t open this work item'],
      [404, 'You can’t open this work item'],
      [401, 'Sign in'],
    ] as const) {
      fetchStub.mockReset();
      let calls = 0;
      serve(() => (++calls === 2 ? json(status, { code: 'denied', message: 'No' }) : json(200, item('W-1003'))));
      const view = render(<WorkItemView id="W-1003" tab="overview" />);
      await settle();
      await settle();
      await advance(5000);
      expect(screen.queryByText('Delta Foods · Weekly client update'), String(status)).toBeNull();
      expect(screen.getAllByText(new RegExp(text)).length, String(status)).toBeGreaterThan(0);
      await advance(30000);
      expect(itemUrls(), String(status)).toHaveLength(2);
      view.unmount();
    }
  });

  it('a new revision on the history view reloads history once from the first page', async () => {
    let calls = 0;
    serve(
      () => json(200, { ...item('W-1003'), revision: ++calls >= 3 ? 4 : 3 }),
      () => json(200, { ...history('W-1004'), next_cursor: 'o:12' }),
    );
    await openWithFakeTimers('W-1003', 'history');
    await settle();
    expect(historyUrls()).toHaveLength(1);
    await advance(5000); // revision still 3
    expect(historyUrls()).toHaveLength(1);
    await advance(5000); // revision 4
    await settle();
    expect(historyUrls()).toHaveLength(2);
    expect(historyUrls()[1].search).toBe('?kind=all&limit=20');
    await advance(5000); // still 4
    expect(historyUrls()).toHaveLength(2);
  });
});
