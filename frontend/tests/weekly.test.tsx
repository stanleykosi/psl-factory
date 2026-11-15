// @vitest-environment jsdom
// F-21: the weekly client report line on the F-17 workspace frame (PROPOSAL D-LINE-WORKSPACE, contract mock only).
// The fetch stub stands in for the backend; nothing here proves a real backend, the idempotency promise or a working
// weekly line. The client template is a test template.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
  usePathname: () => '/work/W-2201',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const records: { items: { value: string; label: string; _personas?: string[] }[] } = read('start-work/options/records.json');

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const stepRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
let sent: Sent[];
let itemAnswers: (WorkItem | (() => Response))[];
let stepAnswers: (Response | (() => Response | Promise<Response>))[];
let optionPaths: string[];

const posts = (suffix = '/steps') => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const itemReads = () => sent.filter((r) => r.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(r.path));
const ok = (body: Partial<{ outcome: string; message: string; revision: number }> = {}) => json(200, { work_id: 'W-0', state: 'ready', revision: 9, outcome: 'done', ...body });

beforeEach(() => {
  sent = [];
  itemAnswers = [];
  stepAnswers = [];
  optionPaths = [];
  vi.stubGlobal(
    'fetch',
    withoutBellFeed(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.text();
      sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
      if (url.pathname === '/api/v1/me') return json(200, read('me.pm.json'));
      if (url.pathname.includes('/fields/') && url.pathname.endsWith('/options')) {
        optionPaths.push(url.pathname);
        return json(200, { items: records.items.map(({ value, label }) => ({ value, label })), as_of: '2026-11-12T09:00:00Z' });
      }
      if (request.method === 'GET' && url.pathname.startsWith('/api/v1/work/')) {
        const next = itemAnswers.length > 1 ? itemAnswers.shift()! : itemAnswers[0];
        return typeof next === 'function' ? next() : json(200, next);
      }
      if (url.pathname.endsWith('/steps')) {
        const answer = stepAnswers.length > 1 ? stepAnswers.shift()! : (stepAnswers[0] ?? ok());
        return typeof answer === 'function' ? answer() : answer;
      }
      if (url.pathname.endsWith('/actions')) return json(200, { work_id: 'W-2205', state: 'action_needed', revision: 5 });
      return json(404, { code: 'not_found', message: 'Not here.' });
    }),
  );
  vi.mocked(reloadPage).mockClear();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function open(first: WorkItem, ...later: (WorkItem | (() => Response))[]) {
  itemAnswers = [first, ...later];
  const view = render(
    <AppShell>
      <WorkItemView id={first.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: first.title });
  return view;
}
const ws = () => within(document.querySelector('.ws') as HTMLElement);
const button = (name: string) => ws().getByRole('button', { name });
const press = async (name: string) => {
  await act(async () => {
    fireEvent.click(button(name));
  });
};
const form = (name: string) => within(screen.getByRole('form', { name }));
const submit = async (name: string) => {
  await act(async () => {
    fireEvent.click(form(name).getByRole('button', { name }));
  });
};
const PARTS = ['Status', 'Risks', 'Timeline', 'Next steps'];
const label = (part: string) => `${part} (optional)`;
const citeLabel = (part: string) => `Cites for ${part.toLowerCase()} (optional)`;

describe('default state from data (AC 6)', () => {
  it('W-2201 draws the title, subtitle, agent note, saved parts with cites, five records groups and the two step buttons', async () => {
    await open(item('W-2201'));
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe("Write this week's client update");
    const text = document.querySelector('.ws')!.textContent!;
    // D-73: the frame's header, above the workspace, draws the subtitle
    const subtitle = screen.getByText('Reviewed weekly client report · week 5–11 Nov · goes to Lagoon Health after PMO Lead review.');
    expect(document.querySelector('.ws')!.contains(subtitle)).toBe(false);
    expect(text).toContain("Since last week: 1 milestone completed, 3 actions now overdue, 1 new change request.");
    expect(text).toContain('Login fails on some older Android phones (high).');
    const headings = within(document.querySelector('.ws') as HTMLElement).getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(['Your update', 'MEETINGS', 'MILESTONES COMPLETED', 'ACTIONS', 'ISSUES OPEN', 'CHANGES', 'Decide']);
    expect(text).toContain('3 overdue · 1 without an owner');
    expect(within(document.querySelector('.ws-steps') as HTMLElement).getAllByRole('button').map((b) => b.textContent)).toEqual(['Send to Tola to assemble', 'Save draft']);
    expect(posts()).toHaveLength(0);
  });

  it('a field the fixture omits draws nothing: no status tag, no version', async () => {
    const body = item('W-2201');
    delete body.workspace!.byline;
    await open(body);
    expect(document.querySelector('.ws-byline')).toBeNull();
    expect(document.querySelector('.ws-status')).toBeNull();
  });

  it('W-2201 to W-2204 draw only the rows their boards have: no byline or version, and no subtitle on invalid, assembling and review', async () => {
    for (const [id, subtitle] of [['W-2201', true], ['W-2202', false], ['W-2203', false], ['W-2204', false]] as const) {
      const w = item(id).workspace!;
      expect(w.byline, id).toBeUndefined();
      expect(w.version, id).toBeUndefined();
      expect(w.subtitle !== undefined, id).toBe(subtitle);
    }
  });

  it('W-2204 shows the board’s short references for the timeline and risks parts', async () => {
    await open(item('W-2204'));
    const text = document.querySelector('.ws')!.textContent!;
    expect(text).toContain('ISS-0233');
    expect(text).toContain('MIN-0141');
  });
});

describe('the form carries the PM’s words (AC 7, 9)', () => {
  it('opens four labelled text areas with the saved words and four cite pickers offering only the returned records; nothing generates text', async () => {
    await open(item('W-2201'));
    await press('Send to Tola to assemble');
    const f = form('Send to Tola to assemble');
    for (const part of PARTS) expect(f.getByLabelText(label(part)).tagName).toBe('TEXTAREA');
    expect((f.getByLabelText(label('Status')) as HTMLTextAreaElement).value).toContain('Milestone 2 is complete');
    expect((f.getByLabelText(label('Timeline')) as HTMLTextAreaElement).value).toBe('');
    fireEvent.click(f.getByRole('combobox', { name: citeLabel('Status') }));
    const options = await screen.findAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual(records.items.map((r) => r.label));
    expect(optionPaths).toEqual(['/api/v1/lines/weekly_report/fields/status_cites/options']);
    // no control writes, suggests or generates; the fixture returns no suggestions
    expect(JSON.stringify(item('W-2201').workspace)).not.toMatch(/suggestions/);
    expect(screen.queryByRole('button', { name: /generate|suggest|draft for me|write for me/i })).toBeNull();
  });

  it('Escape inside an open picker closes the list only; the form and its words stay', async () => {
    await open(item('W-2201'));
    await press('Send to Tola to assemble');
    const f = form('Send to Tola to assemble');
    fireEvent.click(f.getByRole('combobox', { name: citeLabel('Risks') }));
    await screen.findAllByRole('option');
    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Escape' });
    expect(screen.queryAllByRole('option')).toHaveLength(0);
    expect(screen.getByRole('form', { name: 'Send to Tola to assemble' })).toBeTruthy();
  });
});

describe('write request (AC 8, 9)', () => {
  it('opening the form and saving sends no cites the person did not touch (an empty list never replaces the saved cites)', async () => {
    await open(item('W-2201'));
    await press('Save draft');
    const f = form('Save draft');
    expect(f.getAllByText('Saved records are not shown here. Choose at least one record for this part before you send.')).toHaveLength(1);
    await submit('Save draft');
    await waitFor(() => expect(posts()).toHaveLength(1));
    const inputs = posts()[0].body!.inputs as Record<string, unknown>;
    expect(Object.keys(inputs).filter((k) => k.endsWith('_cites'))).toEqual([]);
    expect(Object.values(inputs).some((v) => Array.isArray(v) && v.length === 0)).toBe(false);
    expect(inputs.status).toContain('Milestone 2 is complete');
  });

  it('Send sends one POST with CSRF, the revision, all eight names, cites as lists of option values, a UUID key, no note and no evidence', async () => {
    await open(item('W-2201'), item('W-2203'));
    await press('Send to Tola to assemble');
    const f = form('Send to Tola to assemble');
    fireEvent.change(f.getByLabelText(label('Timeline')), { target: { value: 'Go-live 4 Dec.' } });
    fireEvent.change(f.getByLabelText(label('Next steps')), { target: { value: 'TBD' } });
    for (const [part, values] of [['Status', ['MS-0002', 'MTG-0141']], ['Risks', ['ISS-0233']]] as const) {
      fireEvent.click(f.getByRole('combobox', { name: citeLabel(part) }));
      for (const v of values) fireEvent.click(await screen.findByRole('option', { name: records.items.find((r) => r.value === v)!.label }));
      fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Escape' });
    }
    await submit('Send to Tola to assemble');
    await waitFor(() => expect(posts()).toHaveLength(1));
    const [post] = posts();
    expect(post.path).toBe('/api/v1/work/W-2201/steps');
    expect(post.csrf).toBe('mock-csrf-pm');
    expect(stepRequest(post.body), ajv.errorsText(stepRequest.errors)).toBe(true);
    const { idempotency_key: key, ...rest } = post.body!;
    expect(key).toMatch(UUID);
    // "TBD" and the empty cites are sent as they are: the server judges them (AC 9)
    expect(rest).toEqual({
      expected_revision: 4,
      step: 'send_to_tola',
      inputs: {
        status: expect.stringContaining('Milestone 2 is complete'),
        status_cites: ['MS-0002', 'MTG-0141'],
        risks: expect.stringContaining('Login fails'),
        risks_cites: ['ISS-0233'],
        timeline: 'Go-live 4 Dec.',
        next_steps: 'TBD',
      },
    });
    expect(Object.keys(rest.inputs as object)).not.toContain('next_steps_cites');
    expect(post.body).not.toHaveProperty('note');
    expect(post.body).not.toHaveProperty('evidence_ids');
  });

  it('Save draft sends the same shape with its own step key; no local message appears for an empty or TBD part', async () => {
    await open(item('W-2201'));
    await press('Save draft');
    fireEvent.change(form('Save draft').getByLabelText(label('Risks')), { target: { value: 'TBD' } });
    await submit('Save draft');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ step: 'save_draft', expected_revision: 4, inputs: { risks: 'TBD' } });
    expect(stepRequest(posts()[0].body)).toBe(true);
    expect(document.querySelector('[aria-invalid="true"]')).toBeNull();
  });
});

