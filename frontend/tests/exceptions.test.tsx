// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ExceptionsList } from '@/features/exceptions';
import { ExceptionsPage as ExceptionsScreen } from '@/features/exceptions/ExceptionsPage';
import type { WorkListPage, WorkListRow, WorkState } from '@/features/work-list';

import { page as basePage, row as baseRow } from './work-list-rows';

// SCR-10 All exceptions on the live work list (F-62).
vi.mock('next/navigation', () => ({ usePathname: () => '/exceptions', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const row = (id: number, over: Partial<WorkListRow> = {}) =>
  baseRow(id, { title: `Invoice INV-0${id} · Marina Bank`, state: 'awaiting_reconciliation', status_label: 'Checking whether the email was sent', owner: null, updated_at: '2026-11-23T09:02:00Z', ...over });
const page = (items: WorkListRow[], over: Partial<WorkListPage> = {}) => basePage(items, { lines: [{ key: 'finance-ledger/v1', title: 'Finance ledger' }], ...over });

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const urls = () => fetchStub.mock.calls.map(([request]) => new URL(request.url));
const serve = (answer: (url: URL) => Response | Promise<Response>) => fetchStub.mockImplementation(async (request) => answer(new URL(request.url)));
const asPhone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));

beforeEach(() => {
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

const settled = () => waitFor(() => expect(screen.queryByText('Loading exceptions…')).toBeNull());
const tableRows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1);
const titles = () => within(screen.getByRole('table')).queryAllByRole('link').map((a) => a.textContent);
const search = (text: string) => fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), { target: { value: text } });

