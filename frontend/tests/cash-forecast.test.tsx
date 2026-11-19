// @vitest-environment jsdom
// F-43: the cash forecast's work item (W-4001 to W-4013) drawn from E-WORK-ITEM `workspace`: the review decided in place
// (E-TASK-CLAIM, E-TASK-DECIDE through F-33's InlineDecide and useDecision) and the uncertain delivery recorded through the
// existing ReconcilePanel (E-WORK-ACTION, E-EVIDENCE-UPLOAD). Contract mock only; the fetch stub stands in for the backend.
// Money rules: every amount as returned, nothing computed, Unknown never 0.
import { execFileSync } from 'node:child_process';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { reloadPage } from '@/features/response';
import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-4002',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
/** A served item: W-40xx and its decide sidecars from fixtures/work, the reconcile sidecars ("W-4003.delivered") from fixtures/response. */
const item = (name: string): WorkItem => (/^W-4003\.[a-z_]+$/.test(name) ? read(`response/${name}.json`) : read(`work/${name}.json`));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const decideRequest = ajv.compile(openapi.paths['/api/v1/tasks/{task_id}/decision'].post.requestBody.content['application/json'].schema);
const actionRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/actions'].post.requestBody.content['application/json'].schema);

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Body = Record<string, unknown>;
type Handler = (body: Body, path: string) => Response | Promise<Response>;
let sent: Sent[];
let served: WorkItem;
let readAnswer: (() => Response) | null;
let who: string;
let onClaim: Handler;
let onDecide: Handler;
let onAction: Handler;
let onUpload: Handler;

const posts = (suffix: string) => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const taskPosts = () => sent.filter((r) => r.method === 'POST' && r.path.startsWith('/api/v1/tasks/'));
const writes = () => sent.filter((r) => r.method === 'POST');
const answer = (task: string, verdict: string, workState = 'processing') => json(200, { task_id: task, verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-13T14:05:00Z', work_state: workState });
const taskOf = (path: string) => path.split('/')[4];

beforeEach(() => {
  sent = [];
  readAnswer = null;
  who = 'finance_lead';
  vi.mocked(reloadPage).mockClear();
  onClaim = (body) => json(200, { task_id: 'T', revision: body.expected_revision, claimed_by: 'Ada Okafor' });
  // the mock's swap: the decided item is <work_id>.<verdict>.json
  onDecide = (body, path) => {
    served = item(`${served.id}.${body.verdict as string}`);
    return answer(taskOf(path), body.verdict as string, served.state);
  };
  // the reconcile mock's swap: response/<work_id>.<outcome>.json; the page reloads itself to read it
  onAction = (body) => {
    served = item(`${served.id}.${body.outcome as string}`);
    return json(200, { work_id: served.id, state: served.state, revision: served.revision });
  };
  onUpload = (body, path) => json(200, { evidence_id: `EV-${path.split('/')[4]}-1`, sha256: 'a'.repeat(64), case_revision: (body.case_revision as number) + 1 });
  const fetchStub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    const body = text ? JSON.parse(text) : undefined;
    sent.push({ method: request.method, path: url.pathname, body, csrf: request.headers.get('X-CSRFToken') });
    if (url.pathname === '/api/v1/me') return json(200, read(`me.${who}.json`));
    if (request.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(url.pathname)) return readAnswer ? readAnswer() : json(200, served);
    if (request.method === 'POST' && url.pathname.endsWith('/claim')) return onClaim(body, url.pathname);
    if (request.method === 'POST' && url.pathname.endsWith('/decision')) return onDecide(body, url.pathname);
    if (request.method === 'POST' && url.pathname.endsWith('/actions')) return onAction(body, url.pathname);
    if (request.method === 'POST' && url.pathname.endsWith('/evidence')) return onUpload(body, url.pathname);
    return json(404, { code: 'not_found', message: 'Not here.' });
  });
  vi.stubGlobal('fetch', withoutBellFeed(fetchStub));
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

const phone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));

async function open(body: WorkItem) {
  served = body;
  const view = render(
    <AppShell>
      <WorkItemView id={body.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: body.title });
  return view;
}

