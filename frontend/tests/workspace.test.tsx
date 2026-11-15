// @vitest-environment jsdom
// F-17 Part A: the line workspace drawn from E-WORK-ITEM `workspace` alone (PROPOSAL D-LINE-WORKSPACE, contract
// mock only). Fixtures W-2001 to W-2005 copy board wording; W-2010 is an item without a workspace.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { STATUS_WORDS, RECEIPT_WORDS, SEVERITY_WORDS } from '@/features/workspace/labels';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

// A busy machine can take more than the default second to render a page; nothing here waits on a timer.
configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2001',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (id: string): WorkItem => read(`work/${id}.json`);
const me = read('me.finance_lead.json');
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const requests = () => fetchStub.mock.calls.map(([request]) => `${request.method} ${new URL(request.url).pathname}`);

function serve(body: WorkItem) {
  fetchStub.mockImplementation(async (request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    return json(200, body);
  });
}

beforeEach(() => {
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', withoutBellFeed(fetchStub));
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

async function open(body: WorkItem) {
  serve(body);
  const view = render(
    <AppShell>
      <WorkItemView id={body.id} tab="overview" />
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
  await screen.findByRole('heading', { level: 1, name: body.title });
  return view;
}

const workspace = () => document.querySelector('.ws') as HTMLElement;
const section = (title: string) => screen.getByRole('region', { name: title });
const rows = (title: string) => within(section(title)).getAllByRole('listitem');
const text = (el: Element | null) => el?.textContent ?? '';

describe('unchanged without a workspace', () => {
  it('W-2010 draws exactly what W-1002 draws, and no workspace', async () => {
    const before = await open(item('W-1002'));
    const reference = before.container.innerHTML.replaceAll('W-1002', 'W-2010');
    before.unmount();
    const after = await open(item('W-2010'));
    expect(after.container.innerHTML).toBe(reference);
    expect(workspace()).toBeNull();
  });

  for (const id of ['W-1701', 'W-1901']) {
    it(`${id} carries no workspace and draws none`, async () => {
      expect(item(id).workspace).toBeUndefined();
      await open(item(id));
      expect(workspace()).toBeNull();
    });
  }
});

describe('header from data', () => {
  it('W-2001 shows subtitle, status word, byline, version, crumbs and the agent note; one h1 and no repeated title', async () => {
    const body = item('W-2001');
    await open(body);
    const ws = within(workspace());
    const data = body.workspace!;
    // D-73: the frame's header, above the workspace, draws the subtitle, the status word and the crumbs
    expect(screen.getByText(data.subtitle!)).toBeTruthy();
    expect(screen.getByText(data.status!.label).className).toContain('psl-tag--person');
    expect(workspace().contains(screen.getByText(data.subtitle!))).toBe(false);
    expect(ws.getByText(data.byline!)).toBeTruthy();
    expect(ws.getByText(data.version!.label)).toBeTruthy();
    const trail = screen.getByRole('navigation', { name: 'Where this sits' });
    expect(workspace().contains(trail)).toBe(false);
    expect(within(trail).getAllByRole('listitem').map(text)).toEqual(data.context!.crumbs!.map((c) => c.label));
    expect(within(trail).queryAllByRole('link')).toHaveLength(0);
    expect(within(trail).getAllByRole('listitem').at(-1)?.getAttribute('aria-current')).toBe('location');
    for (const line of data.agent_note!.lines) expect(ws.getByText(line)).toBeTruthy();
    expect(text(workspace().querySelector('.ws-agentnote strong'))).toBe('Tola');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    // the workspace title equals the item title: it is not drawn again
    expect(ws.queryByRole('heading', { name: data.title })).toBeNull();
  });

  it('W-2002 draws the workspace title as an h2 because it differs from the item title', async () => {
    await open(item('W-2002'));
    expect(within(workspace()).getByRole('heading', { level: 2, name: 'Requirements' })).toBeTruthy();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    // sections sit under the workspace h2
    expect(within(workspace()).getByRole('heading', { level: 3, name: 'Pricing lines' })).toBeTruthy();
  });

  it('W-2005 returns no header field and draws no header', async () => {
    await open(item('W-2005'));
    expect(workspace().querySelector('.ws-header')).toBeNull();
    expect(within(workspace()).queryByRole('navigation')).toBeNull();
  });
});

describe('the nine section kinds, in returned order', () => {
  it('sections follow the returned order on every fixture', async () => {
    for (const id of ['W-2001', 'W-2002', 'W-2003', 'W-2004']) {
      const body = item(id);
      const view = await open(body);
      const titles = [...workspace().querySelectorAll('.ws-section__head')].map(text);
      expect(titles, id).toEqual(body.workspace!.sections.map((s) => s.title));
      view.unmount();
    }
  });

  it('facts: label and value pairs', async () => {
    await open(item('W-2001'));
    const pairs = [...section('This week').querySelectorAll('.ws-fact')].map((f) => [text(f.querySelector('dt')), text(f.querySelector('dd'))]);
    expect(pairs).toEqual([
      ['Week', '5–11 Nov 2026'],
      ['Client', 'Lagoon Health'],
      ['Audience', 'Client'],
    ]);
  });

  it('text: each part with its cites; a cite label stands for the list', async () => {
    await open(item('W-2001'));
    const parts = rows('Report v1 · written by Tunde Bello, assembled by Tola');
    expect(parts.map(text)).toEqual([
      'Status · Milestone 2 complete; go-live work started2 RECORDS (Milestone 2 sign-off, UAT-0031)',
      'Risks · Login fails on older Android phones (high)ISS-0233',
      'Timeline · Go-live 4 Dec, subject to the login fixMIN-0141',
      'Next steps · Fix verification; go-live plan2 ACTIONS (ACT-0412, ACT-0413)',
    ]);
    // a work item cite is a link to its page; a document has no page and stays text
    expect(within(parts[1]).getByRole('link', { name: 'ISS-0233' }).getAttribute('href')).toBe('/work/W-1404');
    expect(within(parts[2]).queryByRole('link')).toBeNull();
  });

  it('recipients: name, channel, receipt word and WAT time', async () => {
    await open(item('W-2001'));
    expect(rows('Who receives it').map(text)).toEqual([
      'Dr Amaka ObiEmailReceived 12 Nov 15:10',
      'Lagoon Health projects inboxEmailNot yet',
      'Chinedu EzeWhatsAppUncertain 12 Nov 15:12',
      'Lagoon Health board inboxEmailFailed 12 Nov 15:13',
      'Funke AdeEmailUnknown',
    ]);
  });

  it('timeline: WAT time, words, agent or owner, detail', async () => {
    await open(item('W-2001'));
    expect(rows('What happened').map(text)).toEqual([
      'Approved by Kemi AdebayoKemi Adebayo12 Nov 14:58',
      'Emailed to Dr Amaka ObiTolaDelivered 15:1012 Nov 15:10',
      'Emailed to Lagoon Health projects inboxTola12 Nov 15:11',
    ]);
  });

  it('table: header from columns, cells by column kind, links only for app paths', async () => {
    await open(item('W-2002'));
    const pricing = section('Pricing lines');
    expect(within(pricing).getAllByRole('columnheader').map(text)).toEqual(['Line', 'Amount', 'Due', 'Days', 'Work item']);
    const [first, second] = within(pricing).getAllByRole('row').slice(1);
    expect(within(first).getAllByRole('cell').map(text)).toEqual(['Discovery and design', '₦4,250,000.00', '28 Nov 2026', '12', 'WCR-0216']);
    expect(within(first).getByRole('link', { name: 'WCR-0216' }).getAttribute('href')).toBe('/work/W-2001');
    expect(within(second).queryByRole('link')).toBeNull();
    const requirements = section('Requirements');
    // the first column holds the Accept selected checkboxes (Part B)
    expect(within(requirements).getAllByRole('columnheader').map(text)).toEqual(['Select', '#', 'Requirement', 'Suggested answer', 'Status']);
    const r07 = within(requirements).getAllByRole('row')[1];
    expect(within(r07).getAllByRole('cell').map(text)).toEqual([
      '',
      'R-07',
      'Loan officers approve applications above a set amount RFP p.6',
      'Approvals above a configurable threshold go to a named loan officer; every decision is recorded.',
      'Suggested by Tola',
    ]);
    expect(within(r07).getByText('Suggested by Tola').className).toContain('psl-tag--agent');
    // the table scrolls inside its own frame
    expect(requirements.querySelector('.psl-tablewrap')).not.toBeNull();
  });

  it('a crafted link to https://x.example never becomes an anchor', async () => {
    const body = item('W-2002');
    const pricing = body.workspace!.sections[1];
    const crafted = [
      { work_id: 'https://x.example' },
      { case_id: '//x.example' },
      { label: 'x', reference: 'https://x.example' },
      { document_id: 'https://x.example', label: 'https://x.example' },
      { work_id: 'javascript:alert(1)', label: 'js' },
      { work_id: '/\\x.example', label: 'slash' },
    ];
    pricing.items = crafted.map((link, i) => ({ id: `X-${i}`, cells: [{ column: 'work', link: { reference: 'https://x.example', ...link } }] }));
    await open(body);
    const table = section('Pricing lines');
    expect(table.querySelectorAll('a')).toHaveLength(0);
    expect(within(table).getAllByRole('row')).toHaveLength(crafted.length + 1);
  });

  it('suggestions: words, detail, agent, tag and cites', async () => {
    await open(item('W-2002'));
    const [s07, s08] = rows('Review Tola’s suggestion');
    expect(text(s07)).toBe(
      'R-07 · RFP p.6Approvals above a configurable threshold go to a named loan officer; every decision is recorded.' +
        'From PSL’s past answer: Harmattan Bank RFP 2025 · R-12 · that bid was wonSuggested by Tola' +
        'Accept answerEdit answer',
    );
    expect(within(s07).getByText('Suggested by Tola').className).toContain('psl-tag--agent');
    expect(text(s08)).toContain('Suggested by Tola');
    expect(section('Review Tola’s suggestion').querySelector('.ws-meta')?.textContent).toBe('Tola');
  });

  it('suggestions: the reference, the answer box and the source beneath, nothing said twice (UI-2-6)', async () => {
    await open(item('W-2002'));
    const [s07] = rows('Review Tola’s suggestion');
    expect(text(s07.querySelector('.ws-sugg__ref'))).toBe('R-07 · RFP p.6');
    expect(text(s07.querySelector('.ws-sugg__answer'))).toContain('Approvals above a configurable threshold');
    expect(within(s07).getAllByText(/RFP p\.6/)).toHaveLength(1);
  });

  it('a section note is an amber warning box under the section; money has no headline style (UI-2-7, D-63)', async () => {
    await open(item('W-2004'));
    const forecast = section('Forecast · 6 months');
    const note = forecast.querySelector('.ws-note');
    expect(note?.className).toContain('psl-callout--warning');
    expect(forecast.lastElementChild?.lastElementChild).toBe(note);
    expect(forecast.querySelector('.psl-amount')).toBeNull();
  });

  it('checklist: status word, owner, due and who holds it ("You" when it is you)', async () => {
    await open(item('W-2003'));
    expect(rows('What closure needs').map(text)).toEqual([
      'Go-live acceptedDone',
      'Hypercare qualifiedOwner: Tunde Bello (PM)In progress',
      'Archive verifiedDone',
      'Handover acknowledged · 2 gapsOwner: Ngozi Bello (Client) · Held by Tamarind LoansHeld',
      'Retrospective savedHeld by YouNot yet · Due 14 May 2027',
      'Finance confirmationUnknown',
    ]);
    // D-63: no check marks, the status stays in words
    for (const li of rows('What closure needs')) expect(li.querySelector('.ws-mark')).toBeNull();
  });

  it('findings: words, detail, severity and cites', async () => {
    await open(item('W-2003'));
    expect(rows('Open findings').map(text)).toEqual([
      'Login fails on older Android phonesSeen on 3 of 12 test devicesHighISS-0233',
      'Two handover documents are missing a versionMedium2 RECORDS (HND-0012, HND-0013)',
      'Retrospective template is the test templateLow',
      'Finance confirmation source isn’t defined yetIt shows Unknown, never assumed done.Info',
    ]);
  });

  it('figures: label, money or value, detail', async () => {
    await open(item('W-2004'));
    expect(rows('January').map(text)).toEqual([
      'Opening balance₦7,800,000.00',
      'Receipts inKola Foods hasn’t confirmed its payment dateUnknown',
      'Payments out₦19,800,000.00',
      'Months of runway1.4',
      'Restricted',
    ]);
  });
});

describe('item words are words, not colour alone', () => {
  it('every checklist status on W-2003 and every receipt on W-2001 reads as a word', async () => {
    const view = await open(item('W-2003'));
    const page = text(workspace());
    for (const status of Object.keys(STATUS_WORDS) as (keyof typeof STATUS_WORDS)[]) expect(page, status).toContain(STATUS_WORDS[status]);
    for (const severity of Object.keys(SEVERITY_WORDS) as (keyof typeof SEVERITY_WORDS)[]) expect(page, severity).toContain(SEVERITY_WORDS[severity]);
    view.unmount();
    await open(item('W-2001'));
    const receipts = rows('Who receives it');
    expect(receipts.map((li) => text(li.querySelector('.ws-word')))).toEqual(Object.values(RECEIPT_WORDS));
    expect(text(receipts[2])).not.toMatch(/received/i);
  });

  it('an enum value the frame does not know is shown raw, never hidden', async () => {
    const body = item('W-2003');
    const gates = body.workspace!.sections[1];
    Object.assign(gates.items[0], { status: 'waiting_on_vendor' });
    Object.assign(body.workspace!.sections[2].items[0], { severity: 'critical' });
    await open(body);
    expect(text(rows('Release gates')[0])).toContain('waiting_on_vendor');
    expect(text(rows('Open findings')[0])).toContain('critical');
  });
});

describe('INV-UNKNOWN', () => {
  it('W-2004: unknown and missing amounts, an unknown due and an unknown date read Unknown, never 0, ₦0, a dash or blank', async () => {
    await open(item('W-2004'));
    const jan = within(section('Forecast · 6 months')).getAllByRole('row')[3];
    const cells = within(jan).getAllByRole('cell').map(text);
    // In is unknown; Closing has no amount at all: both read Unknown
    expect(cells).toEqual(['Jan', '₦7,800,000.00', 'Unknown', '₦19,800,000.00', 'Unknown']);
    const kola = within(section('Receipts')).getAllByRole('row')[2];
    const receipt = within(kola).getAllByRole('cell').map(text);
    expect(receipt).toEqual(['Kola Foods', 'Unknown', 'Unknown', 'Bisi Ade']);
    expect(text(rows('January')[1])).toMatch(/Unknown$/);
    expect(text(rows('Payment dates')[0])).toBe('Kola Foods payment dateUnknown');
    for (const value of [cells[2], cells[4], receipt[1], receipt[2]]) expect(value).not.toMatch(/^(0|₦0(\.00)?|-|—|)$/);
    expect(text(workspace())).not.toMatch(/₦0\.00|₦0\b/);
  });
});

describe('INV-RESTRICTED', () => {
  it('W-2004: a restricted section shows only its label; a restricted item and cell read Restricted; nothing hidden is drawn', async () => {
    const body = item('W-2004');
    await open(body);
    const payroll = section('Payroll lines');
    expect(text(payroll.querySelector('.ws-section__body'))).toBe('Payroll lines are restricted to Finance Leads.');
    expect(within(payroll).queryAllByRole('listitem')).toHaveLength(0);
    const dec = within(section('Receipts')).getAllByRole('row')[1];
    expect(within(dec).getAllByRole('cell').at(-1)?.textContent).toBe('Restricted');
    const page = document.body.textContent ?? '';
    for (const hidden of ['HIDDEN-ROW-TEXT', 'HIDDEN-ROW-DETAIL', 'HIDDEN-CITE', 'HIDDEN-CITE-LABEL', 'HIDDEN-SECTION-NOTE', 'HIDDEN-SECTION-COVERAGE', 'HIDDEN-ITEM-LABEL', 'HIDDEN-ITEM-DETAIL', '9,999,999', '5,555,555']) {
      expect(page, hidden).not.toContain(hidden);
    }
    // the cell's own words are not drawn either
    expect(text(dec)).not.toContain('Ada Okafor');
    expect(document.querySelectorAll('a[href="/work/W-1001"]')).toHaveLength(0);
  });

  it('a restricted section without its own label reads Restricted', async () => {
    const body = item('W-2004');
    delete body.workspace!.sections.find((s) => s.key === 'payroll')!.restricted_label;
    await open(body);
    expect(text(section('Payroll lines').querySelector('.ws-section__body'))).toBe('Restricted');
  });
});

describe('a blank value is Unknown (TECH-1-3)', () => {
  it('a fact or figure whose value is empty or blank reads Unknown', async () => {
    const body = item('W-2001');
    const facts = { key: 'f', kind: 'facts', title: 'Blank facts', items: [{ id: 'a', label: 'Empty', value: '' }, { id: 'b', label: 'Spaces', value: '   ' }] };
    const figures = { key: 'g', kind: 'figures', title: 'Blank figures', items: [{ id: 'c', label: 'Empty', value: '' }] };
    await open({ ...body, workspace: { ...body.workspace!, sections: [facts, figures] } } as WorkItem);
    expect([...section('Blank facts').querySelectorAll('dd')].map(text)).toEqual(['Unknown', 'Unknown']);
    expect(text(section('Blank figures').querySelector('.ws-row__end'))).toBe('Unknown');
  });
});

describe('as_of, coverage and sample', () => {
  it('W-2004 shows as_of in WAT and the coverage text; the record’s sample label shows when switched on', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    await open(item('W-2004'));
    expect(text(section('Forecast · 6 months').querySelector('.ws-meta'))).toBe('As of 14 Nov 10:40 WAT3 of 4 bank accounts reconciled');
    expect(text(section('January').querySelector('.ws-meta'))).toBe('ChidiAs of 14 Nov 10:40 WATReceipts from 11 of 12 clients');
    expect(screen.getAllByText('SAMPLE DATA').length).toBeGreaterThan(0);
  });

  it('W-2001 returns no as_of or coverage and draws none; an item with sample false draws no sample label', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    vi.stubEnv('NEXT_PUBLIC_API_MODE', 'live');
    const body = { ...item('W-2001'), sample: false };
    await open(body);
    expect(text(workspace())).not.toContain('As of');
    expect(workspace().querySelector('.ws-meta')).toBeNull();
    expect(screen.queryByText('SAMPLE DATA')).toBeNull();
  });
});

describe('empty', () => {
  it('W-2005: an empty section draws its title and "Nothing here yet."', async () => {
    await open(item('W-2005'));
    expect(text(section('Actions'))).toBe('ActionsNothing here yet.');
  });

  it('a workspace with no sections and no steps draws only its (empty) frame and throws nothing', async () => {
    const body = item('W-2005');
    body.workspace = { line_key: 'minutes', sections: [] };
    await open(body);
    expect(workspace()).not.toBeNull();
    expect(workspace().textContent).toBe('');
  });
});

describe('paging and filters are inert', () => {
  it('W-2002 shows the filter, total and Show more disabled with the sentence, and pressing them sends nothing', async () => {
    await open(item('W-2002'));
    const table = section('Requirements');
    const filters = within(table).getByRole('group', { name: 'Requirements filters' });
    expect(within(filters).getByRole('button', { name: 'Filter' })).toHaveProperty('disabled', true);
    expect(within(filters).getByRole('button', { name: 'Status: Suggested by Tola' })).toHaveProperty('disabled', true);
    expect(text(filters)).toContain('4 of 64');
    const more = within(table).getByRole('button', { name: 'Show more' });
    expect(more).toHaveProperty('disabled', true);
    expect(document.getElementById(more.getAttribute('aria-describedby')!)?.textContent).toBe('More rows aren’t available yet.');
    const before = requests();
    for (const button of within(table).getAllByRole('button')) fireEvent.click(button);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(requests()).toEqual(before);
    expect(before.filter((r) => !r.endsWith('/api/v1/me'))).toEqual(['GET /api/v1/work/W-2002']);
  });

  it('the "more rows" line shows once per section and both controls point at it (UX-1-3)', async () => {
    await open(item('W-2002'));
    const table = section('Requirements');
    expect(within(table).getAllByText('More rows aren’t available yet.')).toHaveLength(1);
    const filters = within(table).getByRole('group', { name: 'Requirements filters' });
    expect(filters.getAttribute('aria-describedby')).toBe(within(table).getByRole('button', { name: 'Show more' }).getAttribute('aria-describedby'));
  });

  it('a section with only a cursor shows the line beside Show more, once', async () => {
    const body = item('W-2002');
    const only = { ...body.workspace!.sections[0], filters: undefined, total: undefined };
    await open({ ...body, workspace: { ...body.workspace!, sections: [only] } });
    const table = section('Requirements');
    expect(within(table).getAllByText('More rows aren’t available yet.')).toHaveLength(1);
    expect(document.getElementById(within(table).getByRole('button', { name: 'Show more' }).getAttribute('aria-describedby')!)?.textContent).toBe('More rows aren’t available yet.');
  });

  it('a section without filters, total or cursor draws none of them', async () => {
    await open(item('W-2001'));
    expect(within(workspace()).queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(within(workspace()).queryByRole('group')).toBeNull();
  });
});

describe('the renderer never asks /me who may act', () => {
  it('the workspace sends no request of its own (only the frame’s E-ME and the item read)', async () => {
    await open(item('W-2003'));
    expect(requests().filter((r) => !r.endsWith('/api/v1/me'))).toEqual(['GET /api/v1/work/W-2003']);
    expect(requests().filter((r) => r.endsWith('/api/v1/me'))).toHaveLength(1);
  });
});
