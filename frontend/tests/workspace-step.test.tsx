// @vitest-environment jsdom
// F-17 Part B: step controls, the step form and the E-WORK-STEP write (PROPOSAL D-LINE-WORKSPACE, contract mock
// only). The fetch stub stands in for the backend; nothing here proves the backend's idempotency promise.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { StrictMode } from 'react';

import { act, configure, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { reloadPage } from '@/features/response';
import type { WorkItem } from '@/features/work-item/labels';
import { ApiError } from '@/api/errors';
import { useWorkspacePage } from '@/features/workspace/usePageReload';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

// A busy machine can take more than the default second to render a page; nothing here waits on a timer.
configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2001',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const persona = (name: string) => read(`me.${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const stepRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Answer = Response | Promise<Response> | (() => Response | Promise<Response>);
type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
let sent: Sent[];
let itemAnswers: (WorkItem | (() => Response))[];
let stepAnswers: Answer[];
let me: unknown;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;

const posts = (suffix = '/steps') => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const itemReads = () => sent.filter((r) => r.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(r.path));
const ok = (body: Partial<{ outcome: string; message: string; revision: number }> = {}) => json(200, { work_id: 'W-0', state: 'ready', revision: 9, outcome: 'done', ...body });

beforeEach(() => {
  sent = [];
  itemAnswers = [];
  stepAnswers = [];
  me = persona('pm');
  fetchStub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (request.method === 'GET' && url.pathname.startsWith('/api/v1/work/')) {
      const next = itemAnswers.length > 1 ? itemAnswers.shift()! : itemAnswers[0];
      return typeof next === 'function' ? next() : json(200, next);
    }
    if (url.pathname.endsWith('/steps')) {
      const answer = stepAnswers.length > 1 ? stepAnswers.shift()! : (stepAnswers[0] ?? ok());
      return typeof answer === 'function' ? answer() : answer;
    }
    if (url.pathname.endsWith('/actions')) return json(200, { work_id: 'W-2008', state: 'action_needed', revision: 5 });
    return json(404, { code: 'not_found', message: 'Not here.' });
  });
  vi.stubGlobal('fetch', withoutBellFeed(fetchStub));
  vi.mocked(reloadPage).mockClear();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Serves the item, then each later read in turn (the last one repeats). */
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
const bump = (body: WorkItem, revision: number): WorkItem => ({ ...body, revision, workspace: { ...body.workspace!, revision } });

describe('steps only as returned (AC 12)', () => {
  it('W-2001 draws its three steps in order; the unavailable one shows its reason and sends nothing', async () => {
    await open(item('W-2001'));
    const row = document.querySelector('.ws-steps') as HTMLElement;
    expect(within(row).getAllByRole('button').map((b) => b.textContent)).toEqual(['Approve and send', 'Return with a note', 'Refuse']);
    const refuse = button('Refuse');
    expect(refuse.getAttribute('aria-disabled')).toBe('true');
    expect(document.getElementById(refuse.getAttribute('aria-describedby')!)?.textContent).toBe('Only the PMO Lead can refuse a report once it is assembled.');
    await press('Refuse');
    expect(posts()).toHaveLength(0);
    expect(ws().queryByRole('form')).toBeNull();
  });

  it('without workspace.revision no step control is drawn', async () => {
    const body = item('W-2001');
    delete body.workspace!.revision;
    await open(body);
    expect(ws().queryAllByRole('button')).toHaveLength(0);
    expect(document.querySelector('.ws-steps')).toBeNull();
  });

  it('every persona sees the same controls for the same item (nothing is derived from /me)', async () => {
    const seen: string[][] = [];
    for (const who of ['finance_lead', 'pm', 'ceo', 'admin']) {
      me = persona(who);
      const view = await open(item('W-2002'));
      seen.push(ws().getAllByRole('button').map((b) => `${b.textContent}:${b.getAttribute('aria-disabled')}`));
      view.unmount();
    }
    for (const list of seen) expect(list).toEqual(seen[0]);
  });

  it('a step the consequence doesn’t say sends gets "This sends to the client."; one that says so does not repeat it', async () => {
    const body = item('W-2001');
    body.workspace!.steps!.push({ key: 'nudge', label: 'Nudge the client', sends: true });
    await open(body);
    expect(ws().getByText('Approving sends this exact version to Lagoon Health.')).toBeTruthy();
    expect(ws().getAllByText('This sends to the client.')).toHaveLength(1);
  });
});

describe('scopes (AC 13)', () => {
  it('W-2002: item steps sit on the right items; Accept selected is off with nothing checked and sends the checked ids in item order', async () => {
    await open(item('W-2002'));
    const suggestions = screen.getByRole('region', { name: 'Review Tola’s suggestion' });
    const [s07, s08] = within(suggestions).getAllByRole('listitem');
    expect(within(s07).getAllByRole('button').map((b) => b.textContent)).toEqual(['Accept answer', 'Edit answer']);
    expect(within(s08).getAllByRole('button').map((b) => b.textContent)).toEqual(['Accept answer']);
    // no workspace-level row on this item: every step is item or items scope
    expect(document.querySelector('.ws > .ws-steps')).toBeNull();

    const accept = button('Accept selected');
    expect(accept.getAttribute('aria-disabled')).toBe('true');
    await press('Accept selected');
    expect(posts()).toHaveLength(0);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select R-09' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select R-07' }));
    expect(screen.getByText('2 selected')).toBeTruthy();
    expect(accept.getAttribute('aria-disabled')).toBeNull();
    await press('Accept selected');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ step: 'accept_selected', item_ids: ['R-07', 'R-09'], expected_revision: 7 });
  });

  it('an item step acts on its own item only, with no item_ids', async () => {
    await open(item('W-2002'));
    const s08 = within(screen.getByRole('region', { name: 'Review Tola’s suggestion' })).getAllByRole('listitem')[1];
    await act(async () => {
      fireEvent.click(within(s08).getByRole('button', { name: 'Accept answer' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).not.toHaveProperty('item_ids');
    expect(posts()[0].body).toMatchObject({ step: 'accept_answer' });
  });
});

describe('the step form (AC 14, 15)', () => {
  async function openForm(name = 'Save and accept') {
    await open(item('W-2006'));
    await press(name);
    return screen.getByRole('form', { name });
  }

  it('W-2006: every field kind is drawn, focus moves to the form heading, display is shown, restricted draws no value', async () => {
    const form = await openForm();
    expect(document.activeElement).toBe(within(form).getByRole('heading', { name: 'Save and accept' }));
    const f = within(form);
    expect(f.getByLabelText('Your answer').tagName).toBe('TEXTAREA');
    expect(f.getByLabelText('Short title (optional)').getAttribute('placeholder')).toBe('e.g. Approval threshold');
    expect(f.getByLabelText('Answer due (optional)').getAttribute('placeholder')).toBe('DD Mmm YYYY');
    expect(f.getByRole('group', { name: 'Covers (optional)' })).toBeTruthy();
    expect(f.getByLabelText('Reporting month (optional)').getAttribute('type')).toBe('month');
    expect(f.getByLabelText('Discussed at (optional)').getAttribute('type')).toBe('datetime-local');
    expect(f.getByLabelText('Hours to build (optional)').getAttribute('type')).toBe('number');
    expect(f.getByLabelText('Price for this requirement (optional)')).toBeTruthy();
    expect(f.getByRole('radiogroup', { name: 'Status' })).toBeTruthy();
    expect(f.getByRole('combobox', { name: 'Project (optional)' })).toBeTruthy();
    expect(f.getByText('Choose Project first')).toBeTruthy();
    expect(f.getByRole('button', { name: /Add another file|Supporting document/ })).toBeTruthy();
    expect(f.getByText('RFP answer · test template v1')).toBeTruthy();
    expect(f.getByText('Restricted')).toBeTruthy();
    expect(document.body.textContent).not.toContain('HIDDEN-COST-CODE');
    expect(f.getByText('Your words replace Tola’s once you save; Tola’s version stays in the history.')).toBeTruthy();
    expect(f.getByText('Accepting records your name. Tola’s original suggestion stays in the history.')).toBeTruthy();
  });

  it('the descriptor’s required check runs before any request; nothing else is invented', async () => {
    const form = await openForm();
    await act(async () => {
      fireEvent.click(within(form).getByRole('button', { name: 'Save and accept' }));
    });
    expect(posts()).toHaveLength(0);
    const answer = within(form).getByLabelText('Your answer');
    expect(answer.getAttribute('aria-invalid')).toBe('true');
    expect(document.getElementById(answer.getAttribute('aria-describedby')!.split(' ').at(-1)!)?.textContent).toBe('Add your answer to continue.');
    // optional fields left blank raise nothing
    expect(within(form).getAllByText(/to continue\.$/).map((e) => e.textContent)).toEqual(['Add your answer to continue.', 'Add status to continue.']);
  });

  it('submitting sends exactly one POST with CSRF, the revision, inputs shaped per kind, a UUID key and the note; it validates against the request schema', async () => {
    const form = await openForm();
    const f = within(form);
    fireEvent.change(f.getByLabelText('Your answer'), { target: { value: '  Approvals above a threshold go to a named officer.  ' } });
    fireEvent.change(f.getByLabelText('Hours to build (optional)'), { target: { value: '12' } });
    fireEvent.change(f.getByLabelText('Price for this requirement (optional)'), { target: { value: '4250000' } });
    fireEvent.change(f.getByLabelText('Answer due (optional)'), { target: { value: '20 Nov 2026' } });
    fireEvent.blur(f.getByLabelText('Answer due (optional)'));
    fireEvent.click(f.getByRole('radio', { name: 'Clarify' }));
    fireEvent.change(f.getByLabelText('Note (optional)'), { target: { value: ' Checked with Tunde. ' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Save and accept' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const [post] = posts();
    expect(post.path).toBe('/api/v1/work/W-2006/steps');
    expect(post.csrf).toBe('mock-csrf-pm');
    expect(stepRequest(post.body), ajv.errorsText(stepRequest.errors)).toBe(true);
    const { idempotency_key: key, ...rest } = post.body!;
    expect(key).toMatch(UUID);
    expect(rest).toEqual({
      expected_revision: 2,
      step: 'save_answer',
      inputs: {
        answer: 'Approvals above a threshold go to a named officer.',
        due: '2026-11-20',
        hours: 12,
        price: { amount: '4250000.00', currency: 'NGN', unknown: false },
        status: 'clarify',
      },
      note: 'Checked with Tunde.',
    });
  });

  it('a blank money field is sent as unknown, never 0; display, restricted and evidence-free fields send nothing', async () => {
    const form = await openForm();
    const f = within(form);
    fireEvent.change(f.getByLabelText('Your answer'), { target: { value: 'Yes' } });
    fireEvent.click(f.getByRole('radio', { name: 'Addressed' }));
    fireEvent.change(f.getByLabelText('Price for this requirement (optional)'), { target: { value: '   ' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Save and accept' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const body = posts()[0].body!;
    expect(body.inputs).toEqual({ answer: 'Yes', status: 'addressed', price: { currency: 'NGN', unknown: true } });
    expect(body).not.toHaveProperty('note');
    expect(body).not.toHaveProperty('evidence_ids');
    expect(body).not.toHaveProperty('case_revision');
  });

  it('a note over 2000 characters is refused before any request', async () => {
    const form = await openForm();
    const f = within(form);
    fireEvent.change(f.getByLabelText('Your answer'), { target: { value: 'Yes' } });
    fireEvent.click(f.getByRole('radio', { name: 'Addressed' }));
    fireEvent.change(f.getByLabelText('Note (optional)'), { target: { value: 'x'.repeat(2001) } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Save and accept' }));
    });
    expect(posts()).toHaveLength(0);
    expect(f.getByLabelText('Note (optional)').getAttribute('aria-invalid')).toBe('true');
    // the message is on the page once (the field's own error), not repeated in a hidden summary
    expect(f.getAllByText('Keep the note to 2000 characters.')).toHaveLength(1);
  });

  it('a whole-number field with other text is refused before any request', async () => {
    const form = await openForm();
    const f = within(form);
    fireEvent.change(f.getByLabelText('Your answer'), { target: { value: 'Yes' } });
    fireEvent.click(f.getByRole('radio', { name: 'Addressed' }));
    fireEvent.change(f.getByLabelText('Hours to build (optional)'), { target: { value: '1.5' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Save and accept' }));
    });
    expect(posts()).toHaveLength(0);
    const hours = f.getByLabelText('Hours to build (optional)');
    expect(hours.getAttribute('aria-invalid')).toBe('true');
    expect(hours.getAttribute('aria-describedby')!.split(' ').map((id) => document.getElementById(id)?.textContent)).toContain('Enter a whole number.');
  });

  it('a step with no note field sends no note; a confirm step shows its text above the submit', async () => {
    await open(item('W-2006'));
    await press('Mark as addressed');
    const form = screen.getByRole('form', { name: 'Mark as addressed' });
    const confirm = within(form).getByText('This marks R-07 as addressed with Tola’s suggested answer.');
    const submit = within(form).getByRole('button', { name: 'Mark as addressed' });
    expect(confirm.compareDocumentPosition(submit) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await act(async () => {
      fireEvent.click(submit);
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(Object.keys(posts()[0].body!).sort()).toEqual(['expected_revision', 'idempotency_key', 'step']);
  });

  it('Cancel and Escape close the form with no request and put focus back on the step control', async () => {
    const form = await openForm();
    fireEvent.keyDown(form, { key: 'Escape' });
    expect(screen.queryByRole('form')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(button('Save and accept')));
    await press('Save and accept');
    fireEvent.click(within(screen.getByRole('form')).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('form')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(button('Save and accept')));
    expect(posts()).toHaveLength(0);
  });
});

describe('one key per attempt; no double send (AC 16)', () => {
  it('a double click sends one request; while pending the button reads "<label>…" and is aria-disabled', async () => {
    let release: (r: Response) => void = () => {};
    stepAnswers = [() => new Promise<Response>((resolve) => (release = resolve))];
    await open(item('W-2001'));
    const approve = button('Approve and send');
    fireEvent.click(approve);
    fireEvent.click(approve);
    await waitFor(() => expect(button('Approve and send…').getAttribute('aria-disabled')).toBe('true'));
    // another step can't be pressed while one is in flight
    expect(button('Return with a note').getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(button('Return with a note'));
    expect(screen.queryByRole('form')).toBeNull();
    await act(async () => release(ok()));
    expect(posts()).toHaveLength(1);
  });

  it('under StrictMode a press sends once', async () => {
    itemAnswers = [item('W-2001')];
    render(
      <StrictMode>
        <AppShell>
          <WorkItemView id="W-2001" tab="overview" />
        </AppShell>
      </StrictMode>,
    );
    await screen.findByRole('heading', { level: 1, name: 'Weekly client report · 5–11 Nov' });
    await press('Approve and send');
    await waitFor(() => expect(screen.getByText('Done: Approve and send.')).toBeTruthy());
    expect(posts()).toHaveLength(1);
  });

  it('opening the form twice gives two keys; Try again after a network failure on a step that doesn’t send reuses the key', async () => {
    stepAnswers = [() => Promise.reject(new TypeError('offline')), ok()];
    await open(item('W-2007'));
    await press('Edit your update');
    fireEvent.change(within(screen.getByRole('form')).getByLabelText('Your update'), { target: { value: 'Fixed the login.' } });
    await act(async () => {
      fireEvent.click(within(screen.getByRole('form')).getByRole('button', { name: 'Edit your update' }));
    });
    await waitFor(() => expect(screen.getByText('We couldn’t confirm this step. Check the page before trying again.')).toBeTruthy());
    const first = posts()[0].body!.idempotency_key;
    // the form stays, with the typed words and a Try again
    expect((within(screen.getByRole('form')).getByLabelText('Your update') as HTMLTextAreaElement).value).toBe('Fixed the login.');
    await act(async () => {
      fireEvent.click(within(screen.getByRole('form')).getByRole('button', { name: 'Try again' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body!.idempotency_key).toBe(first);
    // done renews: a new form is a new attempt
    await press('Edit your update');
    fireEvent.change(within(screen.getByRole('form')).getByLabelText('Your update'), { target: { value: 'Again.' } });
    await act(async () => {
      fireEvent.click(within(screen.getByRole('form')).getByRole('button', { name: 'Edit your update' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(3));
    expect(posts()[2].body!.idempotency_key).not.toBe(first);
  });

  it('Cancel then reopen gives a new key; a key is renewed after done', async () => {
    stepAnswers = [json(500, { code: 'server', message: 'Boom.' }), ok()];
    await open(item('W-2007'));
    await press('Refresh the records');
    await waitFor(() => expect(posts()).toHaveLength(1));
    const first = posts()[0].body!.idempotency_key;
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Try again' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body!.idempotency_key).toBe(first);
    await press('Refresh the records');
    await waitFor(() => expect(posts()).toHaveLength(3));
    expect(posts()[2].body!.idempotency_key).not.toBe(first);
  });
});

describe('no automatic retry (AC 17)', () => {
  const cases: [string, Answer][] = [
    ['500', json(500, { code: 'server', message: 'Boom.' })],
    ['network failure', () => Promise.reject(new TypeError('offline'))],
    ['409', json(409, { code: 'stale_revision', message: 'Changed.' })],
    ['effect_uncertain', ok({ outcome: 'effect_uncertain', message: 'Not sure it arrived.' })],
  ];
  for (const [name, answer] of cases) {
    it(`${name}: one POST, still one after 60 seconds`, async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      stepAnswers = [answer];
      await open(item('W-2007'));
      await press('Refresh the records');
      await waitFor(() => expect(posts()).toHaveLength(1));
      await act(async () => {
        vi.advanceTimersByTime(60_000);
      });
      expect(posts()).toHaveLength(1);
    });
  }
});

describe('done and queued (AC 18)', () => {
  it('done reloads once, shows the live Done line, and the next press uses the new revision', async () => {
    const body = item('W-2001');
    await open(body, bump(body, 4));
    await press('Approve and send');
    await waitFor(() => expect(screen.getByRole('status', { name: '' }).textContent).toBe('Done: Approve and send.'));
    expect(itemReads()).toHaveLength(2);
    expect(posts()).toHaveLength(1);
    await press('Approve and send');
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body!.expected_revision).toBe(4);
    expect(posts()[1].body!.idempotency_key).not.toBe(posts()[0].body!.idempotency_key);
  });

  it('the returned message is the Done line when present', async () => {
    stepAnswers = [ok({ message: 'Sent to 2 client contacts.' })];
    await open(item('W-2001'));
    await press('Approve and send');
    await waitFor(() => expect(screen.getByText('Sent to 2 client contacts.')).toBeTruthy());
  });

  it('W-2007 queued shows Waiting with the message and reloads once; nothing is resent', async () => {
    stepAnswers = [ok({ outcome: 'queued', message: 'Tola reassembles the report after the 16:00 records sync.' })];
    await open(item('W-2007'));
    await press('Ask Tola to reassemble');
    await waitFor(() => expect(screen.getByText('Waiting: Tola reassembles the report after the 16:00 records sync.')).toBeTruthy());
    expect(screen.getByText(/^Waiting:/).closest('[role="status"]')).not.toBeNull();
    expect(itemReads()).toHaveLength(2);
    expect(posts()).toHaveLength(1);
  });

  it('queued without a message says the step is queued', async () => {
    stepAnswers = [ok({ outcome: 'queued' })];
    await open(item('W-2007'));
    await press('Ask Tola to reassemble');
    await waitFor(() => expect(screen.getByText('Waiting: This step is queued.')).toBeTruthy());
  });
});

describe('effect_uncertain (AC 19, INV-RESEND)', () => {
  it('W-2008: the uncertain callout, every step off, then ReconcilePanel from the re-read item answering through E-WORK-ACTION', async () => {
    stepAnswers = [ok({ outcome: 'effect_uncertain', message: 'Delivery to Lagoon Health couldn’t be confirmed.' })];
    await open(item('W-2008'), item('W-2008.next'));
    await press('Approve and send');
    const callout = await screen.findByText('Delivery to Lagoon Health couldn’t be confirmed.');
    expect(callout.closest('[role="alert"]')).not.toBeNull();
    await screen.findByRole('radiogroup', { name: 'Confirm what happened' });
    expect(itemReads()).toHaveLength(2);
    for (const b of within(document.querySelector('.ws-steps') as HTMLElement).getAllByRole('button')) expect(b.getAttribute('aria-disabled')).toBe('true');
    await press('Approve and send');
    await press('Return with a note');
    expect(screen.queryByRole('form', { name: 'Return with a note' })).toBeNull();
    fireEvent.click(screen.getByRole('radio', { name: /It didn’t arrive/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    await waitFor(() => expect(posts('/actions')).toHaveLength(1));
    expect(posts('/actions')[0].body).toMatchObject({ action: 'reconcile', outcome: 'not_delivered', expected_revision: 4 });
    expect(posts()).toHaveLength(1);
  });

  it('when the re-read item has no reconcile the page says it is checking and offers only a reload', async () => {
    stepAnswers = [ok({ outcome: 'effect_uncertain' })];
    const body = item('W-2008');
    await open(body, bump(body, 4));
    await press('Approve and send');
    await screen.findByText('We are checking what happened. Nothing was sent again.');
    const callout = screen.getByText('We are checking what happened. Nothing was sent again.').closest('[role="alert"]') as HTMLElement;
    expect(within(callout).getAllByRole('button').map((b) => b.textContent)).toEqual(['Reload']);
    await act(async () => {
      fireEvent.click(within(callout).getByRole('button', { name: 'Reload' }));
    });
    expect(itemReads()).toHaveLength(3);
    expect(posts()).toHaveLength(1);
    expect(screen.queryByRole('radiogroup', { name: 'Confirm what happened' })).toBeNull();
  });
});

describe('409 (AC 20)', () => {
  it('W-2007 keeps the typed words, reloads once, shows version 5 and re-bases the next deliberate press with a new key', async () => {
    stepAnswers = [json(409, { code: 'stale_revision', message: 'Changed.' }), ok()];
    await open(item('W-2007'), item('W-2007.next'));
    await press('Edit your update');
    fireEvent.change(within(screen.getByRole('form')).getByLabelText('Your update'), { target: { value: 'Login fix verified on 12 devices.' } });
    await act(async () => {
      fireEvent.click(within(screen.getByRole('form')).getByRole('button', { name: 'Edit your update' }));
    });
    await screen.findByText('This changed while you were working. Showing version 5.');
    expect(itemReads()).toHaveLength(2);
    expect(posts()).toHaveLength(1);
    expect((within(screen.getByRole('form')).getByLabelText('Your update') as HTMLTextAreaElement).value).toBe('Login fix verified on 12 devices.');
    await act(async () => {
      fireEvent.click(within(screen.getByRole('form')).getByRole('button', { name: 'Edit your update' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body).toMatchObject({ expected_revision: 5, inputs: { summary: 'Login fix verified on 12 devices.' } });
    expect(posts()[1].body!.idempotency_key).not.toBe(posts()[0].body!.idempotency_key);
  });
});

describe('422 (AC 21)', () => {
  it('W-2006: each named message under its input, focus on the first, the unnamed one on top, inputs kept, a new key', async () => {
    const script = read('work/W-2006.steps.json').check_answer;
    stepAnswers = [json(422, script.body), ok()];
    await open(item('W-2006'));
    await press('Check my answer');
    const form = screen.getByRole('form', { name: 'Check my answer' });
    const f = within(form);
    fireEvent.change(f.getByLabelText('Your answer'), { target: { value: 'Officers approve.' } });
    fireEvent.change(f.getByLabelText('Hours to build (optional)'), { target: { value: '400' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Check my answer' }));
    });
    await waitFor(() => expect(f.getByLabelText('Your answer').getAttribute('aria-invalid')).toBe('true'));
    const answer = f.getByLabelText('Your answer');
    const hours = f.getByLabelText('Hours to build (optional)');
    const described = (el: HTMLElement) => el.getAttribute('aria-describedby')!.split(' ').map((id) => document.getElementById(id)?.textContent);
    expect(described(answer)).toContain('Say how approvals are recorded.');
    expect(described(hours)).toContain('Hours must be under 200.');
    expect(hours.getAttribute('aria-invalid')).toBe('true');
    await waitFor(() => expect(document.activeElement).toBe(answer));
    expect(within(f.getAllByRole('alert')[0]).getByText(script.body.message)).toBeTruthy();
    expect((answer as HTMLTextAreaElement).value).toBe('Officers approve.');
    expect((hours as HTMLInputElement).value).toBe('400');
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Check my answer' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body!.idempotency_key).not.toBe(posts()[0].body!.idempotency_key);
  });

  it('a 422 with no fields shows the message at the top of the form', async () => {
    stepAnswers = [json(422, { code: 'invalid', message: 'This answer can’t be saved yet.' })];
    await open(item('W-2006'));
    await press('Check my answer');
    const f = within(screen.getByRole('form'));
    fireEvent.change(f.getByLabelText('Your answer'), { target: { value: 'Yes.' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Check my answer' }));
    });
    await waitFor(() => expect(f.getByRole('alert').textContent).toBe('This answer can’t be saved yet.'));
  });
});

describe('422 for a field the form does not show (UX-1-1)', () => {
  it('shows the message at the top of the form, with the matched ones under their inputs', async () => {
    stepAnswers = [
      json(422, {
        code: 'invalid',
        message: 'This answer can’t be saved yet.',
        fields: [
          { name: 'answer', message: 'Say how approvals are recorded.' },
          { name: 'reviewer', message: 'A reviewer must be free.' },
        ],
      }),
    ];
    await open(item('W-2006'));
    await press('Check my answer');
    const f = within(screen.getByRole('form', { name: 'Check my answer' }));
    fireEvent.change(f.getByLabelText('Your answer'), { target: { value: 'Yes.' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Check my answer' }));
    });
    const top = await f.findByText('A reviewer must be free.');
    expect(top.closest('[role="alert"]')).toBeTruthy();
    expect(f.getByText('This answer can’t be saved yet.')).toBeTruthy();
    expect(f.getByLabelText('Your answer').getAttribute('aria-invalid')).toBe('true');
  });

  it('a message for a field the form has is shown once, under its input, and not on top', async () => {
    stepAnswers = [json(422, { code: 'invalid', message: 'Fix the answer.', fields: [{ name: 'answer', message: 'Say how approvals are recorded.' }] })];
    await open(item('W-2006'));
    await press('Check my answer');
    const f = within(screen.getByRole('form', { name: 'Check my answer' }));
    fireEvent.change(f.getByLabelText('Your answer'), { target: { value: 'Yes.' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Check my answer' }));
    });
    await waitFor(() => expect(f.getByLabelText('Your answer').getAttribute('aria-invalid')).toBe('true'));
    expect(f.queryByText('Fix the answer.')).toBeNull();
  });
});

describe('notices name the step (UX-1-2, UX-1-4, UX-1-5)', () => {
  it('a returned message that does not name the step gets the step name beside it', async () => {
    stepAnswers = [ok({ message: 'Sent.' })];
    await open(item('W-2001'));
    await press('Approve and send');
    const line = (await ws().findByText('Sent.')).closest('.psl-callout')!;
    expect(line.textContent).toBe('Approve and send Sent.');
  });

  it('a failed step is named in the message', async () => {
    stepAnswers = [json(500, { code: 'server', message: 'Boom.' })];
    await open(item('W-2007'));
    await press('Send to the client');
    const alert = (await ws().findByText('We couldn’t confirm this step. Check the page before trying again.')).closest('[role="alert"]') as HTMLElement;
    expect(within(alert).getByText('Send to the client')).toBeTruthy();
  });

  it('after an uncertain effect the buttons say why they are off', async () => {
    stepAnswers = [ok({ outcome: 'effect_uncertain', message: 'We are not sure it was sent.' })];
    await open(item('W-2001'));
    await press('Approve and send');
    await screen.findByText('We are not sure it was sent.');
    expect(ws().getByText('Confirm what happened first.')).toBeTruthy();
  });

  it('a viewer without the reconcile grant is told someone with reconcile access has to confirm first (UX-5-1)', async () => {
    const body = item('W-2008.next');
    expect(body.reconcile).toBeTruthy();
    await open({ ...body, allowed_actions: (body.allowed_actions ?? []).filter((a) => a !== 'reconcile') });
    expect(ws().getByText('Someone with reconcile access needs to confirm what happened first.')).toBeTruthy();
    expect(ws().queryByText('Confirm what happened first.')).toBeNull();
  });

  it('a viewer who can reconcile keeps the short hint (UX-5-1)', async () => {
    const body = item('W-2008.next');
    await open({ ...body, allowed_actions: [...new Set([...(body.allowed_actions ?? []), 'reconcile' as const])] });
    expect(ws().getByText('Confirm what happened first.')).toBeTruthy();
  });

  it('a 409 whose re-read fails does not name a version', async () => {
    stepAnswers = [json(409, { code: 'stale_revision', message: 'Changed.' })];
    await open(item('W-2007'), () => json(500, { code: 'server', message: 'Boom.' }));
    await press('Send to the client');
    await screen.findByText('This changed while you were working, and we couldn’t reload it.');
    expect(document.body.textContent).not.toContain('version unknown');
  });
});

describe('other errors (AC 22)', () => {
  it('401 shows the signed-out callout with next = this page', async () => {
    stepAnswers = [json(401, { code: 'not_signed_in', message: 'Sign in.' })];
    await open(item('W-2001'));
    await press('Approve and send');
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(link.getAttribute('href')).toContain(`next=${encodeURIComponent('/work/W-2001')}`);
  });

  it('403 reloads and says "You can’t take that step."', async () => {
    stepAnswers = [json(403, { code: 'forbidden', message: 'No.' })];
    const body = item('W-2001');
    const after = { ...body, workspace: { ...body.workspace!, steps: body.workspace!.steps!.filter((s) => s.key !== 'approve_send') } };
    await open(body, after);
    await press('Approve and send');
    await screen.findByText('You can’t take that step.');
    expect(itemReads()).toHaveLength(2);
    expect(ws().queryByRole('button', { name: 'Approve and send' })).toBeNull();
  });

  it('403 then a 403 on the re-read shows the no-access state', async () => {
    stepAnswers = [json(403, { code: 'forbidden', message: 'No.' })];
    await open(item('W-2001'), () => json(403, { code: 'forbidden', message: 'No.' }));
    await press('Approve and send');
    await screen.findByRole('heading', { name: 'You can’t open this work item' });
    expect(document.body.textContent).not.toContain('WCR-0216');
  });

  it('404 shows the no-access state with no id or title', async () => {
    stepAnswers = [json(404, { code: 'not_found', message: 'Gone.' })];
    await open(item('W-2001'));
    await press('Approve and send');
    await screen.findByRole('heading', { name: 'You can’t open this work item' });
    expect(document.body.textContent).not.toContain('Weekly client report');
    expect(document.body.textContent).not.toContain('W-2001');
    expect(document.body.textContent).not.toContain('WCR-0216');
  });

  it('500 on a step that sends: the message and no way to press it again', async () => {
    stepAnswers = [json(500, { code: 'server', message: 'Boom.' })];
    await open(item('W-2007'));
    await press('Send to the client');
    await screen.findByText('We couldn’t confirm this step. Check the page before trying again.');
    expect(itemReads()).toHaveLength(2);
    expect(ws().queryByRole('button', { name: 'Try again' })).toBeNull();
    expect(button('Send to the client').getAttribute('aria-disabled')).toBe('true');
    await press('Send to the client');
    expect(posts()).toHaveLength(1);
  });
});

describe('decision steps (AC 23)', () => {
  it('W-2009: the task step is a link to the decision page and the workspace sends nothing', async () => {
    await open(item('W-2009'));
    const link = ws().getByRole('link', { name: 'Open the decision' });
    expect(link.getAttribute('href')).toBe('/work/W-2009/decide?task=T-2009');
    expect(ws().getByText('Claim it first')).toBeTruthy();
    const later = ws().getByRole('button', { name: 'Second approval' });
    expect(later.getAttribute('aria-disabled')).toBe('true');
    expect(ws().queryByRole('link', { name: 'Second approval' })).toBeNull();
    fireEvent.click(later);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(sent.filter((r) => r.method === 'POST')).toEqual([]);
  });
});

describe('a different item starts clean (TECH-1-1)', () => {
  it('access lost on one item is not carried to the next id', () => {
    const { result, rerender } = renderHook(({ id }) => useWorkspacePage(id), { initialProps: { id: 'W-2001' } });
    act(() => result.current.page.onAccessLost(new ApiError(404, 'not_found', 'not_found', 'Not here.')));
    expect(result.current.lost).not.toBeNull();
    rerender({ id: 'W-2002' });
    expect(result.current.lost).toBeNull();
    expect(result.current.fresh).toBeNull();
  });
});

describe('a read that lands after the id changed (TECH-2-1)', () => {
  it('is ignored', async () => {
    let release: (r: Response) => void = () => {};
    itemAnswers = [() => new Promise<Response>((resolve) => (release = resolve)) as unknown as Response];
    const { result, rerender } = renderHook(({ id }) => useWorkspacePage(id), { initialProps: { id: 'W-2001' } });
    let late: Promise<WorkItem | undefined> = Promise.resolve(undefined);
    act(() => {
      late = result.current.page.reload();
    });
    await waitFor(() => expect(itemReads()).toHaveLength(1));
    rerender({ id: 'W-2002' });
    await act(async () => {
      release(json(200, item('W-2001')));
      await late;
    });
    expect(result.current.fresh).toBeNull();
  });
});