const ws = () => within(document.querySelector('.ws') as HTMLElement);
const buttons = () => ws().queryAllByRole('button').map((b) => b.textContent);
const status = () => document.querySelector('.work-state')!;
const ready = async (name: string) => waitFor(() => expect(ws().getByRole('button', { name }).hasAttribute('disabled')).toBe(false));
const click = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const note = () => ws().getByLabelText(/^Note \(needed to/) as HTMLTextAreaElement;
/** What the page says about the write: its notices, the status tag and the side column (not the station names). The
 *  reconcile choices' own labels ("It arrived. I have proof it was received…", the approved wording) are not a claim. */
const said = () =>
  [document.querySelector('.ws-notices'), status(), document.querySelector('.ws-side')]
    .map((el) => {
      if (!el) return '';
      const copy = el.cloneNode(true) as HTMLElement;
      copy.querySelectorAll('.resp-options').forEach((options) => options.remove());
      return copy.textContent ?? '';
    })
    .join(' ');
const factValue = (label: string) => [...document.querySelectorAll('.ws-fact')].find((f) => f.querySelector('dt')?.textContent === label)?.querySelector('dd')?.textContent;
const column = (label: string) => [...document.querySelectorAll(`.ws-table td[data-label="${label}"]`)].map((td) => td.textContent);
const settle = () => new Promise((r) => setTimeout(r, 50));
/** The record panel: a named section inside the desktop side column (no second complementary landmark), its own aside on a phone. */
const panel = () => screen.queryByRole('region', { name: 'Record what happened' }) ?? screen.queryByRole('complementary', { name: 'Record what happened' });
/** A fact's tag as drawn: its words and its design-system tone class. */
const factTag = (label: string) => {
  const tag = [...document.querySelectorAll('.ws-fact')].find((f) => f.querySelector('dt')?.textContent === label)?.querySelector('dd .psl-tag');
  return tag ? { text: tag.textContent, done: tag.classList.contains('psl-tag--done'), waiting: tag.classList.contains('psl-tag--waiting') } : null;
};
const record = () => screen.getByRole('button', { name: /Record and continue|Recording…/ }) as HTMLButtonElement;
const choose = (name: RegExp) => fireEvent.click(screen.getByRole('radio', { name }));
type Money = { amount?: string; currency: string; unknown: boolean };
const cell = (body: WorkItem, row: number, col: number) => body.workspace!.sections[0].items[row].cells![col] as { money?: Money };

describe('four states from data (AC 1, 9, 10, 12)', () => {
  it('W-4001 investigating: the Sources facts as returned, Chidi working in the card with steps, sources and Ask Chidi, and no decide control or figure', async () => {
    await open(item('W-4001'));
    expect(status().textContent).toBe('CHIDI INVESTIGATING');
    expect(status().className).toContain('agent');
    expect(ws().getByRole('heading', { name: 'Sources' })).toBeTruthy();
    expect(factValue('Opening balances')).toBe('ACCEPTED');
    expect(factValue('Assumptions workbook')).toBe('ACCEPTED');
    expect(factValue('Payroll estimate')).toBe('ACCEPTED');
    // UI-1-2: the tag the backend sends is drawn in its tone, once
    for (const label of ['Opening balances', 'Assumptions workbook', 'Payroll estimate']) expect(factTag(label), label).toEqual({ text: 'ACCEPTED', done: true, waiting: false });
    const card = document.querySelector('.ws-lineagent')!;
    for (const text of ['WORKING', 'Read opening balances', '3 BANK ACCOUNTS · 31 OCT', 'Aged open invoices', '9 INVOICES · ₦31.4M', 'FC-0013', 'Hand to calculation']) expect(card.textContent, text).toContain(text);
    expect(card.querySelector('.psl-agent__foot')!.textContent).toBe('Started 08:40Ask Chidi');
    expect(ws().getAllByRole('link', { name: 'Ask Chidi' })).toHaveLength(1);
    expect(ws().getByRole('link', { name: 'Ask Chidi' }).getAttribute('href')).toBe('/assistant');
    expect(buttons()).toEqual([]);
    expect(document.querySelector('.ws-idecide, .ws-table')).toBeNull();
    // the only ₦ on the page is Chidi's source label, never a forecast figure
    expect(document.querySelector('.ws-sections')?.textContent ?? '').not.toContain('₦');
    expect([...document.querySelectorAll('.ws-stations .psl-station strong')].map((s) => s.textContent)).toEqual([
      'Chidi investigates',
      'Calculate',
      'Review',
      'Group rows',
      'Group review',
      'Chidi drafts',
      'Publish',
      'Verified',
    ]);
    await settle();
    expect(writes()).toHaveLength(0);
  });

  it('W-4002 review: the six-month table, the backend note and the Decide panel with the basis, the consequence and the note label', async () => {
    await open(item('W-4002'));
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect(ws().getByRole('heading', { name: 'Forecast · 6 months' })).toBeTruthy();
    expect([...document.querySelectorAll('.ws-table th')].map((th) => th.textContent)).toEqual(['MONTH', 'OPENING', 'IN', 'OUT', 'CLOSING']);
    expect(column('MONTH')).toEqual(['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr']);
    expect(ws().getByText("January receipts are Unknown: Kola Foods hasn't confirmed its payment date. The forecast shows Unknown, not 0.")).toBeTruthy();
    const decide = await ws().findByRole('region', { name: 'Decide · Forecast reviewer' });
    expect(within(decide).getByText("Approve the base-case forecast for management. It doesn't move any cash.")).toBeTruthy();
    expect(within(decide).getByText("Approving doesn't move any cash or authorise a payment.")).toBeTruthy();
    expect(within(decide).getByLabelText('Note (needed to return or reject)')).toBeTruthy();
    await ready('Approve forecast');
    expect(within(decide).getAllByRole('button').map((b) => b.textContent)).toEqual(['Approve forecast', 'Return with a note', 'Reject']);
    expect(document.querySelector('.ws-idecide strong, .ws-idecide b')?.textContent ?? '').not.toContain('management');
  });

  it('W-4003 uncertain: the banner, the Delivery facts and Next as returned, the "Record what happened" panel, and no cancel, resend or retry control', async () => {
    await open(item('W-4003'));
    expect(status().textContent).toBe('EFFECT UNCERTAIN');
    expect(ws().getByText("We don't know if the CEO received the forecast. The delivery is held; it can't be sent again until someone checks.")).toBeTruthy();
    expect(factValue('Sent')).toBe('14 NOV 09:00');
    expect(factValue('Confirmation')).toBe('UNKNOWN');
    expect(factTag('Confirmation')).toEqual({ text: 'UNKNOWN', done: false, waiting: true });
    expect(factTag('Sent')).toBeNull();
    expect(screen.getAllByText("Check with the CEO's office, then record it.").length).toBeGreaterThan(0);
    const reconcile = panel()!;
    // TECH-1-2: inside the side column it is a named section, not a complementary landmark nested in another
    expect(reconcile.tagName).toBe('SECTION');
    expect(document.querySelectorAll('aside aside')).toHaveLength(0);
    expect(within(reconcile).getByRole('heading', { level: 2 }).textContent).toBe('Record what happened');
    // the board draws it in the side column above Next, not above the workspace (desktop)
    expect(document.querySelector('.ws-side')!.contains(reconcile)).toBe(true);
    expect(document.querySelectorAll('.resp-reconcile')).toHaveLength(1);
    expect(reconcile.textContent).toContain('Nothing is sent again until a person records what happened.');
    expect(reconcile.textContent).not.toMatch(/client|invoiced/i);
    const options = within(within(reconcile).getByRole('radiogroup', { name: 'Record what happened' })).getAllByRole('radio') as HTMLInputElement[];
    expect(options.map((o) => o.labels![0].textContent)).toEqual(['It arrived. I have proof it was received (upload it next).', 'It didn’t arrive.', 'I can’t tell yet. Keep it held and check again tomorrow.']);
    expect(screen.queryAllByRole('button').map((b) => b.textContent)).not.toEqual(expect.arrayContaining([expect.stringMatching(/Cancel delivery|Send again|Resend|Retry|^Send/)]));
    expect(document.body.textContent).not.toMatch(/Cancel delivery|Send again|Resend|Retry/);
    await settle();
    expect(writes()).toHaveLength(0);
  });

  it('W-4004 verified: VERIFIED, the six figures, the limit sentence and Next as returned, with no Record actuals and no control', async () => {
    await open(item('W-4004'));
    expect(status().textContent).toBe('VERIFIED');
    // UI-1-1: the board's strip of six cells, each label over its value as returned; the VERIFIED cell in the tone its tag sends
    expect(document.querySelector('.ws-rows--figures')).toBeNull();
    const cells = [...document.querySelectorAll('.ws-section--strip .ws-figstrip__cell')];
    expect(cells.map((c) => [c.querySelector('dt')?.textContent, c.querySelector('dd')?.textContent])).toEqual([
      ['CALCULATED', '12 Nov'],
      ['REVIEWED', '13 Nov'],
      ['DRAFTED', '13 Nov'],
      ['PUBLISHED', '14 Nov'],
      ['RECEIPTS', '2 of 2'],
      ['VERIFIED', '14 Nov'],
    ]);
    expect(cells.map((c) => c.getAttribute('data-tone'))).toEqual([null, null, null, null, null, 'done']);
    // the limit sentence is a caption under the strip, with no panel of its own
    const caption = ws().getByText('The forecast never moves cash or authorises a payment.');
    expect(caption.tagName).toBe('P');
    expect(caption.className).toBe('ws-caption');
    expect(caption.closest('.psl-panel')).toBeNull();
    expect(document.querySelector('.ws-section--strip')!.compareDocumentPosition(caption) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getAllByText('As months close, record actual cash against the forecast.').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /Record actuals/ })).toBeNull();
    expect(buttons()).toEqual([]);
    expect(panel()).toBeNull();
  });

  it('changing a fixture string changes only that text (W-4003); a copy without reconcile and allowed_actions shows the lock and no panel', async () => {
    const changed = item('W-4003');
    changed.workspace!.sections[0].note = 'Changed banner.';
    (changed.workspace!.sections[1].items[0] as { value: string }).value = '15 NOV 10:00';
    changed.workspace!.next = ['Changed next.'];
    await open(changed);
    expect(ws().getByText('Changed banner.')).toBeTruthy();
    expect(factValue('Sent')).toBe('15 NOV 10:00');
    expect(factValue('Confirmation')).toBe('UNKNOWN');
    expect(screen.getAllByText('Changed next.').length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("CEO's office");
    expect(document.body.textContent).not.toContain("We don't know if the CEO");
    cleanup();
    const bare = item('W-4003') as WorkItem & { reconcile?: unknown; allowed_actions?: unknown };
    delete bare.reconcile;
    delete bare.allowed_actions;
    await open(bare);
    expect(panel()).toBeNull();
    expect(await screen.findByText('We are checking what happened. Nothing was sent again.')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Cancel delivery|Send again|Resend|Retry/);
  });

  it('no board string is written in src (AC 1)', () => {
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.(tsx?|css)$/.test(name) && !name.endsWith('schema.d.ts')) files.push(path);
      }
    };
    walk(join(__dirname, '../src'));
    const text = files.map((f) => readFileSync(f, 'utf8')).join('\n');
    for (const board of ['CHIDI INVESTIGATING', 'AWAITING FINANCE DECISION', 'EFFECT UNCERTAIN', 'Forecast reviewer', "CEO's office", 'Kola Foods', 'never moves cash', 'base case']) expect(text, board).not.toContain(board);
  });
});

