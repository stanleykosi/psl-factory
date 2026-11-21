// @vitest-environment jsdom
// F-40 SCR-48: the handover to Support as the fixtures return it (contract mock only). Nothing here publishes to Support, and no
// Support person receives or replies to anything: every "published", "received", "acknowledged" and "Femi Ojo" is fixture text
// the response returned. The page says them only after the re-read says so; the PM records Support's reply with proof.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';
import { setWhen } from './controls';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-3701',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const side = (name: string): WorkItem => read(`response/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path: string) => ajv.compile(openapi.paths[path].post.requestBody.content['application/json'].schema);
const responseRequest = schemaOf('/api/v1/tasks/{task_id}/response');
const stepRequest = schemaOf('/api/v1/work/{work_id}/steps');

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = Response | (() => Response | Promise<Response>);
let sent: Sent[];
let reads: Record<string, (WorkItem | (() => Response | Promise<Response>))[]>;
let writes: Record<string, Answer[]>;
let who: string;
let uploads: number;

const posts = (suffix: string) => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const itemReads = (id: string) => sent.filter((r) => r.method === 'GET' && r.path === `/api/v1/work/${id}`);
const SUFFIX = /\/(steps|response|claim|evidence)$/;
const GAPS = ['No contact for the credit bureau outage', 'Runbook misses the nightly export restart'];

