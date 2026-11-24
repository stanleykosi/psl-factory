// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useMemo, useSyncExternalStore } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { moneyRoute } from '../mock/money.mjs';
// @ts-expect-error plain ESM module without type declarations
import { projectTab } from '../mock/project-tabs.mjs';
// @ts-expect-error plain ESM module without type declarations
import { normaliseProjectPath, projects, uuidOf } from '../mock/projects.mjs';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

// The URL of the page: replace() rewrites it and the page re-renders, as the router does.
const nav = vi.hoisted(() => {
  const state = { search: '', listeners: new Set<() => void>(), replaced: [] as string[] };
  return state;
});
vi.mock('next/navigation', () => ({
  usePathname: () => '/projects/P-0101/milestones',
  useRouter: () => ({
    replace: (href: string) => {
      nav.replaced.push(href);
      nav.search = href.includes('?') ? href.slice(href.indexOf('?') + 1) : '';
      nav.listeners.forEach((l) => l());
    },
    push: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => {
    const search = useSyncExternalStore(
      (l) => {
        nav.listeners.add(l);
        return () => nav.listeners.delete(l);
      },
      () => nav.search,
      () => nav.search,
    );
    return useMemo(() => new URLSearchParams(search), [search]);
  },
}));

const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let persona = 'pm';
let cookies: Record<string, string>;
let respond: ((url: URL) => Response | Promise<Response> | undefined) | undefined;
let calls: URL[];

beforeEach(() => {
  persona = 'pm';
  cookies = {};
  respond = undefined;
  calls = [];
  nav.search = '';
  nav.replaced = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me(persona));
      calls.push(url);
      // the mock server names a project by its P-nnnn id for the tab fixtures (normaliseProjectPath); the request keeps the UUID
      const mockUrl = new URL(normaliseProjectPath(url.pathname) + url.search, url);
      const custom = respond?.(mockUrl);
      if (custom) return custom;
      const parts = mockUrl.pathname.split('/');
      if (parts[5] === 'money' || (parts[5] === 'milestones' && parts.length === 7)) {
        return json(...(moneyRoute({ route: { operationId: 'E-PROJECT-TAB', statuses: ['401', '403', '404'] }, url: mockUrl, req: { headers: {} }, cookies: { psl_mock_persona: persona, ...cookies } }) as [number, unknown]));
      }
      const r = parts.length > 5 ? projectTab({ url: mockUrl, persona }) : projects({ operationId: 'E-PROJECT', url: mockUrl, persona });
      return json(r.status, r.body);
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

async function until(check: () => void, ms = 3000) {
  const end = Date.now() + ms;
  for (;;) {
    try {
      check();
      return;
    } catch (error) {
      if (Date.now() > end) throw error;
    }
    await act(async () => {
      await new Promise((r) => setTimeout(r, 5));
    });
  }
}

const tabCalls = () => calls.filter((u) => u.pathname.split('/').length > 5);
const reads = () => tabCalls().map((u) => u.pathname.replace(/^\/api\/v1\/projects\/[^/]+/, '') + u.search);

async function open(caseId: string, search = '') {
  nav.search = search;
  const result = render(
    <AppShell>
      <ProjectJourneyPage caseId={caseId} tab="milestones" />
    </AppShell>,
  );
  await until(() => expect(screen.queryByText('Loading…')).toBeNull());
  await until(() => expect(tabCalls().length).toBeGreaterThan(0));
  await until(() => expect(screen.queryByText('Loading…')).toBeNull());
  return result;
}

const text = () => document.body.textContent ?? '';
const rowsOf = () => [...document.querySelectorAll('tbody tr')].map((tr) => [...tr.children].map((c) => c.textContent));
const phone = () =>
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));

const panel = () => screen.getByRole('tabpanel', { name: 'Milestones' });
const proofButtons = () => [...panel().querySelectorAll('button')].filter((b) => b.textContent!.startsWith('Proof'));
const buttons = (name: string) => [...panel().querySelectorAll('button')].filter((b) => b.textContent === name);
const press = async (name: string, nth = 0) => {
  fireEvent.click(buttons(name)[nth]);
};
const detailCalls = () => tabCalls().filter((u) => /\/milestones\/\d+$/.test(u.pathname));
const NO_FINANCE = 'Contract amounts, invoices and payments aren’t available to your role.';

describe('Milestones (SCR-38) on the live reads', () => {
  it('P-0101: contract stages only, in the order sent, numbered where they have a position, two reads, no CHANGES column', async () => {
    await open('P-0101');
    expect(reads().sort()).toEqual(['/milestones', '/money']);
    expect(screen.getByRole('tab', { name: /^Milestones/ }).getAttribute('aria-selected')).toBe('true');
    expect([...document.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['MILESTONE', 'CONTRACT AMOUNT', 'COMPLETION', 'INVOICE', 'PAID']);
    const rows = rowsOf();
    expect(rows.map((r) => [r[0], r[1]])).toEqual([
      ['1 · Kick-off', 'NGN 3,000,000.00'],
      ['2 · UAT sign-off', 'NGN 4,250,000.00'],
      ['3 · Go-live', 'UnknownThe reviewed stage terms do not state an amount.'],
      ['Hypercare', 'NGN 500,000.00'],
    ]);
    expect(text()).not.toContain('INV-0420');
    expect(rows[0][3]).toBe('INV-0398 · DeliveredINV-0399 · Issued');
    expect(rows[1][4]).toBe('Paid Unknown · Owed Unknown');
    expect(rows[3].slice(3)).toEqual(['—No invoice', '—No payment']);
    expect(document.querySelector('.psl-unknown')!.textContent).toBe('Unknown');
    expect(text()).toContain('As of 12 Nov 16:40');
    expect(text()).toContain('Milestones and amounts come from the signed SOW.');
    expect(text()).not.toMatch(/total|subtotal|part paid|not paid/i);
  });

  it('COMPLETION: Done, Due, Not completed; who recorded it only through milestone_id; Proof only where a link exists', async () => {
    await open('P-0101');
    const done = rowsOf().map((r) => r[2]!.replace(/Proof for .*/, '').replace(/Proof$/, ''));
    expect(done).toEqual(['Done 27 OctDue 30 OctRecorded by Tunde Bello', 'Done 11 NovDue 10 Nov', 'Not completedDue 12 Dec', 'Not completed']);
    expect(text().match(/Ada Obi/g)).toHaveLength(1); // only in the completions list, never joined to UAT by its name
    expect(within(document.querySelectorAll('tbody tr')[1] as HTMLElement).queryByRole('button')).toBeNull();
    expect(within(document.querySelectorAll('tbody tr')[0] as HTMLElement).getAllByRole('button')).toHaveLength(1);
    expect(proofButtons()).toHaveLength(3); // the Kick-off row and the two completions
  });

  it('Recorded completions is its own list under the table, never merged into rows', async () => {
    await open('P-0101');
    expect(within(panel()).getByRole('heading', { level: 2, name: 'Recorded completions' })).toBeTruthy();
    const items = [...panel().querySelectorAll('.ptabs__completion')].map((li) => li.textContent);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatch(/^Kick-offCompletion recorded27 Oct.*Recorded by Tunde Bello/);
    expect(items[1]).toMatch(/UAT sign-offCompletion recorded11 Nov.*Recorded by Ada Obi/);
    expect(document.querySelectorAll('tbody tr')).toHaveLength(4);
    expect(text()).not.toContain('recorded'.toUpperCase() + 'x'); // state_code is never shown
    expect(text()).not.toMatch(/\brecorded\b(?! completions| by)/);
  });

  it('a changed section title still renders the rows', async () => {
    respond = (url) => {
      if (!url.pathname.endsWith('/milestones')) return undefined;
      const r = projectTab({ url, persona }) as { body: { sections: { title: string }[] } };
      r.body.sections[0].title = 'Something else';
      return json(200, r.body);
    };
    await open('P-0101');
    expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(2);
  });

  it('a row without who recorded it says so', async () => {
    await open('P-0102');
    expect(panel().querySelectorAll('.ptabs__completion')[0].textContent).toContain('Recorded by: not shown');
  });

  it('changed: a CHANGES column with the reference and note; the change amount is Unknown and never added', async () => {
    cookies = { psl_mock_milestones: 'changed' };
    await open('P-0101');
    expect([...document.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['MILESTONE', 'CONTRACT AMOUNT', 'COMPLETION', 'INVOICE', 'PAID', 'CHANGES']);
    const goLive = rowsOf()[2];
    expect(goLive[1]).toBe('UnknownThe reviewed stage terms do not state an amount. + the change · change amount Unknown');
    expect(goLive[5]).toBe('CHG-0007 · Extra reporting scope');
    expect(rowsOf()[0][5]).toBe('—');
    expect(rowsOf()[0][1]).toBe('NGN 3,000,000.00');
    expect(text()).not.toMatch(/7,250,000|4,250,000\.00 \+/);
  });

  it('limited: true shows the warning', async () => {
    await open('P-0102');
    expect(within(panel()).getByText('Some figures may be incomplete.')).toBeTruthy();
  });

  it('P-0106: no stages and no completions say so', async () => {
    await open('P-0106');
    expect(within(panel()).getByText('No milestones on this project yet.')).toBeTruthy();
    expect(within(panel()).getByText('No completions recorded yet.')).toBeTruthy();
    expect(panel().querySelector('table')).toBeNull();
  });
});

describe('F-71 round 2: Unknown, headings, Proof state', () => {
  it('UI-1-4: Unknown is plain text, not a tag, on the table and the phone cards, styled as bold text', async () => {
    await open('P-0101');
    const unknowns = [...panel().querySelectorAll('.psl-unknown')];
    expect(unknowns.length).toBeGreaterThan(0);
    expect(unknowns.every((u) => u.textContent === 'Unknown' && !u.closest('.psl-tag'))).toBe(true);
    const css = readFileSync(join(__dirname, '../src/features/projects/project-tabs.css'), 'utf8');
    expect(css).toMatch(/\.ptabs__ms \.psl-unknown[^{]*\.ptabs__card \.psl-unknown[^{]*\{[^}]*background: none[^}]*font-weight: 600/);
  });

  it('UX-1-2: a section heading for the table and for the completions', async () => {
    await open('P-0101');
    expect(within(panel()).getByRole('heading', { level: 2, name: 'Contract milestones' })).toBeTruthy();
    expect(within(panel()).getByRole('heading', { level: 2, name: 'Recorded completions' })).toBeTruthy();
  });

  it('UX-1-3: Proof buttons say whether the proof is shown', async () => {
    await open('P-0101');
    expect(proofButtons().every((b) => b.getAttribute('aria-expanded') === 'false')).toBe(true);
    await press('Proof for Kick-off');
    await until(() => expect(panel().textContent).toContain('Proof version 2'));
    const kickoff = proofButtons().find((b) => b.textContent === 'Proof for Kick-off')!;
    expect(kickoff.getAttribute('aria-expanded')).toBe('true');
    expect(proofButtons().filter((b) => b !== kickoff).every((b) => b.getAttribute('aria-expanded') === 'false')).toBe(true);
  });

  it('TECH-2-1: Proof is a toggle; aria-expanded is true from the press, through the read, until the second press', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    respond = (url) => (/\/milestones\/\d+$/.test(url.pathname) ? gate.then(() => json(200, { id: 3101, name: 'Kick-off', completed_at: '2026-10-27T10:00:00Z', evidence_id: 1, proof_version: 2 })) : undefined);
    await open('P-0101');
    const kick = buttons('Proof for Kick-off')[0];
    fireEvent.click(kick);
    const kickoff = () => kick;
    expect(kickoff().getAttribute('aria-expanded')).toBe('true');
    release();
    await until(() => expect(panel().textContent).toContain('Proof version 2'));
    expect(kickoff().getAttribute('aria-expanded')).toBe('true');
    await press('Proof for Kick-off');
    expect(kickoff().getAttribute('aria-expanded')).toBe('false');
    expect(panel().textContent).not.toContain('Proof version 2');
    expect(detailCalls()).toHaveLength(1);
  });
});

describe('Proof', () => {
  it('one read per press; shows the name, the date and the proof version', async () => {
    await open('P-0101');
    expect(detailCalls()).toHaveLength(0);
    await press('Proof for Kick-off');
    await until(() => expect(within(panel()).getAllByText('Proof version 2')).toHaveLength(1));
    expect(detailCalls().map((u) => u.pathname)).toEqual([`/api/v1/projects/${uuidOf('P-0101')}/milestones/3101`]);
    const shown = panel().querySelector('.ptabs__proofbody')!.textContent;
    expect(shown).toBe('Kick-offCompleted 27 OctProof version 2');
    await press('Proof for Kick-off');
    expect(panel().querySelector('.ptabs__proofbody')).toBeNull();
    expect(detailCalls()).toHaveLength(1);
    await press('Proof for Kick-off');
    await until(() => expect(detailCalls()).toHaveLength(2));
  });

  it('a completion in the list reads its own record_id', async () => {
    await open('P-0101');
    await press('Proof for UAT sign-off');
    await until(() => expect(panel().textContent).toContain('Proof version 1'));
    expect(detailCalls().map((u) => u.pathname.split('/').pop())).toEqual(['3102']);
  });

  it.each([403, 404])('a %i says the proof is not available to the role', async (status) => {
    respond = (url) => (/\/milestones\/\d+$/.test(url.pathname) ? json(status, { code: 'x', message: 'SECRET' }) : undefined);
    await open('P-0101');
    await press('Proof for Kick-off');
    await until(() => expect(panel().textContent).toContain('Proof isn’t available to your role.'));
    expect(text()).not.toContain('SECRET');
  });

  it('an error shows "We couldn’t load the proof." and Try again reads once more', async () => {
    let fail = true;
    respond = (url) => (fail && /\/milestones\/\d+$/.test(url.pathname) ? json(500, { code: 'server_error', message: 'x' }) : undefined);
    await open('P-0101');
    await press('Proof for Kick-off');
    await until(() => expect(panel().textContent).toContain('We couldn’t load the proof.'));
    fail = false;
    fireEvent.click(buttons('Try again')[0]);
    await until(() => expect(panel().textContent).toContain('Proof version 2'));
    expect(detailCalls()).toHaveLength(2);
  });

  it('no file link and no write control', async () => {
    await open('P-0101');
    await press('Proof for Kick-off');
    await until(() => expect(panel().textContent).toContain('Proof version 2'));
    expect(panel().querySelector('a, form, input, [type="submit"]')).toBeNull();
    expect(calls.every((u) => !u.pathname.includes('files'))).toBe(true);
  });
});

describe('who can see what', () => {
  it('money refused (P-0108 404): the completions and the plain note, no figure, column or invoice', async () => {
    persona = 'finance_lead';
    await open('P-0108');
    expect(within(panel()).getByText(NO_FINANCE)).toBeTruthy();
    expect(within(panel()).getByRole('heading', { level: 2, name: 'Recorded completions' })).toBeTruthy();
    expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(1);
    expect(panel().querySelector('table, thead')).toBeNull();
    expect(text()).not.toMatch(/NGN|INV-|CONTRACT AMOUNT|Not completed|Some figures/);
    expect(text()).not.toContain('Milestones and amounts come from');
  });

  it('money refused (403) reads the same', async () => {
    respond = (url) => (url.pathname.endsWith('/money') ? json(403, { code: 'forbidden', message: 'SECRET' }) : undefined);
    await open('P-0101');
    expect(within(panel()).getByText(NO_FINANCE)).toBeTruthy();
    expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(2);
    expect(text()).not.toContain('SECRET');
  });

  it.each([
    ['P-0105 (404)', 'P-0105'],
    ['P-0103 (403)', 'P-0103'],
  ])('completions refused, %s: the table shows without a completions heading', async (_name, id) => {
    await open(id);
    expect(document.querySelectorAll('tbody tr')).toHaveLength(4);
    expect(screen.queryByText('Recorded completions')).toBeNull();
    expect(text()).not.toContain(NO_FINANCE);
    expect(text()).not.toContain('No completions recorded yet.');
  });

  it('both refused: only the note', async () => {
    respond = (url) => (url.pathname.endsWith('/money') || url.pathname.endsWith('/milestones') ? json(404, { code: 'not_found', message: 'x' }) : undefined);
    await open('P-0101');
    expect(within(panel()).getByText(NO_FINANCE)).toBeTruthy();
    expect(panel().querySelector('table, section, h2')).toBeNull();
  });

  it('P-0099: no tab request', async () => {
    render(
      <AppShell>
        <ProjectJourneyPage caseId="P-0099" tab="milestones" />
      </AppShell>,
    );
    await until(() => expect(screen.getByRole('heading', { name: /can.t open this project/ })).toBeTruthy());
    expect(tabCalls()).toHaveLength(0);
  });

  it('a 401 on either read signs in back to the tab', async () => {
    respond = (url) => (url.pathname.endsWith('/milestones') ? json(401, { code: 'not_signed_in', message: 'x' }) : undefined);
    await open('P-0101');
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fprojects%2FP-0101%2Fmilestones');
  });
});

describe('errors and paging', () => {
  it('a failed money read gets its own card; the completions still show; Try again re-reads money only', async () => {
    let fail = true;
    respond = (url) => (fail && url.pathname.endsWith('/money') ? json(500, { code: 'server_error', message: 'Boom' }) : undefined);
    await open('P-0101');
    expect(screen.getByRole('alert').textContent).toContain('We couldn’t load this project’s milestones.');
    expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(2);
    expect(text()).not.toContain('Boom');
    fail = false;
    const before = tabCalls().length;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(document.querySelectorAll('tbody tr')).toHaveLength(4));
    expect(tabCalls().slice(before).map((u) => u.pathname.split('/').pop())).toEqual(['money']);
  });

  it('a failed completions read gets its own card; the table still shows', async () => {
    respond = (url) => (url.pathname.endsWith('/milestones') ? json(500, { code: 'server_error', message: 'Boom' }) : undefined);
    await open('P-0101');
    expect(screen.getByRole('alert').textContent).toContain('We couldn’t load the recorded completions.');
    expect(document.querySelectorAll('tbody tr')).toHaveLength(4);
  });

  it('a body that fails the guard draws nothing partial', async () => {
    respond = (url) => (url.pathname.endsWith('/money') ? json(200, { items: [{ key: 'x' }], limited: false, as_of: 'x', finance_url: '/f' }) : undefined);
    await open('P-0101');
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(panel().querySelector('table')).toBeNull();
  });

  it('Show more asks for the next page, appends the rows, and goes when there is no more', async () => {
    await open('P-0102');
    expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(25);
    await press('Show more');
    await until(() => expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(27));
    expect(reads().filter((r) => r.startsWith('/milestones'))).toEqual(['/milestones', '/milestones?page=2']);
    expect(within(panel()).queryByRole('button', { name: 'Show more' })).toBeNull();
    await until(() => expect(document.activeElement).toBe(panel().querySelectorAll('.ptabs__completion')[25]));
  });

  it('a failed second page says so and Show more tries again', async () => {
    let fail = true;
    respond = (url) => (fail && url.searchParams.get('page') === '2' ? json(500, { code: 'server_error', message: 'x' }) : undefined);
    await open('P-0102');
    await press('Show more');
    await until(() => expect(text()).toContain('We couldn’t load more.'));
    expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(25);
    fail = false;
    await press('Show more');
    await until(() => expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(27));
  });

  it('only GET requests leave the tab', async () => {
    const methods: string[] = [];
    const base = globalThis.fetch;
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      methods.push(request.method);
      return base(request);
    }));
    await open('P-0101');
    await press('Proof for Kick-off');
    await until(() => expect(panel().textContent).toContain('Proof version 2'));
    expect(new Set(methods)).toEqual(new Set(['GET']));
  });
});

describe('phone (390)', () => {
  beforeEach(phone);

  it('one card per stage in the order sent, then the completions list; Proof works in a card', async () => {
    await open('P-0101');
    const cards = [...panel().querySelectorAll('.ptabs__card')];
    expect(cards.map((c) => c.querySelector('strong')!.textContent)).toEqual(['1 · Kick-off', '2 · UAT sign-off', '3 · Go-live', 'Hypercare']);
    expect(panel().querySelector('table')).toBeNull();
    expect(cards[0].textContent).toContain('NGN 3,000,000.00');
    expect(cards[0].textContent).toContain('Done 27 Oct');
    expect(cards[2].textContent).toContain('Unknown');
    expect(panel().querySelectorAll('.ptabs__completion')).toHaveLength(2);
    fireEvent.click([...cards[0].querySelectorAll('button')].find((b) => b.textContent!.startsWith('Proof'))!);
    await until(() => expect(cards[0].textContent).toContain('Proof version 2'));
  });

  it('changed: the CHANGED tag names the change', async () => {
    cookies = { psl_mock_milestones: 'changed' };
    await open('P-0101');
    expect([...panel().querySelectorAll('.ptabs__card')][2].textContent).toContain('CHANGED · CHG-0007');
  });
});