describe('amounts as returned (AC 2 to 4)', () => {
  it('the full amounts at desktop and phone, never a short "M" form; a changed and a 17-digit amount show digit for digit', async () => {
    const full = ['₦22,600,000.00', '₦20,000,000.00', '₦7,800,000.00', 'Unknown', 'Unknown', 'Unknown'];
    // the only short form on the page is Chidi's source label "9 INVOICES · ₦31.4M", sent as text (Conflicts 1)
    const shortForms = () => document.querySelector('main')!.textContent!.replace('9 INVOICES · ₦31.4M', '').match(/₦[\d.,]+\s?[MKB]\b/g);
    await open(item('W-4002'));
    expect(column('OPENING')).toEqual(full);
    expect(document.querySelector('.ws-table')!.textContent).not.toMatch(/\d(\.\d)?M\b/);
    expect(shortForms()).toBeNull();
    cleanup();
    phone();
    await open(item('W-4002'));
    expect(column('OPENING')).toEqual(full);
    expect(shortForms()).toBeNull();
    cleanup();
    const changed = item('W-4002');
    cell(changed, 0, 1).money = { amount: '22600000.10', currency: 'NGN', unknown: false };
    cell(changed, 1, 2).money = { amount: '12345678901234567.89', currency: 'NGN', unknown: false };
    await open(changed);
    expect(column('OPENING')[0]).toBe('₦22,600,000.10');
    expect(column('IN')[1]).toBe('₦12,345,678,901,234,567.89');
  });

  it('the page computes nothing: a changed Nov IN leaves Nov CLOSING and Dec OPENING as sent; an Unknown Dec CLOSING leaves Jan OPENING as sent; no total row', async () => {
    const changed = item('W-4002');
    cell(changed, 0, 2).money = { amount: '1.00', currency: 'NGN', unknown: false };
    cell(changed, 1, 4).money = { currency: 'NGN', unknown: true };
    await open(changed);
    expect(column('IN')[0]).toBe('₦1.00');
    expect(column('CLOSING')[0]).toBe('₦20,000,000.00');
    expect(column('OPENING')[1]).toBe('₦20,000,000.00');
    expect(column('CLOSING')[1]).toBe('Unknown');
    expect(column('OPENING')[2]).toBe('₦7,800,000.00');
    expect(document.querySelectorAll('.ws-table tbody tr')).toHaveLength(6);
    expect(document.querySelector('.ws-table tfoot')).toBeNull();
    expect(document.querySelector('main')!.textContent).not.toMatch(/total|variance|difference|\bsum\b/i);
  });

  it('no changed file under src adds parseFloat, Number(, reduce(, compactAmount or toFixed (AC 3) and none reads /me (AC 8)', () => {
    const root = join(__dirname, '../..');
    let diff = '';
    try {
      // against the branch point, so later dlv-00 commits are not read as this branch's lines
      const base = execFileSync('git', ['merge-base', 'HEAD', 'origin/dlv-00-delivery-setup'], { cwd: root, encoding: 'utf8' }).trim();
      diff = execFileSync('git', ['diff', '-U0', base, '--', 'frontend/src'], { cwd: root, encoding: 'utf8' });
    } catch {
      diff = execFileSync('git', ['diff', '-U0', 'HEAD', '--', 'frontend/src'], { cwd: root, encoding: 'utf8' });
    }
    const added = diff.split('\n').filter((l) => l.startsWith('+') && !l.startsWith('+++'));
    expect(added.filter((l) => /parseFloat|Number\(|\.reduce\(|compactAmount|toFixed/.test(l))).toEqual([]);
    expect(added.filter((l) => /\buseMe\b|\/api\/v1\/me/.test(l))).toEqual([]);
  });

  it('Unknown is never 0 at desktop and phone; a real "0.00" reads ₦0.00', async () => {
    for (const width of ['desktop', 'phone']) {
      if (width === 'phone') phone();
      await open(item('W-4002'));
      expect(column('IN')[2], width).toBe('Unknown');
      expect(column('CLOSING').slice(2), width).toEqual(['Unknown', 'Unknown', 'Unknown', 'Unknown']);
      expect(column('OPENING').slice(3), width).toEqual(['Unknown', 'Unknown', 'Unknown']);
      for (const text of [...column('OPENING'), ...column('IN'), ...column('OUT'), ...column('CLOSING')]) expect(text, width).not.toMatch(/^(|-|—|0|₦0|₦0\.00)$/);
      expect(document.querySelector('.ws')!.textContent, width).not.toContain('₦0');
      cleanup();
    }
    const zero = item('W-4002');
    cell(zero, 2, 2).money = { amount: '0.00', currency: 'NGN', unknown: false };
    await open(zero);
    expect(column('IN')[2]).toBe('₦0.00');
  });

  it('every fixture is marked sample because the record says so; a copy with sample false is not (AC 5)', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    for (let n = 4001; n <= 4013; n += 1) {
      await open(item(`W-${n}`));
      expect(document.querySelector('.work-lineend')!.textContent, `W-${n}`).toContain('SAMPLE DATA');
      cleanup();
    }
    await open({ ...item('W-4002'), sample: false });
    expect(document.querySelector('.work-lineend')!.textContent).not.toContain('SAMPLE DATA');
  });
});

describe('holds and who may act (AC 6 to 8, 11, 15)', () => {
  for (const [id, label, sentence] of [
    ['W-4006', 'Forecast preparer', 'An admin sets Forecast preparer in Setup · Finance rules. The forecast is prepared then.'],
    ['W-4007', 'Inclusion rule', "The inclusion rule for the cash forecast isn't set yet. The forecast is calculated once it is."],
  ] as const) {
    it(`${id} (${label} not set): the backend’s hold, no Decide panel, no button, no reconcile panel, no write and no person named`, async () => {
      await open(item(id));
      expect(status().textContent).toBe('SETUP NEEDED');
      expect(factValue(label)).toBe('NOT SET');
      expect(screen.getAllByText(sentence).length).toBeGreaterThan(0);
      expect(buttons()).toEqual([]);
      expect(document.querySelector('.ws-idecide')).toBeNull();
      expect(panel()).toBeNull();
      expect(document.querySelector('.ws')!.textContent).not.toMatch(/Forecast reviewer|Bisi Ade|Ada Okafor/);
      expect(document.querySelector('main')!.textContent).not.toMatch(/Forecast reviewer|Bisi Ade/);
      expect(document.querySelector('.ws-table')).toBeNull();
      expect(document.querySelector('.ws-sections, .ws')!.textContent!.replace('9 INVOICES · ₦31.4M', '')).not.toContain('₦');
      expect(screen.queryByRole('link', { name: 'See all exceptions' })).toBeNull();
      await settle();
      expect(writes()).toHaveLength(0);
    });
  }

  it('the Decide title is required_role as returned: Finance Lead when the copy says so, no role name when absent', async () => {
    const lead = item('W-4002');
    lead.tasks[0].required_role = 'Finance Lead';
    await open(lead);
    expect(await ws().findByRole('region', { name: 'Decide · Finance Lead' })).toBeTruthy();
    expect(document.body.textContent).not.toContain('Forecast reviewer');
    cleanup();
    const none = item('W-4002') as WorkItem;
    delete (none.tasks[0] as { required_role?: string }).required_role;
    for (const step of none.tasks[0].decision?.chain?.steps ?? []) delete (step as { role?: string }).role;
    await open(none);
    await ready('Approve forecast');
    expect(document.body.textContent).not.toContain('Forecast reviewer');
    expect(document.querySelector('.ws-idecide')!.textContent).not.toMatch(/Finance Lead|Forecast reviewer|reviewer/);
  });

  it('W-4009 shows only Approve and Return; W-4011 draws neither revoke nor post; W-4010 draws the existing decision-page link', async () => {
    await open(item('W-4009'));
    await ready('Approve forecast');
    expect(buttons()).toEqual(['Approve forecast', 'Return with a note']);
    expect(ws().getByLabelText('Note (needed to return)')).toBeTruthy();
    cleanup();
    await open(item('W-4011'));
    await settle();
    expect(buttons().filter((b) => /Withdraw|Post/i.test(b ?? ''))).toEqual([]);
    expect(document.body.textContent).not.toMatch(/Withdraw forecast|Post forecast/);
    cleanup();
    await open(item('W-4010'));
    const link = await ws().findByRole('link', { name: 'Review forecast' });
    expect(link.getAttribute('href')).toBe('/work/W-4010/decide?task=T-4010');
    expect(buttons().filter((b) => /Approve|Return|Reject/.test(b ?? ''))).toEqual([]);
  });

  it('W-4005 (you prepared it) and W-4008 (not your role) show the reason, no button and send no claim', async () => {
    await open(item('W-4005'));
    expect(await ws().findByText('You prepared Forecast v1, so someone else must review it.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    cleanup();
    await open(item('W-4008'));
    expect(await ws().findByText('This decision needs a Forecast reviewer.')).toBeTruthy();
    expect(buttons()).toEqual([]);
    await settle();
    expect(writes()).toHaveLength(0);
  });

  it('the controls follow you_can_act only: finance_lead, ceo and pm see the same buttons on the same items', async () => {
    for (const persona of ['finance_lead', 'ceo', 'pm']) {
      who = persona;
      sent = [];
      await open(item('W-4002'));
      await ready('Approve forecast');
      expect(buttons(), persona).toEqual(['Approve forecast', 'Return with a note', 'Reject']);
      expect(posts('/claim').map((p) => p.path), persona).toEqual(['/api/v1/tasks/T-4002/claim']);
      cleanup();
      sent = [];
      await open(item('W-4008'));
      expect(await ws().findByText('This decision needs a Forecast reviewer.')).toBeTruthy();
      expect(buttons(), persona).toEqual([]);
      await settle();
      expect(taskPosts(), persona).toHaveLength(0);
      cleanup();
    }
  });

  it('W-4012 (reconcile, no grant) shows no panel and the lock; W-4004 and W-4002 have no panel; nothing is sent', async () => {
    await open(item('W-4012'));
    expect(panel()).toBeNull();
    expect(screen.queryByRole('radio')).toBeNull();
    for (const b of screen.queryAllByRole('button')) fireEvent.click(b);
    cleanup();
    for (const id of ['W-4004', 'W-4002']) {
      await open(item(id));
      expect(panel(), id).toBeNull();
      cleanup();
    }
    await settle();
    expect(posts('/actions')).toHaveLength(0);
  });
});

describe('approve, return and reject (AC 12 to 14)', () => {
  it('W-4002: claims once, then one decision with CSRF and {verdict, expected_revision}; a double press sends one; APPROVED from the re-read, never Verified', async () => {
    await open(item('W-4002'));
    await ready('Approve forecast');
    expect(posts('/api/v1/tasks/T-4002/claim')).toHaveLength(1);
    await act(async () => {
      const approve = ws().getByRole('button', { name: 'Approve forecast' });
      fireEvent.click(approve);
      fireEvent.click(approve);
    });
    await waitFor(() => expect(status().textContent).toBe('APPROVED'));
    expect(posts('/decision')).toHaveLength(1);
    const [decision] = posts('/api/v1/tasks/T-4002/decision');
    expect(decision.body).toEqual({ verdict: 'approve', expected_revision: 1 });
    expect(decideRequest(decision.body)).toBe(true);
    expect(decision.csrf).toBe('mock-csrf-finance_lead');
    // "Verified" only from a re-read state verified: here the status, the notices and the side column never say it
    expect(said()).not.toMatch(/verified/i);
    expect(document.querySelectorAll('.work-state')).toHaveLength(1);
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(buttons()).toEqual([]);
  });

  it('a 200 whose re-read still serves the review never says approved or APPROVED', async () => {
    onDecide = (body, path) => answer(taskOf(path), body.verdict as string);
    await open(item('W-4002'));
    await ready('Approve forecast');
    await click('Approve forecast');
    await waitFor(() => expect(posts('/decision')).toHaveLength(1));
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-4002').length).toBeGreaterThanOrEqual(3));
    expect(status().textContent).toBe('AWAITING FINANCE DECISION');
    expect(said()).not.toMatch(/APPROVED|[Vv]erified/);
  });

  it('return and reject need a note: empty, blank and over 2000 characters send nothing; with a note one POST with the trimmed note and RETURNED', async () => {
    await open(item('W-4002'));
    await ready('Approve forecast');
    await click('Return with a note');
    expect(await screen.findByText('Add a note to return it.')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(note()));
    expect(note().getAttribute('aria-invalid')).toBe('true');
    fireEvent.change(note(), { target: { value: '   ' } });
    await click('Reject');
    expect(await screen.findByText('Add a note to reject it.')).toBeTruthy();
    fireEvent.change(note(), { target: { value: 'x'.repeat(2001) } });
    await click('Return with a note');
    expect(await screen.findByText('Keep the note to 2000 characters or fewer.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    fireEvent.change(note(), { target: { value: '  Check the January receipts.  ' } });
    await click('Return with a note');
    await waitFor(() => expect(status().textContent).toBe('RETURNED'));
    expect(posts('/decision').map((p) => p.body)).toEqual([{ verdict: 'return', expected_revision: 1, note: 'Check the January receipts.' }]);
    expect(decideRequest(posts('/decision')[0].body)).toBe(true);
    expect(buttons()).toEqual([]);
  });

  it('reject with a note shows the REJECTED state the re-read returns', async () => {
    await open(item('W-4002'));
    await ready('Approve forecast');
    fireEvent.change(note(), { target: { value: 'Not this month.' } });
    await click('Reject');
    await waitFor(() => expect(status().textContent).toBe('REJECTED'));
    expect(posts('/api/v1/tasks/T-4002/decision')[0].body).toEqual({ verdict: 'reject', expected_revision: 1, note: 'Not this month.' });
    expect(buttons()).toEqual([]);
  });
});

describe('refusals and uncertain decides (AC 16, 17, 20)', () => {
  it('403 on decide: read-only from the re-read reason, no approved', async () => {
    onDecide = () => {
      served = { ...item('W-4002'), tasks: [{ ...item('W-4002').tasks[0], you_can_act: false, cannot_act_reason: 'not_your_role' }] };
      return json(403, { code: 'forbidden', message: 'No.' });
    };
    await open(item('W-4002'));
    await ready('Approve forecast');
    await click('Approve forecast');
    expect(await ws().findByText('This decision needs a Forecast reviewer.')).toBeTruthy();
    expect(said()).not.toMatch(/approved/i);
    expect(buttons().filter((b) => b === 'Approve forecast')).toHaveLength(0);
  });

  it('409: the stale view keeps the note; a new press after Review the latest carries the new revision', async () => {
    const newer = { ...item('W-4002'), revision: 2, tasks: [{ ...item('W-4002').tasks[0], revision: 2 }] };
    onDecide = () => {
      served = newer;
      return json(409, { code: 'stale', message: 'Changed.' });
    };
    await open(item('W-4002'));
    await ready('Approve forecast');
    fireEvent.change(note(), { target: { value: 'Check January.' } });
    await click('Return with a note');
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(1);
    await click('Review the latest');
    await ready('Approve forecast');
    expect(note().value).toBe('Check January.');
    onDecide = (body, path) => answer(taskOf(path), body.verdict as string);
    await click('Return with a note');
    await waitFor(() => expect(posts('/decision')).toHaveLength(2));
    expect(posts('/decision')[1].body!.expected_revision).toBe(2);
  });

  it('409 after another reviewer decided first: the closed task keeps the lasting stale notice and the unsent note, with no decide buttons', async () => {
    onDecide = () => {
      served = item('W-4002.approve');
      return json(409, { code: 'stale_revision', message: 'Someone changed this since you opened it.' });
    };
    await open(item('W-4002'));
    await ready('Approve forecast');
    fireEvent.change(note(), { target: { value: '  Check January first.  ' } });
    await click('Return with a note');
    expect(await ws().findByText('This review changed while you were reading it, so nothing was recorded.')).toBeTruthy();
    expect(ws().getByText('Your note wasn’t sent: “Check January first.”')).toBeTruthy();
    expect(document.querySelector('.ws-idecide')).toBeNull();
    expect(buttons().filter((b) => /Approve forecast|Return with a note|Reject/.test(b))).toEqual([]);
    expect(posts('/decision')).toHaveLength(1);
  });

  it('422: the backend message under the note', async () => {
    onDecide = () => json(422, { code: 'invalid', message: 'Say which month.', fields: [{ name: 'note', message: 'Say which month.' }] });
    await open(item('W-4002'));
    await ready('Approve forecast');
    fireEvent.change(note(), { target: { value: 'Fix it.' } });
    await click('Return with a note');
    expect(await ws().findByText('Say which month.')).toBeTruthy();
  });

  for (const [name, reply] of [
    ['a 500', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['a timeout', () => Promise.reject(new DOMException('Timed out', 'TimeoutError'))],
  ] as const) {
    it(`${name} re-reads first, shows the uncertain notice, says nothing was decided and never sends again by itself`, async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'setInterval'], shouldAdvanceTime: true });
      onDecide = reply as unknown as Handler;
      await open(item('W-4002'));
      await ready('Approve forecast');
      const before = sent.length;
      await click('Approve forecast');
      expect(await screen.findByText(/We couldn.t confirm your decision/)).toBeTruthy();
      const after = sent.slice(before);
      expect(after[0].path).toBe('/api/v1/tasks/T-4002/decision');
      expect(after[1]).toMatchObject({ method: 'GET', path: '/api/v1/work/W-4002' });
      expect(said()).not.toMatch(/is approved|was returned|was rejected|APPROVED|RETURNED|REJECTED/i);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(posts('/decision')).toHaveLength(1);
    }, 90_000);
  }

  it('W-4013: each verdict ends on the re-read DECISION NOT CONFIRMED with no success words', async () => {
    for (const verdict of ['approve', 'return', 'reject'] as const) {
      sent = [];
      await open(item('W-4013'));
      await ready('Approve forecast');
      if (verdict !== 'approve') fireEvent.change(note(), { target: { value: 'Check January.' } });
      await click(verdict === 'approve' ? 'Approve forecast' : verdict === 'return' ? 'Return with a note' : 'Reject');
      await waitFor(() => expect(status().textContent, verdict).toBe('DECISION NOT CONFIRMED'));
      expect(said(), verdict).not.toMatch(/is approved|was returned|was rejected|APPROVED|RETURNED|REJECTED/i);
      expect(document.querySelector('.ws-live .psl-callout--success')).toBeNull();
      expect(posts('/decision')).toHaveLength(1);
      expect(buttons().filter((b) => /Approve|Return|Reject/.test(b ?? ''))).toEqual([]);
      cleanup();
    }
  });

  it('401 on decide and on read show the signed-out state with next=/work/<id>', async () => {
    onDecide = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await open(item('W-4002'));
    await ready('Approve forecast');
    await click('Approve forecast');
    expect((await screen.findByRole('link', { name: /sign in/i })).getAttribute('href')).toContain('next=%2Fwork%2FW-4002');
    cleanup();
    readAnswer = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    served = item('W-4003');
    render(
      <AppShell>
        <WorkItemView id="W-4003" tab="overview" />
      </AppShell>,
    );
    expect((await screen.findByRole('link', { name: /sign in/i })).getAttribute('href')).toContain('next=%2Fwork%2FW-4003');
  });

  it('403 and 404 on read look the same: no title, amount, fact or figure; persona none gets it with no further call', async () => {
    for (const code of [403, 404]) {
      readAnswer = () => json(code, { code: code === 403 ? 'forbidden' : 'not_found', message: 'No.' });
      served = item('W-4002');
      render(
        <AppShell>
          <WorkItemView id="W-4002" tab="overview" />
        </AppShell>,
      );
      await screen.findByText(/isn.t open to you|can.t open|not open/i);
      expect(document.body.textContent).not.toMatch(/Cash forecast|22,600,000|Kola Foods|FC-0014/);
      cleanup();
    }
    who = 'none';
    sent = [];
    readAnswer = () => json(403, { code: 'forbidden', message: 'No.' });
    render(
      <AppShell>
        <WorkItemView id="W-4002" tab="overview" />
      </AppShell>,
    );
    await screen.findByText('No sections are open to your role yet.');
    await settle();
    expect(sent.filter((r) => r.path.startsWith('/api/v1/work/'))).toHaveLength(0);
    expect(writes()).toHaveLength(0);
  });
});

describe('record what happened (AC 12, 18, 19)', () => {
  for (const width of ['phone', 'desktop'] as const) {
    it(`${width}: a press with no choice sends nothing and asks for one (UX-1-1: the button is pressable at both widths)`, async () => {
      if (width === 'phone') phone();
      await open(item('W-4003'));
      expect(record().disabled).toBe(false);
      fireEvent.click(record());
      expect(screen.getByRole('alert').textContent).toBe('Choose what happened to continue.');
      await settle();
      expect(writes()).toHaveLength(0);
      // a choice clears the ask
      choose(/^It didn’t arrive\./);
      expect(screen.queryByText('Choose what happened to continue.')).toBeNull();
    });
  }

  it('"It arrived": button off until the proof is uploaded, one POST with evidence_id and case_revision, Verified only after the re-read', async () => {
    await open(item('W-4003'));
    choose(/^It arrived\./);
    expect(record().disabled).toBe(true);
    // UX-1-1: the off button says why, beside it
    const why = screen.getByText('Upload the proof to continue.');
    expect(record().getAttribute('aria-describedby')).toBe(why.id);
    const before = posts('/evidence').length;
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [new File([new Uint8Array(2048).fill(37)], 'ceo-receipt.pdf', { type: 'application/pdf' })] } });
    await waitFor(() => expect(posts('/evidence')).toHaveLength(before + 1));
    expect(posts('/evidence')[0]).toMatchObject({ path: '/api/v1/cases/C-4003/evidence', body: { kind: 'delivery_receipt', case_revision: 2 }, csrf: 'mock-csrf-finance_lead' });
    await waitFor(() => expect(record().disabled).toBe(false));
    expect(screen.queryByText('Upload the proof to continue.')).toBeNull();
    expect(record().hasAttribute('aria-describedby')).toBe(false);
    fireEvent.click(record());
    fireEvent.click(record());
    await screen.findByText('Recorded. Reloading the work item…');
    expect(posts('/actions')).toEqual([
      { method: 'POST', path: '/api/v1/work/W-4003/actions', csrf: 'mock-csrf-finance_lead', body: { expected_revision: 5, action: 'reconcile', outcome: 'delivered', evidence_id: 'EV-C-4003-1', case_revision: 3 } },
    ]);
    expect(actionRequest(posts('/actions')[0].body)).toBe(true);
    expect(posts('/steps').length + posts('/claim').length + posts('/decision').length).toBe(0);
    // nothing says Verified, Delivered or received from the 200 itself
    expect(status().textContent).toBe('EFFECT UNCERTAIN');
    expect(said()).not.toMatch(/verified|delivered|received/i);
    expect(reloadPage).toHaveBeenCalledTimes(1);
    // the reload reads the swapped item
    cleanup();
    await open(served);
    expect(status().textContent).toBe('VERIFIED');
    expect(panel()).toBeNull();
  });

  it('a 200 whose re-read still serves W-4003 never says Verified, Delivered or received', async () => {
    onAction = () => json(200, { work_id: 'W-4003', state: 'verified', revision: 6 });
    await open(item('W-4003'));
    choose(/^I can’t tell yet\./);
    fireEvent.click(record());
    await screen.findByText('Recorded. Reloading the work item…');
    cleanup();
    await open(served);
    expect(status().textContent).toBe('EFFECT UNCERTAIN');
    // the status, notices and side column only: the approved option label "I have proof it was received" stays (build.md)
    expect(said()).not.toMatch(/verified|delivered|received/i);
    expect(panel()).not.toBeNull();
  });

  for (const [outcome, label, state] of [
    ['not_delivered', /^It didn’t arrive\./, 'NOT DELIVERED · HELD'],
    ['unknown', /^I can’t tell yet\./, 'HELD'],
  ] as const) {
    it(`"${outcome}" sends one POST with that outcome and no evidence; the re-read shows ${state} with no resend`, async () => {
      await open(item('W-4003'));
      choose(label);
      fireEvent.click(record());
      fireEvent.click(record());
      await screen.findByText('Recorded. Reloading the work item…');
      expect(posts('/actions').map((p) => p.body)).toEqual([{ expected_revision: 5, action: 'reconcile', outcome }]);
      expect(actionRequest(posts('/actions')[0].body)).toBe(true);
      expect(writes()).toHaveLength(1);
      cleanup();
      await open(served);
      expect(status().textContent).toBe(state);
      expect(panel()).toBeNull();
      expect(document.body.textContent).not.toMatch(/Send again|Resend|Retry|Cancel delivery/);
    });
  }

  it('500, network failure and timeout say "We couldn’t confirm your answer…" and send nothing again; 409 the stale sentence; 403 and 422 the backend message', async () => {
    for (const reply of [() => json(500, { code: 'server_error', message: 'Down.' }), () => Promise.reject(new TypeError('Failed to fetch')), () => Promise.reject(new DOMException('Timed out', 'TimeoutError'))]) {
      sent = [];
      onAction = reply as unknown as Handler;
      await open(item('W-4003'));
      choose(/^I can’t tell yet\./);
      fireEvent.click(record());
      await screen.findByText('We couldn’t confirm your answer. Reload the work item to see whether it was recorded.');
      await settle();
      expect(posts('/actions')).toHaveLength(1);
      expect(reloadPage).not.toHaveBeenCalled();
      cleanup();
    }
    let n = 0;
    onAction = () => {
      n += 1;
      return n === 1
        ? json(409, { code: 'stale_revision', message: 'Changed.' })
        : n === 2
          ? json(403, { code: 'forbidden', message: 'Your role does not allow this.' })
          : json(422, { code: 'invalid', message: 'Check these fields: outcome.' });
    };
    await open(item('W-4003'));
    choose(/^I can’t tell yet\./);
    fireEvent.click(record());
    await screen.findByText('This item changed. Reload it to see the latest.');
    cleanup();
    await open(item('W-4003'));
    choose(/^I can’t tell yet\./);
    fireEvent.click(record());
    await screen.findByText('Your role does not allow this.');
    fireEvent.click(record());
    await screen.findByText('Check these fields: outcome.');
    // after a reload the item's own reconcile keeps the lock: no send control
    cleanup();
    await open(item('W-4003'));
    expect(panel()).not.toBeNull();
    expect(document.body.textContent).not.toMatch(/Send again|Resend|Retry|Cancel delivery/);
  });

  it('other lines keep the client-invoice words (W-1603)', () => {
    const src = readFileSync(join(__dirname, '../src/features/response/ReconcilePanel.tsx'), 'utf8');
    expect(src.match(/invoiced twice/g)).toHaveLength(1);
  });
});

