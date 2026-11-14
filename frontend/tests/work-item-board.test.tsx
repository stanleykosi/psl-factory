// @vitest-environment jsdom
// F-14: the work item page on the SCR-02 board fixtures (W-1701 to W-1711), with the PROPOSAL presentation block.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { nextStepKind, STATE_TAGS, type HistoryEntry, type WorkHistory, type WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-1701',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
type BoardItem = WorkItem & { presentation?: Record<string, unknown> };
const item = (id: string): BoardItem => (id === 'W-1001' ? read('E-WORK-ITEM.json') : read(`work/${id}.json`));
function history(id: string): WorkHistory {
  const raw = read(`work/${id}.history.json`) as { items: (HistoryEntry & { _kind?: string })[]; as_of: string };
  return { as_of: raw.as_of, items: raw.items.map(({ _kind, ...entry }) => (void _kind, entry)) };
}
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const BOARD_IDS = ['W-1701', 'W-1702', 'W-1703', 'W-1704', 'W-1705', 'W-1706', 'W-1707', 'W-1708', 'W-1709', 'W-1710', 'W-1711'];

type Handler = (url: URL) => Response | Promise<Response>;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let me: unknown;
const calls = () => fetchStub.mock.calls.map(([request]) => ({ method: request.method, url: new URL(request.url) }));
const itemUrls = () => calls().filter((c) => c.url.pathname.startsWith('/api/v1/work/') && !c.url.pathname.endsWith('/history'));

function serve(itemAnswer: Handler, historyAnswer: Handler = () => json(200, { items: [], as_of: '2026-11-12T15:45:00Z' })) {
  fetchStub.mockImplementation(async (request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    return url.pathname.endsWith('/history') ? historyAnswer(url) : itemAnswer(url);
  });
}

function phone() {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
}

