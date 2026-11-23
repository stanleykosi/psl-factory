// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { moneyRoute } from '../mock/money.mjs';
// @ts-expect-error plain ESM module without type declarations
import { normaliseProjectPath, projects, uuidOf } from '../mock/projects.mjs';
import { destinationList } from './destinations';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

// F-26 Money tab (SCR-12) against the contract mock's own handlers. Every money rule is a test here: Unknown is never
// 0 or blank, nothing is totalled, invoice and paid are separate, the drill-down shows only the figure's own sources,
// and a refused read names no stage or amount.
const nav = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  let params = new URLSearchParams();
  const set = (search: string) => {
    params = new URLSearchParams(search);
    listeners.forEach((l) => l());
  };
  const router = {
    replace: vi.fn((url: string) => set(new URL(url, 'http://localhost').search)),
    push: vi.fn(),
    prefetch: vi.fn(),
  };
  return { listeners, get: () => params, set, router };
});
vi.mock('next/navigation', async () => {
  const { useSyncExternalStore } = await import('react');
  const subscribe = (cb: () => void) => {
    nav.listeners.add(cb);
    return () => nav.listeners.delete(cb);
  };
  return {
    usePathname: () => '/projects/P-0101/money',
    useRouter: () => nav.router,
    useSearchParams: () => useSyncExternalStore(subscribe, nav.get),
  };
});

type Body = Record<string, unknown>;
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const fixture = (path: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', path), 'utf8')) as Body;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const STATUSES = ['200', '401', '403', '404'];

/** The mock's own answer for a request: E-PROJECT from projects.mjs, money and reports from money.mjs. */
function fromMock(raw: URL, who: string): Response {
  // the mock server names a project by its P-nnnn id for the money fixtures (normaliseProjectPath)
  const url = new URL(normaliseProjectPath(raw.pathname) + raw.search, raw);
  const parts = url.pathname.split('/');
  const cookies = { psl_mock_persona: who };
  if (parts[3] === 'reports') return json(...(moneyRoute({ route: { operationId: 'E-REPORT', statuses: STATUSES }, url, req: { headers: {} }, cookies }) as [number, Body]));
  if (parts[5] === 'money') return json(...(moneyRoute({ route: { operationId: 'E-PROJECT-TAB', statuses: STATUSES }, url, req: { headers: {} }, cookies }) as [number, Body]));
  const r = projects({ operationId: 'E-PROJECT', url, persona: who }) as { status: number; body: Body };
  return json(r.status, r.body);
}

let persona = 'finance_lead';
let destinations: string[] | undefined;
let respond: (url: URL) => Response | Promise<Response>;
let calls: URL[];

beforeEach(() => {
  persona = 'finance_lead';
  destinations = undefined;
  calls = [];
  respond = (url) => fromMock(url, persona);
  nav.router.replace.mockClear();
  nav.set('');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, { ...me(persona), ...(destinations ? { destinations: destinationList(destinations) } : {}) });
      calls.push(url);
      return respond(url);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});

async function until(check: () => void, tries = 100) {
  for (let i = 0; ; i++) {
    try {
      check();
      return;
    } catch (error) {
      if (i >= tries) throw error;
    }
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
  }
}

const settle = () => until(() => expect(document.querySelector('.psl-loading')).toBeNull());

async function open(caseId = 'P-0101', search = '') {
  nav.set(search);
  render(
    <AppShell>
      <ProjectJourneyPage caseId={caseId} tab="money" />
    </AppShell>,
  );
  await until(() => expect(calls.length).toBeGreaterThan(0));
  await settle();
}

const phone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
const panel = () => screen.getByRole('tabpanel', { name: 'Money' });
const bodyRows = () => [...panel().querySelectorAll('tbody tr')] as HTMLTableRowElement[];
const cells = () => bodyRows().map((tr) => [...tr.cells].map((td) => td.textContent));
const cell = (row: number, col: number) => bodyRows()[row].cells[col];
const paths = () => calls.map((u) => u.pathname);
const aside = () => screen.getByRole('complementary');
// A zero or a missing number: "₦0", a lone "0.00" (not the end of "₦3,000,000.00") or NaN.
const ZERO = /₦0(?![\d,.])|₦0\.00|(?<![\d,])0\.00|NaN/;