describe('phone (AC 21)', () => {
  it('the step labels in the pinned bar; Return with a note opens the Drawer with the note; Cancel closes it and returns focus', async () => {
    phone();
    await open(item('W-4002'));
    await ready('Approve forecast');
    expect(buttons()).toEqual(['Approve forecast', 'Return with a note', 'Reject']);
    expect(document.querySelector('.ws-ministations')!.textContent).toContain('Station 3 of 8 · Review');
    await click('Return with a note');
    const dialog = await screen.findByRole('dialog', { name: 'Return with a note' });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Return with a note' }));
    });
    expect(await within(dialog).findByText('Add a note to return it.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement?.textContent).toBe('Return with a note'));
  });

  it('the phone reconcile panel is named "Record what happened" and the uncertain page shows the same banner, facts and Next as desktop', async () => {
    phone();
    await open(item('W-4003'));
    expect(panel()).not.toBeNull();
    // TECH-1-4: exactly one panel on a phone too
    expect(document.querySelectorAll('.resp-reconcile')).toHaveLength(1);
    // UI-1-3: the board's order: stations, banner, Delivery, Next, then the choices above the pinned button
    const banner = ws().getByText("We don't know if the CEO received the forecast. The delivery is held; it can't be sent again until someone checks.");
    const order = [document.querySelector('.ws-ministations')!, banner, ws().getByRole('heading', { name: 'Delivery' }), ws().getByRole('heading', { name: 'Next' }), panel()!];
    for (let i = 1; i < order.length; i++) expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING, `${i}`).toBeTruthy();
    // nothing of the panel is drawn ahead of the workspace
    expect(document.querySelector('.ws')!.contains(panel()!)).toBe(true);
    expect(ws().getByText("We don't know if the CEO received the forecast. The delivery is held; it can't be sent again until someone checks.")).toBeTruthy();
    expect(factValue('Sent')).toBe('14 NOV 09:00');
    expect(screen.getAllByText("Check with the CEO's office, then record it.").length).toBeGreaterThan(0);
  });
});

describe('other lines are unchanged', () => {
  it('W-2701 keeps the income line frame; W-1603 keeps the "Confirm what happened" panel', async () => {
    await open(item('W-2701'));
    expect(document.querySelectorAll('.ws-stations .psl-station')).toHaveLength(5);
    cleanup();
    served = read('response/work/W-1603.json');
    render(
      <AppShell>
        <WorkItemView id="W-1603" tab="overview" />
      </AppShell>,
    );
    expect(await screen.findByRole('complementary', { name: 'Confirm what happened' })).toBeTruthy();
    expect(panel()).toBeNull();
  });
});