beforeEach(() => {
  sent = [];
  reads = {};
  writes = {};
  who = 'pm';
  uploads = 0;
  vi.stubGlobal(
    'fetch',
    withoutBellFeed(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.text();
      sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
      if (url.pathname === '/api/v1/me') return json(200, read(`me.${who}.json`));
      const itemMatch = /^\/api\/v1\/work\/(W-\d+)$/.exec(url.pathname);
      if (request.method === 'GET' && itemMatch) {
        const queue = reads[itemMatch[1]];
        if (!queue) return json(404, { code: 'not_found', message: 'Not here.' });
        const next = queue.length > 1 ? queue.shift()! : queue[0];
        return typeof next === 'function' ? next() : json(200, next);
      }
      const write = SUFFIX.exec(url.pathname);
      if (request.method === 'POST' && write) {
        if (write[1] === 'evidence' && !writes.evidence) {
          uploads += 1;
          const body = JSON.parse(text) as { case_revision: number };
          return json(200, { evidence_id: `EV-${uploads}`, sha256: 'a'.repeat(64), case_revision: body.case_revision + 1 });
        }
        const queue = writes[write[1]] ?? [ok()];
        const answer = queue.length > 1 ? queue.shift()! : queue[0];
        return typeof answer === 'function' ? answer() : answer;
      }
      return json(404, { code: 'not_found', message: 'Not here.' });
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ok = (body: Record<string, unknown> = {}) => json(200, { work_id: 'W-0', state: 'ready', revision: 9, outcome: 'done', ...body });
function phone() {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
}

async function open(first: WorkItem, ...later: (WorkItem | (() => Response | Promise<Response>))[]) {
  reads[first.id] = [first, ...later];
  const view = render(
    <AppShell>
      <WorkItemView id={first.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1 });
  return view;
}

const ws = () => within(document.querySelector('.ws') as HTMLElement);
const pageText = () => document.body.textContent ?? '';
const wsText = () => (document.querySelector('.ws') as HTMLElement).textContent ?? '';
const notices = () => [document.querySelector('.ws-notices'), document.querySelector('.cmp-toasts')].map((el) => el?.textContent ?? '').join(' ');
const press = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
const ready = () => screen.findByRole('radio', { name: 'Received' });
const panel = () => within(screen.getByRole('region', { name: 'Record Support’s reply' }));
const recordButton = () => panel().getByRole('button', { name: 'Record reply' }) as HTMLButtonElement;
const uploadProof = async () => {
  const input = document.querySelector('.ws input[type="file"]') as HTMLInputElement;
  await act(async () => {
    fireEvent.change(input, { target: { files: [new File(['%PDF-1.4'], 'support-reply-10apr.pdf', { type: 'application/pdf' })] } });
  });
  await waitFor(() => expect(panel().getByText(/Uploaded/)).toBeTruthy());
};
async function fill({ action = 'Gaps found', gaps = GAPS.join('\n'), proof = true, attest = true, when = true } = {}) {
  await ready();
  if (when) setWhen('When they replied', '2026-04-10T11:00', panel());
  fireEvent.click(panel().getByRole('radio', { name: action }));
  if (action === 'Gaps found' && gaps) fireEvent.change(panel().getByLabelText('Gaps'), { target: { value: gaps } });
  if (proof) await uploadProof();
  if (attest) fireEvent.click(panel().getByRole('checkbox', { name: 'I confirm this response is genuine.' }));
}
const buttonsAndLinks = (root: HTMLElement) => [...root.querySelectorAll('button, a[href], input, select, textarea, form')];

describe('four states from the fixture (AC 4)', () => {
  it('W-3701 ready to publish: status, facts, Tola’s steps, Next, the one step and the Ask Tola link; the consequence once', async () => {
    await open(item('W-3701'));
    expect(pageText()).toContain('Handover · ready to publish');
    expect(ws().getByText('Handover to Support')).toBeTruthy();
    expect(ws().getByText('Review needed?')).toBeTruthy();
    expect(ws().getByText('No · below the rule’s threshold')).toBeTruthy();
    expect(ws().getByText('REL-0091 · GLV-0104 · ARC-0130')).toBeTruthy();
    expect(ws().getByText('As of 08 Apr 14:30 WAT')).toBeTruthy();
    expect(ws().getAllByRole('button').map((b) => b.textContent)).toEqual(['Publish to Support']);
    expect(ws().getByRole('link', { name: 'Ask Tola' }).getAttribute('href')).toBe('/assistant');
    expect(wsText().match(/Publishing sends it to Support/g)).toHaveLength(1);
    expect(wsText()).not.toContain('This sends to the client.');
    expect(wsText()).not.toMatch(/published|acknowledged/i);
  });

  it('W-3703 record: the reply form is drawn in place, titled with the step’s label, and the step is not a button', async () => {
    await open(item('W-3703'));
    expect(pageText()).toContain('Handover · published 08 Apr');
    expect(screen.getByRole('region', { name: 'Record Support’s reply' })).toBeTruthy();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(ws().queryByRole('button', { name: 'Record Support’s reply' })).toBeNull();
  });

  it('W-3704 gaps: the returned banner, two OPEN gaps and Ask Tola to draft v2', async () => {
    await open(item('W-3704'));
    expect(pageText()).toContain('Gaps · 2');
    expect(ws().getByText(/Support listed 2 gaps on 10 Apr/)).toBeTruthy();
    expect(ws().getAllByText('OPEN')).toHaveLength(2);
    expect(ws().getByText('No contact for the credit bureau outage')).toBeTruthy();
    expect(ws().getByRole('button', { name: 'Ask Tola to draft v2' })).toBeTruthy();
    expect(ws().getByText(/Tola drafts v2 covering both gaps/)).toBeTruthy();
  });

  it('W-3705 acknowledged: the green banner, Next and the closure link to W-3720', async () => {
    await open(item('W-3705'));
    expect(pageText()).toContain('Handover acknowledged');
    expect(document.querySelector('.ws .ws-note.psl-callout--success')).toBeTruthy();
    expect(ws().getByText(/Recorded by Tunde Bello with Support’s reply as proof, verified/)).toBeTruthy();
    expect(ws().getByText(/Closure needs this. Remaining: hypercare and the retrospective./)).toBeTruthy();
    expect(ws().getByRole('link', { name: 'See what closure needs' }).getAttribute('href')).toBe('/work/W-3720');
    expect(ws().queryAllByRole('button')).toHaveLength(0);
  });

  it('draws the same sections at 390 and 1440', async () => {
    phone();
    await open(item('W-3704'));
    expect(ws().getAllByText('OPEN')).toHaveLength(2);
    expect(ws().getByRole('button', { name: 'Ask Tola to draft v2' })).toBeTruthy();
  });
});

describe('round 2: the boards’ tones, rows, form fields, phone headings and Back', () => {
  const stateTag = () => document.querySelector('.work-state') as HTMLElement;
  it('the state chip takes its tone from the data: amber for ready and published, red for gaps, green for acknowledged', async () => {
    for (const [id, cls] of [['W-3701', 'psl-tag--waiting'], ['W-3703', 'psl-tag--waiting'], ['W-3704', 'psl-tag--person'], ['W-3705', 'psl-tag--done']] as const) {
      await open(item(id));
      expect(stateTag().className).toContain(cls);
      cleanup();
    }
  });

  it('the DRAFT row tag is the agent tone and the review row tag stays neutral (rows are laid out by CSS on data-line)', async () => {
    await open(item('W-3701'));
    expect(document.querySelector('.ws')!.getAttribute('data-line')).toBe('delivery_handover');
    expect(ws().getByText('DRAFT').className).toContain('psl-tag--agent');
    expect(ws().getByText('No · below the rule’s threshold').className).toContain('psl-tag--neutral');
  });

  it('Support replied is one field holding who replied and when; the Proof label and the gaps hint are screen-reader only; the tick stays', async () => {
    await open(item('W-3703'));
    await ready();
    const p = panel();
    const group = p.getByRole('group', { name: 'Support replied' });
    expect(within(group).getByText('Femi Ojo · Support lead')).toBeTruthy();
    expect(within(group).getByLabelText('When they replied')).toBeTruthy();
    expect(p.getByText('When they replied').className).toContain('cmp-sr');
    expect(p.getByText('Proof of the reply').className).toContain('cmp-sr');
    fireEvent.click(p.getByRole('radio', { name: 'Gaps found' }));
    expect(p.getByText('One gap per line.').className).toContain('cmp-sr');
    expect(p.getByRole('checkbox', { name: /I confirm this response is genuine/ })).toBeTruthy();
  });

  it('at 390 the heading is the board’s screen heading, from the data, and the project title is not the h1', async () => {
    phone();
    for (const [id, heading] of [['W-3701', 'Support handover'], ['W-3703', 'Support\'s reply'], ['W-3704', 'Support found gaps'], ['W-3705', 'Handover acknowledged']] as const) {
      await open(item(id));
      expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(heading);
      expect(document.querySelectorAll('.ws-title')).toHaveLength(0);
      cleanup();
    }
  });

  it('at 1440 the h1 stays the project title and the screen heading is not drawn', async () => {
    await open(item('W-3703'));
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · patient app');
    expect(screen.queryByRole('heading', { name: 'Support\'s reply' })).toBeNull();
  });

  it('at 390 Back from the handover says Delivery and goes to the project’s Delivery tab, not the Queue', async () => {
    phone();
    await open(item('W-3704'));
    const back = screen.getByRole('link', { name: /Delivery/, hidden: false });
    expect(back.textContent).toContain('Delivery');
    expect(back.getAttribute('href')).toBe('/projects/P-0101/delivery');
    expect(screen.queryByRole('link', { name: /Queue/ })).toBeNull();
  });
});

describe('the hold has no controls (AC 5)', () => {
  it('W-3702: Review needed? reads Unknown, the Next sentence shows and nothing in the workspace can be pressed', async () => {
    await open(item('W-3702'));
    const root = document.querySelector('.ws') as HTMLElement;
    expect(within(root).getByText('Review needed?').closest('li')!.textContent).toContain('Unknown');
    expect(wsText()).toContain('Publishing waits until PSL sets when a handover needs review (Setup › Rules).');
    expect(buttonsAndLinks(root)).toHaveLength(0);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });
});

describe('Publish (AC 6, 7)', () => {
  it('sends one step with the revision, a key and CSRF; a double press sends one; "published 08 Apr" waits for the re-read', async () => {
    let release!: (response: Response) => void;
    const held = new Promise<Response>((resolve) => {
      release = resolve;
    });
    writes.steps = [ok({ outcome: 'done' })];
    await open(item('W-3701'), () => (posts('/steps').length > 0 ? held.then((r) => r.clone()) : json(200, item('W-3701'))));
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Publish to Support' }));
      fireEvent.click(ws().getByRole('button', { name: 'Publish to Support' }));
    });
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    const call = posts('/steps')[0];
    expect(call.path).toBe('/api/v1/work/W-3701/steps');
    expect(call.csrf).toBe('mock-csrf-pm');
    expect(call.body).toMatchObject({ step: 'publish', expected_revision: 1 });
    expect(typeof call.body!.idempotency_key).toBe('string');
    expect(stepRequest(call.body), ajv.errorsText(stepRequest.errors)).toBe(true);
    await waitFor(() => expect(itemReads('W-3701').length).toBeGreaterThan(1));
    expect(pageText()).not.toMatch(/published 08 Apr/i);
    expect(notices()).not.toMatch(/Done/);
    await act(async () => {
      release(json(200, item('W-3701.next')));
    });
    await waitFor(() => expect(pageText()).toContain('Handover · published 08 Apr'));
    expect(screen.getByRole('region', { name: 'Record Support’s reply' })).toBeTruthy();
  });

  it('W-3706 (200 effect_uncertain): the uncertain banner and the reconcile panel; Publish is off and a second press sends nothing', async () => {
    writes.steps = [ok({ outcome: 'effect_uncertain', message: 'We couldn’t confirm Support received the handover.' })];
    await open(item('W-3706'), item('W-3706.next'));
    await press('Publish to Support');
    await waitFor(() => expect(pageText()).toContain('Handover · delivery unconfirmed'));
    expect(pageText()).toContain('We couldn’t confirm Support received the handover.');
    expect(await screen.findByText(/It arrived\./)).toBeTruthy();
    expect(ws().getByRole('button', { name: 'Publish to Support' }).getAttribute('aria-disabled')).toBe('true');
    await press('Publish to Support');
    expect(posts('/steps')).toHaveLength(1);
    expect(pageText()).not.toMatch(/Handover · published|Support received it|has been sent/i);
  });

  it('W-3707 (reply lost, 502): the same hold, no resend', async () => {
    writes.steps = [json(502, { code: 'mock_lost', message: 'The mock dropped this reply.' })];
    await open(item('W-3707'), item('W-3707.next'));
    await press('Publish to Support');
    await waitFor(() => expect(pageText()).toContain('Handover · delivery unconfirmed'));
    expect(ws().getByRole('button', { name: 'Publish to Support' }).getAttribute('aria-disabled')).toBe('true');
    await press('Publish to Support');
    expect(posts('/steps')).toHaveLength(1);
  });

  it('W-3708 (409): the stale notice and the re-read’s status, no Done', async () => {
    writes.steps = [json(409, { code: 'conflict', message: 'Changed.' })];
    await open(item('W-3708'), item('W-3708.next'));
    await press('Publish to Support');
    await waitFor(() => expect(pageText()).toContain('This changed while you were working. Showing version 2.'));
    await waitFor(() => expect(pageText()).toContain('Handover · published 08 Apr'));
    expect(notices()).not.toMatch(/Done/);
  });

  it('a network failure locks Publish, re-reads and asks for a check before trying again', async () => {
    writes.steps = [() => Promise.reject(new TypeError('Failed to fetch'))];
    await open(item('W-3701'));
    const before = itemReads('W-3701').length;
    await press('Publish to Support');
    await waitFor(() => expect(pageText()).toContain('We couldn’t confirm this step. Check the page before trying again.'));
    await waitFor(() => expect(itemReads('W-3701').length).toBeGreaterThan(before));
    expect(ws().getByRole('button', { name: 'Publish to Support' }).getAttribute('aria-disabled')).toBe('true');
    expect(posts('/steps')).toHaveLength(1);
    expect(notices()).not.toMatch(/Done/);
  });
});

describe('Draft v2 is Tola’s work (AC 8)', () => {
  it('sends one step, says Tola is drafting, then shows the re-read’s Drafting v2 with the gaps still OPEN and no green banner', async () => {
    writes.steps = [ok({ outcome: 'queued', message: 'Tola is drafting v2.' })];
    await open(item('W-3704'), () => json(200, posts('/steps').length > 0 ? item('W-3704.next') : item('W-3704')));
    await press('Ask Tola to draft v2');
    await waitFor(() => expect(pageText()).toContain('Drafting v2'));
    expect(posts('/steps')).toHaveLength(1);
    expect(posts('/steps')[0].body).toMatchObject({ step: 'draft_v2', expected_revision: 1 });
    await waitFor(() => expect(notices()).toContain('Waiting: Tola is drafting v2.'));
    expect(ws().getAllByText('OPEN')).toHaveLength(2);
    expect(document.querySelector('.ws .ws-note.psl-callout--success')).toBe(null);
    expect(pageText()).not.toMatch(/Handover acknowledged|v2 published/i);
    expect(ws().queryByRole('button', { name: 'Ask Tola to draft v2' })).toBeNull();
  });
});

describe('the form comes only from the response (AC 9)', () => {
  it('shows the fixed responder, the date-time, the returned choices (none chosen), proof and the tick, Next and the intro; Gaps only after Gaps found', async () => {
    await open(item('W-3703'));
    await ready();
    const p = panel();
    expect(p.getByText('Support replied')).toBeTruthy();
    expect(p.getByText('Femi Ojo · Support lead')).toBeTruthy();
    expect(p.getByLabelText('When they replied')).toBeTruthy();
    expect(p.getAllByRole('radio').map((r) => (r as HTMLInputElement).labels![0].textContent)).toEqual(['Received', 'Gaps found']);
    expect(p.getAllByRole('radio').every((r) => !(r as HTMLInputElement).checked)).toBe(true);
    expect(p.queryByLabelText('Gaps')).toBeNull();
    expect(p.getByText(/gaps go back to Tola for v2 of the handover/)).toBeTruthy();
    expect(p.getByText('Support doesn’t log in. You record their reply with proof, and the record keeps your name.')).toBeTruthy();
    expect(p.getByRole('checkbox', { name: 'I confirm this response is genuine.' })).toBeTruthy();
    expect(recordButton().disabled).toBe(true);
    fireEvent.click(p.getByRole('radio', { name: 'Gaps found' }));
    expect(p.getByLabelText('Gaps')).toBeTruthy();
    expect(p.getByText('One gap per line.')).toBeTruthy();
    fireEvent.click(p.getByRole('radio', { name: 'Received' }));
    expect(p.queryByLabelText('Gaps')).toBeNull();
  });

  it('actions without labels offer no choice and no form: the step is unavailable', async () => {
    const body = item('W-3703');
    for (const a of body.tasks[0].response!.actions) delete (a as { label?: string }).label;
    await open(body);
    expect(screen.queryByRole('region', { name: 'Record Support’s reply' })).toBeNull();
    expect(ws().getByRole('button', { name: 'Record Support’s reply' }).getAttribute('aria-disabled')).toBe('true');
  });

  for (const persona of ['pm', 'finance_lead']) {
    it(`W-3709 as ${persona}: no form; the step is unavailable and names the returned role`, async () => {
      who = persona;
      await open(item('W-3709'));
      expect(screen.queryByRole('region', { name: 'Record Support’s reply' })).toBeNull();
      const button = ws().getByRole('button', { name: 'Record Support’s reply' });
      expect(button.getAttribute('aria-disabled')).toBe('true');
      expect(wsText()).toContain('This decision needs a PM.');
      expect(ws().queryByRole('link', { name: 'Record Support’s reply' })).toBeNull();
    });
  }

  it('a step whose task is not in the item is unavailable with the default sentence', async () => {
    const body = item('W-3703');
    body.tasks = [];
    await open(body);
    expect(ws().getByRole('button', { name: 'Record Support’s reply' }).getAttribute('aria-disabled')).toBe('true');
    expect(wsText()).toContain('This decision isn’t open to you here.');
  });
});

describe('recording the reply (AC 10, 11, 12)', () => {
  it('Record stays off without the proof, the tick or a gap, and the line says what is missing', async () => {
    await open(item('W-3703'));
    await fill({ proof: false, attest: false });
    expect(recordButton().disabled).toBe(true);
    expect(panel().getByText('Add the proof and confirm it’s genuine to record this.')).toBeTruthy();
    await uploadProof();
    expect(recordButton().disabled).toBe(true);
    fireEvent.click(panel().getByRole('checkbox', { name: 'I confirm this response is genuine.' }));
    expect(recordButton().disabled).toBe(false);
    fireEvent.change(panel().getByLabelText('Gaps'), { target: { value: ' \n  ' } });
    expect(recordButton().disabled).toBe(true);
    expect(panel().getByText('Add at least one gap to record this.')).toBeTruthy();
    await act(async () => {
      fireEvent.click(recordButton());
    });
    expect(posts('/response')).toHaveLength(0);
  });

  it('Gaps found: the proof is uploaded first, then one POST with the gaps in order, no claim; the double press sends one; the notice and the gaps state come after the re-read', async () => {
    writes.response = [json(200, { task_id: 'T-3703', work_state: 'waiting' })];
    let release!: (response: Response) => void;
    const held = new Promise<Response>((resolve) => {
      release = resolve;
    });
    await open(item('W-3703'), () => (posts('/response').length > 0 ? held.then((r) => r.clone()) : json(200, item('W-3703'))));
    await fill({ gaps: `  ${GAPS[0]}  \n\n${GAPS[1]}\n` });
    await act(async () => {
      fireEvent.click(recordButton());
      fireEvent.click(recordButton());
    });
    await waitFor(() => expect(posts('/response')).toHaveLength(1));
    const order = sent.filter((r) => r.method === 'POST').map((r) => r.path);
    expect(order).toEqual(['/api/v1/cases/P-0101/evidence', '/api/v1/tasks/T-3703/response']);
    expect(posts('/claim')).toHaveLength(0);
    const call = posts('/response')[0];
    expect(call.csrf).toBe('mock-csrf-pm');
    expect(call.body).toEqual({
      expected_revision: 1,
      who: 'R-3701',
      action: 'changes_requested',
      responded_at: '2026-04-10T11:00:00+01:00',
      evidence_id: 'EV-1',
      attested: true,
      case_revision: 3,
      version_id: 'V-3701',
      gaps: GAPS,
    });
    const { gaps, ...rest } = call.body!;
    expect(gaps).toEqual(GAPS);
    expect(responseRequest(rest), ajv.errorsText(responseRequest.errors)).toBe(true);
    // the re-read has not resolved: nothing says recorded, received or acknowledged
    await waitFor(() => expect(itemReads('W-3703').length).toBeGreaterThan(1));
    expect(pageText()).not.toMatch(/Recorded under your name|acknowledged|Gaps · 2/);
    await act(async () => {
      release(json(200, side('W-3703.recorded.changes_requested')));
    });
    await waitFor(() => expect(pageText()).toContain('Gaps · 2'));
    expect(await screen.findByText(/Recorded under your name/)).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Record Support’s reply' })).toBeNull();
    expect(ws().getAllByText('OPEN')).toHaveLength(2);
    await waitFor(() => expect(document.activeElement?.tagName).toBe('H1'));
  });

  it('Received sends no gaps and the acknowledged state shows only from the re-read', async () => {
    writes.response = [json(200, { task_id: 'T-3703', work_state: 'verified' })];
    await open(item('W-3703'), () => json(200, posts('/response').length > 0 ? side('W-3703.recorded.approved') : item('W-3703')));
    await fill({ action: 'Received' });
    await act(async () => {
      fireEvent.click(recordButton());
    });
    await waitFor(() => expect(pageText()).toContain('Handover acknowledged'));
    const call = posts('/response')[0];
    expect(call.body).toMatchObject({ action: 'approved' });
    expect(call.body).not.toHaveProperty('gaps');
    expect(ws().getByRole('link', { name: 'See what closure needs' }).getAttribute('href')).toBe('/work/W-3720');
  });

  it('a claim comes first only when the response asks for it', async () => {
    const body = item('W-3703');
    body.tasks[0].response!.claim_required = true;
    writes.claim = [json(200, { task_id: 'T-3703', revision: 2 })];
    await open(body);
    await fill();
    await act(async () => {
      fireEvent.click(recordButton());
    });
    await waitFor(() => expect(posts('/response')).toHaveLength(1));
    expect(sent.filter((r) => r.method === 'POST').map((r) => r.path.split('/').pop())).toEqual(['evidence', 'claim', 'response']);
    expect(posts('/response')[0].body).toMatchObject({ expected_revision: 2 });
  });

  it('record-then-fail (written, then 502): re-reads, says so in the reply’s words, shows the gaps state from the re-read and sends nothing again', async () => {
    writes.response = [json(502, { code: 'mock_lost', message: 'The mock dropped this reply.' })];
    await open(item('W-3703'), () => json(200, posts('/response').length > 0 ? side('W-3703.recorded.changes_requested') : item('W-3703')));
    await fill();
    await act(async () => {
      fireEvent.click(recordButton());
    });
    await waitFor(() => expect(pageText()).toContain('Gaps · 2'));
    expect(pageText()).toContain('We couldn’t confirm the reply was recorded. We’ve reloaded this item so you can see whether it was.');
    expect(pageText()).not.toMatch(/Recorded under your name/);
    expect(posts('/response')).toHaveLength(1);
  });

  for (const [label, answer] of [['a 500', () => json(500, { code: 'server_error', message: 'x' })], ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))]] as const) {
    it(`${label} keeps every entry, shows the uncertain notice on the re-read form and sends nothing until a new press`, async () => {
      writes.response = [answer];
      await open(item('W-3703'));
      await fill();
      await act(async () => {
        fireEvent.click(recordButton());
      });
      expect(await screen.findByText('We couldn’t confirm the reply was recorded. We’ve reloaded this item so you can see whether it was.')).toBeTruthy();
      expect(posts('/response')).toHaveLength(1);
      expect((panel().getByLabelText('Gaps') as HTMLTextAreaElement).value).toBe(GAPS.join('\n'));
      expect((panel().getByRole('radio', { name: 'Gaps found' }) as HTMLInputElement).checked).toBe(true);
      expect(pageText()).not.toMatch(/Recorded under your name/);
      expect(recordButton().disabled).toBe(false);
      await act(async () => {
        fireEvent.click(recordButton());
      });
      expect(posts('/response')).toHaveLength(2);
    });
  }

  it('a 409 keeps the entries and shows the stale notice', async () => {
    writes.response = [json(409, { code: 'conflict', message: 'Changed.' })];
    await open(item('W-3703'));
    await fill();
    await act(async () => {
      fireEvent.click(recordButton());
    });
    expect(await screen.findByText(/This changed while you were recording/)).toBeTruthy();
    expect((panel().getByLabelText('Gaps') as HTMLTextAreaElement).value).toBe(GAPS.join('\n'));
    expect(pageText()).not.toMatch(/Recorded under your name/);
  });

  it('a 409 whose re-read shows the item moved on tells the page, which re-reads', async () => {
    writes.response = [json(409, { code: 'conflict', message: 'Changed.' })];
    await open(item('W-3703'), () => json(200, posts('/response').length > 0 ? side('W-3703.recorded.changes_requested') : item('W-3703')));
    await fill();
    await act(async () => {
      fireEvent.click(recordButton());
    });
    await waitFor(() => expect(pageText()).toContain('Gaps · 2'));
    expect(notices()).toContain('This changed while you were recording');
  });

  it('a 422 on gaps reads "Add at least one gap." under Gaps and keeps the form', async () => {
    writes.response = [json(422, { code: 'invalid', message: 'Check these fields: gaps.' })];
    await open(item('W-3703'));
    await fill();
    await act(async () => {
      fireEvent.click(recordButton());
    });
    expect(await screen.findByText('Add at least one gap.')).toBeTruthy();
    expect(panel().getByLabelText('Gaps').getAttribute('aria-invalid')).toBe('true');
    expect(panel().getByLabelText('Gaps').getAttribute('aria-describedby')).toContain(panel().getByText('Add at least one gap.').id);
    expect(pageText()).not.toMatch(/Recorded under your name/);
  });

  it('recorded text is under the PM’s name and never says Support logged in, signed or sent', async () => {
    writes.response = [json(200, { task_id: 'T-3703', work_state: 'waiting' })];
    await open(item('W-3703'), () => json(200, posts('/response').length > 0 ? side('W-3703.recorded.changes_requested') : item('W-3703')));
    await fill();
    await act(async () => {
      fireEvent.click(recordButton());
    });
    expect(await screen.findByText('Recorded under your name')).toBeTruthy();
    expect(pageText()).not.toMatch(/logged in|signed in as|support (sent|signed)/i);
  });

  it('on a phone Record reply sits in the pinned action bar', async () => {
    phone();
    await open(item('W-3703'));
    await ready();
    expect(recordButton().closest('.psl-actionbar')).toBeTruthy();
  });
});