describe('board rows from data (P-0101, as SCR-12 draws it)', () => {
  it('four stages in position order, amounts with two decimals, invoice and paid as sent, the note and the time', async () => {
    await open();
    expect(paths()).toEqual(['/api/v1/projects/P-0101', `/api/v1/projects/${uuidOf('P-0101')}/money`, '/api/v1/reports/R-0101']);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · patient app');
    expect(within(panel()).getByRole('heading', { level: 2 }).textContent).toBe('Lagoon Health · billing by contract stage');
    expect(within(panel()).getAllByRole('columnheader').map((th) => [th.textContent, th.getAttribute('scope')])).toEqual([
      ['STAGE', 'col'],
      ['AMOUNT', 'col'],
      ['INVOICE', 'col'],
      ['PAID', 'col'],
    ]);
    expect(within(panel()).getByRole('table', { name: 'Billing by contract stage' })).toBeTruthy();
    expect(cells()).toEqual([
      ['Stage 1 · kick-off', '₦3,000,000.00', 'Verified 03 Nov, INV-0398', 'Finance tracks'],
      ['Stage 2 · UAT', '₦4,250,000.00', 'Awaiting Finance decision, INV-0412', '—Not due'],
      ['Stage 3 · go-live', '₦4,250,000.00', 'Held · owner needed, INV-0419', '—Not due'],
      ['Stage 4 · hypercare', 'UnknownNot yet due · amount set at go-live', '—No invoice', '—Not due'],
    ]);
    expect(cell(3, 1).querySelector('.money__note')!.textContent).toBe('Not yet due · amount set at go-live');
    expect(panel().querySelector('.money__asof')!.textContent).toBe('As of 12 Nov 16:40');
    expect(screen.getByText('Every figure links to the record it came from. Unknown amounts are shown as Unknown, never as 0.')).toBeTruthy();
  });

  it('No access in the frontend: finance_lead and pm see the same rows; only /me assistant is read', async () => {
    await open();
    const lead = cells();
    document.body.innerHTML = '';
    persona = 'pm';
    calls = [];
    await open();
    expect(cells()).toEqual(lead);
  });

  it('No total, no computation: exactly four rows, no footer, no sum, balance, percentage or outstanding', async () => {
    await open();
    expect(bodyRows()).toHaveLength(4);
    expect(panel().querySelector('tfoot')).toBeNull();
    expect(panel().textContent).not.toMatch(/total|sum\b|balance|outstanding|%|subtotal/i);
  });
});

describe('Unknown is not zero', () => {
  it('P-0101 Stage 4: amber Unknown, plain text, not a link, never a dash or blank', async () => {
    await open();
    const unknown = cell(3, 1).querySelector('.psl-unknown')!;
    expect(unknown.textContent).toBe('Unknown');
    expect(cell(3, 1).querySelector('a')).toBeNull();
    expect(panel().textContent).not.toMatch(ZERO);
  });

  it('P-0102: unknown amount (unknown:false with no amount), unknown owed and unknown figure value all read Unknown', async () => {
    await open('P-0102', '?figure=FIG-0102-S6');
    const stage4 = bodyRows().find((tr) => tr.cells[0].textContent === 'Stage 4 · hypercare')!;
    expect(stage4.cells[1].querySelector('.psl-unknown')!.textContent).toBe('Unknown');
    expect(stage4.cells[3].querySelector('.psl-unknown')!.textContent).toBe('Unknown');
    const stage3 = bodyRows().find((tr) => tr.cells[0].textContent === 'Stage 3 · go-live')!;
    expect(stage3.cells[3].textContent).toBe('Not paid · owed Unknown');
    expect(stage3.cells[3].querySelector('.psl-unknown')).toBeTruthy();
    expect(within(aside()).getByText('Where this figure comes from')).toBeTruthy();
    expect(aside().textContent).toContain('Amount: Unknown');
    expect(aside().querySelector('.psl-unknown')).toBeTruthy();
    expect(panel().textContent).not.toMatch(ZERO);
  });
});