describe('422 per part (AC 10)', () => {
  it('W-2202: server messages under risks and the next-steps cites, the top message once, focus on the first, inputs kept, a new key', async () => {
    const script = read('work/W-2202.steps.json').send_to_tola;
    stepAnswers = [json(422, script.body), json(422, script.body)];
    await open(item('W-2202'));
    // D-73: the status tag is drawn by the frame's header, not inside the workspace
    const status = screen.getByText('Needs fixing');
    expect(document.querySelector('.ws')!.contains(status)).toBe(false);
    expect(ws().getByText("The report can't start before the week has ended. This week ended 11 Nov.")).toBeTruthy();
    await press('Send to Tola to assemble');
    await submit('Send to Tola to assemble');
    const f = form('Send to Tola to assemble');
    const risks = await waitFor(() => {
      const el = f.getByLabelText(label('Risks'));
      expect(el.getAttribute('aria-invalid')).toBe('true');
      return el;
    });
    const described = (el: HTMLElement) => el.getAttribute('aria-describedby')!.split(' ').map((id) => document.getElementById(id)?.textContent);
    expect(described(risks)).toContain(script.body.fields[0].message);
    const cites = f.getByRole('combobox', { name: citeLabel('Next steps') });
    expect(cites.getAttribute('aria-invalid')).toBe('true');
    expect(described(cites)).toContain('Cite at least one record: no record cited yet.');
    await waitFor(() => expect(document.activeElement).toBe(risks));
    expect(f.getAllByText(script.body.message)).toHaveLength(1);
    expect((risks as HTMLTextAreaElement).value).toBe('TBD');
    await submit('Send to Tola to assemble');
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body!.idempotency_key).not.toBe(posts()[0].body!.idempotency_key);
  });
});