describe('exceptions list', () => {
  it('reads queue=exceptions only: heading without a count, four columns, tag with Last updated, status_label and who acts', async () => {
    serve(() => json(200, page([row(377), row(378, { state: 'action_needed', status_label: 'A person needs to review', owner: 'Chidi Okafor' })])));
    render(<ExceptionsScreen />);
    await settled();
    expect(urls().map((u) => `${u.pathname}${u.search}`)).toEqual(['/api/v1/work?queue=exceptions&page=1']);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('All exceptions');
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search exceptions');
    expect(within(screen.getByRole('table')).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['WHAT HAPPENED', 'WORK', 'WHAT’S BEING DONE', 'WHO ACTS']);
    const [first, second] = tableRows();
    expect(within(first).getByText('Awaiting reconciliation')).toBeTruthy();
    expect(within(first).getByText('Last updated 23 Nov 10:02').getAttribute('dateTime')).toBe('2026-11-23T09:02:00Z');
    expect(within(first).getByText('Checking whether the email was sent')).toBeTruthy();
    expect(within(first).getByText('Unassigned')).toBeTruthy();
    expect(within(second).getByText('Action needed')).toBeTruthy();
    expect(within(second).getByText('Chidi Okafor')).toBeTruthy();
    expect(screen.getByText(/^The factory never resends after an unknown outcome/)).toBeTruthy();
    expect(screen.queryByText(/OPEN|since|Leads only/)).toBeNull();
    expect(screen.queryByRole('radiogroup', { name: 'Rows per page' })).toBeNull();
    expect(screen.queryByRole('table')?.textContent).not.toMatch(/INV-0\d+\s*$/);
  });

  it('every state in the queue shows its own tag and none is dropped', async () => {
    const expected: Record<WorkState, string> = {
      ready: 'Ready to continue',
      waiting: 'Waiting',
      action_needed: 'Action needed',
      owner_needed: 'Owner needed',
      setup_needed: 'Setup needed',
      verified: 'Verified',
      cancelled: 'Cancelled',
      awaiting_reconciliation: 'Awaiting reconciliation',
      followup_needed: 'Stopped: invoice follow-up needed',
      processing: 'Processing',
      effect_uncertain: 'Effect uncertain',
    };
    const states = Object.keys(expected) as WorkState[];
    serve(() => json(200, page(states.map((state, i) => row(i + 1, { state })))));
    render(<ExceptionsList />);
    await settled();
    expect(tableRows()).toHaveLength(states.length);
    tableRows().forEach((tr, i) => expect(tr.querySelector('.psl-tag')!.textContent).toBe(expected[states[i]]));
    // Effect uncertain is amber (waiting), Action needed is orange (a person acts).
    expect(tableRows()[states.indexOf('effect_uncertain')].querySelector('.psl-tag')!.className).toContain('waiting');
    expect(tableRows()[states.indexOf('action_needed')].querySelector('.psl-tag')!.className).toContain('person');
  });

  it('titles link to /work/{id} with the integer id, never to the server’s own page or api links; the case id is not shown', async () => {
    serve(() => json(200, page([row(377), row(5)])));
    render(<ExceptionsList />);
    await settled();
    const links = within(screen.getByRole('table')).getAllByRole('link');
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/work/377', '/work/5']);
    expect(document.body.textContent).not.toMatch(/7d7c0c9e/);
  });

  it('keeps the order returned', async () => {
    serve(() => json(200, page([row(9), row(2), row(5)])));
    render(<ExceptionsList />);
    await settled();
    expect(titles()).toEqual([row(9).title, row(2).title, row(5).title]);
  });

  it('coverage: as-of always; incomplete and still-being-checked lines from the server; the count says so far', async () => {
    serve(() => json(200, page([row(377)], { limited: true, next_page: 8, evaluated: 24, deferred: [{ id: 390, url: '/work/390/' }] })));
    render(<ExceptionsList />);
    await settled();
    expect(screen.getByText('As of 23 Nov 12:00')).toBeTruthy();
    expect(screen.getByText('This list may be incomplete. Some work could not be checked yet.')).toBeTruthy();
    expect(screen.getByText('1 more item is still being checked.')).toBeTruthy();
    expect(screen.getByText('1 shown so far')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\d+ of \d+|24/);
  });

  it('a complete, checked list shows only the as-of line and no more button', async () => {
    serve(() => json(200, page([row(1)])));
    render(<ExceptionsList />);
    await settled();
    expect(screen.queryByText(/incomplete|still being checked/)).toBeNull();
    expect(screen.queryByRole('button', { name: /Show more|Keep looking/ })).toBeNull();
    expect(screen.getByText('1 shown')).toBeTruthy();
  });

  it('Show more skips empty pages; after ten empty pages it reads Keep looking and the rows stay', async () => {
    serve((url) => {
      const n = Number(url.searchParams.get('page'));
      return json(200, n === 1 ? page([row(1)], { next_page: 2 }) : n === 40 ? page([row(40)], { page: 40 }) : page([], { page: n, next_page: n + 1 }));
    });
    render(<ExceptionsList />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await screen.findByRole('button', { name: 'Keep looking' });
    expect(titles()).toEqual([row(1).title]);
    expect(urls()).toHaveLength(11);
  });

  it('a failed Show more keeps the rows and offers Try again', async () => {
    serve((url) => (url.searchParams.get('page') === '2' ? json(500, { code: 'server_error', message: 'Boom.' }) : json(200, page([row(1)], { next_page: 2 }))));
    render(<ExceptionsList />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await screen.findByText('We couldn’t load more. The rows above are unchanged.');
    expect(titles()).toEqual([row(1).title]);
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it('empty: "No exceptions right now." with no table; a search that finds nothing says so and Clear search restarts', async () => {
    serve(() => json(200, page([])));
    const view = render(<ExceptionsList />);
    await screen.findByText('No exceptions right now.');
    expect(screen.queryByRole('table')).toBeNull();
    view.unmount();
    serve((url) => json(200, page(url.searchParams.has('q') ? [] : [row(1)])));
    render(<ExceptionsList />);
    await settled();
    search('nothing');
    await screen.findByText('No exceptions match your search.');
    expect(urls().at(-1)!.searchParams.get('q')).toBe('nothing');
    fireEvent.click(within(screen.getByRole('heading', { level: 2 }).parentElement!).getByRole('button', { name: 'Clear search' }));
    await waitFor(() => expect(titles()).toHaveLength(1));
  });

  it('the filter has the line only: choosing one sends line=<key> from page 1; there is no kind filter', async () => {
    serve(() => json(200, page([row(1)])));
    render(<ExceptionsList />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
    const dialog = screen.getByRole('dialog', { name: 'Filter' });
    expect(within(dialog).getAllByRole('group').map((g) => g.textContent)).toEqual(['LineAll linesFinance ledger']);
    expect(within(dialog).queryByRole('radio', { name: 'Effect uncertain' })).toBeNull();
    fireEvent.click(within(dialog).getByRole('radio', { name: 'Finance ledger' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Show results' }));
    await waitFor(() => expect(urls().at(-1)!.searchParams.get('line')).toBe('finance-ledger/v1'));
    expect(urls().at(-1)!.searchParams.get('page')).toBe('1');
    expect(await screen.findByRole('button', { name: 'Remove Line filter' })).toBeTruthy();
  });

  it('phone: outlined cards (tag, title link, status, owner and Last updated)', async () => {
    asPhone();
    serve(() => json(200, page([row(377), row(378, { owner: 'Chidi Okafor', sample: true })])));
    render(<ExceptionsList />);
    await settled();
    expect(screen.queryByRole('table')).toBeNull();
    const cards = within(screen.getByRole('list', { name: /Exceptions/ })).getAllByRole('listitem');
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByRole('link').getAttribute('href')).toBe('/work/377');
    expect(within(cards[0]).getByText('Awaiting reconciliation')).toBeTruthy();
    expect(within(cards[0]).getByText(/Unassigned/)).toBeTruthy();
    expect(within(cards[0]).getByText('Last updated 23 Nov 10:02')).toBeTruthy();
    expect(within(cards[1]).getByText('SAMPLE DATA')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Filter' })).toBeTruthy();
  });

  describe('errors', () => {
    it('401 shows the signed-out state with next=/exceptions', async () => {
      serve(() => json(401, { code: 'not_signed_in', message: 'Sign in.' }));
      render(<ExceptionsList />);
      await screen.findByText('You’re signed out.');
      expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fexceptions');
    });
    it('403 says the list is not open to the role, with no retry, rows or search', async () => {
      serve(() => json(403, { code: 'queue_not_open', message: 'No.' }));
      render(<ExceptionsScreen />);
      await screen.findByText('This list isn’t open to your role.');
      expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('All exceptions');
      expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
      expect(screen.queryByRole('table')).toBeNull();
      expect(screen.queryByRole('searchbox')).toBeNull();
    });
    for (const [label, answer] of [
      ['503', () => json(503, { code: 'unavailable', message: 'Down.' })],
      ['a network error', () => Promise.reject(new TypeError('Failed to fetch'))],
    ] as const) {
      it(`${label} shows the error card saying nothing was changed; Try again reloads`, async () => {
        serve(answer);
        render(<ExceptionsList />);
        await screen.findByText('ERROR · COULDN’T LOAD');
        expect(screen.getByText('We couldn’t load the exceptions. Your work is safe; nothing was changed.')).toBeTruthy();
        serve(() => json(200, page([row(1)])));
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
        await settled();
        expect(titles()).toHaveLength(1);
      });
    }
  });

  it('no writes and no old exceptions call; the only buttons narrow or page the list', async () => {
    serve(() => json(200, page([row(1)], { next_page: 2 })));
    render(<ExceptionsList />);
    await settled();
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Filter', 'Show more']);
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(urls()).toHaveLength(2));
    expect(fetchStub.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
    expect(urls().every((u) => u.pathname === '/api/v1/work')).toBe(true);
  });
});