describe('invoice and paid are separate (INV-FACTS)', () => {
  it('P-0102: paid absent is Unknown whatever the invoice says; part paid and not paid with owed; a USD row; 19 digits', async () => {
    await open('P-0102');
    expect(cells()).toEqual([
      ['Stage 1 · kick-off', '₦2,500,000.00', 'Verified 20 Oct, INV-0501', 'Part paid · ₦1,250,000.00 owed'],
      ['Stage 2 · UAT', '₦2,500,000.00', 'Awaiting Finance decision', 'Unknown'],
      ['Stage 3 · go-live', '1,200.00 USD', 'INV-0503', 'Not paid · owed Unknown'],
      ['Stage 4 · hypercare', 'Unknown', '—No invoice', 'Unknown'],
      ['Change request CR-0031', '₦800,000.00', '—No invoice', '—Not due'],
      ['Stage 6 · support', '₦500,000.00', 'Verified 05 Nov, INV-0506', 'Paid'],
      ['Stage 7 · extension', '₦9,223,372,036,854,775,807.00', '—No invoice', '—Not due'],
    ]);
    expect(cell(1, 3).querySelector('.psl-unknown')).toBeTruthy();
    // Not due is a dash for the eye and words for a screen reader.
    expect(cell(4, 3).querySelector('[aria-hidden="true"]')!.textContent).toBe('—');
    expect(cell(4, 3).querySelector('.cmp-sr')!.textContent).toBe('Not due');
  });

  it('changing only invoice_status never changes the PAID cell', async () => {
    const body = fixture('projects/money/P-0101.json') as { money: { invoice_status?: string; invoice?: unknown }[] };
    body.money[1].invoice_status = 'Paid in full 01 Nov';
    body.money[3].invoice_status = 'Verified 12 Nov';
    respond = (url) => (url.pathname.endsWith('/money') ? json(200, body) : fromMock(url, persona));
    await open();
    expect(cell(1, 2).textContent).toBe('Paid in full 01 Nov, INV-0412');
    expect(cell(1, 3).textContent).toBe('—Not due');
    expect(cell(3, 3).textContent).toBe('—Not due');
  });

  it('a paid status outside the enum shows its raw value', async () => {
    const body = fixture('projects/money/P-0101.json') as { money: { paid?: { status: string } }[] };
    body.money[0].paid = { status: 'written_off' };
    respond = (url) => (url.pathname.endsWith('/money') ? json(200, body) : fromMock(url, persona));
    await open();
    expect(cell(0, 3).textContent).toBe('written_off');
  });

  it('invoice cell: the composed status links to its work item with the reference in the name; reference alone is text; neither is a dash', async () => {
    await open();
    const link = within(cell(0, 2)).getByRole('link');
    expect(link.getAttribute('href')).toBe('/work/W-1713');
    expect(link.textContent).toBe('Verified 03 Nov, INV-0398');
    expect(link.querySelector('.cmp-sr')!.textContent).toBe(', INV-0398');
    expect(within(cell(1, 2)).getByRole('link').getAttribute('href')).toBe('/work/W-1001');
    expect(within(cell(2, 2)).getByRole('link').getAttribute('href')).toBe('/work/W-1714');
    expect(cell(3, 2).querySelector('.cmp-sr')!.textContent).toBe('No invoice');
    document.body.innerHTML = '';
    calls = [];
    await open('P-0102');
    expect(cell(2, 2).textContent).toBe('INV-0503');
    expect(cell(2, 2).querySelector('a')).toBeNull();
  });
});