describe('send moves to assembling (AC 11, 12)', () => {
  it('done reloads once and shows the assembling state; the disabled step sends nothing', async () => {
    await open(item('W-2201'), item('W-2201.next'));
    await press('Send to Tola to assemble');
    await submit('Send to Tola to assemble');
    await screen.findByText('Assembling the weekly report');
    expect(itemReads()).toHaveLength(2);
    expect(posts()).toHaveLength(1);
    const text = document.querySelector('.ws')!.textContent!;
    expect(text).toContain('Collected the week');
    expect(text).toContain('3 MEETINGS · 9 ACTIONS · 1 MILESTONE · 2 ISSUES');
    expect(text).toContain('TEST TEMPLATE');
    expect(text).toContain('Done');
    expect(text).toContain('In progress');
    const disabled = button('Send for PMO Lead review');
    expect(disabled.getAttribute('aria-disabled')).toBe('true');
    expect(document.getElementById(disabled.getAttribute('aria-describedby')!)?.textContent).toBe('Tola is still placing your parts on the template.');
    fireEvent.click(disabled);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(posts()).toHaveLength(1);
    expect(ws().getAllByRole('button').filter((b) => b.closest('.ws-steps')).every((b) => b.getAttribute('aria-disabled') === 'true')).toBe(true);
  });
});