describe('verified only from the backend (AC 13)', () => {
  it('W-3711: Tola’s "Support acknowledged the handover" is done, with no green banner, no acknowledged status and no closure link', async () => {
    await open(item('W-3711'));
    expect(ws().getByText('Support acknowledged the handover')).toBeTruthy();
    expect(pageText()).not.toContain('Handover acknowledged');
    expect(document.querySelector('.ws .ws-note.psl-callout--success')).toBe(null);
    expect(ws().queryByRole('link', { name: /closure/i })).toBeNull();
  });

  it('the same acknowledged text with a tone other than verified draws the warning banner', async () => {
    const body = item('W-3705');
    body.workspace!.status!.tone = 'person';
    await open(body);
    expect(document.querySelector('.ws .ws-note.psl-callout--success')).toBe(null);
    expect(document.querySelector('.ws .ws-note.psl-callout--warning')).toBeTruthy();
  });
});

describe('unknown, not zero (AC 14)', () => {
  it('W-3710: the unknown gap reads Unknown and Tola’s checklist has no time line', async () => {
    await open(item('W-3710'));
    expect(ws().getByText('Runbook misses the nightly export restart').closest('li')!.textContent).toContain('Unknown');
    expect(wsText()).not.toContain('As of');
    expect(ws().queryByText(/Support listed 2 gaps/)).toBeNull();
  });

  it('"Gaps · 2" is only the returned label: three gap items under that label still read Gaps · 2', async () => {
    const body = item('W-3704');
    const gaps = body.workspace!.sections.find((s) => s.key === 'gaps')!;
    gaps.items.push({ id: 'G-3', text: 'A third gap', tag: { label: 'OPEN', tone: 'uncertain' } });
    await open(body);
    expect(pageText()).toContain('Gaps · 2');
    expect(ws().getAllByText('OPEN')).toHaveLength(3);
  });
});

