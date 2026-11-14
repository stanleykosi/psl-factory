// @vitest-environment jsdom
import { readFileSync } from 'node:fs';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import axe from 'axe-core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { StartWorkButton } from '@/features/start-work/StartWorkButton';
import type { Field, Line, Lines } from '@/features/start-work/types';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { createStartWorkMock } from '../mock/start-work.mjs';

const nav = vi.hoisted(() => ({ pathname: '/my-work', push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
}));

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Post = { headers: Headers; body: Record<string, unknown> & { intake: Record<string, unknown>; idempotency_key: string } };
type Handler = (request: Request, url: URL) => Promise<Response> | Response | undefined;

let mock: ReturnType<typeof createStartWorkMock>;
let persona: string;
let posts: Post[];
let gets: URL[];
/** Per-test override: return a Response to answer instead of the contract mock, or undefined to fall through. */
let override: Handler | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;

function operationOf(request: Request, url: URL) {
  if (url.pathname === '/api/v1/lines') return 'E-LINES';
  if (url.pathname.startsWith('/api/v1/lines/')) return 'E-LINE-OPTIONS';
  if (url.pathname === '/api/v1/work' && request.method === 'POST') return 'E-WORK-START';
  throw new Error(`unexpected request ${request.method} ${url.pathname}`);
}

