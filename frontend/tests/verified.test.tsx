// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { VerifiedPage } from '@/features/verified/VerifiedPage';

import { page, row } from './work-list-rows';

// SCR-14 Verified outputs on the live work list (F-62).
vi.mock('next/navigation', () => ({ usePathname: () => '/verified', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const urls = () => fetchStub.mock.calls.map(([request]) => new URL(request.url));
const serve = (answer: (url: URL) => Response | Promise<Response>) => fetchStub.mockImplementation(async (request) => answer(new URL(request.url)));
const asPhone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));

beforeEach(() => {
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

const settled = () => waitFor(() => expect(screen.queryByText('Loading verified outputs…')).toBeNull());
const search = (text: string) => fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), { target: { value: text } });
const rowLinks = () => within(screen.getByRole('table')).getAllByRole('link');

describe('verified outputs', () => {
  it('reads queue=verified only, and draws the columns, line titles, owner, Last updated and no "Verified at"', async () => {
    serve(() => json(200, page([row(412), row(413, { owner: null, sample: true, line: 'pmo-minutes/v1' })])));
    render(<VerifiedPage />);
    await settled();
    expect(urls().map((u) => `${u.pathname}${u.search}`)).toEqual(['/api/v1/work?queue=verified&page=1']);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Verified outputs');
    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['OUTPUT', 'LINE', 'OWNER', 'LAST UPDATED', 'Actions']);
    const [first, second] = within(table).getAllByRole('row').slice(1);
    expect(within(first).getByText('Finance ledger')).toBeTruthy();
    expect(within(first).getByText('Chidi Okafor')).toBeTruthy();
    expect(within(first).getByText('23 Nov 11:20').getAttribute('dateTime')).toBe('2026-11-23T10:20:00Z');
    expect(within(second).getByText('PMO minutes')).toBeTruthy();
    expect(within(second).getByText('Unassigned')).toBeTruthy();
    expect(within(second).getByText('SAMPLE DATA')).toBeTruthy();
    expect(within(first).queryByText('SAMPLE DATA')).toBeNull();
    expect(document.body.textContent).not.toMatch(/Verified at/);
    expect(screen.queryByText(/Facts earned|Proof|This month/)).toBeNull();
    expect(screen.queryByRole('radiogroup', { name: 'Rows per page' })).toBeNull();
  });

  it('a line key the response does not list shows as received', async () => {
    serve(() => json(200, page([row(1, { line: 'pmo-weekly-report/v1' })])));
    render(<VerifiedPage />);
    await settled();
    expect(within(screen.getByRole('table')).getByText('pmo-weekly-report/v1')).toBeTruthy();
  });

  it('titles link to /work/{id} with the integer id, never to the server’s own page or api links', async () => {
    serve(() => json(200, page([row(412), row(413)])));
    render(<VerifiedPage />);
    await settled();
    expect(rowLinks().map((a) => a.getAttribute('href'))).toEqual(['/work/412', '/work/413']);
  });

  it('keeps the server order and shows only the as-of line when the list is complete and checked', async () => {
    serve(() => json(200, page([row(9), row(3), row(7)])));
    render(<VerifiedPage />);
    await settled();
    expect(rowLinks().map((a) => a.getAttribute('href'))).toEqual(['/work/9', '/work/3', '/work/7']);
    expect(screen.getByText('As of 23 Nov 12:00')).toBeTruthy();
    expect(screen.queryByText(/may be incomplete|still being checked/)).toBeNull();
    expect(screen.getByText('3 shown')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Show more|Keep looking/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/\d+ of \d+|\b0 shown|\b0 items/);
  });

  it('coverage: limited and deferred lines show, with "so far" while more pages exist', async () => {
    serve(() => json(200, page([row(1)], { limited: true, next_page: 2, deferred: [{ id: 5, url: '/work/5/' }], evaluated: 24 })));
    render(<VerifiedPage />);
    await settled();
    expect(screen.getByText('This list may be incomplete. Some work could not be checked yet.')).toBeTruthy();
    expect(screen.getByText('1 more item is still being checked.')).toBeTruthy();
    expect(screen.getByText('1 shown so far')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/24/);
  });

  it('Show more skips an empty page and adds the rows of the next one', async () => {
    serve((url) => {
      const n = Number(url.searchParams.get('page'));
      return json(200, n === 1 ? page([row(1)], { next_page: 2 }) : n === 2 ? page([], { page: 2, next_page: 3 }) : page([row(30)], { page: 3 }));
    });
    render(<VerifiedPage />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(rowLinks()).toHaveLength(2));
    expect(urls().map((u) => u.searchParams.get('page'))).toEqual(['1', '2', '3']);
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('empty: no rows and no next page says so; with a search it says nothing matches and Clear search brings the list back', async () => {
    serve((url) => json(200, page(url.searchParams.has('q') ? [] : [row(1)])));
    render(<VerifiedPage />);
    await settled();
    search('zzz');
    await screen.findByText('No verified outputs match your search.');
    expect(urls().at(-1)!.searchParams.get('q')).toBe('zzz');
    fireEvent.click(within(screen.getByRole('heading', { level: 2 }).parentElement!).getByRole('button', { name: 'Clear search' }));
    await waitFor(() => expect(rowLinks()).toHaveLength(1));
    expect((screen.getByRole('searchbox', { name: 'Search' }) as HTMLInputElement).value).toBe('');
  });

  it('empty with nothing narrowing it: "Nothing has been verified yet." and no table; an empty first page with a next page is not empty', async () => {
    serve(() => json(200, page([])));
    const view = render(<VerifiedPage />);
    await screen.findByText('Nothing has been verified yet.');
    expect(screen.queryByRole('table')).toBeNull();
    view.unmount();
    serve((url) => json(200, Number(url.searchParams.get('page')) === 1 ? page([], { next_page: 2 }) : page([row(2)], { page: 2 })));
    render(<VerifiedPage />);
    await waitFor(() => expect(rowLinks()).toHaveLength(1));
    expect(screen.queryByText('Nothing has been verified yet.')).toBeNull();
  });

  it('the line filter sends line=<key> from page 1 and shows a removable chip', async () => {
    serve(() => json(200, page([row(1)])));
    render(<VerifiedPage />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
    const dialog = screen.getByRole('dialog', { name: 'Filter' });
    fireEvent.click(within(dialog).getByRole('radio', { name: 'PMO minutes' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Show results' }));
    await waitFor(() => expect(urls().at(-1)!.searchParams.get('line')).toBe('pmo-minutes/v1'));
    expect(urls().at(-1)!.searchParams.get('page')).toBe('1');
    await settled();
    expect(screen.getByRole('button', { name: 'Remove Line filter' })).toBeTruthy();
  });

  describe('Open output', () => {
    const open = vi.fn();
    beforeEach(() => {
      open.mockReset();
      vi.stubGlobal('open', open);
    });
    const press = (title: string) => {
      const tr = screen.getByRole('link', { name: title }).closest('tr')!;
      fireEvent.click(within(tr).getByRole('button', { name: 'Open output' }));
      return tr;
    };

    it('reads that one item and opens output_url in a new tab with noopener noreferrer; no other row changes', async () => {
      serve((url) => (url.pathname === '/api/v1/work/412' ? json(200, { ...row(412), output_url: 'https://files.example/inv-0412.pdf', blocker: null, next_step: null }) : json(200, page([row(412), row(413)]))));
      render(<VerifiedPage />);
      await settled();
      press('Invoice INV-0412 · Lagoon Health');
      await waitFor(() => expect(open).toHaveBeenCalledWith('https://files.example/inv-0412.pdf', '_blank', 'noopener,noreferrer'));
      expect(urls().filter((u) => u.pathname.startsWith('/api/v1/work/'))).toHaveLength(1);
      expect(screen.queryByRole('status')).toBeNull();
    });

    it('a null output_url shows the note on that row only', async () => {
      serve((url) => (url.pathname === '/api/v1/work/413' ? json(200, { ...row(413), output_url: null, blocker: null, next_step: null }) : json(200, page([row(412), row(413)]))));
      render(<VerifiedPage />);
      await settled();
      const tr = press('Invoice INV-0413 · Lagoon Health');
      await within(tr).findByText('No output file is attached to this item yet. Open the item to see its records.');
      expect(open).not.toHaveBeenCalled();
      expect(screen.getAllByRole('status')).toHaveLength(1);
    });

    it('a failed read shows the retry message on that row; the rest of the list is unchanged; pressing again retries', async () => {
      let fail = true;
      serve((url) => {
        if (url.pathname === '/api/v1/work/412') return fail ? json(500, { code: 'server_error', message: 'Boom.' }) : json(200, { ...row(412), output_url: '/outputs/412.pdf', blocker: null, next_step: null });
        return json(200, page([row(412), row(413)]));
      });
      render(<VerifiedPage />);
      await settled();
      const tr = press('Invoice INV-0412 · Lagoon Health');
      await within(tr).findByText('We couldn’t open the output. Try again.');
      expect(rowLinks()).toHaveLength(2);
      fail = false;
      press('Invoice INV-0412 · Lagoon Health');
      await waitFor(() => expect(open).toHaveBeenCalledTimes(1));
      expect(open.mock.calls[0][0]).toBe(`${window.location.origin}/outputs/412.pdf`);
    });

    it('refuses an address that is not http or https', async () => {
      serve((url) => (url.pathname === '/api/v1/work/412' ? json(200, { ...row(412), output_url: 'javascript:alert(1)', blocker: null, next_step: null }) : json(200, page([row(412)]))));
      render(<VerifiedPage />);
      await settled();
      const tr = press('Invoice INV-0412 · Lagoon Health');
      await within(tr).findByText('We couldn’t open the output. Try again.');
      expect(open).not.toHaveBeenCalled();
    });
  });

  it('phone: outlined cards with the title link, Open output and no table', async () => {
    asPhone();
    serve(() => json(200, page([row(412), row(413, { owner: null })])));
    render(<VerifiedPage />);
    await settled();
    expect(screen.queryByRole('table')).toBeNull();
    const cards = within(screen.getByRole('list', { name: /Verified outputs/ })).getAllByRole('listitem');
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByRole('link').getAttribute('href')).toBe('/work/412');
    expect(within(cards[0]).getByText(/Finance ledger · Chidi Okafor/)).toBeTruthy();
    expect(within(cards[1]).getByText(/Unassigned/)).toBeTruthy();
    expect(within(cards[0]).getByText('23 Nov 11:20')).toBeTruthy();
    expect(within(cards[0]).getByRole('button', { name: 'Open output' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Filter' })).toBeTruthy();
  });

  describe('errors', () => {
    it('401 shows the signed-out state with a sign-in link', async () => {
      serve(() => json(401, { code: 'not_signed_in', message: 'Sign in.' }));
      render(<VerifiedPage />);
      await screen.findByText('You’re signed out.');
      expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fverified');
    });
    it('403 says the list is not open to the role and offers no retry', async () => {
      serve(() => json(403, { code: 'queue_not_open', message: 'No.' }));
      render(<VerifiedPage />);
      await screen.findByText('This list isn’t open to your role.');
      expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    });
    it('a server failure shows the error card saying nothing was changed, and Try again reloads', async () => {
      serve(() => json(500, { code: 'server_error', message: 'Boom.' }));
      render(<VerifiedPage />);
      await screen.findByText('We couldn’t load the verified outputs. Your work is safe; nothing was changed.');
      serve(() => json(200, page([row(1)])));
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
      await waitFor(() => expect(rowLinks()).toHaveLength(1));
    });
  });

  it('never writes', async () => {
    serve(() => json(200, page([row(1)], { next_page: 2 })));
    render(<VerifiedPage />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(urls()).toHaveLength(2));
    expect(fetchStub.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
  });
});
