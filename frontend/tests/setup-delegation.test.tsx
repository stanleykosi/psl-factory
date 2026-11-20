// @vitest-environment jsdom
// F-27 Setup delegation: the list as returned, the add control only on can_add, From/To/Authority only from the
// backend's lists, the E-DELEGATION request, every outcome (200, 422, 409, 401, 403/404, uncertain with an unchanged or
// moved revision, a failed re-read), double submit, paging, empty, view-only and the phone sheet. fetch is stubbed and
// records every call; fixtures are the mock's.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { DelegationRow, DelegationsPage } from '@/features/setup/contract-proposal';
import { CHANGED, CHOOSE_FROM_FIRST, NOTE, TO_HINT } from '@/features/setup/DelegationForm';
import { DelegationPageView } from '@/features/setup/DelegationView';
import { dateRange } from '@/features/setup/format';
import { AppShell } from '@/shell/AppShell';
import { bellFeed, isBellFeed } from './bell-feed';

const pathname = { value: '/setup/delegation' };
vi.mock('next/navigation', () => ({
  usePathname: () => pathname.value,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const mockDir = join(__dirname, '../mock');
const read = <T,>(path: string): T => JSON.parse(readFileSync(join(mockDir, path), 'utf8')) as T;
const fixture = (name: string): DelegationsPage => read(`fixtures/delegations/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const BOOM = { code: 'server_error', message: 'Something broke.' };
const STALE_TEXT = 'This changed while you were working. The list has been reloaded; check it and add again.';
const NOT_ADDED = 'It was not added. You can add it again.';

type Call = { method: string; path: string; query: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = (n: number, call: Call) => Response | Promise<Response>;
let calls: Call[];
let answers: { me: () => Response; list: Answer; put: Answer };

const lists = () => calls.filter((c) => c.method === 'GET' && c.path === '/api/v1/setup/delegations');
const puts = () => calls.filter((c) => c.method === 'PUT');

const NEW_ROW: DelegationRow = {
  delegation_id: 'DL-9001',
  from: { name: 'Kemi Adebayo', role: 'PMO Lead' },
  delegate: { name: 'Femi Ade', role: 'PMO Lead' },
  starts: '2026-12-01',
  ends: '2026-12-03',
  reason: 'Training',
  status: 'scheduled',
};

/** A list that follows the writes as the backend would: a write appends NEW_ROW and bumps the revision. */
function live(start: DelegationsPage, reply: (page: DelegationsPage) => Response = (page) => json(200, { revision: page.revision, delegation_id: 'DL-9001' })) {
  const page = structuredClone(start);
  return {
    list: () => json(200, page),
    put: () => {
      page.items.push(NEW_ROW);
      page.revision = (page.revision ?? 0) + 1;
      return reply(page);
    },
    page,
  };
}

const meWith = (persona: string, patch: Record<string, unknown> = {}) => () => json(200, { ...read<Record<string, unknown>>(`fixtures/me.${persona}.json`), ...patch });

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-11-16T09:00:00+01:00') });
  pathname.value = '/setup/delegation';
  calls = [];
  const start = live(fixture('default'));
  answers = { me: meWith('admin'), list: start.list, put: start.put };
  const n = { list: 0, put: 0 };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const c: Call = { method: request.method, path: url.pathname, query: url.search, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') };
      calls.push(c);
      if (url.pathname === '/api/v1/me') return answers.me();
      if (request.method === 'PUT') return answers.put(n.put++, c);
      return answers.list(n.list++, c);
    }),
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function serveList(page: DelegationsPage) {
  const l = live(page);
  answers.list = l.list;
  answers.put = l.put;
  return l;
}

async function open() {
  render(
    <AppShell>
      <DelegationPageView />
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
const desktop = () => within(document.querySelector('.setup-desktop') as HTMLElement);
const phone = () => within(document.querySelector('.setup-phone') as HTMLElement);
const panel = () => within(screen.getByRole('complementary', { name: 'Add a delegation' }));
const announced = () => document.querySelector('[aria-live="polite"]:not(.psl-showmore__count)')?.textContent;
const rows = () =>
  desktop()
    .getAllByRole('row')
    .slice(1)
    .map((tr) => Array.from(tr.querySelectorAll('td')).map((td) => td.textContent));
const combo = (scope: ReturnType<typeof panel>, name: string) => scope.getByRole('combobox', { name }) as HTMLButtonElement;
const optionsOf = (scope: ReturnType<typeof panel>, name: string) => {
  fireEvent.click(combo(scope, name));
  const found = screen.getAllByRole('option').map((o) => [o.textContent, o.getAttribute('aria-selected')]);
  fireEvent.click(combo(scope, name));
  return found;
};
function pick(scope: ReturnType<typeof panel>, name: string, option: string) {
  fireEvent.click(combo(scope, name));
  fireEvent.click(screen.getByRole('option', { name: option }));
}
function typeDate(scope: ReturnType<typeof panel>, label: string, text: string) {
  const input = scope.getByLabelText(label);
  fireEvent.change(input, { target: { value: text } });
  fireEvent.blur(input);
}
function fill(scope = panel(), entries: { from?: string; to?: string; starts?: string; ends?: string; reason?: string } = {}) {
  const e = { from: 'Kemi Adebayo · PMO Lead', to: 'Femi Ade · PMO Lead', starts: '01 Dec 2026', ends: '03 Dec 2026', reason: 'Training', ...entries };
  if (e.from) pick(scope, 'From', e.from);
  if (e.to) pick(scope, 'To', e.to);
  if (e.starts) typeDate(scope, 'Starts', e.starts);
  if (e.ends) typeDate(scope, 'Ends', e.ends);
  if (e.reason !== undefined) fireEvent.change(scope.getByLabelText('Reason'), { target: { value: e.reason } });
}
const addButton = (scope = panel()) => scope.getByRole('button', { name: /^Add delegation$|^Adding…$/ }) as HTMLButtonElement;
const send = async (scope = panel()) => {
  await act(async () => {
    fireEvent.click(addButton(scope));
  });
};

describe('the list (AC 3)', () => {
  it('desktop: FROM, TO, DATES, REASON, STATE as returned; phone: from → to, the role, dates and reason line and the tag', async () => {
    await open();
    expect(desktop().getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['FROM', 'TO', 'DATES', 'REASON', 'STATE']);
    expect(rows()).toEqual([
      ['Kemi Adebayo · PMO Lead', 'Femi Ade · PMO Lead', '18–25 Nov 2026', 'Annual leave', 'Upcoming'],
      ['Ada Okafor · Finance Lead', 'Chika Obi · Finance Lead', '02–04 Nov 2026', 'Conference', 'Ended'],
    ]);
    const cards = phone().getAllByRole('listitem');
    expect(cards.map((li) => Array.from(li.children).map((c) => c.textContent))).toEqual([
      ['Kemi Adebayo → Femi Ade', 'PMO Lead · 18–25 Nov 2026 · Annual leave', 'Upcoming'],
      ['Ada Okafor → Chika Obi', 'Finance Lead · 02–04 Nov 2026 · Conference', 'Ended'],
    ]);
    expect(phone().getByRole('heading', { level: 1 }).textContent).toBe('Delegation');
    expect(desktop().getByRole('heading', { level: 1 }).textContent).toBe('Roles, rules and delegation');
  });

  it('a missing end is Unknown; a missing reason or role draws nothing; status only from status (a past scheduled row stays Upcoming)', async () => {
    const page = fixture('default');
    page.items = [
      { delegation_id: 'DL-1', from: { name: 'Kemi Adebayo' }, delegate: { name: 'Femi Ade' }, starts: '2026-01-05', status: 'scheduled' },
      { delegation_id: 'DL-2', from: { name: 'Ada Okafor', role: 'Finance Lead' }, delegate: { name: 'Chika Obi' }, starts: '2026-11-10', ends: '2026-11-20', status: 'active' },
    ];
    serveList(page);
    await open();
    expect(rows()).toEqual([
      ['Kemi Adebayo', 'Femi Ade', '05 Jan 2026 – Unknown', '', 'Upcoming'],
      ['Ada Okafor · Finance Lead', 'Chika Obi', '10–20 Nov 2026', '', 'Active'],
    ]);
    expect(desktop().getByText('Unknown').className).toContain('psl-unknown');
    expect(phone().getAllByRole('listitem').map((li) => li.children[1].textContent)).toEqual(['05 Jan 2026 – Unknown', 'Finance Lead · 10–20 Nov 2026']);
  });

  it('writes ranges across months and years as the board does', () => {
    expect(dateRange('2026-11-28', '2026-12-03')).toBe('28 Nov – 03 Dec 2026');
    expect(dateRange('2026-12-28', '2027-01-03')).toBe('28 Dec 2026 – 03 Jan 2027');
    expect(dateRange('2026-11-02', '2026-11-02')).toBe('02–02 Nov 2026');
  });

  it('empty: the empty sentence, and the add panel still shows with can_add', async () => {
    serveList(fixture('empty'));
    await open();
    expect(desktop().getByText('No delegations to show.')).toBeTruthy();
    expect(desktop().queryByRole('table')).toBeNull();
    expect(panel().getByRole('button', { name: 'Add delegation' })).toBeTruthy();
  });

  it('pages: 10 rows, Show more appends 10, 10, 10 then 5 by cursor and says the end; a failed page keeps the rows with the problem', async () => {
    const all = fixture('many');
    const pageAt = (offset: number, size: number) => {
      const body: DelegationsPage = { ...all, items: all.items.slice(offset, offset + size) };
      if (offset + size < all.items.length) body.next_cursor = `o:${offset + size}`;
      else delete body.next_cursor;
      return body;
    };
    let failNext = false;
    answers.list = (_, c) => {
      if (failNext) {
        failNext = false;
        return json(500, BOOM);
      }
      const m = /cursor=o%3A(\d+)/.exec(c.query);
      return json(200, pageAt(m ? Number(m[1]) : 0, 10));
    };
    await open();
    expect(rows()).toHaveLength(10);
    failNext = true;
    fireEvent.click(desktop().getByRole('button', { name: /Show more/ }));
    await waitFor(() => expect(desktop().getByText('We couldn’t load more. Choose Show more to try again.')).toBeTruthy());
    expect(rows()).toHaveLength(10);
    fireEvent.click(desktop().getByRole('button', { name: /Show more/ }));
    await waitFor(() => expect(rows()).toHaveLength(20));
    fireEvent.click(desktop().getByRole('button', { name: /Show more/ }));
    await waitFor(() => expect(rows()).toHaveLength(30));
    fireEvent.click(desktop().getByRole('button', { name: /Show more/ }));
    await waitFor(() => expect(rows()).toHaveLength(40));
    fireEvent.click(desktop().getByRole('button', { name: /Show more/ }));
    await waitFor(() => expect(rows()).toHaveLength(45));
    expect(desktop().getByText('All 45 delegations are shown.')).toBeTruthy();
    expect(lists().map((c) => c.query)).toEqual(['?limit=10', '?limit=10&cursor=o%3A10', '?limit=10&cursor=o%3A10', '?limit=10&cursor=o%3A20', '?limit=10&cursor=o%3A30', '?limit=10&cursor=o%3A40']);
    expect(desktop().getAllByText('Unknown')).toHaveLength(1);
  });
});

describe('the add control follows the response only (AC 4, 5)', () => {
  it('readonly (no can_add), can_add false and a read without revision show no panel, no phone button and no placeholder', async () => {
    for (const page of [fixture('readonly'), { ...fixture('default'), can_add: false }, { ...fixture('default'), revision: undefined }]) {
      serveList(page);
      const view = render(
        <AppShell>
          <DelegationPageView />
        </AppShell>,
      );
      await waitFor(() => expect(desktop().getByRole('table')).toBeTruthy());
      expect(screen.queryByRole('complementary', { name: 'Add a delegation' })).toBeNull();
      expect(screen.queryByRole('button', { name: /Add delegation/ })).toBeNull();
      expect(screen.queryByText(NOTE)).toBeNull();
      view.unmount();
    }
  });

  it('admin, finance_lead and ceo with the same fixture get the same controls; /me roles are not read', async () => {
    const seen: string[] = [];
    for (const persona of ['admin', 'finance_lead', 'ceo']) {
      answers.me = meWith(persona, { destinations: ['my_work', 'setup'], roles: ['Somebody'] });
      const view = render(
        <AppShell>
          <DelegationPageView />
        </AppShell>,
      );
      await waitFor(() => expect(panel().getByRole('button', { name: 'Add delegation' })).toBeTruthy());
      seen.push(optionsOf(panel(), 'From').map(([label]) => label).join('|'));
      view.unmount();
    }
    expect(new Set(seen).size).toBe(1);
  });

  it('From, To offer exactly the backend options in order with none chosen; an option added to the DOM sends nothing', async () => {
    await open();
    expect(optionsOf(panel(), 'From')).toEqual([
      ['Kemi Adebayo · PMO Lead', 'false'],
      ['Ada Okafor · Finance Lead', 'false'],
    ]);
    expect(combo(panel(), 'From').textContent).toContain('Choose who is delegating');
    pick(panel(), 'From', 'Kemi Adebayo · PMO Lead');
    expect(optionsOf(panel(), 'To')).toEqual([['Femi Ade · PMO Lead', 'false']]);
    // An option planted in the open list has no handler and no value: choosing it changes nothing.
    fireEvent.click(combo(panel(), 'To'));
    const planted = document.createElement('li');
    planted.setAttribute('role', 'option');
    planted.textContent = 'Someone Else · CEO';
    screen.getByRole('listbox').appendChild(planted);
    fireEvent.click(planted);
    fireEvent.keyDown(combo(panel(), 'To'), { key: 'Escape' });
    fill(panel(), { from: '', to: '' });
    await send();
    expect(puts()).toHaveLength(0);
    expect(panel().getByText('Choose who to delegate to.')).toBeTruthy();
  });

  it('a chosen delegate the next read no longer lists is not sent', async () => {
    const l = serveList(fixture('default'));
    await open();
    fill();
    l.page.delegate_options = l.page.delegate_options!.filter((o) => o.person_id !== 'P-FEMI');
    l.page.revision = 5;
    answers.put = () => json(409, { code: 'stale_revision', message: 'Changed.' });
    await send();
    await waitFor(() => expect(panel().getByText(STALE_TEXT)).toBeTruthy());
    await send();
    expect(puts()).toHaveLength(1);
    expect(panel().getByText('Choose who to delegate to.')).toBeTruthy();
  });
});

describe('From, To and Authority (AC 6, 7, 8)', () => {
  it('default: From is a Select and its person_id is sent; To waits for From, pairs exactly and clears when From changes', async () => {
    await open();
    expect(combo(panel(), 'To').disabled).toBe(true);
    expect(panel().getByText(CHOOSE_FROM_FIRST)).toBeTruthy();
    expect(panel().getByText(TO_HINT)).toBeTruthy();
    pick(panel(), 'From', 'Ada Okafor · Finance Lead');
    expect(optionsOf(panel(), 'To').map(([l]) => l)).toEqual(['Chika Obi · Finance Lead']);
    pick(panel(), 'To', 'Chika Obi · Finance Lead');
    pick(panel(), 'From', 'Kemi Adebayo · PMO Lead');
    expect(combo(panel(), 'To').textContent).toContain('Choose a delegate');
    expect(optionsOf(panel(), 'To').map(([l]) => l)).toEqual(['Femi Ade · PMO Lead']);
    fill(panel(), { from: '' });
    await send();
    expect(puts()).toHaveLength(1);
    expect(puts()[0].body).toMatchObject({ from_person_id: 'P-KEMI', delegate: 'P-FEMI' });
    expect(puts()[0].body).not.toHaveProperty('authority');
    expect(panel().queryByRole('combobox', { name: 'Authority' })).toBeNull();
  });

  it('single: From reads You with no control and no from_person_id; To lists every option; the one authority is a line and is sent', async () => {
    serveList(fixture('single'));
    await open();
    expect(panel().queryByRole('combobox', { name: 'From' })).toBeNull();
    expect(panel().getByText('You')).toBeTruthy();
    expect(optionsOf(panel(), 'To').map(([l]) => l)).toEqual(['Femi Ade · PMO Lead', 'Chika Obi · Finance Lead']);
    expect(panel().getByText('Authority: Approve milestones')).toBeTruthy();
    fill(panel(), { from: '', to: 'Chika Obi · Finance Lead' });
    await send();
    expect(puts()[0].body).toEqual({ expected_revision: 1, delegate: 'P-CHIKA', starts: '2026-12-01', ends: '2026-12-03', authority: 'approve_milestones', reason: 'Training' });
  });

  it('authority: the one From is text and is sent as from_person_id (SEC-1-1); To lists only its paired delegate; Authority is a required Select with no default; rows show the label, else the raw value', async () => {
    serveList(fixture('authority'));
    await open();
    expect(panel().queryByRole('combobox', { name: 'From' })).toBeNull();
    expect(panel().getByText('Kemi Adebayo · PMO Lead')).toBeTruthy();
    // Chika is offered unpaired (the caller's option), so with Kemi shown as From only Femi is listed.
    expect(optionsOf(panel(), 'To').map(([l]) => l)).toEqual(['Femi Ade · PMO Lead']);
    expect(optionsOf(panel(), 'Authority')).toEqual([
      ['Approve milestones', 'false'],
      ['Approve invoices', 'false'],
    ]);
    expect(rows().map((r) => r[3])).toEqual(['Annual leaveAuthority: Approve milestones', 'ConferenceAuthority: close_month']);
    expect(phone().getAllByRole('listitem')[0].children[1].textContent).toBe('PMO Lead · 18–25 Nov 2026 · Annual leave · Authority: Approve milestones');
    fill(panel(), { from: '' });
    await send();
    expect(puts()).toHaveLength(0);
    expect(panel().getByText('Choose an authority.')).toBeTruthy();
    pick(panel(), 'Authority', 'Approve invoices');
    await send();
    expect(puts()[0].body).toEqual({ expected_revision: 2, from_person_id: 'P-KEMI', delegate: 'P-FEMI', starts: '2026-12-01', ends: '2026-12-03', authority: 'approve_invoices', reason: 'Training' });
  });

  it('pairing keys without a From list (SEC-1-2): From reads You and To lists only the unpaired options', async () => {
    const page = fixture('single');
    page.delegate_options = [
      { person_id: 'P-FEMI', name: 'Femi Ade', role: 'PMO Lead', for_person_id: 'P-KEMI' },
      { person_id: 'P-CHIKA', name: 'Chika Obi', role: 'Finance Lead' },
    ];
    serveList(page);
    await open();
    expect(panel().getByText('You')).toBeTruthy();
    expect(combo(panel(), 'To').disabled).toBe(false);
    expect(optionsOf(panel(), 'To').map(([l]) => l)).toEqual(['Chika Obi · Finance Lead']);
    fill(panel(), { from: '', to: 'Chika Obi · Finance Lead' });
    await send();
    expect(puts()[0].body).not.toHaveProperty('from_person_id');
    expect(puts()[0].body!.delegate).toBe('P-CHIKA');
  });
});

describe('the request and its checks (AC 9, 10)', () => {
  it('sends one PUT with the CSRF header and exactly the body keys; a double click sends one; a blank reason is left out', async () => {
    await open();
    fill(panel(), { reason: '   ' });
    await act(async () => {
      fireEvent.click(addButton());
      fireEvent.click(addButton());
    });
    await waitFor(() => expect(lists()).toHaveLength(2));
    expect(puts()).toHaveLength(1);
    expect(puts()[0].path).toBe('/api/v1/setup/delegation');
    expect(puts()[0].csrf).toBe('mock-csrf-admin');
    expect(puts()[0].body).toEqual({ expected_revision: 2, from_person_id: 'P-KEMI', delegate: 'P-FEMI', starts: '2026-12-01', ends: '2026-12-03' });
  });

  it('trims the reason', async () => {
    await open();
    fill(panel(), { reason: '  Annual leave  ' });
    await send();
    expect(puts()[0].body!.reason).toBe('Annual leave');
  });

  it('missing To, a date that is not a date, and Ends before Starts show under the field and send nothing; a past Starts is sent', async () => {
    await open();
    fill(panel(), { to: '', starts: '31/02/2026', ends: '' });
    await send();
    expect(puts()).toHaveLength(0);
    expect(panel().getByText('Choose who to delegate to.')).toBeTruthy();
    expect(panel().getByText('Enter the start date, for example 18 Nov 2026.')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(combo(panel(), 'To')));
    expect(combo(panel(), 'To').getAttribute('aria-invalid')).toBe('true');
    pick(panel(), 'To', 'Femi Ade · PMO Lead');
    typeDate(panel(), 'Starts', '10 Nov 2026');
    typeDate(panel(), 'Ends', '09 Nov 2026');
    await send();
    expect(puts()).toHaveLength(0);
    expect(panel().getByText("Ends can't be before Starts.")).toBeTruthy();
    expect(panel().getByLabelText('Ends').getAttribute('aria-invalid')).toBe('true');
    typeDate(panel(), 'Starts', '01 Jan 2020');
    typeDate(panel(), 'Ends', '02 Jan 2020');
    await send();
    expect(puts()).toHaveLength(1);
    expect(puts()[0].body).toMatchObject({ starts: '2020-01-01', ends: '2020-01-02' });
  });
});

describe('outcomes (AC 11 to 15)', () => {
  it('200: re-reads, the row comes from the re-read, the notice is announced, focus moves to the row, the form clears; nothing claims an effect', async () => {
    await open();
    fill();
    await send();
    await waitFor(() => expect(rows()).toHaveLength(3));
    expect(lists()).toHaveLength(2);
    expect(rows()[2]).toEqual(['Kemi Adebayo · PMO Lead', 'Femi Ade · PMO Lead', '01–03 Dec 2026', 'Training', 'Upcoming']);
    expect(announced()).toBe('Delegation added: Kemi Adebayo to Femi Ade, 01–03 Dec 2026.');
    await waitFor(() => expect(document.activeElement?.querySelector('[data-row-for]')?.getAttribute('data-row-for')).toBe('DL-9001'));
    await waitFor(() => expect(document.activeElement?.tagName).toBe('TR'));
    expect(combo(panel(), 'From').textContent).toContain('Choose who is delegating');
    expect((panel().getByLabelText('Reason') as HTMLInputElement).value).toBe('');
    const text = document.body.textContent!.replace(NOTE, '').replace(TO_HINT, '');
    expect(text).not.toMatch(/can now|now able|has been given|granted|approve|in force|agent/i);
  });

  it('200 without delegation_id: the row still comes only from the re-read and focus goes to the list heading', async () => {
    const l = live(fixture('default'), (page) => json(200, { revision: page.revision }));
    answers.list = l.list;
    answers.put = l.put;
    await open();
    fill();
    await send();
    await waitFor(() => expect(rows()).toHaveLength(3));
    expect(announced()).toBe('Delegation added: Kemi Adebayo to Femi Ade, 01–03 Dec 2026.');
    await waitFor(() => expect(document.activeElement?.hasAttribute('data-list-head')).toBe(true));
  });

  it('200 whose body names a row the re-read lacks: nothing is drawn from the body', async () => {
    answers.put = () => json(200, { revision: 3, delegation_id: 'DL-NOT-LISTED' });
    await open();
    fill();
    await send();
    await waitFor(() => expect(lists()).toHaveLength(2));
    expect(rows()).toHaveLength(2);
    expect(document.body.textContent).not.toContain('DL-NOT-LISTED');
  });

  it('422: the top message, the messages under To and Ends, focus to To, entries kept, no re-read', async () => {
    answers.put = () =>
      json(422, {
        code: 'invalid',
        message: 'Check these fields: delegate, ends.',
        fields: [
          { name: 'ends', message: 'Choose an end date within the next 90 days.' },
          { name: 'delegate', message: 'This person can’t take this delegation.' },
        ],
      });
    await open();
    fill();
    await send();
    // The top message names the fields by their visible labels (UX-1-1), in form order.
    await waitFor(() => expect(panel().getByText('Check these fields: To, Ends.')).toBeTruthy());
    expect(panel().queryByText(/delegate, ends/)).toBeNull();
    expect(panel().getByText('This person can’t take this delegation.')).toBeTruthy();
    expect(panel().getByText('Choose an end date within the next 90 days.')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(combo(panel(), 'To')));
    expect(combo(panel(), 'To').textContent).toContain('Femi Ade · PMO Lead');
    expect((panel().getByLabelText('Reason') as HTMLInputElement).value).toBe('Training');
    expect(lists()).toHaveLength(1);
  });

  it('422 naming a field the form lacks keeps the backend message', async () => {
    answers.put = () => json(422, { code: 'invalid', message: 'Something else is wrong.', fields: [{ name: 'expected_revision', message: 'Send the revision.' }] });
    await open();
    fill();
    await send();
    await waitFor(() => expect(panel().getByText('Something else is wrong.')).toBeTruthy());
  });

  it('409 whose re-read fails does not say the list was reloaded (TECH-1-3)', async () => {
    answers.list = (n) => (n === 0 ? json(200, fixture('default')) : json(500, BOOM));
    answers.put = () => json(409, { code: 'stale_revision', message: 'Changed.' });
    await open();
    fill();
    await send();
    await waitFor(() => expect(panel().getByText(/we couldn’t reload the list/)).toBeTruthy());
    expect(panel().queryByText(STALE_TEXT)).toBeNull();
  });

  it('409: re-reads, the stale sentence, entries kept, the next press sends the new revision; nothing resends by itself', async () => {
    const l = serveList(fixture('default'));
    answers.put = (n) => {
      if (n === 0) {
        l.page.revision = 4;
        return json(409, { code: 'stale_revision', message: 'Changed.' });
      }
      return l.put();
    };
    await open();
    vi.useFakeTimers({ now: new Date('2026-11-16T09:00:00+01:00') });
    fill();
    await send();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(puts()).toHaveLength(1);
    expect(lists()).toHaveLength(2);
    expect(panel().getByText(STALE_TEXT)).toBeTruthy();
    expect(combo(panel(), 'To').textContent).toContain('Femi Ade · PMO Lead');
    await send();
    expect(puts()).toHaveLength(2);
    expect(puts()[1].body!.expected_revision).toBe(4);
  });

  it('uncertain, revision unchanged: never "added", then "It was not added" and Add stays enabled', async () => {
    answers.put = () => json(500, BOOM);
    await open();
    fill();
    await send();
    await waitFor(() => expect(panel().getByText(NOT_ADDED)).toBeTruthy());
    expect(lists()).toHaveLength(2);
    expect(document.body.textContent).not.toMatch(/Delegation added/);
    expect(addButton().disabled).toBe(false);
    expect(combo(panel(), 'To').textContent).toContain('Femi Ade');
  });

  it('uncertain, revision moved: the new row is listed, the warning shows, Add is held with its reason; only Start again empties and frees it', async () => {
    const l = live(fixture('default'), () => json(500, BOOM));
    answers.list = l.list;
    answers.put = l.put;
    await open();
    fill();
    await send();
    await waitFor(() => expect(panel().getByText(CHANGED)).toBeTruthy());
    expect(rows()).toHaveLength(3);
    expect(addButton().disabled).toBe(true);
    expect(panel().getByText('Check the list for your delegation, or start again.')).toBeTruthy();
    await send();
    expect(puts()).toHaveLength(1);
    expect(document.body.textContent).not.toMatch(/Delegation added/);
    fireEvent.click(panel().getByRole('button', { name: 'Start again' }));
    expect(addButton().disabled).toBe(false);
    expect(combo(panel(), 'From').textContent).toContain('Choose who is delegating');
    expect((panel().getByLabelText('Reason') as HTMLInputElement).value).toBe('');
    expect(panel().queryByText(CHANGED)).toBeNull();
  });

  it('uncertain and the re-read fails: locked; Try again only reads, then settles against the revision sent', async () => {
    const page = fixture('default');
    answers.list = (n) => (n === 1 ? json(500, BOOM) : json(200, page));
    answers.put = () => json(503, BOOM);
    await open();
    fill();
    await send();
    await waitFor(() => expect(panel().getByText(/We couldn’t check whether the delegation was added/)).toBeTruthy());
    expect(addButton().disabled).toBe(true);
    await act(async () => {
      fireEvent.click(panel().getByRole('button', { name: 'Try again' }));
    });
    await waitFor(() => expect(panel().getByText(NOT_ADDED)).toBeTruthy());
    expect(puts()).toHaveLength(1);
    expect(lists()).toHaveLength(3);
    expect(addButton().disabled).toBe(false);
  });

  it('a network failure is uncertain too', async () => {
    answers.put = () => {
      throw new TypeError('fetch failed');
    };
    await open();
    fill();
    await send();
    await waitFor(() => expect(panel().getByText(NOT_ADDED)).toBeTruthy());
  });
});

describe('access (AC 15)', () => {
  it('401 on the read: signed out with next=/setup/delegation', async () => {
    answers.list = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fsetup%2Fdelegation'));
  });

  it('401 on the write: signed out', async () => {
    answers.put = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    fill();
    await send();
    await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fsetup%2Fdelegation'));
  });

  it('403 or 404 on the read: the not-open view, no names, no further call', async () => {
    for (const status of [403, 404]) {
      calls = [];
      answers.list = () => json(status, status === 403 ? FORBIDDEN : { code: 'not_found', message: 'Not found.' });
      const view = render(
        <AppShell>
          <DelegationPageView />
        </AppShell>,
      );
      await waitFor(() => expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy());
      expect(document.body.textContent).not.toMatch(/Kemi|Femi|Chika/);
      expect(lists()).toHaveLength(1);
      expect(puts()).toHaveLength(0);
      view.unmount();
    }
  });

  it('403 and 404 on the write: the backend message and the list re-read', async () => {
    for (const [status, body] of [
      [403, FORBIDDEN],
      [404, { code: 'not_found', message: 'We could not find that record.' }],
    ] as const) {
      calls = [];
      answers.put = () => json(status, body);
      const view = render(
        <AppShell>
          <DelegationPageView />
        </AppShell>,
      );
      await waitFor(() => expect(panel()).toBeTruthy());
      fill();
      await send();
      await waitFor(() => expect(panel().getByText(body.message)).toBeTruthy());
      expect(lists()).toHaveLength(2);
      view.unmount();
    }
  });

  it('/me without setup: no delegation call at all', async () => {
    answers.me = meWith('pm');
    render(
      <AppShell>
        <DelegationPageView />
      </AppShell>,
    );
    await waitFor(() => expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy());
    expect(lists()).toHaveLength(0);
  });
});

describe('the phone sheet (AC 17)', () => {
  it('opens "Add a delegation" with the same form; Cancel closes it and focus returns to the button; a success closes it', async () => {
    await open();
    const button = phone().getByRole('button', { name: 'Add delegation' });
    button.focus();
    fireEvent.click(button);
    const sheet = within(screen.getByRole('dialog', { name: 'Add a delegation' }));
    expect(sheet.getByText(TO_HINT)).toBeTruthy();
    expect(sheet.getByText(NOTE)).toBeTruthy();
    fireEvent.click(sheet.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(button));

    fireEvent.click(button);
    const again = within(screen.getByRole('dialog', { name: 'Add a delegation' }));
    fill(again as ReturnType<typeof panel>);
    await send(again as ReturnType<typeof panel>);
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(phone().getAllByRole('listitem')).toHaveLength(3);
    expect(puts()).toHaveLength(1);
  });

  it('the sheet keeps Add and Cancel in its footer, outside the scrolling body (UI-1-2)', async () => {
    await open();
    fireEvent.click(phone().getByRole('button', { name: 'Add delegation' }));
    const dialog = screen.getByRole('dialog', { name: 'Add a delegation' });
    const foot = dialog.querySelector('[class$="__foot"]') as HTMLElement;
    expect(within(foot).getAllByRole('button').map((b) => b.textContent)).toEqual(['Add delegation', 'Cancel']);
    expect(within(foot).queryByText(NOTE)).toBeNull();
    expect(within(dialog).getByText(NOTE)).toBeTruthy();
  });

  it('uncertain and the list moved: the sheet closes so the list can be checked, the warning shows above the cards, and reopening shows Start again (UX-1-2)', async () => {
    const l = live(fixture('default'), () => json(500, BOOM));
    answers.list = l.list;
    answers.put = l.put;
    await open();
    const button = phone().getByRole('button', { name: 'Add delegation' });
    fireEvent.click(button);
    const sheet = within(screen.getByRole('dialog', { name: 'Add a delegation' }));
    fill(sheet as ReturnType<typeof panel>);
    await send(sheet as ReturnType<typeof panel>);
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(phone().getByText(CHANGED)).toBeTruthy();
    expect(phone().getAllByRole('listitem')).toHaveLength(3);
    fireEvent.click(button);
    const again = within(screen.getByRole('dialog', { name: 'Add a delegation' }));
    expect((again.getByRole('button', { name: 'Add delegation' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(again.getByRole('button', { name: 'Start again' }));
    expect((again.getByRole('button', { name: 'Add delegation' }) as HTMLButtonElement).disabled).toBe(false);
    expect(phone().queryByText(CHANGED)).toBeNull();
    expect(puts()).toHaveLength(1);
  });
});