describe('links only from data (AC 15)', () => {
  it('a closure link with a bad work id, or none, draws nothing', async () => {
    const bad = item('W-3705');
    (bad.workspace as unknown as { links: { target: unknown }[] }).links[0].target = { kind: 'work', work_id: '../x' };
    await open(bad);
    expect(ws().queryByRole('link', { name: 'See what closure needs' })).toBeNull();
    cleanup();
    const none = item('W-3705');
    delete (none.workspace as unknown as { links?: unknown }).links;
    await open(none);
    expect(ws().queryByRole('link')).toBeNull();
  });

  it('an empty copy shows only the header and "Nothing here yet."', async () => {
    const body = item('W-3704');
    body.workspace!.sections = [];
    delete body.workspace!.steps;
    delete body.workspace!.next;
    await open(body);
    expect(wsText()).toContain('Nothing here yet.');
  });

  it('a restricted section shows only its label', async () => {
    const body = item('W-3704');
    const gaps = body.workspace!.sections.find((s) => s.key === 'gaps')! as { restricted?: boolean };
    gaps.restricted = true;
    await open(body);
    expect(wsText()).not.toContain('No contact for the credit bureau outage');
  });
});

describe('access (AC 16)', () => {
  for (const [label, status, kind] of [['401', 401, 'unauthenticated'], ['403', 403, 'forbidden'], ['404', 404, 'not_found']] as const) {
    it(`a ${label} on the item shows no title, project, reference, gap or responder text`, async () => {
      reads['W-3703'] = [() => json(status, { code: kind, message: 'x' })];
      render(
        <AppShell>
          <WorkItemView id="W-3703" tab="overview" />
        </AppShell>,
      );
      await waitFor(() => expect(sent.some((r) => r.path === '/api/v1/work/W-3703')).toBe(true));
      await waitFor(() => expect(document.querySelector('.ws')).toBeNull());
      for (const secret of ['Lagoon Health', 'HND-0048', 'Femi Ojo', 'credit bureau']) expect(pageText()).not.toContain(secret);
    });
  }

  it('a 403 on the response write shows the not-open view and nothing reads as recorded', async () => {
    writes.response = [json(403, { code: 'forbidden', message: 'x' })];
    await open(item('W-3703'));
    await fill();
    await act(async () => {
      fireEvent.click(recordButton());
    });
    await waitFor(() => expect(document.querySelector('.ws')).toBeNull());
    expect(pageText()).not.toMatch(/Recorded under your name|Femi Ojo/);
  });
});
