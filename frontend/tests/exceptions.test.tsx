// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ExceptionsList, useExceptions } from '@/features/exceptions';
import { KIND_TAGS, sinceText } from '@/features/exceptions/labels';
import type { ExceptionKind, ExceptionRow, ExceptionsPage } from '@/features/exceptions/types';
import { ExceptionsPage as ExceptionsScreen } from '@/features/exceptions/ExceptionsPage';
import type { WorkItem, WorkState } from '@/features/work-item/labels';
import { NextStep } from '@/features/work-item/WorkItemOverview';

vi.mock('next/navigation', () => ({
  usePathname: () => '/exceptions',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const fixture = read('E-EXCEPTIONS.json') as ExceptionsPage;
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

/** The mock's paging over the fixture rows: "o:<offset>" cursors; `open_count` is the proposal total. */
function page(url: URL, rows: ExceptionRow[] = fixture.items): ExceptionsPage {
  const limit = Number(url.searchParams.get('limit') ?? 20);
  const offset = Number(/^o:(\d+)$/.exec(url.searchParams.get('cursor') ?? '')?.[1] ?? 0);
  const body: ExceptionsPage = { items: rows.slice(offset, offset + limit), as_of: fixture.as_of, open_count: rows.length };
  if (offset + limit < rows.length) body.next_cursor = `o:${offset + limit}`;
  return body;
}

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const urls = () => fetchStub.mock.calls.map(([request]) => new URL(request.url));
const serve = (answer: (url: URL) => Response | Promise<Response>) =>
  fetchStub.mockImplementation(async (request) => answer(new URL(request.url)));

beforeEach(() => {
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

async function settled() {
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
}
const rowTitles = () => within(screen.getByRole('table')).queryAllByRole('link').map((a) => a.textContent);
const search = (text: string) => {
  fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), { target: { value: text } });
  fireEvent.submit(screen.getByRole('search'));
};

describe('exceptions list', () => {
  it('full page: header, search bar with the open total, columns, 20 rows in order, references, paging bar and footer', async () => {
    serve((url) => json(200, page(url)));
    render(<ExceptionsScreen />);
    await settled();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('All exceptions');
    expect(screen.getByText(/^Everyone’s work that can’t move on by itself/)).toBeTruthy();
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search exceptions');
    expect(screen.getByRole('button', { name: 'Filter' }).getAttribute('aria-haspopup')).toBe('dialog');
    expect(screen.getByText('25 OPEN')).toBeTruthy();
    const table = screen.getByRole('table', { name: 'Exceptions, in the order the factory reports them' });
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual([
      'WHAT HAPPENED',
      'WORK',
      'WHAT’S BEING DONE',
      'WHO ACTS',
    ]);
    expect(rowTitles()).toEqual(fixture.items.slice(0, 20).map((r) => r.title));
    const first = within(table).getAllByRole('row')[1];
    expect(within(first).getByText('SEND UNCERTAIN')).toBeTruthy();
    expect(within(first).getByRole('link').getAttribute('href')).toBe('/work/W-1005');
    expect(within(first).getByText('INV-0405').className).toBe('exc-ref');
    expect(screen.getByText('Showing 20')).toBeTruthy();
    expect(screen.getByRole('radiogroup', { name: 'Rows per page' })).toBeTruthy();
    expect(screen.getByText('As of 14 Nov 11:05')).toBeTruthy();
    expect(screen.getByText(/^The factory never resends after an unknown outcome/)).toBeTruthy();
  });

  it('keeps the order returned', async () => {
    const shuffled = [fixture.items[7], fixture.items[0], fixture.items[24], fixture.items[3]];
    serve(() => json(200, { items: shuffled, as_of: fixture.as_of }));
    render(<ExceptionsList />);
    await settled();
    expect(rowTitles()).toEqual(shuffled.map((r) => r.title));
  });

  it('maps every kind', async () => {
    const kinds: ExceptionKind[] = ['effect_uncertain', 'owner_needed', 'setup_needed', 'blocked', 'followup_needed'];
    const rows = kinds.map((what, i) => ({ ...fixture.items[0], work_id: `W-${i}`, title: `Row ${what}`, what }));
    serve(() => json(200, { items: rows, as_of: fixture.as_of }));
    render(<ExceptionsList />);
    await settled();
    const expected: Record<ExceptionKind, [string, string]> = {
      effect_uncertain: ['SEND UNCERTAIN', 'psl-tag psl-tag--waiting'],
      owner_needed: ['OWNER NEEDED', 'psl-tag psl-tag--person'],
      setup_needed: ['SETUP NEEDED', 'psl-tag psl-tag--person'],
      blocked: ['BLOCKED', 'psl-tag psl-tag--person'],
      followup_needed: ['FOLLOW-UP NEEDED', 'psl-tag psl-tag--person'],
    };
    const bodyRows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    bodyRows.forEach((tr, i) => {
      const tag = tr.querySelector('.psl-tag')!;
      expect([tag.textContent, tag.className]).toEqual(expected[kinds[i]]);
    });
    expect(Object.entries(KIND_TAGS).filter(([, t]) => t.className.includes('psl-tag--waiting')).map(([k]) => k)).toEqual([
      'effect_uncertain',
    ]);
  });

  it('times: same Lagos day reads HH:mm, an earlier day reads D Mon, with formatWat in the title', async () => {
    expect(sinceText('2026-11-14T10:02:00Z', '2026-11-14T10:05:00Z')).toBe('since 11:02');
    expect(sinceText('2026-11-10T08:30:00Z', '2026-11-14T10:05:00Z')).toBe('since 10 Nov');
    // 23:30Z on the 13th is 00:30 WAT on the 14th: the same Lagos day as as_of
    expect(sinceText('2026-11-13T23:30:00Z', '2026-11-14T10:05:00Z')).toBe('since 00:30');
    const rows = [fixture.items[0], { ...fixture.items[1], since: '2026-11-10T08:30:00Z' }];
    serve(() => json(200, { items: rows, as_of: fixture.as_of }));
    render(<ExceptionsList />);
    await settled();
    const times = screen.getByRole('table').querySelectorAll('time');
    expect([...times].map((t) => [t.textContent, t.getAttribute('dateTime'), t.getAttribute('title')])).toEqual([
      ['since 11:02', '2026-11-14T10:02:00Z', '14 Nov 11:02'],
      ['since 10 Nov', '2026-11-10T08:30:00Z', '10 Nov 09:30'],
    ]);
  });

  it('paging: limit=20 first, 50 replaces the rows, Show more appends with the cursor, then disappears', async () => {
    serve((url) => json(200, page(url)));
    render(<ExceptionsList />);
    await settled();
    expect(urls().map((u) => u.search)).toEqual(['?limit=20']);
    expect(urls()[0].pathname).toBe('/api/v1/exceptions');

    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(rowTitles()).toHaveLength(25));
    expect(urls()[1].search).toBe('?limit=20&cursor=o%3A20');
    expect(rowTitles()).toEqual(fixture.items.map((r) => r.title));
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(screen.getByText('Showing 25')).toBeTruthy();

    fireEvent.click(screen.getByRole('radio', { name: '10' }));
    await waitFor(() => expect(rowTitles()).toHaveLength(10));
    expect(urls()[2].search).toBe('?limit=10');
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(rowTitles()).toHaveLength(20));
    expect(urls()[3].search).toBe('?limit=10&cursor=o%3A10');

    expect(screen.getByRole('radio', { name: '10' }).getAttribute('aria-checked')).toBe('true');
    fireEvent.click(screen.getByRole('radio', { name: '50' }));
    await waitFor(() => expect(urls()).toHaveLength(5));
    expect(urls()[4].search).toBe('?limit=50');
    await waitFor(() => expect(rowTitles()).toEqual(fixture.items.map((r) => r.title)));
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('drops an answer to a superseded request', async () => {
    let release: (r: Response) => void = () => {};
    serve((url) =>
      !url.searchParams.has('q')
        ? new Promise<Response>((resolve) => (release = resolve))
        : json(200, { items: [fixture.items[3]], as_of: fixture.as_of }),
    );
    render(<ExceptionsList />);
    search('Northwind');
    await waitFor(() => expect(rowTitles()).toEqual([fixture.items[3].title]));
    release(json(200, page(new URL('http://x/?limit=20'))));
    await new Promise((r) => setTimeout(r, 20));
    expect(rowTitles()).toEqual([fixture.items[3].title]);
  });

  it('a Show more failure keeps the rows and says so', async () => {
    serve((url) => (url.searchParams.has('cursor') ? json(500, { code: 'server_error', message: 'Boom.' }) : json(200, page(url))));
    render(<ExceptionsList />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await screen.findByText('We couldn’t load more exceptions. Choose Show more to try again.');
    expect(rowTitles()).toHaveLength(20);
    expect(screen.getByRole('button', { name: 'Show more' })).toBeTruthy();
  });

  it('a 401 on Show more shows the signed-out state', async () => {
    serve((url) => (url.searchParams.has('cursor') ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : json(200, page(url))));
    render(<ExceptionsList />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await screen.findByText('You’re signed out.');
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('empty: the empty card and As of, with no table, Show more or footer', async () => {
    serve(() => json(200, { items: [], as_of: fixture.as_of }));
    render(<ExceptionsList />);
    await settled();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('No exceptions.');
    expect(screen.getByText('Everything is moving or verified.')).toBeTruthy();
    expect(screen.getByText('As of 14 Nov 11:05')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(screen.queryByText(/The factory never resends/)).toBeNull();
    expect(screen.queryByText(/Showing|OPEN/)).toBeNull();
  });

  it('search and Filter send q and what, show the narrowed empty card, and Clear brings every row back', async () => {
    serve((url) => {
      const q = url.searchParams.get('q');
      const what = url.searchParams.get('what');
      const rows = fixture.items.filter((r) => (!q || r.title.includes(q)) && (!what || r.what === what));
      return json(200, page(url, rows));
    });
    render(<ExceptionsList />);
    await settled();
    search('Kora');
    await waitFor(() => expect(rowTitles()).toEqual(fixture.items.filter((r) => r.title.includes('Kora')).map((r) => r.title)));
    expect(urls()[1].search).toBe('?limit=20&q=Kora');

    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
    const dialog = screen.getByRole('dialog', { name: 'Filter' });
    fireEvent.click(within(dialog).getByRole('radio', { name: 'Blocked' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Show results' }));
    await screen.findByText('No exceptions match your search and filter.');
    expect(urls()[2].search).toBe('?limit=20&q=Kora&what=blocked');
    expect(screen.getByText('0 OPEN')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Remove What happened filter' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Clear search and filter' }));
    await waitFor(() => expect(rowTitles()).toHaveLength(20));
    expect(urls()[3].search).toBe('?limit=20');
    expect((screen.getByRole('searchbox', { name: 'Search' }) as HTMLInputElement).value).toBe('');
  });

  it('draws no open total or reference when the backend does not send them (unknown is not zero)', async () => {
    const rows = fixture.items.slice(0, 3).map((r) => ({ work_id: r.work_id, what: r.what, title: r.title, doing: r.doing, who_acts: r.who_acts, since: r.since }));
    serve(() => json(200, { items: rows, as_of: fixture.as_of }));
    render(<ExceptionsList />);
    await settled();
    expect(rowTitles()).toEqual(rows.map((r) => r.title));
    expect(screen.queryByText(/OPEN/)).toBeNull();
    expect(document.querySelector('.exc-ref')).toBeNull();
  });

  it('401 shows the signed-out callout with next=/exceptions', async () => {
    serve(() => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }));
    render(<ExceptionsList />);
    await screen.findByText('You’re signed out.');
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fexceptions');
  });

  for (const status of [403, 404]) {
    it(`${status} shows the no-access view with no rows, count or As of`, async () => {
      serve(() => json(status, { code: status === 403 ? 'forbidden' : 'not_found', message: 'No.' }));
      render(<ExceptionsScreen />);
      await screen.findByText('This list is for Leads');
      expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('All exceptions');
      expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('This list is for Leads');
      expect(screen.getByText('Your own exceptions appear in My work, under Needs me.')).toBeTruthy();
      expect(screen.getByRole('link', { name: 'Go to My work' }).getAttribute('href')).toBe('/my-work');
      expect(screen.queryByRole('table')).toBeNull();
      expect(screen.queryByText(/Showing|As of|OPEN/)).toBeNull();
      expect(screen.queryByRole('searchbox')).toBeNull();
      expect(screen.queryByRole('radiogroup')).toBeNull();
    });
  }

  for (const [label, answer] of [
    ['503', () => json(503, { code: 'unavailable', message: 'Down.' })],
    ['a network error', () => Promise.reject(new TypeError('Failed to fetch'))],
  ] as const) {
    it(`${label} on the first page shows the error card; Try again asks once for the first page`, async () => {
      serve(answer);
      render(<ExceptionsList />);
      await screen.findByText('ERROR · COULDN’T LOAD');
      expect(screen.getByText('We couldn’t load the exceptions. Your work is safe; nothing was changed.')).toBeTruthy();
      expect(screen.getByText(/^Reference \S+ for support\.$/)).toBeTruthy();
      serve((url) => json(200, page(url)));
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
      await settled();
      expect(urls()).toHaveLength(2);
      expect(urls()[1].search).toBe('?limit=20');
      expect(rowTitles()).toHaveLength(20);
    });
  }

  it('no actions: only title links, and controls that narrow or page the list, in the default state', async () => {
    serve((url) => json(200, page(url)));
    render(<ExceptionsList />);
    await settled();
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Filter', 'Show more']);
    expect(screen.getAllByRole('radio').map((b) => b.textContent)).toEqual(['10', '20', '50']);
    const links = screen.getAllByRole('link');
    const titles = fixture.items.slice(0, 20).map((r) => r.title);
    expect(links.map((a) => a.textContent)).toEqual(titles);
    expect(links.every((a) => a.getAttribute('href')!.startsWith('/work/'))).toBe(true);
    expect(document.body.textContent).not.toMatch(/Reconcile|Resume|Cancel|Resend|Record (a )?response|Ask/);
  });

  it('compact: limit 10, 3 rows, no page chrome, one See all link', async () => {
    serve((url) => json(200, page(url)));
    const { unmount } = render(<ExceptionsList compact limit={10} maxRows={3} />);
    await settled();
    expect(urls().map((u) => u.search)).toEqual(['?limit=10']);
    expect(rowTitles()).toEqual(fixture.items.slice(0, 3).map((r) => r.title));
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.queryByRole('radiogroup')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByText(/The factory never resends|Showing|OPEN/)).toBeNull();
    expect(screen.getByText('As of 14 Nov 11:05')).toBeTruthy();
    expect(screen.getAllByRole('link', { name: 'See all exceptions' }).map((a) => a.getAttribute('href'))).toEqual(['/exceptions']);
    unmount();

    render(<ExceptionsList compact maxRows={3} seeAllHref="/exceptions?from=overview" />);
    await settled();
    expect(screen.getByRole('link', { name: 'See all exceptions' }).getAttribute('href')).toBe('/exceptions?from=overview');
  });

  it('compact: the 403 and empty states render inside it', async () => {
    serve(() => json(403, { code: 'forbidden', message: 'No.' }));
    const { unmount } = render(<ExceptionsList compact />);
    await screen.findByText('This list is for Leads');
    expect(screen.getByRole('heading', { level: 3 }).textContent).toBe('This list is for Leads');
    unmount();
    serve(() => json(200, { items: [], as_of: fixture.as_of }));
    render(<ExceptionsList compact />);
    await settled();
    expect(screen.getByRole('heading', { level: 3 }).textContent).toBe('No exceptions.');
  });

  it('useExceptions is exported for reuse', () => {
    expect(typeof useExceptions).toBe('function');
  });
});

describe('work item "See all exceptions" link', () => {
  const base = read('work/W-1005.json') as WorkItem;
  const ALL: WorkState[] = [
    'ready',
    'processing',
    'waiting',
    'owner_needed',
    'setup_needed',
    'action_needed',
    'effect_uncertain',
    'awaiting_reconciliation',
    'verified',
    'cancelled',
    'followup_needed',
  ];
  const WITH_LINK = new Set<WorkState>(['effect_uncertain', 'awaiting_reconciliation', 'owner_needed', 'setup_needed', 'followup_needed']);

  it.each(ALL)('%s', (state) => {
    render(<NextStep item={{ ...base, state }} />);
    const link = screen.queryByRole('link', { name: 'See all exceptions' });
    if (WITH_LINK.has(state)) expect(link?.getAttribute('href')).toBe('/exceptions');
    else expect(link).toBeNull();
  });
});