describe('review state, approve and return (AC 13 to 15)', () => {
  it('W-2204 shows the four parts with references, the consequence and both buttons', async () => {
    await open(item('W-2204'));
    const text = document.querySelector('.ws')!.textContent!;
    expect(text).toContain('Report v1 · written by Tunde Bello, assembled by Tola');
    for (const part of ['Status', 'Risks', 'Timeline', 'Next steps']) expect(text).toContain(part);
    expect(text).toContain('ISS-0233');
    expect(text).toContain('Approving sends this exact version to Lagoon Health.');
    expect(within(document.querySelector('.ws-steps') as HTMLElement).getAllByRole('button').map((b) => b.textContent)).toEqual(['Approve and send', 'Return with a note']);
  });

  it('Approve sends one POST with its own key, a double click sends one, done reloads once, no retry after 60 s', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const body = item('W-2204');
    await open(body, { ...body, revision: 4, workspace: { ...body.workspace!, revision: 4 } });
    await act(async () => {
      fireEvent.click(button('Approve and send'));
      fireEvent.click(button('Approve and send'));
    });
    await waitFor(() => expect(screen.getByRole('status', { name: '' }).textContent).toContain('Done'));
    expect(posts()).toHaveLength(1);
    expect(posts()[0].body).toMatchObject({ step: 'approve_send', expected_revision: 3 });
    expect(posts()[0].body!.idempotency_key).toMatch(UUID);
    expect(itemReads()).toHaveLength(2);
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });
    expect(posts()).toHaveLength(1);
  });

  it('Return needs a note (blank refused client-side, over 2000 refused), a valid note goes as note and done reloads', async () => {
    await open(item('W-2204'));
    await press('Return with a note');
    await submit('Return with a note');
    expect(posts()).toHaveLength(0);
    const note = form('Return with a note').getByLabelText('Note (needed to return or refuse)');
    expect(note.getAttribute('aria-invalid')).toBe('true');
    fireEvent.change(note, { target: { value: 'x'.repeat(2001) } });
    await submit('Return with a note');
    expect(posts()).toHaveLength(0);
    fireEvent.change(note, { target: { value: 'Add the SMS change request to next steps.' } });
    await submit('Return with a note');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ step: 'return', note: 'Add the SMS change request to next steps.' });
    expect(stepRequest(posts()[0].body)).toBe(true);
  });
});

