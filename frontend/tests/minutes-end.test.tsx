// @vitest-environment jsdom
// F-28: the minutes line's two end states on the F-17 workspace frame (PROPOSAL D-LINE-WORKSPACE, contract mock only).
// The fetch stub stands in for the backend. Nothing here proves a working minutes line, a real send, a delivery, a
// filing, duplicate-send protection or a real action record. The client template is a test template.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { reloadPage } from '@/features/response';
import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2311',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const owners: { items: { value: string; label: string; hint?: string }[] } = read('start-work/options/owner.json');
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined };
let sent: Sent[];
let itemAnswers: (WorkItem | (() => Response))[];
let stepAnswers: (Response | (() => Response))[];
let persona: string;

const posts = (suffix = '/steps') => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const documentReads = () => sent.filter((r) => r.method === 'GET' && r.path.startsWith('/api/v1/documents/'));
const ok = () => json(200, { work_id: 'W-0', state: 'ready', revision: 9, outcome: 'done' });

beforeEach(() => {
  sent = [];
  itemAnswers = [];
  stepAnswers = [];
  persona = 'pm';
  vi.stubGlobal(
    'fetch',
    withoutBellFeed(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.text();
      sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined });
      if (url.pathname === '/api/v1/me') return json(200, read(`me.${persona}.json`));
      if (url.pathname.includes('/fields/') && url.pathname.endsWith('/options')) return json(200, { items: owners.items, as_of: '2026-11-12T09:00:00Z' });
      if (url.pathname.startsWith('/api/v1/documents/')) return json(200, read('E-DOCUMENT.json'));
      if (request.method === 'GET' && url.pathname.startsWith('/api/v1/work/')) {
        const next = itemAnswers.length > 1 ? itemAnswers.shift()! : itemAnswers[0];
        return typeof next === 'function' ? next() : json(200, next);
      }
      if (url.pathname.endsWith('/steps')) {
        const answer = stepAnswers.length > 1 ? stepAnswers.shift()! : (stepAnswers[0] ?? ok());
        return typeof answer === 'function' ? answer() : answer;
      }
      if (url.pathname.endsWith('/actions')) return json(200, { work_id: 'W-2312', state: 'action_needed', revision: 10 });
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
const rowOf = (text: string) => within(ws().getByText(text).closest('tr, li') as HTMLElement);
const form = (name: string) => within(screen.getByRole('form', { name }));

describe('internal from data (AC 4)', () => {
  it('W-2310 draws the status, the returned sentence, the Created table with owner, due and state, Next and Open actions', async () => {
    await open(item('W-2310'));
    expect(screen.getByText('Filed · Internal')).toBeTruthy();
    const text = wsEl().textContent!;
    for (const s of ['Internal minutes are filed straight away; no review. 2 actions were created on the action list.', 'Filed', 'Created', 'Owners see their actions in My work.']) expect(text, s).toContain(s);
    expect(ws().getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Action', 'Owner', 'Due', 'State']);
    const first = rowOf('ACT-0451 · Prepare test devices list');
    expect(first.getByText('Tunde Bello')).toBeTruthy();
    expect(first.getByText('13 Nov')).toBeTruthy();
    expect(first.getByText('OPEN')).toBeTruthy();
    expect(rowOf('ACT-0452 · Book go-live rehearsal').getByText('Ada Okoye · Lagoon Health')).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Open actions' }).getAttribute('href')).toBe('/projects/C-0211/actions');
    expect(ws().queryAllByRole('button')).toEqual([]);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });

  it('nothing is counted by the frame: a sentence that says 3 actions over two rows shows both unchanged', async () => {
    const body = item('W-2310');
    body.workspace!.sections![0].items[0].text = '3 actions were created.';
    await open(body);
    expect(ws().getByText('3 actions were created.')).toBeTruthy();
    expect(ws().getAllByRole('row')).toHaveLength(3);
  });
});

describe('published from data (AC 5, 9)', () => {
  it('W-2311 draws the sentence, three actions with OWNER NEEDED on the ownerless one, Sent to with each receipt, Next and Open actions', async () => {
    await open(item('W-2311'));
    expect(screen.getByText('Published · Received')).toBeTruthy();
    const text = wsEl().textContent!;
    for (const s of ['Minutes v1 approved by Kemi Adebayo and emailed to Lagoon Health on 10 Nov 17:30, delivery confirmed. 3 actions are on the action list.', 'Actions created', 'Sent to', 'An action with no owner shows in Unassigned for leads.']) expect(text, s).toContain(s);
    const third = rowOf('Assess the SMS reminders change');
    expect(third.getByText('No owner yet')).toBeTruthy();
    expect(third.getByText('Unknown').className).toContain('psl-unknown');
    expect(third.getByText('OWNER NEEDED')).toBeTruthy();
    expect(rowOf('Send test accounts for UAT').queryByText('OWNER NEEDED')).toBeNull();
    const sentTo = within(ws().getByRole('heading', { name: 'Sent to' }).closest('section') as HTMLElement);
    expect(sentTo.getAllByText('Received')).toHaveLength(2);
    expect(sentTo.getByText('Ada Okoye · Lagoon Health')).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Open actions' }).getAttribute('href')).toBe('/projects/C-0211/actions');
    expect(ws().queryByRole('button', { name: 'Open the minutes' })).toBeNull();
  });

  it('no owner is guessed from text: a row that says "owner Tunde" keeps its owner cell and OWNER NEEDED tag', async () => {
    const body = item('W-2311');
    const table = body.workspace!.sections!.find((s) => s.kind === 'table')!;
    table.items[2].cells![0].text = 'Assess the SMS reminders change, owner Tunde';
    await open(body);
    const row = rowOf('Assess the SMS reminders change, owner Tunde');
    expect(row.getByText('No owner yet')).toBeTruthy();
    expect(row.queryByText('Tunde')).toBeNull();
    expect(row.getByText('OWNER NEEDED')).toBeTruthy();
  });

  it('W-2314 minimal: no Open actions, no Open the minutes, no Next, no Sent to; a missing due reads Unknown', async () => {
    await open(item('W-2314'));
    expect(ws().queryByRole('link', { name: 'Open actions' })).toBeNull();
    expect(ws().queryByRole('button', { name: 'Open the minutes' })).toBeNull();
    expect(ws().queryByText('Sent to')).toBeNull();
    expect(ws().queryByText('Next')).toBeNull();
    const row = rowOf('Assess the SMS reminders change');
    expect(row.getByText('Unknown')).toBeTruthy();
    expect(row.getByText('OWNER NEEDED')).toBeTruthy();
  });
});

describe('receipts are per person (AC 6, 8)', () => {
  const recipients = (...receipts: (string | undefined)[]) => {
    const body = item('W-2311');
    const section = body.workspace!.sections!.find((s) => s.kind === 'recipients')!;
    section.items = receipts.map((receipt, i) => ({ id: `R-${i}`, text: `Person ${i}`, channel: 'email', ...(receipt ? { receipt } : {}) }) as never);
    body.workspace!.sections = [body.workspace!.sections!.find((s) => s.kind === 'text')!, section];
    (body.workspace!.sections[0].items[0] as { text: string }).text = 'Minutes v1 approved by Kemi Adebayo.';
    delete (body.workspace!.sections[0].items[0] as { tag?: unknown }).tag;
    return body;
  };

  it.each([
    ['received', 'Received'],
    ['uncertain', 'Uncertain'],
    ['not_yet', 'Not yet'],
    ['unknown', 'Unknown'],
    ['failed', 'Failed'],
    [undefined, 'Unknown'],
  ])('a recipient with receipt %s reads %s; only a received one is ever Received', async (receipt, word) => {
    await open(recipients(receipt as string | undefined));
    const row = Object.assign(rowOf('Person 0'), { container: ws().getByText('Person 0').closest('tr, li') as HTMLElement });
    expect(row.getByText(word)).toBeTruthy();
    expect(row.container.textContent).not.toMatch(/\bSent\b|\bDelivered\b|delivered|emailed/);
    if (receipt !== 'received') expect(row.queryByText('Received')).toBeNull();
  });

  it('every recipient not_yet: the page carries only returned strings, no emailed or delivered text of the frame', async () => {
    await open(recipients('not_yet', 'not_yet'));
    expect(document.body.textContent).not.toMatch(/emailed|delivered|Delivered|Sent to your/);
    expect(wsEl().textContent).toContain('Minutes v1 approved by Kemi Adebayo.');
  });

  it('W-2312 reads Received, Uncertain and Not yet, the returned unconfirmed status and no aggregate delivery claim', async () => {
    await open(item('W-2312'));
    expect(screen.getByText('Published · Delivery unconfirmed')).toBeTruthy();
    expect(rowOf('Ada Okoye · Lagoon Health').getByText('Received')).toBeTruthy();
    expect(rowOf('Lagoon Health projects inbox').getByText('Uncertain')).toBeTruthy();
    expect(rowOf('Femi Daniel · Lagoon Health').getByText('Not yet')).toBeTruthy();
    expect(wsEl().textContent).not.toMatch(/delivery confirmed/);
  });
});

describe('an uncertain send keeps the lock (AC 7, INV-RESEND)', () => {
  it('W-2312: reconcile is the only action; Open actions and Open the minutes still read; one reconcile press is one POST to /actions only; same after a reload', async () => {
    const view = await open(item('W-2312'));
    expect(await screen.findByRole('radiogroup', { name: 'Confirm what happened' })).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Open actions' }).getAttribute('href')).toBe('/projects/C-0211/actions');
    for (const control of ws().queryAllByRole('button')) if (control.getAttribute('aria-disabled') !== 'true' && control.textContent !== 'Open the minutes') throw new Error(`live control: ${control.textContent}`);
    fireEvent.click(ws().getByRole('button', { name: 'Open the minutes' }));
    await ws().findByRole('heading', { name: 'Weekly sync minutes · Lagoon Health' });
    expect(documentReads().map((r) => r.path)).toEqual(['/api/v1/documents/D-2304/versions/1']);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
    view.unmount();
    await open(item('W-2312'));
    fireEvent.click(await screen.findByRole('radio', { name: /I can’t tell yet/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    await waitFor(() => expect(posts('/actions')).toHaveLength(1));
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(1);
    for (const suffix of ['/steps', '/claim', '/decision']) expect(posts(suffix)).toHaveLength(0);
  });
});

describe('links only from data (AC 10)', () => {
  const withLinks = (links: unknown) => {
    const body = item('W-2310');
    (body.workspace as { links?: unknown }).links = links;
    return body;
  };
  const tab = (target: Record<string, unknown>) => [{ key: 'open_actions', label: 'Open actions', target: { kind: 'project_tab', ...target } }];

  it.each([
    ['milestones', 'C-0211', '/projects/C-0211/milestones'],
    ['journey', 'C-0211', '/projects/C-0211'],
    ['actions', 'C-0211', '/projects/C-0211/actions'],
  ])('a known tab %s with case %s links to %s', async (tabKey, caseId, href) => {
    await open(withLinks(tab({ tab: tabKey, case_id: caseId })));
    expect(ws().getByRole('link', { name: 'Open actions' }).getAttribute('href')).toBe(href);
  });

  it.each([
    ['unknown tab', { tab: 'secrets', case_id: 'C-0211' }],
    ['no tab', { case_id: 'C-0211' }],
    ['no case', { tab: 'actions' }],
    ['dot segments', { tab: 'actions', case_id: '../admin' }],
    ['slash', { tab: 'actions', case_id: 'C-1/../x' }],
    ['absolute url', { tab: 'actions', case_id: 'https://evil.example' }],
    ['protocol-relative', { tab: 'actions', case_id: '//evil.example' }],
    ['encoded', { tab: 'actions', case_id: '%2e%2e' }],
    ['leading dot', { tab: 'actions', case_id: '.hidden' }],
    ['whitespace', { tab: 'actions', case_id: 'C-1 ' }],
    ['query', { tab: 'actions', case_id: 'C-1?x=1' }],
    ['non-string case', { tab: 'actions', case_id: 211 }],
  ])('%s draws nothing', async (_name, target) => {
    await open(withLinks(tab(target)));
    expect(ws().queryByRole('link', { name: 'Open actions' })).toBeNull();
  });

  it('an unknown link kind draws nothing', async () => {
    await open(withLinks([{ key: 'x', label: 'Open actions', target: { kind: 'teleport', tab: 'actions', case_id: 'C-0211' } }]));
    expect(ws().queryByRole('link', { name: 'Open actions' })).toBeNull();
  });
});

describe('owner assignment (AC 13)', () => {
  const body = () => item('W-2313');

  it('only the action whose data lists the step has the control; W-2310, W-2311 and W-2314 have none', async () => {
    const view = await open(body());
    expect(ws().getAllByRole('button', { name: 'Assign owner' })).toHaveLength(1);
    expect(rowOf('ACT-0462 · Book go-live rehearsal').getByRole('button', { name: 'Assign owner' })).toBeTruthy();
    view.unmount();
    for (const id of ['W-2310', 'W-2311', 'W-2314']) {
      const v = await open(item(id));
      expect(ws().queryAllByRole('button', { name: 'Assign owner' }), id).toEqual([]);
      v.unmount();
    }
  });

  it('a chosen owner is one POST with expected_revision = workspace.revision and a UUID key', async () => {
    await open(body());
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Assign owner' }));
    });
    const f = form('Assign owner');
    fireEvent.click(f.getByRole('combobox', { name: /Owner/ }));
    fireEvent.click(await screen.findByRole('option', { name: /Tunde Bello/ }));
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Assign owner' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const { idempotency_key: key, ...rest } = posts()[0].body!;
    expect(key).toMatch(UUID);
    expect(rest).toEqual({ expected_revision: 8, step: 'assign_owner', item_ids: ['A-2'], inputs: { owner: 'U-TUNDE' } });
  });

  it('a blank owner is left out of inputs; a 422 lands under the owner field and keeps the form; a 409 reloads', async () => {
    stepAnswers = [json(422, { code: 'invalid', message: 'Check these fields: owner.', fields: [{ name: 'owner', message: 'Choose an owner.' }] }), json(409, { code: 'stale_revision', message: 'x' })];
    await open(body());
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Assign owner' }));
    });
    const f = form('Assign owner');
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Assign owner' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).not.toHaveProperty('inputs');
    await screen.findByText('Choose an owner.');
    expect(screen.getByRole('form', { name: 'Assign owner' })).toBeTruthy();
    await act(async () => {
      fireEvent.click(form('Assign owner').getByRole('button', { name: 'Assign owner' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body!.idempotency_key).not.toBe(posts()[0].body!.idempotency_key);
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && /^\/api\/v1\/work\/W-2313$/.test(r.path)).length).toBeGreaterThanOrEqual(2));
  });
});

describe('access, signed out, personas, quiet (AC 14, 15, 16)', () => {
  it.each([403, 404])('a %s on the read shows no title, client, project or id', async (status) => {
    itemAnswers = [() => json(status, { code: 'not_found', message: 'x' })];
    render(
      <AppShell>
        <WorkItemView id="W-2311" tab="overview" />
      </AppShell>,
    );
    await waitFor(() => expect(screen.queryByText(/Loading/i)).toBeNull());
    expect(document.body.textContent).not.toMatch(/Weekly sync|Lagoon Health|MIN-0141|W-2311|Kemi Adebayo/);
  });

  it('a 401 shows the signed-out callout with a sign-in way back to this page', async () => {
    itemAnswers = [() => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' })];
    render(
      <AppShell>
        <WorkItemView id="W-2311" tab="overview" />
      </AppShell>,
    );
    await screen.findByText(/Sign in/);
    expect(document.body.textContent).not.toMatch(/Lagoon Health|MIN-0141/);
  });

  it.each(['pm', 'ceo', 'finance_lead'])('%s sees the same links and controls for W-2312', async (who) => {
    persona = who;
    await open(item('W-2312'));
    expect(ws().getAllByRole('link').map((l) => l.textContent)).toEqual(['Open actions']);
    expect(ws().getAllByRole('button').map((b) => b.textContent)).toEqual(['Open the minutes']);
  });

  it('nothing is requested on a timer and nothing is written on load (60 s of fake time)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open(item('W-2311'));
    const before = sent.length;
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });
    expect(sent.filter((r) => r.method !== 'GET')).toHaveLength(0);
    expect(sent.slice(before).filter((r) => r.path.startsWith('/api/v1/work/'))).toHaveLength(0);
    expect(ws().queryByRole('button', { name: /resend|send again|file|approve/i })).toBeNull();
  });
});

describe('reaching internal (AC 11)', () => {
  const confirm = async (audience: 'Internal' | 'Client') => {
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Confirm and create actions' }));
    });
    const f = form('Confirm and create actions');
    fireEvent.click(f.getByRole('radio', { name: audience }));
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Confirm and create actions' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
  };

  it('choosing Internal sends the F-23 request with audience internal and the reload renders the internal view', async () => {
    await open(item('W-2301'), item('W-2301.next.internal' as string));
    await confirm('Internal');
    expect(posts()[0].body).toMatchObject({ step: 'confirm_minutes', expected_revision: 4, item_ids: ['D-1', 'D-2', 'A-1', 'A-2', 'A-3'], inputs: { audience: 'internal' } });
    await screen.findByText('Filed · Internal');
    expect(ws().getByRole('link', { name: 'Open actions' }).getAttribute('href')).toBe('/projects/C-0211/actions');
    expect(posts()).toHaveLength(1);
  });

  it('choosing Client still ends on the drafted view', async () => {
    await open(item('W-2301'), item('W-2301.next' as string));
    await confirm('Client');
    expect(posts()[0].body).toMatchObject({ inputs: { audience: 'client' } });
    await screen.findByText('Drafted');
    expect(screen.queryByText('Filed · Internal')).toBeNull();
  });
});