describe('drill-down (E-REPORT)', () => {
  it('nothing chosen on load: amounts with a figure are links, the aside asks for a choice above Chidi', async () => {
    await open();
    expect(within(aside()).getByText('Choose an amount to see where it comes from.')).toBeTruthy();
    expect(aside().getAttribute('aria-labelledby')).toBeTruthy();
    const links = [0, 1, 2].map((i) => within(cell(i, 1)).getByRole('link'));
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/projects/P-0101/money?figure=FIG-0101-S1', '/projects/P-0101/money?figure=FIG-0101-S2', '/projects/P-0101/money?figure=FIG-0101-S3']);
    expect(links.every((a) => !a.hasAttribute('aria-current'))).toBe(true);
    expect(aside().querySelector('ol')).toBeNull();
  });

  it('?figure=FIG-0101-S2 opens Stage 2: the figure value in the title, its label in the name, three sources in order, no links', async () => {
    await open('P-0101', '?figure=FIG-0101-S2');
    const region = screen.getByRole('complementary', { name: 'Where ₦4,250,000.00 comes from, Stage 2 · UAT amount' });
    const items = [...region.querySelectorAll('ol > li')];
    expect(items.map((li) => li.textContent)).toEqual([
      'Signed SOW v2, stage table, row 2 SOW-0198 v2',
      'Stage terms v1, active since 30 Jun RULE · stage terms',
      'Milestone 2 completion, recorded by Tunde Bello HB-M2',
    ]);
    expect(items.map((li) => li.querySelector('.money__ref')!.textContent)).toEqual(['SOW-0198 v2', 'RULE · stage terms', 'HB-M2']);
    expect(region.querySelectorAll('ol a')).toHaveLength(0);
    expect(within(cell(1, 1)).getByRole('link').getAttribute('aria-current')).toBe('true');
    expect(within(cell(2, 1)).getByRole('link').hasAttribute('aria-current')).toBe(false);
    expect(region.querySelector('.psl-callout--warning')).toBeNull();
  });

  it('pressing an amount announces the figure (the URL change itself is the e2e)', async () => {
    await open('P-0101', '?figure=FIG-0101-S3');
    const live = panel().querySelector('[aria-live="polite"]')!;
    expect(live.textContent).toBe('');
    fireEvent.click(within(cell(2, 1)).getByRole('link'));
    await until(() => expect(live.textContent).toBe('Showing where ₦4,250,000.00 comes from'));
    expect(screen.getByRole('complementary').textContent).toContain('Go-live invoice, held for an owner');
  });

  it('P-0102: the title uses the figure value, not the row, and "These figures differ" shows both', async () => {
    await open('P-0102', '?figure=FIG-0102-S1');
    expect(screen.getByRole('complementary', { name: 'Where ₦2,400,000.00 comes from, Stage 1 · kick-off amount' })).toBeTruthy();
    expect(aside().querySelector('.psl-callout--warning')!.textContent).toBe('These figures differ: the table shows ₦2,500,000.00; the report shows ₦2,400,000.00.');
    // A work item source links; a document source is text (no document page yet).
    expect(within(aside()).getByRole('link', { name: 'Kick-off invoice, verified 20 Oct' }).getAttribute('href')).toBe('/work/W-1713');
    expect(within(aside()).queryByRole('link', { name: /Signed SOW v1/ })).toBeNull();
    expect(aside().textContent).toContain('Signed SOW v1, stage table, row 1');
  });

  it('No source, never empty: unmatched figure ids are plain text; an unmatched deep link, no sources, strings only', async () => {
    await open('P-0102', '?figure=FIG-0102-S2');
    const stage2 = bodyRows().find((tr) => tr.cells[0].textContent === 'Stage 2 · UAT')!;
    expect(stage2.cells[1].querySelector('a')).toBeNull();
    expect(stage2.cells[1].textContent).toBe('₦2,500,000.00');
    expect(within(aside()).getByText('Where this figure comes from')).toBeTruthy();
    expect(within(aside()).getByText('No source recorded')).toBeTruthy();

    act(() => nav.set('?figure=FIG-0102-S5'));
    await until(() => expect(screen.getByRole('complementary', { name: 'Where ₦800,000.00 comes from, Change request CR-0031 amount' })).toBeTruthy());
    expect(within(aside()).getByText('No source recorded')).toBeTruthy();

    act(() => nav.set('?figure=FIG-0102-S3'));
    await until(() => expect(screen.getByRole('complementary', { name: 'Where 1,200.00 USD comes from, Stage 3 · go-live amount' })).toBeTruthy());
    expect([...aside().querySelectorAll('ol > li')].map((li) => li.textContent)).toEqual(['SOW-0221 v1, row 3', 'Exchange note EX-14']);

    act(() => nav.set('?figure=NOPE'));
    await until(() => expect(within(aside()).getByText('Where this figure comes from')).toBeTruthy());
    expect(within(aside()).getByText('No source recorded')).toBeTruthy();
  });

  it('Chidi: name and role, "Ask me" to /assistant?agent=chidi with no figure; no link without the Assistant; no card without an agent', async () => {
    await open('P-0101', '?figure=FIG-0101-S2');
    const card = aside().querySelector('.money__agent')!;
    expect(card.textContent).toBe('Chidi · Finance agentAsk me about any figure here.');
    expect(within(card as HTMLElement).getByRole('link', { name: 'Ask me' }).getAttribute('href')).toBe('/assistant?agent=chidi');

    document.body.innerHTML = '';
    calls = [];
    destinations = ['my_work', 'projects'];
    await open('P-0101', '?figure=FIG-0101-S2');
    expect(aside().querySelector('.money__agent')!.textContent).toBe('Chidi · Finance agent');
    expect(within(aside()).queryByRole('link', { name: 'Ask me' })).toBeNull();

    document.body.innerHTML = '';
    calls = [];
    destinations = undefined;
    const report = fixture('reports/R-0101.json');
    delete report.agent;
    respond = (url) => (url.pathname.startsWith('/api/v1/reports/') ? json(200, report) : fromMock(url, persona));
    await open('P-0101', '?figure=FIG-0101-S2');
    expect(aside().querySelector('.money__agent')).toBeNull();
    expect(aside().querySelectorAll('ol > li')).toHaveLength(3);
  });

  it('no report_id: no report request, plain amounts, "No source recorded" for any figure', async () => {
    const body = fixture('projects/money/P-0101.json');
    delete body.summary;
    respond = (url) => (url.pathname.endsWith('/money') ? json(200, body) : fromMock(url, persona));
    await open('P-0101', '?figure=FIG-0101-S2');
    expect(paths().some((p) => p.startsWith('/api/v1/reports/'))).toBe(false);
    expect(panel().querySelectorAll('tbody a[href*="figure="]')).toHaveLength(0);
    expect(within(aside()).getByText('No source recorded')).toBeTruthy();
  });

  it('the report id is URL-encoded', async () => {
    const body = fixture('projects/money/P-0101.json');
    body.summary = { report_id: 'R 01/x' };
    respond = (url) => (url.pathname.endsWith('/money') ? json(200, body) : url.pathname.startsWith('/api/v1/reports/') ? json(404, { code: 'not_found', message: 'x' }) : fromMock(url, persona));
    await open();
    expect(calls.map((u) => u.href).find((h) => h.includes('/reports/'))).toContain('/api/v1/reports/R%2001%2Fx');
  });
});