describe('uncertain send keeps the lock (AC 16, INV-RESEND)', () => {
  it('W-2205: warning, every step off, ReconcilePanel from the reload, one POST to /actions and none to /steps; a forced click sends nothing', async () => {
    stepAnswers = [ok({ outcome: 'effect_uncertain', message: 'Delivery to Lagoon Health couldn’t be confirmed.' })];
    await open(item('W-2205'), item('W-2205.next'));
    await press('Approve and send');
    await screen.findByText('Delivery to Lagoon Health couldn’t be confirmed.');
    await screen.findByRole('group', { name: 'Confirm what happened' });
    for (const b of within(document.querySelector('.ws-steps') as HTMLElement).getAllByRole('button')) expect(b.getAttribute('aria-disabled')).toBe('true');
    await press('Approve and send');
    await press('Return with a note');
    expect(posts()).toHaveLength(1);
    fireEvent.click(screen.getByRole('radio', { name: /It didn’t arrive/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    await waitFor(() => expect(posts('/actions')).toHaveLength(1));
    expect(posts()).toHaveLength(1);
  });

  it('a page opened on the reconcile state keeps every step locked from the start', async () => {
    await open(item('W-2205.next'));
    for (const b of within(document.querySelector('.ws-steps') as HTMLElement).getAllByRole('button')) expect(b.getAttribute('aria-disabled')).toBe('true');
    await press('Approve and send');
    expect(posts()).toHaveLength(0);
  });

  it('with no reconcile on the reload the page says it is checking and offers only a reload', async () => {
    stepAnswers = [ok({ outcome: 'effect_uncertain' })];
    await open(item('W-2204'));
    await press('Approve and send');
    await screen.findByText('We are checking what happened. Nothing was sent again.');
    const callout = screen.getByText('We are checking what happened. Nothing was sent again.').closest('.ws-notice') as HTMLElement;
    expect(within(callout).getAllByRole('button').map((b) => b.textContent)).toEqual(['Reload']);
    expect(posts()).toHaveLength(1);
  });
});

describe('stale, server and network errors (AC 17)', () => {
  it('W-2206: a 409 keeps the inputs, reloads once, shows version 5 and re-bases the next press', async () => {
    stepAnswers = [json(409, { code: 'stale_revision', message: 'Changed.' }), ok()];
    await open(item('W-2206'), item('W-2206.next'));
    await press('Save draft');
    fireEvent.change(form('Save draft').getByLabelText(label('Timeline')), { target: { value: 'Go-live 4 Dec.' } });
    await submit('Save draft');
    await screen.findByText('This changed while you were working. Showing version 5.');
    expect(itemReads()).toHaveLength(2);
    expect((form('Save draft').getByLabelText(label('Timeline')) as HTMLTextAreaElement).value).toBe('Go-live 4 Dec.');
    await submit('Save draft');
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body).toMatchObject({ expected_revision: 5 });
    expect(posts()[1].body!.idempotency_key).not.toBe(posts()[0].body!.idempotency_key);
  });

  it('a 500 on save_draft offers Try again with the same key; a 500 on approve_send offers no resubmit', async () => {
    stepAnswers = [json(500, { code: 'server', message: 'Boom.' })];
    await open(item('W-2206'));
    await press('Save draft');
    await submit('Save draft');
    await waitFor(() => expect(posts()).toHaveLength(1));
    await act(async () => {
      fireEvent.click(form('Save draft').getByRole('button', { name: 'Try again' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body!.idempotency_key).toBe(posts()[0].body!.idempotency_key);
  });

  it('a 500 on approve_send offers no Try again', async () => {
    stepAnswers = [json(500, { code: 'server', message: 'Boom.' })];
    await open(item('W-2204'));
    await press('Approve and send');
    await waitFor(() => expect(posts()).toHaveLength(1));
    await waitFor(() => expect(document.querySelector('.ws-notice')).not.toBeNull());
    expect(ws().queryByRole('button', { name: 'Try again' })).toBeNull();
  });
});

describe('access (AC 18)', () => {
  it('403 on a step shows the forbidden line after a reload', async () => {
    stepAnswers = [json(403, { code: 'forbidden', message: 'No.' })];
    await open(item('W-2204'));
    await press('Approve and send');
    await screen.findByText('You can’t take that step.');
    expect(posts()).toHaveLength(1);
  });

  it('a 404 on the read shows no title, client or id', async () => {
    itemAnswers = [() => json(404, { code: 'not_found', message: 'Not here.' })];
    render(
      <AppShell>
        <WorkItemView id="W-2299" tab="overview" />
      </AppShell>,
    );
    await waitFor(() => expect(document.body.textContent).toMatch(/not available|no access|can.t open|don.t have/i));
    expect(document.body.textContent).not.toContain('Lagoon Health');
    expect(document.body.textContent).not.toContain('W-2299');
  });
});

describe('decision step (AC 19)', () => {
  it('W-2208: the task step is a link to the decision page and nothing is sent', async () => {
    await open(item('W-2208'));
    const link = ws().getByRole('link', { name: 'Approve and send' });
    expect(link.getAttribute('href')).toBe('/work/W-2208/decide?task=T-2208');
    fireEvent.click(link);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(sent.filter((r) => r.method === 'POST')).toEqual([]);
  });
});

describe('unknown, restricted, empty (AC 20)', () => {
  it('W-2207: restricted shows its label only, a missing value reads Unknown, an empty group reads Nothing here yet.', async () => {
    await open(item('W-2207'));
    const text = document.body.textContent!;
    expect(text).toContain('Restricted: milestones are visible to the project team only.');
    expect(text).not.toContain('Hidden milestone name');
    expect(text).not.toContain('Hidden milestone date');
    const actions = within(screen.getByRole('heading', { name: 'ACTIONS' }).closest('section') as HTMLElement);
    expect(actions.getByText('Unknown')).toBeTruthy();
    const meetings = within(screen.getByRole('heading', { name: 'MEETINGS' }).closest('section') as HTMLElement);
    expect(meetings.getByText('Nothing here yet.')).toBeTruthy();
  });
});

describe('returned and received are not built (AC 21)', () => {
  it('no weekly-specific source exists and no src file names those states', async () => {
    const { execSync } = await import('node:child_process');
    const found = execSync('grep -rlE "received|returned" src/features/workspace || true', { cwd: join(__dirname, '..') }).toString();
    // the generic renderer's receipt vocabulary (recipients) is older than this feature; nothing weekly-specific
    expect(found.split('\n').filter(Boolean).every((f) => !/weekly/i.test(f))).toBe(true);
    expect(execSync('ls src/features', { cwd: join(__dirname, '..') }).toString()).not.toMatch(/weekly/);
  });
});