beforeEach(() => {
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
  me = read('me.finance_lead.json');
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function open(id: string, tab: 'overview' | 'history' = 'overview', body: unknown = item(id)) {
  serve(
    () => json(200, body),
    () => json(200, id === 'W-1705' ? history('W-1705') : { items: [], as_of: '2026-11-12T15:45:00Z' }),
  );
  const view = render(
    <AppShell>
      <WorkItemView id={id} tab={tab} />
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
  await waitFor(() => expect(document.querySelector('main h1')).toBeTruthy());
  return view;
}

const main = () => document.querySelector('main') as HTMLElement;
const phoneBar = () => document.querySelector('header.psl-phonebar') as HTMLElement;
const facts = () => within(screen.getByRole('list', { name: 'Facts' })).getAllByRole('listitem');
const stations = () => within(screen.getByRole('region', { name: 'Stations' })).getAllByRole('listitem');

describe('header (AC 9) and titles (AC 5)', () => {
  it('W-1701: crumb, title, contract state tag and the started line from started_by, started_at and revision', async () => {
    await open('W-1701');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('My work / Prepare an invoice / INV-0412');
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.textContent).toBe('Lagoon Health · Milestone 2 invoice');
    expect(h1.className).toBe('shell-title');
    expect(h1.parentElement!.querySelector('.psl-tag')!.textContent).toBe(STATE_TAGS.waiting.text);
    expect(screen.getByText('Started by Tunde Bello (PMO) · Mon 10 Nov 14:05 · revision 2')).toBeTruthy();
    expect(document.querySelectorAll('h1')).toHaveLength(1);
  });

  it('an item without started_by shows "revision N" only', async () => {
    await open('W-1702');
    expect(screen.getByText('revision 1')).toBeTruthy();
    expect(document.querySelector('header.work-header')!.textContent).not.toContain('Started by');
  });

  it('board overviews draw no tabs and no next-step block; the next step stays for screen readers', async () => {
    await open('W-1701');
    expect(screen.queryByRole('navigation', { name: 'Work item' })).toBeNull();
    const next = document.querySelector('.work-next')!;
    expect(next.textContent).toContain('A Finance Lead decides invoice v2.');
    expect(next.closest('.work-sr')).not.toBeNull();
  });

  it('the state boards draw the reference and client line instead of the breadcrumb', async () => {
    await open('W-1703');
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).toBeNull();
    expect(screen.getByText('INV-0412 · LAGOON HEALTH')).toBeTruthy();
  });
});

describe('phone back link in the frame slot (AC 4)', () => {
  const back = () => within(phoneBar()).getByRole('link', { name: /^Back to / });

  it.each([
    ['W-1701', 'overview', 'Queue', '/my-work'],
    ['W-1099', 'overview', 'Queue', '/my-work'],
    ['W-1705', 'history', 'Invoice', '/work/W-1705'],
    ['W-1004', 'history', 'Work item', '/work/W-1004'],
  ] as const)('%s %s: "← %s" to %s, and main has no back link of its own', async (id, tab, label, href) => {
    if (id === 'W-1099') {
      serve(() => json(404, { code: 'not_found', message: 'x' }));
      render(
        <AppShell>
          <WorkItemView id={id} tab={tab} />
        </AppShell>,
      );
      await waitFor(() => expect(screen.getByText('NO ACCESS')).toBeTruthy());
    } else {
      await open(id, tab);
    }
    await waitFor(() => expect(back().textContent).toBe(`← ${label}`));
    expect(back().getAttribute('href')).toBe(href);
    expect([...main().querySelectorAll('a')].filter((a) => a.textContent!.startsWith('←'))).toEqual([]);
  });

  it('while the item loads the bar already shows "← Queue"', async () => {
    serve(() => new Promise<Response>(() => {}));
    render(
      <AppShell>
        <WorkItemView id="W-1701" tab="overview" />
      </AppShell>,
    );
    await waitFor(() => expect(within(phoneBar()).getByRole('link', { name: 'Back to Queue' })).toBeTruthy());
    expect(screen.getByRole('status')).toBeTruthy();
  });
});

describe('facts (AC 6, AC 7)', () => {
  it('W-1705 shows the board details, and each box keeps its contract word for screen readers', async () => {
    await open('W-1705');
    const boxes = facts();
    expect(boxes.map((li) => li.querySelector('strong')!.textContent)).toEqual(['v2', 'Ada', '10:47', '11:02', '11:09', '11:12']);
    for (const box of boxes) expect(box.textContent).toContain('Earned');
    expect(boxes[4].textContent).toContain('RECEIPT RECORDED');
  });

  it('Unknown wins over a presentation detail, and a missing fact reads Unknown', async () => {
    const crafted = item('W-1710');
    crafted.presentation = { ...crafted.presentation, facts: { sent: 'Delivered', receipt_recorded: 'Found' } };
    crafted.facts = crafted.facts.filter((f) => f.name !== 'receipt_recorded');
    await open('W-1710', 'overview', crafted);
    expect(facts()[3].querySelector('strong')!.textContent).toBe('Unknown');
    expect(facts()[4].querySelector('strong')!.textContent).toBe('Unknown');
    expect(main().textContent).not.toContain('Delivered');
    expect(main().textContent).not.toContain('Found');
  });

  it('W-1710 Sent reads Unknown', async () => {
    await open('W-1710');
    expect(facts()[3].textContent).toBe('SENTUnknown');
  });
});

describe('stations (AC 8)', () => {
  it('W-1705: number, name, the board detail, and the contract word for screen readers', async () => {
    await open('W-1705');
    const rows = stations();
    expect(rows[0].textContent).toBe('01Milestone evidenceDone');
    expect(rows[3].textContent).toBe('04Finance reviewDone: Approved 10:47');
    expect(rows[6].textContent).toBe('07VerifyVerified: Verified 11:12');
  });

  it('W-1710: the current station is marked and keeps the amber look', async () => {
    await open('W-1710');
    const rows = stations();
    expect(rows.map((li) => li.getAttribute('aria-current'))).toEqual([null, null, null, null, null, 'step', null]);
    expect(rows[5].className).toBe('psl-station psl-station--waiting work-station--uncertain');
    expect(rows[5].textContent).toBe('06DeliverWaiting: Checking delivery');
  });
});

describe('decision summary (AC 10)', () => {
  it('W-1701: rows from tasks[].decision, who can decide, and Open the decision; no decision controls', async () => {
    await open('W-1701');
    const task = screen.getByRole('region', { name: 'Current human task' });
    const dl = task.querySelector('dl.decide-rows')!;
    expect([...dl.querySelectorAll('.decide-row')].map((r) => [r.querySelector('dt')!.textContent, r.querySelector('dd')!.textContent])).toEqual([
      ['Amount', '₦4,250,000.00'],
      ['Basis', 'Contract stage 2 of 4 · terms v1'],
      ['To', 'accounts@lagoonhealth.example'],
      ['Version', 'v2 · changed: PO number'],
    ]);
    expect(within(task).getByText('Only a Finance Lead can decide.')).toBeTruthy();
    expect(within(task).getByText('You are Finance Lead.')).toBeTruthy();
    expect(within(task).getByRole('link', { name: 'Open the decision' }).getAttribute('href')).toBe('/work/W-1701/decide?task=T-1701');
    expect(screen.queryByRole('button', { name: /approve|return|reject/i })).toBeNull();
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  it('W-1002 (you_can_act false): no link or button in its task panel', async () => {
    await open('W-1002');
    const task = screen.getByRole('region', { name: 'Current human task' });
    expect(within(task).queryAllByRole('link')).toEqual([]);
    expect(within(task).queryAllByRole('button')).toEqual([]);
  });
});

describe('agent card (AC 11)', () => {
  const AGENTS: [string, string, string | undefined, string][] = [
    ['W-1701', 'Chidi', 'Finance agent', 'Chidi drafted invoice v2. It is marked DRAFTED, not REVIEWED, until a Finance Lead decides.'],
    ['W-1702', 'Tola', 'PMO agent', "I'll start with the minutes from 06 Nov and the signed SOW."],
    ['W-1703', 'Chidi', 'Finance agent', 'Filling the invoice template'],
    ['W-1704', 'Tola', 'PMO agent', "Tola has done the agent's part and is waiting on Lagoon Health."],
    ['W-1705', 'Chidi', 'Finance agent', 'Found the delivery receipt at 11:09'],
    ['W-1706', 'Chidi', 'Finance agent', 'I drafted invoice v2 from the signed SOW.'],
    ['W-1708', 'Chidi', 'Finance agent', 'no one holds the Finance Lead role for this project'],
    ['W-1710', 'Chidi', 'Finance agent', 'The email provider didn'],
    ['W-1003', 'Tola', undefined, 'Writing the progress section'],
  ];

  it.each(AGENTS)('%s: %s, the role, the mascot with alt text and the message; never a decision control', async (id, name, role, message) => {
    await open(id);
    const cards = screen.getAllByRole('region', { name: 'Agent at work' });
    const text = cards.map((c) => c.textContent).join(' ');
    expect(text).toContain(name);
    if (role) expect(text).toContain(role);
    expect(text).toContain(message);
    expect(text).toContain('Cannot approve, send or pay.');
    if (role) {
      const img = document.querySelector(`img[src^="/agents/${name.toLowerCase()}"]`)!;
      expect(img.getAttribute('alt')).toBe(`${name}, ${role}`);
    }
    const scope = cards[0].closest('.work-agentpanel') ?? cards[0];
    const controls = [...scope.querySelectorAll('a, button')].map((el) => el.textContent ?? '');
    expect(controls.filter((t) => /approve|send|pay/i.test(t))).toEqual([]);
  });
});

describe('state panels (AC 12) and links (AC 13)', () => {
  const PANELS: [string, string, string?][] = [
    ['W-1702', 'Ready to begin'],
    ['W-1703', 'Drafting the invoice'],
    ['W-1704', 'Waiting on the client'],
    ['W-1705', 'Verified', "Verified doesn't mean paid"],
    ['W-1706', 'Issue and send · Finance', "TEST TEMPLATE · NOT PSL'S REAL INVOICE"],
    ['W-1707', 'Cancelled', 'Reason: “Duplicate. Milestone 2 is billed on INV-0412.”'],
    ['W-1708', 'Stopped · owner needed'],
    ['W-1709', 'Setup needed'],
    ['W-1710', 'Awaiting reconciliation'],
  ];

  it.each(PANELS)('%s shows "%s" and its body, and NextStep with the mapped callout', async (id, title, extra) => {
    await open(id);
    expect(screen.getAllByText(title).length).toBeGreaterThan(0);
    if (extra) expect(main().textContent).toContain(extra);
    const next = main().querySelector('.work-next')!;
    expect(next.className).toBe(`psl-callout psl-callout--${nextStepKind(item(id).state)} work-next`);
    expect(next.textContent).toBe(`Next step. ${item(id).next_step}`);
  });

  it('W-1710 lists Sent at, Checks and If not found', async () => {
    await open('W-1710');
    const panel = screen.getByRole('complementary', { name: 'Awaiting reconciliation' });
    expect([...panel.querySelectorAll('dt')].map((dt) => dt.textContent)).toEqual(['Sent at', 'Checks', 'If not found']);
  });

  it.each([
    ['W-1708', 'Fix it in Setup', '/setup'],
    ['W-1709', 'Open Setup', '/setup'],
    ['W-1703', 'Ask Chidi', '/assistant'],
    ['W-1707', 'Open INV-0412', '/work/W-1701'],
    ['W-1705', 'See in Verified outputs', '/my-work?queue=done'],
  ])('%s: "%s" goes to %s', async (id, name, href) => {
    await open(id);
    expect(within(main()).getByRole('link', { name }).getAttribute('href')).toBe(href);
  });

  it('a panel with an absolute, protocol-relative or script href renders none of them', async () => {
    const crafted = item('W-1709');
    const panel = crafted.presentation!.panel as Record<string, unknown>;
    panel.links = [
      { label: 'Absolute', href: 'https://x.example', primary: true },
      { label: 'Protocol', href: '//x.example' },
      { label: 'Script', href: 'javascript:alert(1)' },
    ];
    await open('W-1709', 'overview', crafted);
    for (const name of ['Absolute', 'Protocol', 'Script']) expect(screen.queryByRole('link', { name })).toBeNull();
    expect(main().innerHTML).not.toMatch(/x\.example|javascript:/);
  });
});

describe('read only (AC 14) and no role guesses (AC 15)', () => {
  const allowed = (el: Element) =>
    el.hasAttribute('aria-expanded') || el.getAttribute('role') === 'radio' || /^(Show more|\+ \d+ earlier entries|Try again)$/.test(el.textContent ?? '');

  it.each([...BOARD_IDS, 'W-1001', 'W-1002', 'W-1003', 'W-1004', 'W-1005', 'W-1006'])('%s sends only GETs to E-WORK-ITEM and E-WORK-HISTORY', async (id) => {
    phone();
    await open(id);
    for (const button of [...main().querySelectorAll('button')]) {
      expect(allowed(button), button.outerHTML).toBe(true);
      fireEvent.click(button);
    }
    for (const call of calls()) {
      expect(call.method).toBe('GET');
      expect(call.url.pathname).toMatch(/^\/api\/v1\/(me|work\/W-1\d{3}(\/history)?)$/);
    }
  });

  it('history: filter, rows per page and Show more send GETs only', async () => {
    await open('W-1705', 'history');
    await waitFor(() => expect(screen.getByRole('table')).toBeTruthy());
    fireEvent.click(screen.getByRole('radio', { name: 'Decisions 2' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Rows per page' }), { target: { value: '10' } });
    await waitFor(() => expect(calls().filter((c) => c.url.pathname.endsWith('/history')).length).toBeGreaterThanOrEqual(3));
    for (const button of [...main().querySelectorAll('button')]) expect(allowed(button)).toBe(true);
    for (const call of calls()) expect(call.method).toBe('GET');
  });

  it.each(['W-1708', 'W-1709'])('%s renders the same for finance_lead and pm', async (id) => {
    const view = await open(id);
    // React's generated ids (useId) differ per render; everything else must match.
    const markup = () => main().innerHTML.replace(/_r_\w+_/g, 'id');
    const asFinance = markup();
    view.unmount();
    me = read('me.pm.json');
    await open(id);
    expect(markup()).toBe(asFinance);
  });
});

describe('phone disclosures', () => {
  it('W-1701 "See his steps" shows and hides the steps without a request', async () => {
    phone();
    await open('W-1701');
    const before = calls().length;
    const toggle = screen.getByRole('button', { name: 'See his steps' });
    const steps = document.getElementById(toggle.getAttribute('aria-controls')!)!;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(steps.hidden).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(steps.hidden).toBe(false);
    expect(within(steps).getAllByRole('listitem')).toHaveLength(4);
    fireEvent.click(toggle);
    expect(steps.hidden).toBe(true);
    expect(calls()).toHaveLength(before);
  });

  it('W-1706 "Preview the invoice" shows the test-template preview in place', async () => {
    phone();
    await open('W-1706');
    const toggle = screen.getByRole('button', { name: 'Preview the invoice' });
    const preview = document.getElementById(toggle.getAttribute('aria-controls')!)!;
    expect(preview.hidden).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(within(preview).getByRole('article', { name: 'Invoice preview' }).textContent).toContain("TEST TEMPLATE · NOT PSL'S REAL INVOICE");
  });
});

describe('history on the boards (AC 18)', () => {
  it('W-1705 at desktop: History 7, filter counts, the table with detail lines, About history', async () => {
    await open('W-1705', 'history');
    await waitFor(() => expect(screen.getByRole('table')).toBeTruthy());
    const tabs = within(screen.getByRole('navigation', { name: 'Work item' })).getAllByRole('link');
    expect(tabs.map((a) => a.textContent)).toEqual(['Overview', 'History 7']);
    expect(screen.getAllByRole('radio').map((r) => r.textContent)).toEqual(['All 7', 'Decisions 2', 'Agent work 2', 'Evidence 1']);
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['WHEN', 'WHAT HAPPENED', 'VERSION']);
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(7);
    expect(rows[0].textContent).toBe('12 Nov 16:40PERSON Ada Okafor · Finance LeadApproved invoice v2 for ₦4,250,000.00Note: "Matches SOW-0198 stage 2."Version: v2');
    expect(rows.map((r) => r.querySelector('time')!.textContent)).toEqual([
      '12 Nov 16:40',
      '12 Nov 16:12',
      '12 Nov 15:58',
      '12 Nov 11:04',
      '11 Nov 17:30',
      '11 Nov 17:05',
      '11 Nov 17:02',
    ]);
    expect(screen.getByRole('complementary', { name: 'About history' })).toBeTruthy();
  });

  it('W-1705 at 390: HISTORY eyebrow, "History · INV-0412" and stacked entries', async () => {
    phone();
    await open('W-1705', 'history');
    await waitFor(() => expect(screen.getByRole('list', { name: 'History, newest first' })).toBeTruthy());
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('History · INV-0412');
    expect(screen.getByText('HISTORY')).toBeTruthy();
    const cards = within(screen.getByRole('list', { name: 'History, newest first' })).getAllByRole('listitem');
    // the phone board lists the five newest entries; "+ 2 earlier entries" shows the rest in place
    expect(cards).toHaveLength(5);
    expect(cards[0].textContent).toContain('12 Nov 16:40 · ');
    fireEvent.click(screen.getByRole('button', { name: '+ 2 earlier entries' }));
    expect(within(screen.getByRole('list', { name: 'History, newest first' })).getAllByRole('listitem')).toHaveLength(7);
  });

  it('with counts the phone button reads "+ N earlier entries"; without counts "Show more" and no badges', async () => {
    phone();
    const page = history('W-1705');
    serve(
      () => json(200, item('W-1705')),
      () => json(200, { ...page, items: page.items.slice(0, 5), next_cursor: 'o:5' }),
    );
    const view = render(
      <AppShell>
        <WorkItemView id="W-1705" tab="history" />
      </AppShell>,
    );
    await waitFor(() => expect(screen.getByRole('button', { name: '+ 2 earlier entries' })).toBeTruthy());
    view.unmount();
    serve(
      () => json(200, item('W-1004')),
      () => json(200, { ...history('W-1004'), next_cursor: 'o:12' }),
    );
    render(
      <AppShell>
        <WorkItemView id="W-1004" tab="history" />
      </AppShell>,
    );
    await waitFor(() => expect(screen.getByRole('button', { name: 'Show more' })).toBeTruthy());
    expect(main().querySelectorAll('.psl-badge')).toHaveLength(0);
  });
});

describe('updates (AC 19)', () => {
  beforeEach(() => {
    vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => 'visible');
    vi.useFakeTimers();
  });
  afterEach(() => vi.restoreAllMocks());
  const settle = () => act(() => vi.advanceTimersByTimeAsync(0));

  async function openFake(id: string) {
    serve(() => json(200, item(id)));
    render(
      <AppShell>
        <WorkItemView id={id} tab="overview" />
      </AppShell>,
    );
    await settle();
    await settle();
    await settle();
  }

  it('W-1703 (agent working) re-reads every 5 s', async () => {
    await openFake('W-1703');
    expect(itemUrls()).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(itemUrls()).toHaveLength(2);
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(itemUrls()).toHaveLength(3);
  });

  it.each(BOARD_IDS.filter((id) => id !== 'W-1703'))('%s never polls', async (id) => {
    await openFake(id);
    await act(() => vi.advanceTimersByTimeAsync(30000));
    expect(itemUrls()).toHaveLength(1);
  });
});