describe('phone (390): cards and the bottom sheet', () => {
  beforeEach(phone);

  it('P-0101: four cards, the hint as text, Paid · Finance tracks on Stage 1 only, no table and no aside', async () => {
    await open();
    const cards = [...panel().querySelectorAll('.money__card')];
    expect(cards).toHaveLength(4);
    expect(cards.map((c) => c.querySelector('.money__stage')!.textContent)).toEqual(['Stage 1 · kick-off', 'Stage 2 · UAT', 'Stage 3 · go-live', 'Stage 4 · hypercare']);
    expect(cards.map((c) => [...c.querySelectorAll('.money__line')].map((l) => l.textContent))).toEqual([
      ['Verified 03 Nov, INV-0398', 'Paid · Finance tracks'],
      ['Awaiting Finance decision, INV-0412'],
      ['Held · owner needed, INV-0419'],
      [],
    ]);
    expect(cards[3].querySelector('.psl-unknown')!.textContent).toBe('Unknown');
    expect(cards[3].querySelector('.money__note')!.textContent).toBe('Not yet due · amount set at go-live');
    const hint = screen.getByText('Tap an amount to see where it comes from');
    expect(hint.tagName).toBe('P');
    expect(hint.querySelector('a')).toBeNull();
    expect(panel().querySelector('table')).toBeNull();
    expect(screen.queryByRole('complementary')).toBeNull();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(panel().querySelector('.money__asof')!.textContent).toBe('As of 12 Nov 16:40');
  });

  it('?figure=FIG-0101-S2 opens the sheet with the same title and sources; Esc closes it, drops figure and refocuses the amount', async () => {
    await open('P-0101', '?figure=FIG-0101-S2');
    const sheet = screen.getByRole('dialog', { name: 'Where ₦4,250,000.00 comes from' });
    expect([...sheet.querySelectorAll('ol > li')].map((li) => li.querySelector('.money__ref')!.textContent)).toEqual(['SOW-0198 v2', 'RULE · stage terms', 'HB-M2']);
    expect(sheet.textContent).toContain('Stage 2 · UAT amount');
    expect(sheet.querySelector('.money__agent')).toBeTruthy();
    fireEvent.keyDown(sheet, { key: 'Escape' });
    expect(nav.router.replace).toHaveBeenCalledWith('/projects/P-0101/money', { scroll: false });
    await until(() => expect(screen.queryByRole('dialog')).toBeNull());
    const amount = panel().querySelectorAll('.money__card')[1].querySelector('a')!;
    expect(amount.textContent).toBe('₦4,250,000.00');
    await waitFor(() => expect(document.activeElement).toBe(amount));
  });

  it('the close button closes the sheet too', async () => {
    await open('P-0101', '?figure=FIG-0101-S1');
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close' }));
    await until(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(nav.router.replace).toHaveBeenCalledWith('/projects/P-0101/money', { scroll: false });
  });
});

describe('errors and access', () => {
  it('P-0103 report 500: the table stays, amounts are plain, Try again re-reads E-REPORT only, once', async () => {
    await open('P-0103', '?figure=FIG-0101-S2');
    expect(bodyRows()).toHaveLength(4);
    expect(panel().querySelectorAll('tbody a[href*="figure="]')).toHaveLength(0);
    expect(aside().textContent).toContain('We couldn’t load where these figures come from. Your work is safe; nothing was changed.');
    const before = paths().length;
    fireEvent.click(within(aside()).getByRole('button', { name: 'Try again' }));
    await until(() => expect(paths().length).toBe(before + 1));
    await settle();
    expect(paths().slice(before)).toEqual(['/api/v1/reports/R-0103']);
  });

  it('P-0106 report 403: rows show, amounts plain, the aside says so and nothing from the report body appears', async () => {
    await open('P-0106', '?figure=FIG-0101-S2');
    expect(bodyRows()).toHaveLength(4);
    expect(panel().querySelectorAll('tbody a[href*="figure="]')).toHaveLength(0);
    expect(within(aside()).getByText('You can’t see where these figures come from.')).toBeTruthy();
    expect(within(aside()).queryByRole('button')).toBeNull();
    for (const word of ['billing by contract stage', 'secret', 'SOW-OJO', 'Stage 2 · UAT amount', 'Your role does not allow this']) expect(document.body.textContent).not.toContain(word);
  });

  it.each(['P-0107', 'P-0108'])('%s money refused: the money no-access line in the panel, no stage, amount, title or message; no report read', async (caseId) => {
    await open(caseId);
    expect(within(panel()).getByRole('region', { name: 'No access' }).textContent).toBe('You can’t see this project’s money.');
    // Conflicts 14 Option B: the project-level sentence ("not even its name") is not used under the visible title.
    expect(document.body.textContent).not.toContain('not even its name');
    const text = document.body.textContent!;
    for (const word of ['Stage 1', 'Atlas claims build', 'Brightpath portal', '7,100,000', '₦', 'billing by contract stage', 'Your role does not allow this', 'We could not find that record']) expect(text).not.toContain(word);
    expect(paths().some((p) => p.startsWith('/api/v1/reports/'))).toBe(false);
    expect(paths()).toContain(`/api/v1/projects/${uuidOf(caseId)}/money`);
  });

  it('pm on P-0104 and anyone on P-0099: the project read is refused; no money or report read', async () => {
    persona = 'pm';
    await open('P-0104');
    expect(screen.getByText('You can’t open this project')).toBeTruthy();
    expect(paths()).toEqual(['/api/v1/projects/P-0104']);
    document.body.innerHTML = '';
    persona = 'finance_lead';
    calls = [];
    await open('P-0099');
    expect(paths()).toEqual(['/api/v1/projects/P-0099']);
    expect(document.body.textContent).not.toContain('₦');
  });

  it('401 on the money read signs in back to the money tab', async () => {
    respond = (url) => (url.pathname.endsWith('/money') ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : fromMock(url, persona));
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fprojects%2FP-0101%2Fmoney');
  });

  it('401 on the report read signs in too', async () => {
    respond = (url) => (url.pathname.startsWith('/api/v1/reports/') ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : fromMock(url, persona));
    await open();
    await until(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fprojects%2FP-0101%2Fmoney'));
  });

  it.each([
    ['a 500', () => json(500, { code: 'server_error', message: 'Boom' })],
    ['a network failure', () => Promise.reject(new TypeError('offline'))],
    ['a body without money', () => json(200, { items: fixture('projects/money/P-0101.json').money, as_of: '2026-11-12T15:40:00Z' })],
    ['a malformed row', () => json(200, { items: [], as_of: '2026-11-12T15:40:00Z', money: [{ position: 1, stage: 'Stage 1 · kick-off', amount: { amount: '3000000.00', currency: 'NGN', unknown: false } }, { position: 2, stage: 'Stage 2 · UAT', amount: '4250000.00' }] })],
  ] as const)('money read failure (%s): the error card and Try again, nothing partial', async (_, answer) => {
    respond = (url) => (url.pathname.endsWith('/money') ? answer() : fromMock(url, persona));
    await open();
    await until(() => expect(screen.getByRole('alert').textContent).toContain('We couldn’t load this project’s money. Your work is safe; nothing was changed.'));
    expect(panel().querySelector('table')).toBeNull();
    expect(document.body.textContent).not.toContain('Stage 1 · kick-off');
    expect(paths().some((p) => p.startsWith('/api/v1/reports/'))).toBe(false);
    respond = (url) => fromMock(url, persona);
    const before = paths().length;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(bodyRows()).toHaveLength(4));
    expect(paths().slice(before)).toEqual([`/api/v1/projects/${uuidOf('P-0101')}/money`, '/api/v1/reports/R-0101']);
  });

  it('P-0105 empty: "No contract stages yet", no table, no total, no aside', async () => {
    await open('P-0105');
    expect(within(panel()).getByRole('heading', { level: 2, name: 'No contract stages yet' })).toBeTruthy();
    expect(within(panel()).getByText('Stages appear here once the SOW is signed.')).toBeTruthy();
    expect(panel().querySelector('table')).toBeNull();
    expect(screen.queryByRole('complementary')).toBeNull();
    expect(paths()).toEqual(['/api/v1/projects/P-0105', `/api/v1/projects/${uuidOf('P-0105')}/money`]);
  });
});

describe('round 2: malformed bodies, Unknown amounts with a figure, phone report states', () => {
  it('TECH-1-1: a report figure without sources keeps the four rows and shows the report error with Try again', async () => {
    const report = fixture('reports/R-0101.json') as { figures: Record<string, unknown>[] };
    delete report.figures[0].sources;
    respond = (url) => (url.pathname.startsWith('/api/v1/reports/') ? json(200, report) : fromMock(url, persona));
    await open('P-0101', '?figure=FIG-0101-S2');
    expect(bodyRows()).toHaveLength(4);
    expect(panel().querySelectorAll('tbody a[href*="figure="]')).toHaveLength(0);
    expect(aside().textContent).toContain('We couldn’t load where these figures come from.');
    expect(within(aside()).getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it.each([
    ['a numeric amount', (rows: Body[]) => (rows[0].amount = { amount: 3000000, currency: 'NGN', unknown: false })],
    ['a numeric owed amount', (rows: Body[]) => (rows[0].paid = { status: 'part_paid', owed: { amount: 1, currency: 'NGN', unknown: false } })],
    ['an invoice without a reference', (rows: Body[]) => (rows[0].invoice = { work_id: 'W-1713' })],
    ['a paid status that is not text', (rows: Body[]) => (rows[0].paid = { status: { paid: true } })],
  ] as const)('TECH-1-1: a money row with %s shows the error card, not a crash or a partial table', async (_, spoil) => {
    const body = fixture('projects/money/P-0101.json') as { money: Body[] };
    spoil(body.money);
    respond = (url) => (url.pathname.endsWith('/money') ? json(200, body) : fromMock(url, persona));
    await open();
    await until(() => expect(screen.getByRole('alert').textContent).toContain('We couldn’t load this project’s money.'));
    expect(panel().querySelector('table')).toBeNull();
  });

  it('TECH-1-2: an Unknown amount whose figure the report has is a link, and the panel shows both values', async () => {
    const body = fixture('projects/money/P-0101.json') as { money: Body[] };
    body.money[3].figure_id = 'FIG-0101-S4';
    const report = fixture('reports/R-0101.json') as { figures: Body[] };
    report.figures.push({ id: 'FIG-0101-S4', label: 'Stage 4 · hypercare amount', value: { amount: '1500000.00', currency: 'NGN', unknown: false }, sources: ['Hypercare quote Q-17'] });
    respond = (url) => (url.pathname.endsWith('/money') ? json(200, body) : url.pathname.startsWith('/api/v1/reports/') ? json(200, report) : fromMock(url, persona));
    await open('P-0101', '?figure=FIG-0101-S4');
    const link = within(cell(3, 1)).getByRole('link');
    expect(link.getAttribute('href')).toBe('/projects/P-0101/money?figure=FIG-0101-S4');
    expect(link.querySelector('.psl-unknown')!.textContent).toBe('Unknown');
    expect(link.getAttribute('aria-current')).toBe('true');
    expect(aside().querySelector('.psl-callout--warning')!.textContent).toBe('These figures differ: the table shows Unknown; the report shows ₦1,500,000.00.');
  });

  it('UX-1-1: on phones a failed report shows its error and Try again under the cards; a refused one says so', async () => {
    phone();
    await open('P-0103');
    expect(panel().querySelectorAll('.money__card')).toHaveLength(4);
    expect(panel().textContent).toContain('We couldn’t load where these figures come from. Your work is safe; nothing was changed.');
    const before = paths().length;
    fireEvent.click(within(panel()).getByRole('button', { name: 'Try again' }));
    await until(() => expect(paths().length).toBe(before + 1));
    expect(paths().slice(before)).toEqual(['/api/v1/reports/R-0103']);
    expect(screen.queryByText('Tap an amount to see where it comes from')).toBeNull();
    document.body.innerHTML = '';
    calls = [];
    await open('P-0106');
    expect(within(panel()).getByText('You can’t see where these figures come from.')).toBeTruthy();
    expect(document.body.textContent).not.toContain('secret');
  });
});
