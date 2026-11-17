// @vitest-environment jsdom
// F-23: the minutes line on the F-17 workspace frame (PROPOSAL D-LINE-WORKSPACE, contract mock only). The fetch stub
// stands in for the backend; nothing here proves a real backend, the idempotency promise, a real send or a working
// minutes line. The client template is a test template.
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
  usePathname: () => '/work/W-2301',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const owners: { items: { value: string; label: string; hint?: string }[] } = read('start-work/options/owner.json');

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const stepRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
let sent: Sent[];
let itemAnswers: (WorkItem | (() => Response))[];
let stepAnswers: (Response | (() => Response | Promise<Response>))[];
let documentAnswer: () => Response;
let optionPaths: string[];
let persona: string;

const posts = (suffix = '/steps') => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const itemReads = () => sent.filter((r) => r.method === 'GET' && /^\/api\/v1\/work\/W-\d+$/.test(r.path));
const documentReads = () => sent.filter((r) => r.method === 'GET' && r.path.startsWith('/api/v1/documents/'));
const ok = (body: Partial<{ outcome: string; message: string; revision: number }> = {}) => json(200, { work_id: 'W-0', state: 'ready', revision: 9, outcome: 'done', ...body });

beforeEach(() => {
  sent = [];
  itemAnswers = [];
  stepAnswers = [];
  optionPaths = [];
  persona = 'pm';
  documentAnswer = () => json(200, read('E-DOCUMENT.json'));
  vi.stubGlobal(
    'fetch',
    withoutBellFeed(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.text();
      sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
      if (url.pathname === '/api/v1/me') return json(200, read(`me.${persona}.json`));
      if (url.pathname.includes('/fields/') && url.pathname.endsWith('/options')) {
        optionPaths.push(url.pathname);
        return json(200, { items: owners.items, as_of: '2026-11-12T09:00:00Z' });
      }
      if (url.pathname.startsWith('/api/v1/documents/')) return documentAnswer();
      if (request.method === 'GET' && url.pathname.startsWith('/api/v1/work/')) {
        const next = itemAnswers.length > 1 ? itemAnswers.shift()! : itemAnswers[0];
        return typeof next === 'function' ? next() : json(200, next);
      }
      if (url.pathname.endsWith('/steps')) {
        const answer = stepAnswers.length > 1 ? stepAnswers.shift()! : (stepAnswers[0] ?? ok());
        return typeof answer === 'function' ? answer() : answer;
      }
      if (url.pathname.endsWith('/actions')) return json(200, { work_id: 'W-2305', state: 'action_needed', revision: 8 });
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
const wsEl = () => document.querySelector('.ws') as HTMLElement;
const ws = () => within(wsEl());
const button = (name: string) => ws().getByRole('button', { name });
const press = async (name: string) => {
  await act(async () => {
    fireEvent.click(button(name));
  });
};
const form = (name: string) => within(screen.getByRole('form', { name }));
const box = (name: string) => ws().getByRole('checkbox', { name: `Select ${name}` }) as HTMLInputElement;
const boxes = () => ws().getAllByRole('checkbox') as HTMLInputElement[];
const rowOf = (text: string) => within(ws().getByText(text).closest('tr, li') as HTMLElement);

const D1 = 'Go-live stays planned for 4 Dec, subject to the login fix.';
const D2 = 'SMS reminders go through change control, not into the current scope.';
const A1 = 'Send test accounts for UAT';
const A2 = 'Finish the Android login fix';
const A3 = 'Assess the SMS reminders change';

describe('default from data (AC 6)', () => {
  it('W-2301 draws the title, subtitle, meeting, decisions with their notes cites, actions with owner and due, and the step buttons', async () => {
    await open(item('W-2301'));
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Confirm the minutes');
    expect(screen.getByText('Formal minutes and action handoff · MIN-0141')).toBeTruthy();
    const text = wsEl().textContent!;
    for (const s of ['Meeting', 'Weekly sync · Lagoon Health', '10 Nov 2026 · 14:00–14:45 · 6 attendees', 'weekly-sync-notes-10nov.docx', 'Uploaded · 42 KB', 'Decisions · Tola suggested 2', D1, D2, 'Actions · Tola suggested 3'])
      expect(text, s).toContain(s);
    expect(text).toContain('From Notes · 14:12');
    expect(text).toContain('From Notes · 14:30');
    expect(text).toContain('I read the notes and suggested 2 decisions and 3 actions.');
    expect(text).toContain('One action has no owner and its due date is Unknown.');
    const third = rowOf(A3);
    expect(third.getByText('Choose an owner')).toBeTruthy();
    expect(third.getByText('Unknown').className).toContain('psl-unknown');
    expect(rowOf(A1).getByText('Client · Lagoon Health')).toBeTruthy();
    expect(rowOf(A1).getByText('13 Nov')).toBeTruthy();
    for (const name of ['Confirm and create actions', 'Save for later', '+ Add an action']) expect(button(name)).toBeTruthy();
    expect(ws().getAllByRole('button', { name: 'Edit' })).toHaveLength(5);
    expect(ws().getAllByRole('button', { name: 'Remove' })).toHaveLength(3);
    expect(posts()).toHaveLength(0);
  });
});

describe('pre-ticked from data only (AC 7)', () => {
  it('W-2301 starts every decision and action ticked, and one confirm control sits in the workspace row', async () => {
    await open(item('W-2301'));
    expect(boxes()).toHaveLength(5);
    expect(boxes().every((b) => b.checked)).toBe(true);
    expect(box(D1).checked).toBe(true);
    expect(box(A3).checked).toBe(true);
    expect(ws().getAllByRole('button', { name: 'Confirm and create actions' })).toHaveLength(1);
    expect(button('Confirm and create actions').getAttribute('aria-disabled')).toBeNull();
  });

  it('W-2308 starts every box unticked, the confirm control is unavailable and a press sends nothing', async () => {
    await open(item('W-2308'));
    expect(boxes()).toHaveLength(3);
    expect(boxes().some((b) => b.checked)).toBe(false);
    expect(ws().getByText('Nothing here yet.')).toBeTruthy();
    const confirm = button('Confirm and create actions');
    expect(confirm.getAttribute('aria-disabled')).toBe('true');
    await act(async () => {
      fireEvent.click(confirm);
    });
    expect(screen.queryByRole('form', { name: 'Confirm and create actions' })).toBeNull();
    expect(posts()).toHaveLength(0);
    fireEvent.click(box(A1));
    expect(button('Confirm and create actions').getAttribute('aria-disabled')).toBeNull();
  });

  it('the default is read from the step, not from a word in the page: removing items_default unticks everything', async () => {
    const body = item('W-2301');
    for (const step of body.workspace!.steps!) delete (step as Record<string, unknown>).items_default;
    await open(body);
    expect(boxes().some((b) => b.checked)).toBe(false);
  });
});

describe('the exact confirm set (AC 8)', () => {
  it('unticking one decision then confirming for the client sends exactly the remaining ids in returned order', async () => {
    await open(item('W-2301'), item('W-2301.next' as string));
    fireEvent.click(box(D2));
    expect(box(D2).checked).toBe(false);
    await press('Confirm and create actions');
    const f = form('Confirm and create actions');
    expect(f.getByRole('radio', { name: 'Client' }).getAttribute('aria-checked')).toBe('true');
    expect(f.getByText("Client minutes are reviewed by the PMO Lead before they're sent.")).toBeTruthy();
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Confirm and create actions' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const [post] = posts();
    expect(post.path).toBe('/api/v1/work/W-2301/steps');
    expect(post.csrf).toBe('mock-csrf-pm');
    expect(stepRequest(post.body), ajv.errorsText(stepRequest.errors)).toBe(true);
    const { idempotency_key: key, ...rest } = post.body!;
    expect(key).toMatch(UUID);
    expect(rest).toEqual({ expected_revision: 4, step: 'confirm_minutes', item_ids: ['D-1', 'A-1', 'A-2', 'A-3'], inputs: { audience: 'client' } });
  });

  it('the set sent is the set ticked when the control was pressed: Internal is sent when the PM chooses it', async () => {
    await open(item('W-2301'), item('W-2301.next' as string));
    fireEvent.click(box(A3));
    await press('Confirm and create actions');
    const f = form('Confirm and create actions');
    fireEvent.click(f.getByRole('radio', { name: 'Internal' }));
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Confirm and create actions' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ item_ids: ['D-1', 'D-2', 'A-1', 'A-2'], inputs: { audience: 'internal' } });
  });
});

describe('the set sent is the set on screen', () => {
  it('ticks changed while the form is open are the ones sent; unticking everything sends nothing', async () => {
    await open(item('W-2301'), item('W-2301.next' as string));
    await press('Confirm and create actions');
    fireEvent.click(box(D1));
    await act(async () => {
      fireEvent.click(form('Confirm and create actions').getByRole('button', { name: 'Confirm and create actions' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body!.item_ids).toEqual(['D-2', 'A-1', 'A-2', 'A-3']);
  });

  it('unticking everything while the form is open sends nothing', async () => {
    await open(item('W-2301'));
    await press('Confirm and create actions');
    for (const b of boxes()) fireEvent.click(b);
    await act(async () => {
      fireEvent.click(form('Confirm and create actions').getByRole('button', { name: 'Confirm and create actions' }));
    });
    expect(posts()).toHaveLength(0);
  });
});

describe('nothing becomes an action before confirm (AC 9)', () => {
  it('loading, ticking, unticking, opening Edit and cancelling send no POST; nothing fires on a timer', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open(item('W-2301'));
    fireEvent.click(box(D1));
    fireEvent.click(box(D1));
    fireEvent.click(box(A2));
    await act(async () => {
      fireEvent.click(rowOf(A1).getByRole('button', { name: 'Edit' }));
    });
    expect(screen.getByRole('form', { name: 'Edit' })).toBeTruthy();
    fireEvent.click(form('Edit').getByRole('button', { name: 'Cancel' }));
    const reads = sent.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(sent.length).toBe(reads);
    expect(posts()).toHaveLength(0);
    expect(screen.queryByRole('button', { name: /accept all|auto.?confirm/i })).toBeNull();
  });
});

describe('edit, remove, add (AC 10)', () => {
  it('Edit on an action opens text, owner with the options and their hints, and due; a blank owner and due are left out', async () => {
    await open(item('W-2301'));
    await act(async () => {
      fireEvent.click(rowOf(A3).getByRole('button', { name: 'Edit' }));
    });
    const f = form('Edit');
    const text = f.getByLabelText('Action') as HTMLInputElement;
    fireEvent.change(text, { target: { value: 'Assess the SMS reminders change by Friday' } });
    fireEvent.click(f.getByRole('combobox', { name: /Owner/ }));
    const options = await screen.findAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual(expect.arrayContaining(['Tunde Bello', expect.stringContaining('recorded by PM'), expect.stringContaining('client')]));
    expect(optionPaths).toEqual(['/api/v1/lines/minutes/fields/owner/options']);
    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Escape' });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Edit' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const body = posts()[0].body!;
    expect(stepRequest(body)).toBe(true);
    expect(body).toMatchObject({ step: 'edit_item', item_ids: ['A-3'], inputs: { text: 'Assess the SMS reminders change by Friday' } });
    expect(Object.keys(body.inputs as object)).toEqual(['text']);
  });

  it('a chosen owner and a chosen due are sent as the option value and an ISO date', async () => {
    await open(item('W-2301'));
    await act(async () => {
      fireEvent.click(rowOf(A3).getByRole('button', { name: 'Edit' }));
    });
    const f = form('Edit');
    fireEvent.change(f.getByLabelText('Action'), { target: { value: 'Assess SMS' } });
    fireEvent.click(f.getByRole('combobox', { name: /Owner/ }));
    fireEvent.click(await screen.findByRole('option', { name: /Tunde Bello/ }));
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Edit' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body!.inputs).toEqual({ text: 'Assess SMS', owner: 'U-TUNDE' });
  });

  it('Edit on a decision carries text only', async () => {
    await open(item('W-2301'));
    await act(async () => {
      fireEvent.click(rowOf(D1).getByRole('button', { name: 'Edit' }));
    });
    const f = form('Edit');
    expect(f.queryByRole('combobox')).toBeNull();
    fireEvent.change(f.getByLabelText('Decision'), { target: { value: 'Go-live is 4 Dec.' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Edit' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ step: 'edit_decision', item_ids: ['D-1'], inputs: { text: 'Go-live is 4 Dec.' } });
  });

  it('Remove sends one POST for that item and no inputs', async () => {
    await open(item('W-2301'));
    await act(async () => {
      fireEvent.click(rowOf(A2).getByRole('button', { name: 'Remove' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const body = posts()[0].body!;
    expect(stepRequest(body)).toBe(true);
    expect(body).toMatchObject({ step: 'remove_item', item_ids: ['A-2'] });
    expect(body).not.toHaveProperty('inputs');
  });

  it('+ Add an action: a blank text is refused before any request; a typed one reaches the 422 under text, keeps the inputs and uses a new key', async () => {
    const script = read('work/W-2306.steps.json').add_action;
    stepAnswers = [json(422, script.body), json(422, script.body)];
    await open(item('W-2306'));
    await press('+ Add an action');
    const f = form('+ Add an action');
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: '+ Add an action' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(0));
    expect(f.getByText('Add action to continue.')).toBeTruthy();
    fireEvent.change(f.getByLabelText('Action'), { target: { value: ' ' } });
    // the descriptor says text is required, so a blank is refused before any request; a non-blank one reaches the server's 422
    fireEvent.change(f.getByLabelText('Action'), { target: { value: 'x' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: '+ Add an action' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const input = await waitFor(() => {
      const el = f.getByLabelText('Action');
      expect(el.getAttribute('aria-invalid')).toBe('true');
      return el;
    });
    expect(screen.getByText('Write the action in words.')).toBeTruthy();
    expect(document.activeElement).toBe(input);
    expect((input as HTMLInputElement).value).toBe('x');
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: '+ Add an action' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[0].body!.idempotency_key).not.toBe(posts()[1].body!.idempotency_key);
  });
});

describe('audience from the descriptor (AC 11)', () => {
  it('W-2301 draws Internal / Client as a choice; W-2307 shows Client as display only and sends no audience', async () => {
    await open(item('W-2307'), item('W-2301.next' as string));
    await press('Confirm and create actions');
    const f = form('Confirm and create actions');
    expect(f.queryByRole('radio')).toBeNull();
    expect(f.getByText('Client')).toBeTruthy();
    expect(f.getByText("Client minutes are reviewed by the PMO Lead before they're sent.")).toBeTruthy();
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Confirm and create actions' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).not.toHaveProperty('inputs');
    expect(stepRequest(posts()[0].body)).toBe(true);
  });
});

describe('stale confirm (AC 12)', () => {
  it('W-2306: 409 reloads once, says version 5, ticks the new fourth action, sends nothing until the PM presses again with a new key and revision 5', async () => {
    stepAnswers = [json(409, { code: 'stale_revision', message: 'Someone changed this.' }), ok()];
    await open(item('W-2306'), item('W-2306.next' as string));
    await press('Confirm and create actions');
    const f = form('Confirm and create actions');
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Confirm and create actions' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    await screen.findByText('This changed while you were working. Showing version 5.');
    expect(itemReads()).toHaveLength(2);
    expect(box('Confirm the go-live date with the client').checked).toBe(true);
    expect(posts()).toHaveLength(1);
    // the open form sends the set on screen now, not the set at the first press
    await act(async () => {
      fireEvent.click(form('Confirm and create actions').getByRole('button', { name: 'Confirm and create actions' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body).toMatchObject({ expected_revision: 5, item_ids: ['D-1', 'D-2', 'A-1', 'A-2', 'A-3', 'A-4'] });
    expect(posts()[1].body!.idempotency_key).not.toBe(posts()[0].body!.idempotency_key);
  });
});

describe('server failure on a non-sending step (AC 13)', () => {
  it('Save for later 500 offers Try again with the same key and never retries on its own', async () => {
    stepAnswers = [json(500, { code: 'server_error', message: 'x' }), ok()];
    await open(item('W-2306'));
    await press('Save for later');
    await waitFor(() => expect(posts()).toHaveLength(1));
    const retry = await ws().findByRole('button', { name: 'Try again' });
    expect(posts()).toHaveLength(1);
    await act(async () => {
      fireEvent.click(retry);
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body!.idempotency_key).toBe(posts()[0].body!.idempotency_key);
  });
});

describe('suggesting is quiet (AC 14)', () => {
  it('W-2302 shows the agent list in words, the callout and Ask Tola linking to /assistant; nothing to press or tick', async () => {
    await open(item('W-2302'));
    const text = wsEl().textContent!;
    for (const s of ['Reading the meeting notes', 'PMO agent · step 3 of 4 · Started 10 Nov 15:02', 'Read the meeting notes', 'WEEKLY-SYNC-NOTES-10NOV.DOCX', 'Found 2 decisions', 'In progress', 'Next', 'Hand them to you to confirm'])
      expect(text, s).toContain(s);
    expect(screen.getByText('Nothing Tola suggests becomes a decision or an action until you confirm it.')).toBeTruthy();
    expect(screen.getByText('Reading the notes')).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Ask Tola' }).getAttribute('href')).toBe('/assistant');
    expect(ws().queryAllByRole('button')).toEqual([]);
    expect(ws().queryAllByRole('checkbox')).toEqual([]);
    expect(posts()).toHaveLength(0);
  });
});

describe('drafted and the test template (AC 15)', () => {
  it('W-2303 shows IN, IN, ATTACHED and the agent rows with the data’s own tags; Send for review sends one POST and reloads', async () => {
    await open(item('W-2303'), item('W-2303.next' as string));
    const text = wsEl().textContent!;
    for (const s of ['Minutes v1 · client version', '2 decisions · confirmed by you', 'IN', '3 actions · 1 has no owner yet', 'Attendees and notes', 'ATTACHED', 'Used the decisions and actions you confirmed', '2 DECISIONS · 3 ACTIONS', 'TEST TEMPLATE', '6 ATTENDEES', 'PMO agent · done · Drafted 10 Nov 15:20'])
      expect(text, s).toContain(s);
    expect(screen.getByText("Client minutes go to the PMO Lead before they're sent.")).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Ask Tola' })).toBeTruthy();
    await press('Send for review');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ step: 'send_for_review', expected_revision: 5 });
    expect(stepRequest(posts()[0].body)).toBe(true);
    await waitFor(() => expect(itemReads()).toHaveLength(2));
  });
});

describe('open the minutes (AC 16)', () => {
  it('sends exactly one GET and shows the title, version and a Test template tag; the file link is text unless it is an app path', async () => {
    await open(item('W-2304'));
    fireEvent.click(button('Open the minutes'));
    await screen.findByRole('heading', { name: 'Weekly sync minutes · Lagoon Health' });
    expect(documentReads().map((r) => r.path)).toEqual(['/api/v1/documents/D-2304/versions/1']);
    expect(ws().getByText('Test template')).toBeTruthy();
    expect(ws().queryByRole('link', { name: 'Open the file' })).toBeNull();
    expect(ws().getByText('https://files.example.test/minutes-d-2304-v1.pdf')).toBeTruthy();
  });

  it('an app path becomes a link; any other body_url is text', async () => {
    documentAnswer = () => json(200, { ...read('E-DOCUMENT.json'), body_url: '/documents/D-2304' });
    await open(item('W-2304'));
    fireEvent.click(button('Open the minutes'));
    expect((await ws().findByRole('link', { name: 'Open the file' })).getAttribute('href')).toBe('/documents/D-2304');
  });

  it.each(['//evil.example/x', 'javascript:alert(1)', '/\\evil'])('body_url %s is never a link', async (url) => {
    documentAnswer = () => json(200, { ...read('E-DOCUMENT.json'), body_url: url });
    await open(item('W-2304'));
    fireEvent.click(button('Open the minutes'));
    await ws().findByRole('heading', { name: 'Weekly sync minutes · Lagoon Health' });
    expect(ws().queryByRole('link', { name: 'Open the file' })).toBeNull();
  });

  it('a 404 shows no title; a 500 offers a retry of the read only', async () => {
    documentAnswer = () => json(404, { code: 'not_found', message: 'x' });
    await open(item('W-2304'));
    fireEvent.click(button('Open the minutes'));
    await ws().findByText('You can’t open this document.');
    expect(wsEl().textContent).not.toContain('Weekly sync minutes');
    documentAnswer = () => json(500, { code: 'server_error', message: 'x' });
    fireEvent.click(button('Open the minutes'));
    await ws().findByText('We couldn’t open the minutes. Try again.');
    documentAnswer = () => json(200, read('E-DOCUMENT.json'));
    fireEvent.click(button('Try again'));
    await ws().findByRole('heading', { name: 'Weekly sync minutes · Lagoon Health' });
    expect(posts()).toHaveLength(0);
  });
});

describe('review shows who and what (AC 17)', () => {
  it('W-2304 shows the version, recipients with Not yet, the consequence, and links to the decision page; nothing is sent from here', async () => {
    await open(item('W-2304'));
    const text = wsEl().textContent!;
    expect(text).toContain('Minutes v1 · for Lagoon Health');
    expect(text).toContain('Minutes v1 · client version');
    expect(text).toContain('Goes to');
    expect(text).toContain('Ada Okoye · Lagoon Health');
    expect(text).toContain('Not yet');
    expect(text).toContain('Approving sends this exact version to the client. Actions are created whether or not the client reads it.');
    expect(screen.getByText('Your review')).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Approve and send' }).getAttribute('href')).toBe('/work/W-2304/decide?task=T-2304');
    expect(ws().getByRole('link', { name: 'Return with a note' }).getAttribute('href')).toBe('/work/W-2304/decide?task=T-2304');
    fireEvent.click(ws().getByRole('link', { name: 'Approve and send' }));
    expect(posts()).toHaveLength(0);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });
});

describe('an uncertain send keeps the lock (AC 19, INV-RESEND)', () => {
  it('W-2305 after an uncertain approve: both decision links are aria-disabled with no href, reconcile is the only action, before and after a reload', async () => {
    const uncertain = read('work/W-2305.approve.json') as WorkItem;
    const view = await open(uncertain);
    for (const name of ['Approve and send', 'Return with a note']) {
      const control = ws().getByText(name).closest('a, button') as HTMLElement;
      expect(control.tagName, name).toBe('BUTTON');
      expect(control.getAttribute('aria-disabled'), name).toBe('true');
      expect(control.getAttribute('href'), name).toBeNull();
      await act(async () => {
        fireEvent.click(control);
      });
    }
    expect(ws().queryAllByRole('link', { name: /Approve and send|Return with a note/ })).toEqual([]);
    expect(screen.getByText('Confirm what happened first.')).toBeTruthy();
    expect(await screen.findByRole('radiogroup', { name: 'Confirm what happened' })).toBeTruthy();
    expect(posts()).toHaveLength(0);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
    view.unmount();
    await open(uncertain);
    expect(ws().queryAllByRole('link', { name: /Approve and send|Return with a note/ })).toEqual([]);
    fireEvent.click(screen.getByRole('radio', { name: /It didn’t arrive/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    await waitFor(() => expect(posts('/actions')).toHaveLength(1));
    expect(posts()).toHaveLength(0);
    expect(posts('/decision')).toHaveLength(0);
  });

  const withStep = () => {
    const body = item('W-2304');
    body.workspace!.steps!.push({ key: 'note_it', label: 'Note it', emphasis: 'secondary', applies_to: 'workspace' });
    return body;
  };

  it('a decision link is an unavailable control while a write is in flight, then a link again', async () => {
    let release: (r: Response) => void = () => undefined;
    stepAnswers = [() => new Promise<Response>((resolve) => (release = resolve))];
    await open(withStep());
    expect(ws().getByRole('link', { name: 'Approve and send' }).getAttribute('href')).toBe('/work/W-2304/decide?task=T-2304');
    await press('Note it');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(ws().queryAllByRole('link', { name: /Approve and send|Return with a note/ })).toEqual([]);
    expect(button('Approve and send').getAttribute('aria-disabled')).toBe('true');
    expect(button('Approve and send').getAttribute('href')).toBeNull();
    await act(async () => {
      release(ok());
    });
    await waitFor(() => expect(ws().getByRole('link', { name: 'Approve and send' })).toBeTruthy());
  });

  it('after a failed refresh the decision links stay unavailable until a reload works', async () => {
    stepAnswers = [ok()];
    await open(withStep(), () => json(500, { code: 'server_error', message: 'x' }));
    await press('Note it');
    await waitFor(() => expect(posts()).toHaveLength(1));
    await ws().findByRole('button', { name: 'Reload this item' });
    expect(ws().queryAllByRole('link', { name: /Approve and send|Return with a note/ })).toEqual([]);
    expect(button('Approve and send').getAttribute('aria-disabled')).toBe('true');
  });
});

describe('access and signed out (AC 20)', () => {
  it('a 404 on the read shows the no-access state with no title', async () => {
    itemAnswers = [() => json(404, { code: 'not_found', message: 'x' })];
    render(
      <AppShell>
        <WorkItemView id="W-2301" tab="overview" />
      </AppShell>,
    );
    await waitFor(() => expect(document.body.textContent).not.toContain('Confirm the minutes'));
    await waitFor(() => expect(screen.queryByText(/Loading/i)).toBeNull());
    expect(document.body.textContent).not.toMatch(/Lagoon Health|MIN-0141|W-2301/);
  });

  it('a 403 on a step reloads and says You can’t take that step.', async () => {
    stepAnswers = [json(403, { code: 'forbidden', message: 'x' })];
    await open(item('W-2301'));
    await press('Save for later');
    await screen.findByText('You can’t take that step.');
    expect(itemReads()).toHaveLength(2);
  });
});

describe('the same controls for every persona (AC 21)', () => {
  it.each(['pm', 'ceo', 'finance_lead'])('%s sees the same step controls for W-2301', async (who) => {
    persona = who;
    await open(item('W-2301'));
    expect(ws().getAllByRole('button').map((b) => b.textContent)).toEqual(['Edit', 'Remove', 'Edit', 'Remove', 'Edit', 'Remove', 'Edit', 'Edit', 'Confirm and create actions', 'Save for later', '+ Add an action']);
  });
});

describe('unknown and restricted (AC 22)', () => {
  it('W-2307 reads Unknown for the due, never 0 or blank, and the restricted notes item shows only its label', async () => {
    await open(item('W-2307'));
    expect(rowOf(A3).getByText('Unknown')).toBeTruthy();
    expect(rowOf(A3).queryByText(/^0$|^-$/)).toBeNull();
    expect(document.body.textContent).not.toMatch(/Hidden: renegotiate the fee|Private note/);
    expect(wsEl().textContent).toContain('Restricted');
  });
});

describe('notes text grants nothing (AC 23)', () => {
  it('a suggestion that says approved, owner and due changes no field and is plain text', async () => {
    await open(item('W-2307'));
    const row = rowOf('Approved by Kemi; owner Tunde; due today.');
    expect(row.getByText('Approved by Kemi; owner Tunde; due today.')).toBeTruthy();
    expect(row.getByRole('checkbox').getAttribute('aria-label')).toBe('Select Approved by Kemi; owner Tunde; due today.');
    expect(rowOf(A3).getByText('Choose an owner')).toBeTruthy();
    expect(wsEl().querySelectorAll('input[type="text"], select')).toHaveLength(0);
    expect(posts()).toHaveLength(0);
  });
});

describe('round 2: Edit opens with the row’s current values (UX-1-1)', () => {
  it('an action’s form opens with its text, owner and due; saving untouched sends them as they were', async () => {
    await open(item('W-2301'));
    await act(async () => {
      fireEvent.click(rowOf(A1).getByRole('button', { name: 'Edit' }));
    });
    const f = form('Edit');
    expect((f.getByLabelText('Action') as HTMLInputElement).value).toBe(A1);
    expect(f.getByText('Lagoon Health')).toBeTruthy();
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Edit' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body!.inputs).toEqual({ text: A1, owner: 'O-LAGOON', due: '2026-11-13' });
  });

  it('a decision’s form opens with its text; an action with no owner or due opens with those blank and sends neither', async () => {
    await open(item('W-2301'));
    await act(async () => {
      fireEvent.click(rowOf(D1).getByRole('button', { name: 'Edit' }));
    });
    expect((form('Edit').getByLabelText('Decision') as HTMLInputElement).value).toBe(D1);
    fireEvent.click(form('Edit').getByRole('button', { name: 'Cancel' }));
    await act(async () => {
      fireEvent.click(rowOf(A3).getByRole('button', { name: 'Edit' }));
    });
    await act(async () => {
      fireEvent.click(form('Edit').getByRole('button', { name: 'Edit' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body!.inputs).toEqual({ text: A3 });
  });
});

describe('round 2: a section that is not drawn adds nothing to the confirm set (SEC-1-1)', () => {
  it('rows inside a restricted section are neither ticked, nor counted as a second section, nor sent', async () => {
    const body = item('W-2301');
    body.workspace!.sections.find((sec) => sec.key === 'decisions')!.restricted = true;
    await open(body);
    expect(ws().queryByText(D1)).toBeNull();
    // only the actions remain a target section, so the confirm is the table’s own control, not the workspace row's
    fireEvent.click(ws().getAllByRole('button', { name: 'Confirm and create actions' })[0]);
    const f = await screen.findByRole('form', { name: 'Confirm and create actions' });
    await act(async () => {
      fireEvent.click(within(f).getByRole('button', { name: 'Confirm and create actions' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body!.item_ids).toEqual(['A-1', 'A-2', 'A-3']);
  });
});

describe('round 2: no second card for a task the workspace links to (UI-1-3)', () => {
  it('W-2304 draws no task card and no Open the decision button; the workspace links stay', async () => {
    await open(item('W-2304'));
    expect(screen.queryByRole('link', { name: /Open the decision/ })).toBeNull();
    expect(screen.queryByText('Review client minutes v1')).toBeNull();
    expect(ws().getAllByRole('link', { name: /Approve and send|Return with a note/ })).toHaveLength(2);
  });
});

describe('round 2: wording and board rows', () => {
  it('a step that answers “Done: …” is not prefixed with the step label', async () => {
    stepAnswers = [ok({ message: 'Done: action added.' })];
    await open(item('W-2301'));
    await press('Save for later');
    await screen.findByText('Done: action added.');
    expect(wsEl().textContent).not.toContain('Save for later Done');
  });

  it('W-2303 and W-2304 draw the boards’ rows: Minutes v1 · client version with DRAFTED, IN tags neutral, no extra heading or version line', async () => {
    await open(item('W-2304'));
    expect(ws().getByRole('heading', { name: 'Minutes v1 · for Lagoon Health' })).toBeTruthy();
    expect(rowOf('Minutes v1 · client version').getByText('DRAFTED')).toBeTruthy();
    expect(wsEl().querySelector('.ws-byline')).toBeNull();
    expect(wsEl().querySelectorAll('.psl-tag--done')).toHaveLength(0);
    expect(item('W-2301').workspace!.context).not.toHaveProperty('project');
    expect(item('W-2302').workspace!.context).toHaveProperty('project');
  });
});

describe('round 3: dates stay dates (UI-2-1)', () => {
  it('the Due column is a date column: "13 Nov" when the column says day_month, the full date without it, and an unknown due is the Unknown value', async () => {
    const body = item('W-2301');
    const table = body.workspace!.sections.find((sec) => sec.kind === 'table')!;
    expect(table.columns!.find((c) => c.key === 'due')).toMatchObject({ kind: 'date' });
    expect(table.items[2].cells!.find((c) => c.column === 'due')).toMatchObject({ date: { unknown: true } });
    const view = await open(body);
    expect(rowOf(A3).getByText('Unknown').className).toContain('psl-unknown');
    view.unmount();
    delete (table.columns!.find((c) => c.key === 'due') as Record<string, unknown>).date_format;
    await open(body);
    expect(rowOf(A1).getByText('13 Nov 2026')).toBeTruthy();
  });
});

describe('sign-off round: the sentence that asks the PM to act is an amber warning, chosen by the data', () => {
  it('W-2301 draws the flagged line as a warning callout and the others in the info note; unflagged data draws all in the info note', async () => {
    const body = item('W-2301');
    expect(body.workspace!.agent_note).toMatchObject({ warn_lines: [2] });
    const view = await open(body);
    const warning = wsEl().querySelector('.psl-callout--warning.ws-agentnote') as HTMLElement;
    expect(warning.textContent).toContain('One action has no owner and its due date is Unknown.');
    expect(wsEl().querySelector('.psl-callout--info.ws-agentnote')!.textContent).not.toContain('One action has no owner');
    view.unmount();
    delete (body.workspace!.agent_note as Record<string, unknown>).warn_lines;
    await open(body);
    expect(wsEl().querySelector('.psl-callout--warning.ws-agentnote')).toBeNull();
  });
});