beforeEach(() => {
  nav.push.mockReset();
  mock = createStartWorkMock(openapi);
  persona = 'pm';
  posts = [];
  gets = [];
  override = undefined;
  setCsrfToken('mock-csrf-pm');
  fetchStub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const raw = request.method === 'POST' ? await request.clone().text() : '';
    if (request.method === 'POST') posts.push({ headers: request.headers, body: JSON.parse(raw) });
    else gets.push(url);
    const custom = await override?.(request, url);
    if (custom) return custom;
    const [status, body] = mock.handle(operationOf(request, url), { url, raw, persona });
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const lineGets = () => gets.filter((u) => u.pathname === '/api/v1/lines');
const optionGets = () => gets.filter((u) => u.pathname.startsWith('/api/v1/lines/'));
const dialog = () => screen.getByRole('dialog');
const startButton = () => within(document.body).getAllByRole('button', { name: 'Start work' })[0];

async function openMain() {
  render(<StartWorkButton variant="bar" />);
  fireEvent.click(startButton());
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
}

async function openChooser() {
  render(<StartWorkButton variant="bar" />);
  fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
}

async function pick(field: string, option: string) {
  fireEvent.click(within(dialog()).getByRole('combobox', { name: field }));
  const choice = await within(dialog()).findByRole('option', { name: new RegExp(`^${option}`) });
  fireEvent.click(choice);
}

/** The invoice drawer with Lagoon chosen, and optionally a milestone. */
async function invoiceWith(milestone?: string) {
  await openMain();
  await pick('Project', 'Lagoon Health · patient app');
  if (milestone) await pick('Completed milestone', milestone);
}

const press = (name: string | RegExp) => fireEvent.click(within(dialog()).getByRole('button', { name }));

describe('the main button and the chooser', () => {
  it('pm: the main button opens the invoice drawer directly, with no chooser step and no "change line"', async () => {
    await openMain();
    expect(dialog().getAttribute('aria-modal')).toBe('true');
    expect(screen.getByRole('dialog', { name: 'Invoice preparation and delivery' })).toBeTruthy();
    expect(screen.queryByText('Choose a line')).toBeNull();
    expect(within(dialog()).queryByRole('button', { name: 'change line' })).toBeNull();
    expect(within(dialog()).getByRole('button', { name: 'Cancel' })).toBeTruthy();
    expect(within(dialog()).getByRole('button', { name: 'Start the invoice' })).toBeTruthy();
    expect(lineGets()).toHaveLength(1);
  });

  it('ceo (no default_line): the main button opens "Choose a line" with all 8 lines', async () => {
    persona = 'ceo';
    await openMain();
    expect(screen.getByRole('dialog', { name: 'Choose a line' })).toBeTruthy();
    expect(within(dialog()).getByText('START WORK · Step 1 of 2')).toBeTruthy();
    expect(within(dialog()).getByText('LINES YOU CAN START · 8')).toBeTruthy();
    expect(within(dialog()).getAllByRole('radio')).toHaveLength(8);
  });

  it('the chooser groups lines, shows subtitles, searches, and links to Tola', async () => {
    await openChooser();
    for (const group of ['Client delivery', 'Issues and changes', 'Reporting']) {
      expect(within(dialog()).getByRole('group', { name: group })).toBeTruthy();
    }
    const invoice = within(dialog()).getByRole('radio', { name: /Invoice preparation and delivery/ });
    expect(invoice.closest('label')!.textContent).toBe('Invoice preparation and deliveryFrom a completed milestone');
    expect(within(dialog()).getByRole('link', { name: /Describe it to Tola/ }).getAttribute('href')).toBe('/assistant');
    expect(within(dialog()).getByText('You only see lines your roles let you start. Ask your Lead if one is missing.')).toBeTruthy();
    const search = within(dialog()).getByRole('searchbox', { name: 'Find a line' });
    await waitFor(() => expect(document.activeElement).toBe(search));
    fireEvent.change(search, { target: { value: 'minutes' } });
    expect(within(dialog()).getAllByRole('radio').map((r) => r.closest('label')!.querySelector('strong')!.textContent)).toEqual([
      'Formal minutes and action handoff',
    ]);
    fireEvent.change(search, { target: { value: 'TUESDAY' } });
    expect(within(dialog()).getAllByRole('radio')).toHaveLength(1);
    fireEvent.change(search, { target: { value: 'zzz' } });
    expect(within(dialog()).getByText('No line matches "zzz".')).toBeTruthy();
    expect(within(dialog()).getByText('LINES YOU CAN START · 8')).toBeTruthy();
  });

  it('Next is off until a line is chosen, opens it with "change line", and change line goes back', async () => {
    await openChooser();
    const next = within(dialog()).getByRole('button', { name: 'Next' }) as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    fireEvent.click(within(dialog()).getByRole('radio', { name: /Formal minutes/ }));
    expect(next.disabled).toBe(false);
    fireEvent.click(next);
    expect(screen.getByRole('dialog', { name: 'Formal minutes and action handoff' })).toBeTruthy();
    expect(within(dialog()).getByText(/Line chosen from the Start work menu/)).toBeTruthy();
    expect(within(dialog()).getByRole('button', { name: 'Start minutes' })).toBeTruthy();
    expect(within(dialog()).getByRole('button', { name: 'Back' })).toBeTruthy();
    fireEvent.click(within(dialog()).getByRole('button', { name: 'change line' }));
    expect(screen.getByRole('dialog', { name: 'Choose a line' })).toBeTruthy();
  });

  it('only lines E-LINES returned are offered (finance_lead: exactly 1; a /me key missing from E-LINES is absent)', async () => {
    persona = 'finance_lead';
    await openChooser();
    expect(within(dialog()).getByText('LINES YOU CAN START · 1')).toBeTruthy();
    expect(within(dialog()).getAllByRole('radio').map((r) => r.getAttribute('value'))).toEqual(['invoice']);
  });

  it('E-LINES is read on every press, never before', async () => {
    render(<StartWorkButton variant="bar" />);
    expect(fetchStub).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
    await screen.findByText('LINES YOU CAN START · 8');
    fireEvent.click(within(dialog()).getByRole('button', { name: 'Back' }));
    fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
    await screen.findByText('LINES YOU CAN START · 8');
    expect(lineGets()).toHaveLength(2);
  });

  it('the phone "+ Start" opens the chooser even for pm', async () => {
    render(<StartWorkButton variant="phone" />);
    const plus = screen.getByRole('button', { name: 'Start work' });
    expect(plus.textContent).toBe('Start');
    fireEvent.click(plus);
    expect(await screen.findByRole('dialog', { name: 'Choose a line' })).toBeTruthy();
  });

  it('Esc closes and focus returns to the button that opened it; Tab stays inside', async () => {
    await openChooser();
    const chevron = screen.getByRole('button', { name: 'More ways to start' });
    expect(chevron.getAttribute('aria-expanded')).toBe('true');
    const close = within(dialog()).getByRole('button', { name: 'Close' });
    const back = within(dialog()).getByRole('button', { name: 'Back' });
    back.focus();
    // Next is disabled, so Back is the last focusable: Tab wraps to Close.
    fireEvent.keyDown(back, { key: 'Tab' });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(back);
    fireEvent.keyDown(dialog(), { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(chevron));
  });
});

describe('chooser states', () => {
  it('loading shows a status while E-LINES is pending', async () => {
    let resolve!: (r: Response) => void;
    override = () => new Promise((r) => (resolve = r));
    render(<StartWorkButton variant="bar" />);
    fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
    expect(within(dialog()).getByRole('status').textContent).toBe('Loading…');
    await waitFor(() => expect(resolve).toBeTypeOf('function'));
    await act(async () => resolve(json(200, { items: [], as_of: '2026-11-14T09:00:00Z' })));
  });

  it('no lines shows the empty message and the Tola link', async () => {
    persona = 'none';
    await openChooser();
    expect(within(dialog()).getByText('There are no lines you can start right now.')).toBeTruthy();
    expect(within(dialog()).getByRole('link', { name: /Describe it to Tola/ })).toBeTruthy();
  });

  it('a 500 shows the error with Try again, which reads E-LINES again', async () => {
    override = (_, url) => (url.pathname === '/api/v1/lines' && lineGets().length === 1 ? new Response('<html>', { status: 500 }) : undefined);
    await openChooser();
    expect(within(dialog()).getByText('We couldn’t load your lines. Nothing was started.')).toBeTruthy();
    fireEvent.click(within(dialog()).getByRole('button', { name: 'Try again' }));
    await within(dialog()).findByText('LINES YOU CAN START · 8');
    expect(lineGets()).toHaveLength(2);
  });

  it('a 401 shows signed out with a sign-in link back to this page', async () => {
    override = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await openChooser();
    expect(within(dialog()).getByText('You’re signed out.')).toBeTruthy();
    expect(within(dialog()).getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fmy-work');
  });

  it('a 403 shows the error message', async () => {
    override = () => json(403, { code: 'forbidden', message: 'Your role does not allow this.' });
    await openChooser();
    expect(within(dialog()).getByText('Your role does not allow this.')).toBeTruthy();
  });
});

const synthetic = (intake: Field[], extra: Partial<Line> = {}): Lines => ({
  items: [{ key: 'synthetic', title: 'Every kind', group: 'Test', case_scope: 'fixed', case_id: 'C-T', case_revision: 1, intake, ...extra }],
  default_line: 'synthetic',
  as_of: '2026-11-14T09:00:00Z',
});
const KINDS: Field[] = [
  { name: 'text', label: 'Text', type: 'text', required: true, help: 'Text help', placeholder: 'Type here' },
  { name: 'long_text', label: 'Long text', type: 'long_text', required: false, placeholder: 'Say more' },
  { name: 'date', label: 'Date', type: 'date', required: true, help: 'Date help' },
  { name: 'date_range', label: 'Range', type: 'date_range', required: true },
  { name: 'period', label: 'Period', type: 'period', required: false },
  { name: 'datetime', label: 'When', type: 'datetime', required: false },
  { name: 'integer', label: 'Count', type: 'integer', required: false },
  { name: 'choice', label: 'Audience', type: 'choice', required: true, options: [{ value: 'internal', label: 'Internal' }, { value: 'client', label: 'Client' }] },
  { name: 'record', label: 'Project', type: 'record', required: true, options_source: 'line_options' },
  { name: 'records', label: 'Issues', type: 'records', required: false, options_source: 'line_options', multiple: true },
  { name: 'display', label: 'Template', type: 'display', required: false, value: 'Client weekly report · test template v1' },
];

describe('fields by kind', () => {
  it('renders each kind in the order returned, with help, placeholder, required and (optional)', async () => {
    override = (_, url) => (url.pathname === '/api/v1/lines' ? json(200, synthetic(KINDS)) : undefined);
    await openMain();
    const names = [...dialog().querySelectorAll('[data-field]')].map((el) => el.getAttribute('data-field'));
    expect(names).toEqual(KINDS.map((f) => f.name));
    const text = within(dialog()).getByRole('textbox', { name: 'Text' });
    expect([text.tagName, text.getAttribute('placeholder'), text.getAttribute('aria-required')]).toEqual(['INPUT', 'Type here', 'true']);
    expect(text.getAttribute('aria-describedby')).toBeTruthy();
    expect(document.getElementById(text.getAttribute('aria-describedby')!)!.textContent).toBe('Text help');
    await waitFor(() => expect(document.activeElement).toBe(text));
    const area = within(dialog()).getByRole('textbox', { name: 'Long text (optional)' });
    expect([area.tagName, area.getAttribute('placeholder')]).toEqual(['TEXTAREA', 'Say more']);
    const date = within(dialog()).getByLabelText('Date');
    expect([date.getAttribute('type'), document.getElementById(date.getAttribute('aria-describedby')!)!.textContent]).toEqual(['date', 'Date help']);
    expect(within(dialog()).getByRole('group', { name: 'Range' })).toBeTruthy();
    expect(within(dialog()).getByLabelText('From').getAttribute('type')).toBe('date');
    expect(within(dialog()).getByLabelText('To').getAttribute('type')).toBe('date');
    expect(within(dialog()).getByLabelText('Period (optional)').getAttribute('type')).toBe('month');
    expect(within(dialog()).getByLabelText('When (optional)').getAttribute('type')).toBe('datetime-local');
    expect(within(dialog()).getByLabelText('Count (optional)').getAttribute('type')).toBe('number');
    const audience = within(dialog()).getByRole('radiogroup', { name: 'Audience' });
    expect(within(audience).getAllByRole('radio').map((r) => r.textContent)).toEqual(['Internal', 'Client']);
    expect(within(dialog()).getByRole('combobox', { name: 'Project' }).textContent).toBe('Choose…');
    expect(within(dialog()).getByRole('combobox', { name: 'Issues (optional)' })).toBeTruthy();
    expect(within(dialog()).getByText('Client weekly report · test template v1').tagName).toBe('SPAN');
    expect(within(dialog()).queryByText('Template (optional)')).toBeNull();
  });

  it('a choice with more than 3 options is a select', async () => {
    const options = ['a', 'b', 'c', 'd'].map((v) => ({ value: v, label: v.toUpperCase() }));
    override = (_, url) => (url.pathname === '/api/v1/lines' ? json(200, synthetic([{ name: 'pick', label: 'Pick', type: 'choice', required: true, options }])) : undefined);
    await openMain();
    const select = within(dialog()).getByRole('combobox', { name: 'Pick' });
    expect(select.tagName).toBe('SELECT');
    fireEvent.change(select, { target: { value: 'c' } });
    press('Start work');
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body.intake).toEqual({ pick: 'c' });
  });

  it('optional money and evidence fields are neither rendered nor sent', async () => {
    const intake: Field[] = [
      { name: 'note', label: 'Note', type: 'text', required: false },
      { name: 'fee', label: 'Fee', type: 'money', required: false },
      { name: 'proof', label: 'Proof', type: 'evidence', required: false, evidence_kind: 'client_request' },
    ];
    override = (_, url) => (url.pathname === '/api/v1/lines' ? json(200, synthetic(intake)) : undefined);
    await openMain();
    expect(within(dialog()).queryByText(/Fee|Proof/)).toBeNull();
    fireEvent.change(within(dialog()).getByRole('textbox', { name: 'Note (optional)' }), { target: { value: 'hi' } });
    press('Start work');
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body.intake).toEqual({ note: 'hi' });
  });

  it.each([
    ['a required evidence field', synthetic([{ name: 'proof', label: 'Proof', type: 'evidence', required: true }])],
    ['start_via finance_import', synthetic([], { start_via: 'finance_import' })],
    ['no case_scope', synthetic([], { case_scope: undefined })],
  ])('%s: the drawer says it can’t start here and has no start button', async (_, lines) => {
    override = (__, url) => (url.pathname === '/api/v1/lines' ? json(200, lines) : undefined);
    await openMain();
    expect(within(dialog()).getByText(/You can’t start this line from here yet\./)).toBeTruthy();
    expect(within(dialog()).getByRole('link', { name: 'Describe it to Tola' }).getAttribute('href')).toBe('/assistant');
    expect(within(dialog()).getAllByRole('button').map((b) => b.textContent || b.getAttribute('aria-label'))).toEqual(['Close', 'Cancel']);
    expect(within(dialog()).queryByText('Proof')).toBeNull();
  });
});

describe('record options from E-LINE-OPTIONS', () => {
  it('milestone waits for the project, is narrowed by it, shows disabled reasons, and is cleared when the project changes', async () => {
    await openMain();
    // The picker is rebuilt for each parent, so it is looked up again after the project changes.
    const milestone = () => within(dialog()).getByRole('combobox', { name: 'Completed milestone' }) as HTMLButtonElement;
    expect(milestone().disabled).toBe(true);
    expect(within(dialog()).getByText('Choose Project first')).toBeTruthy();
    await pick('Project', 'Lagoon Health · patient app');
    expect(milestone().disabled).toBe(false);
    expect(within(dialog()).getByText('Only milestones marked complete, with proof, are listed.')).toBeTruthy();
    fireEvent.click(milestone());
    const m4 = await within(dialog()).findByRole('option', { name: /Milestone 4 · hypercare/ });
    const last = optionGets().at(-1)!;
    expect(last.pathname + last.search).toBe('/api/v1/lines/invoice/fields/milestone/options?parent=P-0101&limit=20');
    expect(m4.getAttribute('aria-disabled')).toBe('true');
    expect(m4.textContent).toContain("Milestone 4 isn't marked complete yet. Record its completion and proof first.");
    fireEvent.click(m4);
    expect(within(dialog()).getByRole('listbox')).toBeTruthy();
    fireEvent.click(within(dialog()).getByRole('option', { name: /Milestone 3/ }));
    expect(milestone().textContent).toBe('Milestone 3 · UAT signed 07 Nov');
    await pick('Project', 'Harmattan Bank · mobile onboarding');
    expect(milestone().textContent).toBe('Choose…');
    fireEvent.click(milestone());
    await within(dialog()).findByRole('option', { name: /Milestone 2 · beta signed/ });
    expect(optionGets().at(-1)!.searchParams.get('parent')).toBe('P-0102');
  });

  it('ceo: the project picker lists 20, Show more fetches the next page, and search sends q', async () => {
    persona = 'ceo';
    await openChooser();
    fireEvent.click(within(dialog()).getByRole('radio', { name: /Controlled change/ }));
    press('Next');
    fireEvent.click(within(dialog()).getByRole('combobox', { name: 'Project' }));
    await within(dialog()).findByRole('option', { name: 'Lagoon Health · patient app' });
    expect(within(dialog()).getAllByRole('option')).toHaveLength(20);
    press('Show more');
    await waitFor(() => expect(within(dialog()).getAllByRole('option')).toHaveLength(26));
    expect(optionGets().at(-1)!.searchParams.get('cursor')).toBe('o:20');
    expect(within(dialog()).queryByRole('button', { name: 'Show more' })).toBeNull();
    fireEvent.change(within(dialog()).getByRole('searchbox', { name: 'Search Project' }), { target: { value: 'harm' } });
    await waitFor(() => expect(within(dialog()).getAllByRole('option').map((o) => o.textContent)).toEqual(['Harmattan Bank · mobile onboarding']));
    expect(optionGets().at(-1)!.searchParams.get('q')).toBe('harm');
    expect(optionGets().every((u) => u.searchParams.get('limit') === '20')).toBe(true);
    expect(optionGets().filter((u) => u.searchParams.has('q')).map((u) => u.searchParams.get('q'))).toEqual(['harm']);
  });

  it('a failed options read says so and Try again reads again', async () => {
    let failed = false;
    override = (_, url) => {
      if (!url.pathname.endsWith('/options') || failed) return undefined;
      failed = true;
      return Promise.reject(new TypeError('Failed to fetch'));
    };
    await openMain();
    fireEvent.click(within(dialog()).getByRole('combobox', { name: 'Project' }));
    expect(await within(dialog()).findByText(/We couldn’t load these options\./)).toBeTruthy();
    press('Try again');
    expect(await within(dialog()).findByRole('option', { name: 'Lagoon Health · patient app' })).toBeTruthy();
  });
});

describe('the case and the start request', () => {
  it('a valid invoice start sends exactly line, case, intake and key with CSRF, then goes to the work item', async () => {
    await invoiceWith('Milestone 3');
    fireEvent.change(within(dialog()).getByRole('textbox', { name: 'Anything Chidi should know (optional)' }), { target: { value: '  PO 4471  ' } });
    press('Start the invoice');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-1401'));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(posts).toHaveLength(1);
    expect(posts[0].headers.get('X-CSRFToken')).toBe('mock-csrf-pm');
    expect(Object.keys(posts[0].body).sort()).toEqual(['case_id', 'case_revision', 'idempotency_key', 'intake', 'line']);
    expect(posts[0].body).toMatchObject({
      line: 'invoice',
      case_id: 'C-0101',
      case_revision: 6,
      intake: { project: 'P-0101', milestone: 'M-0103', note: 'PO 4471' },
    });
    expect(posts[0].body.idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
    expect(mock.started.size).toBe(1);
  });

  it('a leadership start uses the fixed case and sends no project', async () => {
    await openChooser();
    fireEvent.click(within(dialog()).getByRole('radio', { name: /Leadership report/ }));
    press('Next');
    expect(within(dialog()).queryByRole('combobox', { name: 'Project' })).toBeNull();
    fireEvent.click(within(dialog()).getByRole('radio', { name: 'Internal Tuesday' }));
    fireEvent.change(within(dialog()).getByLabelText('Period'), { target: { value: '2026-11-17' } });
    expect(within(dialog()).getByText('PMO staff')).toBeTruthy();
    press('Start report');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-1408'));
    expect(posts[0].body).toMatchObject({
      line: 'leadership_report',
      case_id: 'C-PMO-REPORTING',
      case_revision: 4,
      intake: { report: 'internal_tuesday', report_date: '2026-11-17' },
    });
  });

  it('start is off until the case resolves, and a project without a case keeps it off', async () => {
    persona = 'ceo';
    await openChooser();
    fireEvent.click(within(dialog()).getByRole('radio', { name: /Controlled change/ }));
    press('Next');
    const start = within(dialog()).getByRole('button', { name: 'Log change' }) as HTMLButtonElement;
    expect(start.disabled).toBe(true);
    fireEvent.click(within(dialog()).getByRole('combobox', { name: 'Project' }));
    fireEvent.change(await within(dialog()).findByRole('searchbox', { name: 'Search Project' }), { target: { value: 'ojo' } });
    fireEvent.click(await within(dialog()).findByRole('option', { name: 'Ojo Foods · ordering app' }));
    expect(within(dialog()).getByText('This project can’t be started on from here.')).toBeTruthy();
    expect(start.disabled).toBe(true);
    fireEvent.click(start);
    expect(posts).toHaveLength(0);
  });
});

describe('server answers', () => {
  it('422: the missing milestone is named inline, the callout counts it, focus moves there, and the next press uses a new key', async () => {
    await invoiceWith();
    press('Start the invoice');
    const message = await within(dialog()).findByText('Completed milestone is required.');
    const milestone = within(dialog()).getByRole('combobox', { name: 'Completed milestone' });
    expect(milestone.getAttribute('aria-invalid')).toBe('true');
    expect(milestone.getAttribute('aria-describedby')!.split(' ')).toContain(message.closest('.psl-error')!.id);
    const callout = within(dialog()).getByRole('alert');
    expect(callout.textContent).toBe('1 things to fix before Chidi can start.');
    expect(document.activeElement).toBe(callout);
    expect(within(dialog()).getByText('1 things to fix')).toBeTruthy();
    await pick('Completed milestone', 'Milestone 3');
    press('Start the invoice');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-1401'));
    expect(posts).toHaveLength(2);
    expect(posts[1].body.idempotency_key).not.toBe(posts[0].body.idempotency_key);
  });

  it('422: a message for a field the drawer does not render goes in the callout', async () => {
    await openMain();
    await pick('Project', 'Harmattan Bank · mobile onboarding');
    await pick('Completed milestone', 'Milestone 2');
    press('Start the invoice');
    const callout = await within(dialog()).findByRole('alert');
    expect(callout.textContent).toBe(
      "1 things to fix before Chidi can start.The client register has no billing contact for Harmattan Bank. Add one in the project's client details.",
    );
  });

  it('a double press sends one start', async () => {
    let resolve!: (r: Response) => void;
    override = (request) => (request.method === 'POST' ? new Promise((r) => (resolve = r)) : undefined);
    await invoiceWith('Milestone 3');
    const start = within(dialog()).getByRole('button', { name: 'Start the invoice' });
    fireEvent.click(start);
    fireEvent.click(start);
    await waitFor(() => expect(within(dialog()).getByRole('button', { name: /Starting…/ }).getAttribute('aria-busy')).toBe('true'));
    fireEvent.click(within(dialog()).getByRole('button', { name: /Starting…/ }));
    expect(posts).toHaveLength(1);
    await act(async () => resolve(json(201, { work_id: 'W-1401', state: 'processing' })));
    expect(nav.push).toHaveBeenCalledWith('/work/W-1401');
    expect(posts).toHaveLength(1);
  });

  it('a network failure locks the form; only "Check again" resends, with the same key and body', async () => {
    override = (request) => (request.method === 'POST' && posts.length === 1 ? Promise.reject(new TypeError('Failed to fetch')) : undefined);
    await invoiceWith('Milestone 3');
    fireEvent.change(within(dialog()).getByRole('textbox', { name: /Anything Chidi/ }), { target: { value: 'PO 4471' } });
    press('Start the invoice');
    expect(await within(dialog()).findByText(/We couldn’t confirm the start\. Check again/)).toBeTruthy();
    expect(within(dialog()).getByText('If it started, it will appear in My work.')).toBeTruthy();
    expect(within(dialog()).getByRole('textbox', { name: /Anything Chidi/ }).hasAttribute('readonly')).toBe(true);
    expect((within(dialog()).getByRole('combobox', { name: 'Project' }) as HTMLButtonElement).disabled).toBe(true);
    await new Promise((r) => setTimeout(r, 50));
    expect(posts).toHaveLength(1);
    press('Check again');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-1401'));
    expect(posts).toHaveLength(2);
    expect(posts[1].body).toEqual(posts[0].body);
    expect(mock.started.size).toBe(1);
  });

  it('after a 500 the fields are read-only; Check again on a start that did happen goes to it and starts nothing new', async () => {
    // The first start reached the mock, but its answer was lost as a 500.
    override = (request) => {
      if (request.method !== 'POST' || posts.length !== 1) return undefined;
      return request.clone().text().then((raw) => {
        mock.handle('E-WORK-START', { url: new URL(request.url), raw, persona });
        return new Response('<html>', { status: 500 });
      });
    };
    await invoiceWith('Milestone 3');
    press('Start the invoice');
    await within(dialog()).findByRole('button', { name: 'Check again' });
    expect(within(dialog()).getByRole('textbox', { name: /Anything Chidi/ }).hasAttribute('readonly')).toBe(true);
    expect(mock.started.size).toBe(1);
    press('Check again');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-1401'));
    expect(posts[1].body.idempotency_key).toBe(posts[0].body.idempotency_key);
    expect(mock.started.size).toBe(1);
  });

  it('409: keeps what was typed, re-reads the project revision, and only resends on a press, with a new key', async () => {
    override = (request, url) => {
      if (request.method === 'POST' && posts.length === 1) return json(409, { code: 'stale_revision', message: 'Changed.' });
      if (url.pathname.endsWith('/project/options') && url.searchParams.get('q')) {
        return json(200, { items: [{ value: 'P-0101', label: 'Lagoon Health · patient app', case_id: 'C-0101', case_revision: 7 }], as_of: '2026-11-14T09:05:00Z' });
      }
      return undefined;
    };
    await invoiceWith('Milestone 3');
    fireEvent.change(within(dialog()).getByRole('textbox', { name: /Anything Chidi/ }), { target: { value: 'PO 4471' } });
    press('Start the invoice');
    expect(
      await within(dialog()).findByText(
        'This project changed since you opened the form. We’ve loaded the latest version; check your entries and press start again.',
      ),
    ).toBeTruthy();
    const reread = optionGets().at(-1)!;
    expect([reread.pathname, reread.searchParams.get('q')]).toEqual(['/api/v1/lines/invoice/fields/project/options', 'Lagoon Health · patient app']);
    expect((within(dialog()).getByRole('textbox', { name: /Anything Chidi/ }) as HTMLTextAreaElement).value).toBe('PO 4471');
    expect(within(dialog()).getByRole('combobox', { name: 'Project' }).textContent).toBe('Lagoon Health · patient app');
    expect(within(dialog()).getByRole('combobox', { name: 'Completed milestone' }).textContent).toBe('Milestone 3 · UAT signed 07 Nov');
    await new Promise((r) => setTimeout(r, 50));
    expect(posts).toHaveLength(1);
    press('Start the invoice');
    await waitFor(() => expect(posts).toHaveLength(2));
    expect(posts[1].body.case_revision).toBe(7);
    expect(posts[1].body.idempotency_key).not.toBe(posts[0].body.idempotency_key);
  });

  it('409: when the project is no longer returned, it and its milestone are cleared and say so', async () => {
    override = (request, url) => {
      if (request.method === 'POST') return json(409, { code: 'stale_revision', message: 'Changed.' });
      if (url.pathname.endsWith('/project/options') && url.searchParams.get('q')) return json(200, { items: [], as_of: '2026-11-14T09:05:00Z' });
      return undefined;
    };
    await invoiceWith('Milestone 3');
    press('Start the invoice');
    expect(await within(dialog()).findByText('That choice is no longer available. Choose again.')).toBeTruthy();
    expect(within(dialog()).getByRole('combobox', { name: 'Project' }).textContent).toBe('Choose a project');
    expect(within(dialog()).getByRole('combobox', { name: 'Completed milestone' }).textContent).toBe('Choose…');
    expect((within(dialog()).getByRole('button', { name: 'Start the invoice' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('409 on a fixed case re-reads E-LINES; a line no longer returned removes the start button', async () => {
    override = (request, url) => {
      if (request.method === 'POST') return json(409, { code: 'stale_revision', message: 'Changed.' });
      if (url.pathname === '/api/v1/lines' && lineGets().length > 1) return json(200, { items: [], as_of: '2026-11-14T09:05:00Z' });
      return undefined;
    };
    await openChooser();
    fireEvent.click(within(dialog()).getByRole('radio', { name: /Leadership report/ }));
    press('Next');
    press('Start report');
    expect(await within(dialog()).findByText('You can no longer start this line.')).toBeTruthy();
    expect(within(dialog()).queryByRole('button', { name: 'Start report' })).toBeNull();
    expect(lineGets()).toHaveLength(2);
  });

  it('403: says you can’t start this here, keeps the drawer and what was typed', async () => {
    override = (request) => (request.method === 'POST' ? json(403, { code: 'forbidden', message: 'Your role does not allow this.' }) : undefined);
    await invoiceWith('Milestone 3');
    fireEvent.change(within(dialog()).getByRole('textbox', { name: /Anything Chidi/ }), { target: { value: 'PO 4471' } });
    press('Start the invoice');
    expect((await within(dialog()).findByRole('alert')).textContent).toBe('You can’t start this here. Your role does not allow this.');
    expect((within(dialog()).getByRole('textbox', { name: /Anything Chidi/ }) as HTMLTextAreaElement).value).toBe('PO 4471');
    expect(within(dialog()).getByRole('combobox', { name: 'Project' }).textContent).toBe('Lagoon Health · patient app');
    expect(nav.push).not.toHaveBeenCalled();
  });

  it('401 on start shows signed out in the drawer', async () => {
    override = (request) => (request.method === 'POST' ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : undefined);
    await invoiceWith('Milestone 3');
    press('Start the invoice');
    expect(await within(dialog()).findByText('You’re signed out.')).toBeTruthy();
  });
});

describe('accessibility (axe-core in jsdom, colour contrast checked in the browser run)', () => {
  const options: axe.RunOptions = {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
    rules: { 'color-contrast': { enabled: false } },
  };
  const violations = async () =>
    (await axe.run(document.body, options)).violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`);

  it('the chooser, the invoice drawer with an open picker, and the validation state have no violations', async () => {
    await openChooser();
    expect(await violations()).toEqual([]);
    fireEvent.click(within(dialog()).getByRole('radio', { name: /Invoice preparation/ }));
    press('Next');
    fireEvent.click(within(dialog()).getByRole('combobox', { name: 'Project' }));
    await within(dialog()).findByRole('option', { name: 'Lagoon Health · patient app' });
    expect(await violations()).toEqual([]);
    fireEvent.click(within(dialog()).getByRole('option', { name: 'Lagoon Health · patient app' }));
    press('Start the invoice');
    await within(dialog()).findByText('Completed milestone is required.');
    expect(await violations()).toEqual([]);
  });

  it('a drawer with every kind has no violations', async () => {
    override = (_, url) => (url.pathname === '/api/v1/lines' ? json(200, synthetic(KINDS)) : undefined);
    await openMain();
    expect(await violations()).toEqual([]);
  });
});
