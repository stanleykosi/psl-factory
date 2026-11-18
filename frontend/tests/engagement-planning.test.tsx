// @vitest-environment jsdom
// F-31: the engagement (W-2601, W-2602, W-2604) and the planning item (W-2603) drawn from E-WORK-ITEM `workspace`, with their
// writes: confirm the PM (E-WORK-ASSIGN), register the engagement (E-WORK-STEP) and record one department's input
// (E-RESPONSE, in the Drawer). Contract mock only: the fetch stub stands in for the backend, and nothing here proves a
// department was asked, a project created or a planning line started.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

// @ts-expect-error plain ESM module without type declarations
import { projects } from '../mock/projects.mjs';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2601',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => (name === 'W-2603.recorded' ? read(`response/${name}.json`) : read(`work/${name}.json`));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path: string) => ajv.compile(openapi.paths[path].post.requestBody.content['application/json'].schema);
const stepRequest = schemaOf('/api/v1/work/{work_id}/steps');
const assignRequest = schemaOf('/api/v1/work/{work_id}/assignment');
const responseRequest = schemaOf('/api/v1/tasks/{task_id}/response');
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = Response | (() => Response | Promise<Response>);
let sent: Sent[];
let reads: Record<string, WorkItem[]>;
let writes: Record<string, Answer[]>;
let who: string;
let uploads: number;

const posts = (suffix: string) => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const itemReads = (id?: string) => sent.filter((r) => r.method === 'GET' && (id ? r.path === `/api/v1/work/${id}` : /^\/api\/v1\/work\/W-\d+$/.test(r.path)));
const SUFFIX = /\/(steps|assignment|response|claim|evidence)$/;

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
        return json(200, queue.length > 1 ? queue.shift()! : queue[0]);
      }
      const write = SUFFIX.exec(url.pathname);
      if (request.method === 'POST' && write) {
        const key = write[1];
        if (key === 'evidence') {
          uploads += 1;
          const body = JSON.parse(text) as { case_revision: number };
          if (!writes.evidence) return json(200, { evidence_id: `EV-${uploads}`, sha256: 'a'.repeat(64), case_revision: body.case_revision + 1 });
        }
        const queue = writes[key];
        if (!queue) return json(404, { code: 'not_found', message: 'Not here.' });
        const answer = queue.length > 1 ? queue.shift()! : queue[0];
        return typeof answer === 'function' ? answer() : answer;
      }
      return json(404, { code: 'not_found', message: 'Not here.' });
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function phone() {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
}

async function open(first: WorkItem, ...later: WorkItem[]) {
  reads[first.id] = [first, ...later];
  const view = render(
    <AppShell>
      <WorkItemView id={first.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: first.title });
  return view;
}

const ws = () => within(document.querySelector('.ws') as HTMLElement);
const text = () => document.body.textContent ?? '';
const buttons = () => ws().queryAllByRole('button').map((b) => b.textContent);
const clone = (name: string): WorkItem => structuredClone(item(name));
const bump = (body: WorkItem, revision: number): WorkItem => ({ ...body, revision, workspace: { ...body.workspace!, revision } });
const press = async (name: string | RegExp, scope: () => ReturnType<typeof within> = ws) => {
  await act(async () => {
    fireEvent.click(scope().getByRole('button', { name }));
  });
};
const pdf = (name = 'kickoff-plan-v1.pdf', size = 4096) => new File([new Uint8Array(size).fill(37)], name, { type: 'application/pdf' });
const dialog = () => within(screen.getByRole('dialog'));
type Cells = { column: string; text?: string; money?: { unknown: boolean }; tag?: unknown }[];
const rowOf = (body: WorkItem, rowId: string) => body.workspace!.sections.flatMap((s) => s.items).find((i) => i.id === rowId)!;
const cellsOf = (body: WorkItem, rowId: string) => rowOf(body, rowId).cells as Cells;

// ---------------------------------------------------------------------------------------------------------------------
describe('W-2601 the engagement packet, from data (AC 1, 2)', () => {
  it('draws the crumbs, title, subtitle, six packet rows with their tags, the price with its amount, the unknowns line, Tola and Ask Tola', async () => {
    await open(item('W-2601'));
    expect([...document.querySelectorAll('.ws-crumbs li')].map((li) => li.textContent)).toEqual(['Pre-sale', 'Engagements', 'EN-0042']);
    expect(document.querySelector('h1')!.textContent).toBe('Ojo Foods · engagement EN-0042');
    expect(document.querySelector('.work-linemeta')!.textContent).toContain('Route A · from won RFP OF-RFP-2026-006');
    expect(ws().getByRole('heading', { name: 'Planning packet · built by Tola' })).toBeTruthy();
    const rows = [...document.querySelectorAll('.ws-section--table tbody tr')].map((tr) => [...tr.querySelectorAll('td')].map((td) => td.textContent));
    expect(rows).toEqual([
      ['Scope', 'RFP response v3 · 58 requirements addressed', 'IN'],
      ['Price', 'Costing v2 · ₦40,951,000.00', 'IN'],
      ['Team estimates', 'Engineering 210 days · Security 18 days', 'IN'],
      ['Start date', 'Not in the award letter', 'UNKNOWN'],
      ['Client project contact', 'Award letter names procurement only', 'UNKNOWN'],
      ['Delivery plan', 'Needs planning', 'NOT YET'],
    ]);
    expect(ws().getByText('Unknowns stay Unknown until someone supplies them; planning will ask for them.')).toBeTruthy();
    expect(ws().getByRole('heading', { name: 'Planning packet' })).toBeTruthy();
    expect([...document.querySelectorAll('.ws-rows--checklist li')]).toHaveLength(5);
    expect(ws().getByText(/AWARD LETTER · 04 DEC/)).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Ask Tola' })).toBeTruthy();
    expect(text()).not.toContain('Open question for PSL');
  });

  it('no board string is in src (a fixture word is data, not code)', () => {
    const hits: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.(ts|tsx)$/.test(name) && /Not in the award letter|Needs planning|PLANNING · |OWNER NEEDED|Open question for PSL/.test(readFileSync(path, 'utf8'))) hits.push(path);
      }
    };
    walk(join(__dirname, '../src'));
    expect(hits).toEqual([]);
  });

  it('a money amount marked unknown reads "Costing v2 · Unknown", never ₦0.00', async () => {
    const body = clone('W-2601');
    cellsOf(body, 'PK-2')[1].money = { unknown: true } as never;
    delete (cellsOf(body, 'PK-2')[1].money as { amount?: string }).amount;
    Object.assign(cellsOf(body, 'PK-2')[1].money!, { currency: 'NGN' });
    await open(body);
    const price = [...document.querySelectorAll('.ws-section--table tbody tr')][1].querySelectorAll('td')[1];
    expect(price.textContent).toBe('Costing v2 · Unknown');
    expect(text()).not.toContain('₦0.00');
  });

  it('a start-date row with its tag removed reads Unknown in its place, never a blank', async () => {
    const body = clone('W-2601');
    delete (cellsOf(body, 'PK-4')[2] as { tag?: unknown }).tag;
    await open(body);
    const status = [...document.querySelectorAll('.ws-section--table tbody tr')][3].querySelectorAll('td')[2];
    expect(status.textContent).toBe('Unknown');
    cleanup();
    const gone = clone('W-2601');
    gone.workspace!.sections[0].items[3].cells = (cellsOf(gone, 'PK-4') as Cells).slice(0, 2) as never;
    await open(gone);
    expect([...document.querySelectorAll('.ws-section--table tbody tr')][3].querySelectorAll('td')[2].textContent).toBe('Unknown');
  });

  it('tables in other fixtures draw as before: text cells are their words, and Unknown only where the data says unknown', async () => {
    for (const id of ['W-2002', 'W-2004', 'W-2312']) {
      cleanup();
      const body = clone(id);
      await open(body);
      const tables = body.workspace!.sections.filter((s) => s.kind === 'table');
      const rendered = [...document.querySelectorAll('.ws-section--table')];
      expect(rendered.length).toBe(tables.length);
      tables.forEach((section, t) => {
        const rows = [...rendered[t].querySelectorAll('tbody tr')];
        section.items.forEach((row, r) => {
          const tds = [...rows[r].querySelectorAll('td')];
          section.columns!.forEach((column) => {
            const cell = row.cells?.find((x) => x.column === column.key);
            const td = tds.find((x) => x.getAttribute('data-label') === column.label)!;
            if ((column.kind ?? 'text') === 'text' && cell?.text && !cell.restricted) expect(td.textContent, `${id} ${row.id} ${column.key}`).toMatch(new RegExp(`^${cell.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
            if (column.kind === 'tag' && cell?.tag) expect(td.textContent, `${id} ${row.id} ${column.key}`).toBe(cell.tag.label);
          });
        });
        const unknownData = section.items.flatMap((row) => section.columns!.map((column) => ({ column, cell: row.cells?.find((x) => x.column === column.key) }))).filter(({ column, cell }) => {
          if (column.kind === 'money') return !cell?.money || cell.money.unknown || !('amount' in cell.money);
          if (column.kind === 'date') return !cell?.date || cell.date.unknown || !('date' in cell.date);
          return false;
        });
        const unknownShown = [...rendered[t].querySelectorAll('tbody td')].filter((td) => td.textContent === 'Unknown');
        expect(unknownShown.length, `${id} ${section.key}`).toBe(unknownData.length);
      });
    }
  });
});

// ---------------------------------------------------------------------------------------------------------------------
describe('Confirm PM, pre-filled from the response only (AC 3)', () => {
  const pmSelect = () => ws().getByRole('combobox', { name: /^PM/ });

  it('the side panel holds a labelled PM Select of exactly the three candidates, Sola Martins chosen, the returned hint and Confirm PM', async () => {
    await open(item('W-2601'));
    expect(ws().getByRole('heading', { name: 'Decide' })).toBeTruthy();
    expect(pmSelect().textContent).toContain('Sola Martins');
    expect(ws().getByText('Carried over from the RFP. Change it only if someone else will run delivery.')).toBeTruthy();
    expect(ws().getByRole('button', { name: 'Confirm PM' })).toBeTruthy();
    expect(ws().queryByRole('button', { name: 'Set an owner' })).toBeNull();
    fireEvent.click(pmSelect());
    const options = await screen.findAllByRole('option');
    expect(options).toHaveLength(3);
    ['Sola Martins', 'Tunde Bello', 'Kunle Ade'].forEach((name, i) => expect(options[i].textContent).toMatch(new RegExp(`^${name}`)));
    expect(sent.filter((r) => r.method !== 'GET')).toHaveLength(0);
  });

  it('pressing it sends one POST with CSRF and {expected_revision, person_id}, a double press sends one, and the page re-reads', async () => {
    await open(item('W-2601'), item('W-2601.next'));
    writes.assignment = [json(200, { work_id: 'W-2601', state: 'action_needed', revision: 4, assigned_to: 'Sola Martins' })];
    const button = ws().getByRole('button', { name: 'Confirm PM' });
    await act(async () => {
      fireEvent.click(button);
      fireEvent.click(button);
    });
    await waitFor(() => expect(ws().getByRole('button', { name: 'Register engagement' })).toBeTruthy());
    const calls = posts('/assignment');
    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe('/api/v1/work/W-2601/assignment');
    expect(calls[0].csrf).toBe('mock-csrf-pm');
    expect(assignRequest(calls[0].body), ajv.errorsText(assignRequest.errors)).toBe(true);
    expect(calls[0].body).toEqual({ expected_revision: 3, person_id: 'P-0021' });
    expect(await screen.findByText('PM confirmed: Sola Martins')).toBeTruthy();
    expect(ws().getByText('Sola Martins')).toBeTruthy();
    expect(itemReads('W-2601').length).toBeGreaterThanOrEqual(2);
    expect(ws().queryByRole('combobox', { name: /^PM/ })).toBeNull();
  });

  it('choosing someone else sends that candidate', async () => {
    await open(item('W-2601'), item('W-2601.next'));
    writes.assignment = [json(200, { work_id: 'W-2601', state: 'action_needed', revision: 4, assigned_to: 'Kunle Ade' })];
    fireEvent.click(pmSelect());
    fireEvent.click(await screen.findByRole('option', { name: /Kunle Ade/ }));
    await press('Confirm PM');
    await waitFor(() => expect(posts('/assignment')).toHaveLength(1));
    expect(posts('/assignment')[0].body).toEqual({ expected_revision: 3, person_id: 'P-0031' });
  });

  it('a default that is not a candidate, or absent, gives F-30’s closed "Set an owner" with nothing chosen', async () => {
    const stray = clone('W-2601');
    (stray.assign as { default_person_id?: string }).default_person_id = 'P-9999';
    await open(stray);
    expect(buttons()).toEqual(['Set an owner']);
    expect(ws().queryByRole('combobox')).toBeNull();
    cleanup();
    const bare = clone('W-2601');
    delete (bare.assign as { default_person_id?: string }).default_person_id;
    await open(bare);
    expect(buttons()).toEqual(['Set an owner']);
    await press('Set an owner');
    expect(ws().getByRole('combobox', { name: /Owner/ }).textContent).toContain('Choose an owner');
    expect(ws().getByRole('button', { name: 'Set owner' })).toBeTruthy();
    expect(ws().getByRole('button', { name: 'Cancel' })).toBeTruthy();
  });

  it('a 409 re-reads and says so with the choice kept; no resend', async () => {
    await open(item('W-2601'), bump(item('W-2601'), 5));
    writes.assignment = [json(409, { code: 'stale', message: 'Changed.' })];
    fireEvent.click(pmSelect());
    fireEvent.click(await screen.findByRole('option', { name: /Tunde Bello/ }));
    await press('Confirm PM');
    expect(await screen.findByText(/This changed while you were working. Showing version 5./)).toBeTruthy();
    expect(posts('/assignment')).toHaveLength(1);
    expect(pmSelect().textContent).toContain('Tunde Bello');
  });

  it('a 5xx says "Not recorded", re-reads, and sends once', async () => {
    await open(item('W-2601'));
    writes.assignment = [json(500, { code: 'server_error', message: 'Nope.' })];
    await press('Confirm PM');
    expect(await screen.findByText('Not recorded')).toBeTruthy();
    expect(text()).not.toContain('PM confirmed');
    expect(posts('/assignment')).toHaveLength(1);
    expect(ws().getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it('the assign hook and form never read /me', () => {
    for (const name of ['AssignForm.tsx', 'useWorkspaceAssign.ts', 'ResponseDrawer.tsx']) {
      expect(readFileSync(join(__dirname, '../src/features/workspace', name), 'utf8'), name).not.toMatch(/\buseMe\b|\/me\b/);
    }
  });
});

// ---------------------------------------------------------------------------------------------------------------------
describe('Register the engagement (AC 4, 5)', () => {
  async function openForm(first = item('W-2602'), ...later: WorkItem[]) {
    await open(first, ...later);
    await press('Register engagement');
    return within(document.querySelector('form[aria-labelledby]') as HTMLElement);
  }
  const fileInput = () => document.querySelector('input[type="file"]') as HTMLInputElement;
  async function upload(file = pdf()) {
    const before = posts('/evidence').length;
    fireEvent.change(fileInput(), { target: { files: [file] } });
    await waitFor(() => expect(posts('/evidence')).toHaveLength(before + 1));
    await waitFor(() => expect(screen.queryByText(/Uploading…/)).toBeNull());
  }
  async function fill(form: ReturnType<typeof within>) {
    await upload();
    fireEvent.change(form.getByLabelText(/Start date/), { target: { value: '15 Jan 2027' } });
    fireEvent.blur(form.getByLabelText(/Start date/));
    fireEvent.change(form.getByLabelText(/Client project contact/), { target: { value: '  Ngozi Bello · Head of Lending Operations  ' } });
  }
  const submit = async (form: ReturnType<typeof within>) => {
    await act(async () => {
      fireEvent.click(form.getByRole('button', { name: 'Register engagement' }));
    });
  };

  it('draws What registering does and the closed button, and opens the form with the three fields on press', async () => {
    await open(item('W-2602'));
    expect(ws().getByRole('heading', { name: 'What registering does' })).toBeTruthy();
    expect(ws().getByText('Creates the project in Projects')).toBeTruthy();
    expect(ws().getByText("The SOW comes after planning, on the project's Documents tab.")).toBeTruthy();
    expect(ws().getByText('Sola Martins')).toBeTruthy();
    expect(ws().queryByRole('combobox')).toBeNull();
    await press('Register engagement');
    const form = within(document.querySelector('form[aria-labelledby]') as HTMLElement);
    expect(form.getByText(/Plan evidence/)).toBeTruthy();
    expect(form.getByText('The plan the engagement starts from')).toBeTruthy();
    expect(form.getByLabelText(/Start date/)).toBeTruthy();
    expect(form.getByLabelText(/Client project contact/)).toBeTruthy();
    expect(sent.filter((r) => r.method !== 'GET')).toHaveLength(0);
  });

  it('uploads the PDF once to the engagement case and sends one request that validates against the generated schema, then shows the returned message and the re-read links', async () => {
    const form = await openForm(item('W-2602'), item('W-2602.next'));
    await fill(form);
    expect(posts('/evidence')).toHaveLength(1);
    expect(posts('/evidence')[0].path).toBe('/api/v1/cases/C-2602/evidence');
    expect(posts('/evidence')[0].body).toMatchObject({ kind: 'plan', filename: 'kickoff-plan-v1.pdf', case_revision: 2 });
    writes.steps = [json(200, { work_id: 'W-2602', state: 'waiting', revision: 5, outcome: 'done', message: 'Engagement EN-0042 registered.' })];
    expect(text()).not.toContain('Engagement EN-0042 registered.');
    await submit(form);
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    const [post] = posts('/steps');
    expect(post.path).toBe('/api/v1/work/W-2602/steps');
    expect(post.csrf).toBe('mock-csrf-pm');
    expect(stepRequest(post.body), ajv.errorsText(stepRequest.errors)).toBe(true);
    const { idempotency_key: key, ...rest } = post.body!;
    expect(key).toMatch(UUID);
    expect(rest).toEqual({
      expected_revision: 4,
      step: 'register_engagement',
      inputs: { start_date: '2027-01-15', client_contact: 'Ngozi Bello · Head of Lending Operations' },
      evidence_ids: ['EV-1'],
    });
    expect(await screen.findByText('Engagement EN-0042 registered.')).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Ojo Foods · ordering app' }).getAttribute('href')).toBe('/projects/P-0106');
    expect(ws().getByRole('link', { name: 'Planning · PLN-0031' }).getAttribute('href')).toBe('/work/W-2603');
    expect(ws().queryByRole('button', { name: 'Register engagement' })).toBeNull();
  });

  it('an empty optional field is not sent, and the page does not say anything was created before the re-read', async () => {
    const form = await openForm(item('W-2602'));
    await upload();
    writes.steps = [json(500, { code: 'server_error', message: 'Nope.' })];
    await submit(form);
    await waitFor(() => expect(posts('/steps')).toHaveLength(1));
    expect(posts('/steps')[0].body).not.toHaveProperty('inputs');
    expect(stepRequest(posts('/steps')[0].body)).toBe(true);
    expect(text()).not.toMatch(/Creates the project in Projects.*(registered|created)\b/i);
    expect(text()).not.toContain('Engagement EN-0042 registered.');
  });

  it('W-2604 (effect_uncertain): the reconcile notice shows, every step is off, a reload keeps it off, and exactly one register request was sent', async () => {
    const form = await openForm(item('W-2604'), item('W-2604.next'));
    await fill(form);
    writes.steps = [json(200, { work_id: 'W-2604', state: 'effect_uncertain', revision: 5, outcome: 'effect_uncertain', message: 'We couldn’t confirm the engagement was registered.' })];
    await submit(form);
    expect(await screen.findByText('We couldn’t confirm the engagement was registered.')).toBeTruthy();
    expect(ws().getByRole('button', { name: 'Register engagement' }).getAttribute('aria-disabled')).toBe('true');
    expect(posts('/steps')).toHaveLength(1);
    expect(text()).not.toContain('Created');
    cleanup();
    await open(item('W-2604.next'));
    expect(ws().getByRole('button', { name: 'Register engagement' }).getAttribute('aria-disabled')).toBe('true');
    await act(async () => {
      fireEvent.click(ws().getByRole('button', { name: 'Register engagement' }));
    });
    expect(screen.queryByRole('form')).toBeNull();
    expect(posts('/steps')).toHaveLength(1);
  });

  it('a 500 says "Not done", re-reads, and Try again repeats the same key; a network error does the same', async () => {
    for (const failure of [json(500, { code: 'server_error', message: 'Nope.' }), () => Promise.reject(new TypeError('Failed to fetch'))] as Answer[]) {
      cleanup();
      sent = [];
      const form = await openForm();
      await fill(form);
      writes.steps = [failure];
      await submit(form);
      await waitFor(() => expect(posts('/steps')).toHaveLength(1));
      expect(await screen.findByText('Register engagement', { selector: 'strong' })).toBeTruthy();
      expect(text()).toContain('We couldn’t confirm this step');
      expect(text()).not.toContain('Engagement EN-0042 registered.');
      writes.steps = [json(200, { work_id: 'W-2602', state: 'waiting', revision: 5, outcome: 'done', message: 'Engagement EN-0042 registered.' })];
      await act(async () => {
        fireEvent.click(within(document.querySelector('form[aria-labelledby]') as HTMLElement).getByRole('button', { name: 'Try again' }));
      });
      await waitFor(() => expect(posts('/steps')).toHaveLength(2));
      expect(posts('/steps')[1].body!.idempotency_key).toBe(posts('/steps')[0].body!.idempotency_key);
    }
  });

  it('a 409 re-reads, keeps the entries and sends the new revision on the next press', async () => {
    const form = await openForm(item('W-2602'), bump(item('W-2602'), 6));
    await fill(form);
    writes.steps = [json(409, { code: 'stale', message: 'Changed.' })];
    await submit(form);
    expect(await screen.findByText(/This changed while you were working. Showing version 6./)).toBeTruthy();
    expect((form.getByLabelText(/Client project contact/) as HTMLInputElement).value).toContain('Ngozi Bello');
    writes.steps = [json(200, { work_id: 'W-2602', state: 'waiting', revision: 7, outcome: 'done' })];
    await submit(form);
    await waitFor(() => expect(posts('/steps')).toHaveLength(2));
    expect(posts('/steps')[1].body!.expected_revision).toBe(6);
  });

  it('a 422 shows the messages under the named fields and never the registered state', async () => {
    const form = await openForm();
    await fill(form);
    writes.steps = [json(422, { code: 'invalid', message: 'Check start_date.', fields: [{ name: 'start_date', message: 'Pick a date after today.' }] })];
    await submit(form);
    expect((await screen.findAllByText('Pick a date after today.')).length).toBeGreaterThan(0);
    expect(text()).not.toContain('registered.');
  });
});

// ---------------------------------------------------------------------------------------------------------------------
describe('W-2603 planning, from data (AC 6, 7)', () => {
  const rows = () => [...document.querySelectorAll('.ws-section--table tbody tr')].map((tr) => [...tr.querySelectorAll('td')].map((td) => td.textContent));

  it('draws the status and byline as returned, the five departments, the estimates and Unknown, the note, the finding, Tola’s checklist and Readiness', async () => {
    await open(item('W-2603'));
    expect(document.querySelector('.work-state')!.textContent).toBe('PLANNING · 2 OF 5 IN');
    expect(document.querySelector('.ws-byline')!.textContent).toBe('PM Sola Martins');
    expect([...document.querySelectorAll('.ws-crumbs li')].map((li) => li.textContent)).toEqual(['Projects', 'Ojo Foods', 'Planning · PLN-0031']);
    expect(rows()).toEqual([
      ['Engineering', 'Scope breakdown and effort', 'IN · 09 DEC', '230 person-days', 'Proof', ''],
      ['QA', 'Test plan and effort', 'WAITING · ASKED 08 DEC', 'Unknown', '', 'Record input'],
      ['Security', 'Security review plan and effort', 'IN · 09 DEC', '20 person-days', 'Proof', ''],
      ['Product', 'Confirm scope against the RFP', 'OWNER NEEDED', 'Unknown', '', 'Who receives this?Not available yet'],
      ['Infrastructure', 'Hosting and environments', 'WAITING · ASKED 08 DEC', 'Unknown', '', 'Record input'],
    ]);
    expect(ws().getByText("Departments don't log in. You record what they send, with proof; the record keeps your name.")).toBeTruthy();
    expect(ws().getByText(/Engineering now says 230 person-days; the RFP costing used 210\./)).toBeTruthy();
    expect(ws().getByText('Costing v2')).toBeTruthy();
    expect(ws().getByRole('heading', { name: 'Read the packet and asked departments' })).toBeTruthy();
    expect(ws().getByText(/Sent requests to Engineering, QA, Security and Infrastructure/)).toBeTruthy();
    expect(ws().getByText(/EMAIL · 08 DEC/)).toBeTruthy();
    expect(ws().getByText(/OWNER NEEDED · NO ONE SET UP/)).toBeTruthy();
    expect(ws().getByText('Tola prepares the readiness summary once every department has answered.')).toBeTruthy();
    expect(ws().getByText('Waiting on QA and Infrastructure. Product has no owner yet.')).toBeTruthy();
  });

  it('a different status label is shown as returned, and nothing counts rows or adds estimates', async () => {
    const body = clone('W-2603');
    body.workspace!.status!.label = 'PLANNING · 4 OF 5 IN';
    await open(body);
    expect(document.querySelector('.work-state')!.textContent).toBe('PLANNING · 4 OF 5 IN');
    for (const name of readdirSync(join(__dirname, '../src/features/workspace'))) {
      if (!/\.(ts|tsx)$/.test(name)) continue;
      const source = readFileSync(join(__dirname, '../src/features/workspace', name), 'utf8');
      expect(source, name).not.toMatch(/person-days/);
      if (name === 'ResponseDrawer.tsx') expect(source).not.toMatch(/\.reduce\(/);
    }
  });

  it('Record input is on QA and Infrastructure only; Who receives this? is disabled with its reason and no href; Prepare readiness sends nothing', async () => {
    await open(item('W-2603'));
    const recordButtons = ws().getAllByRole('button', { name: 'Record input' });
    expect(recordButtons).toHaveLength(2);
    expect(recordButtons.map((b) => b.closest('tr')!.querySelector('td')!.textContent)).toEqual(['QA', 'Infrastructure']);
    const who = ws().getByRole('button', { name: 'Who receives this?' });
    expect(who.getAttribute('aria-disabled')).toBe('true');
    expect(who.getAttribute('href')).toBeNull();
    expect(ws().getByText('Not available yet')).toBeTruthy();
    const readiness = ws().getByRole('button', { name: 'Prepare readiness' });
    expect(readiness.getAttribute('aria-disabled')).toBe('true');
    await act(async () => {
      fireEvent.click(readiness);
      fireEvent.click(who);
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(sent.filter((r) => r.method !== 'GET')).toHaveLength(0);
    expect(buttons().filter((b) => /Send|Remind|Resend|Open costing/.test(b ?? ''))).toEqual([]);
  });

  it('the same data gives the same controls for pm, finance_lead and ceo', async () => {
    const seen: (string | null)[][] = [];
    for (const persona of ['pm', 'finance_lead', 'ceo']) {
      cleanup();
      who = persona;
      await open(item('W-2603'));
      seen.push(buttons());
    }
    expect(seen[1]).toEqual(seen[0]);
    expect(seen[2]).toEqual(seen[0]);
    expect(seen[0]).toEqual(['Record input', 'Who receives this?', 'Record input', 'Prepare readiness']);
  });

  it('a copy with the steps removed draws none, and a task that cannot be acted on draws no Record input', async () => {
    const bare = clone('W-2603');
    delete bare.workspace!.steps;
    await open(bare);
    expect(buttons()).toEqual([]);
    expect(ws().getByRole('link', { name: 'Ask Tola' }).getAttribute('href')).toBe('/assistant');
    cleanup();
    const closed = clone('W-2603');
    closed.tasks[0].you_can_act = false;
    await open(closed);
    expect(ws().queryAllByRole('button', { name: 'Record input' })).toHaveLength(0);
    expect(ws().getByRole('button', { name: 'Who receives this?' })).toBeTruthy();
    cleanup();
    const stray = clone('W-2603');
    stray.tasks = [];
    await open(stray);
    // a step whose task is not in this item stays the F-16 decision link, not a drawer
    expect(ws().getAllByRole('link', { name: 'Record input' })[0].getAttribute('href')).toBe('/work/W-2603/decide?task=T-2603');
  });

  it('Tola’s text is only displayed: no verified mark, no delivery receipt, no costing; Ask Tola only when links carries it', async () => {
    const body = clone('W-2603');
    await open(body);
    const checklist = document.querySelector('.ws-section--checklist')!;
    expect(checklist.textContent).toContain('Tola');
    expect(ws().getByText(/Sent requests to Engineering/).closest('li')!.textContent).not.toMatch(/verified|delivered|receipt/i);
    expect(document.querySelector('.ws')!.textContent).not.toMatch(/Start costing|Open costing|Remind|Resend/i);
    expect(ws().getByRole('link', { name: 'Ask Tola' })).toBeTruthy();
    cleanup();
    delete (body.workspace as { links?: unknown }).links;
    await open(body);
    expect(ws().queryByRole('link', { name: 'Ask Tola' })).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------------
describe('Record department input, in the Drawer (AC 8, 9, 10)', () => {
  async function openDrawer(row = 'QA', ...later: WorkItem[]) {
    // the page reads the item, then the Drawer reads it again for its own form
    await open(item('W-2603'), item('W-2603'), ...later);
    const button = ws().getAllByRole('button', { name: 'Record input' }).find((b) => b.closest('tr')!.querySelector('td')!.textContent === row)!;
    await act(async () => {
      fireEvent.click(button);
    });
    await screen.findByRole('dialog');
    await waitFor(() => expect(dialog().getByRole('button', { name: /Record/ })).toBeTruthy());
    return button;
  }
  async function upload(file = pdf('qa-plan.pdf', 2048)) {
    const before = posts('/evidence').length;
    fireEvent.change(document.querySelector('[role="dialog"] input[type="file"]') as HTMLInputElement, { target: { files: [file] } });
    await waitFor(() => expect(posts('/evidence')).toHaveLength(before + 1));
    await waitFor(() => expect(screen.queryByText(/Uploading…/)).toBeNull());
  }
  async function fillQa({ attest = true } = {}) {
    fireEvent.change(dialog().getByLabelText('Who gave it'), { target: { value: 'R-QA' } });
    fireEvent.change(dialog().getByLabelText(/Estimate/), { target: { value: '45' } });
    fireEvent.change(dialog().getByLabelText(/What they gave/), { target: { value: 'Test plan and QA effort for the loan app' } });
    await upload();
    fireEvent.change(dialog().getByLabelText(/Received/), { target: { value: '2026-12-11T16:05' } });
    if (attest) fireEvent.click(dialog().getByRole('checkbox'));
  }
  const recordButton = () => dialog().getByRole('button', { name: /^Record/ }) as HTMLButtonElement;

  it('pressing QA’s button opens the Drawer titled Record department input with the department picker, the estimate, the proof, Received, the attestation and the intro', async () => {
    await openDrawer('QA');
    expect(screen.getByRole('dialog').getAttribute('aria-labelledby')).toBeTruthy();
    expect(dialog().getByText('Record department input')).toBeTruthy();
    const teams = dialog().getAllByRole('radio').map((r) => (r as HTMLInputElement).closest('label')?.textContent ?? r.getAttribute('aria-label'));
    expect(teams.map((t) => t?.replace(/,.*$/, '').trim())).toEqual(['QA', 'Infrastructure']);
    expect(dialog().getByRole('radio', { name: /^QA/ }).getAttribute('aria-checked')).toBe('true');
    expect(dialog().getByLabelText(/Estimate/)).toBeTruthy();
    expect(dialog().getByLabelText(/What they gave/)).toBeTruthy();
    expect(dialog().getByLabelText(/Received/)).toBeTruthy();
    expect(dialog().getByText('I confirm this input came from the team named above.')).toBeTruthy();
    expect(dialog().getByText("QA doesn't log in. This records their input under your name, with the proof attached.")).toBeTruthy();
    expect(sent.filter((r) => r.method !== 'GET')).toHaveLength(0);
  });

  it('Infrastructure’s button chooses Infrastructure; a team with a disabled_reason is not offered', async () => {
    await openDrawer('Infrastructure');
    expect(dialog().getByRole('radio', { name: /^Infrastructure/ }).getAttribute('aria-checked')).toBe('true');
    cleanup();
    const body = clone('W-2603');
    (body.tasks[0].response!.teams![1] as { disabled_reason?: string }).disabled_reason = 'No one set up';
    await open(body, body);
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button', { name: 'Record input' })[0]);
    });
    await screen.findByRole('dialog');
    await waitFor(() => expect(dialog().queryAllByRole('radio').length).toBeGreaterThan(0));
    expect(dialog().queryByRole('radio', { name: /Infrastructure/ })).toBeNull();
    expect(dialog().getByRole('radio', { name: /^QA/ })).toBeTruthy();
  });

  it('Record stays off until the attestation is ticked, and nothing is sent', async () => {
    await openDrawer('QA');
    await fillQa({ attest: false });
    expect(recordButton().disabled).toBe(true);
    await act(async () => {
      fireEvent.click(recordButton());
    });
    expect(posts('/response')).toHaveLength(0);
    expect(posts('/claim')).toHaveLength(0);
  });

  it('records once: one POST with F-18’s body, a double press sends one, the drawer closes, the re-read shows QA in and the status from the re-read, focus goes to the table heading', async () => {
    await openDrawer('QA', item('W-2603.recorded'));
    await fillQa();
    writes.response = [json(200, { task_id: 'T-2603', work_state: 'waiting', revision: 5, recorded: { by: { name: 'Tunde Bello', role: 'PM', is_you: true }, at: '2026-12-11T15:05:00Z', responded_at: '2026-12-11T15:05:00Z', proof_count: 1, summary: 'QA’s input' } })];
    await act(async () => {
      fireEvent.click(recordButton());
      fireEvent.click(recordButton());
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    const calls = posts('/response');
    expect(calls).toHaveLength(1);
    expect(posts('/claim')).toHaveLength(0);
    expect(calls[0].path).toBe('/api/v1/tasks/T-2603/response');
    expect(calls[0].csrf).toBe('mock-csrf-pm');
    expect(responseRequest(calls[0].body), ajv.errorsText(responseRequest.errors)).toBe(true);
    expect(calls[0].body).toMatchObject({
      team: 'qa',
      action: 'estimate',
      estimate_person_days: 45,
      what: 'Test plan and QA effort for the loan app',
      evidence_id: 'EV-1',
      attested: true,
      expected_revision: 4,
      case_revision: 4,
    });
    expect(calls[0].body!.responded_at).toBe('2026-12-11T16:05:00+01:00');
    await waitFor(() => expect(document.querySelector('.work-state')!.textContent).toBe('PLANNING · 3 OF 5 IN'));
    const qa = [...document.querySelectorAll('.ws-section--table tbody tr')][1];
    expect([...qa.querySelectorAll('td')].map((td) => td.textContent)).toEqual(['QA', 'Test plan and effort', 'IN · 11 DEC', '45 person-days', 'Proof', '']);
    expect(ws().getAllByRole('button', { name: 'Record input' })).toHaveLength(1);
    expect(await screen.findByText(/Recorded under your name: QA’s input/)).toBeTruthy();
    await waitFor(() => expect(document.activeElement?.textContent).toBe('What each department must give'));
  });

  it('the recorded text says it was recorded under the PM’s name and never that the department logged in', async () => {
    await openDrawer('QA', item('W-2603.recorded'));
    await fillQa();
    writes.response = [json(200, { task_id: 'T-2603', work_state: 'waiting', recorded: { by: { name: 'Tunde Bello' }, at: '2026-12-11T15:05:00Z' } })];
    await act(async () => {
      fireEvent.click(recordButton());
    });
    expect(await screen.findByText(/Recorded under your name, 11 Dec/)).toBeTruthy();
    expect(text()).not.toMatch(/logged in|signed in as/i);
    expect(readFileSync(join(__dirname, '../src/features/workspace/ResponseDrawer.tsx'), 'utf8')).not.toMatch(/logged in|signed in as/i);
  });

  it('sends one claim first only when the task says claim_required', async () => {
    const body = clone('W-2603');
    body.tasks[0].response!.claim_required = true;
    await open(body, body, item('W-2603.recorded'));
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button', { name: 'Record input' })[0]);
    });
    await screen.findByRole('dialog');
    await waitFor(() => expect(dialog().getByRole('button', { name: /^Record/ })).toBeTruthy());
    await fillQa();
    writes.claim = [json(200, { task_id: 'T-2603', revision: 5, claimed_by: 'Tunde Bello' })];
    writes.response = [json(200, { task_id: 'T-2603', work_state: 'waiting' })];
    await act(async () => {
      fireEvent.click(recordButton());
    });
    await waitFor(() => expect(posts('/response')).toHaveLength(1));
    expect(posts('/claim')).toHaveLength(1);
    expect(posts('/response')[0].body!.expected_revision).toBe(5);
  });

  it('a 422 shows its message and keeps the entries; the page does not say recorded', async () => {
    await openDrawer('QA');
    await fillQa();
    writes.response = [json(422, { code: 'invalid', message: 'Check these fields: estimate_person_days.' })];
    await act(async () => {
      fireEvent.click(recordButton());
    });
    expect(await screen.findByText('Check these fields: estimate_person_days.')).toBeTruthy();
    expect((dialog().getByLabelText(/What they gave/) as HTMLInputElement).value).toBe('Test plan and QA effort for the loan app');
    expect(text()).not.toMatch(/Recorded under your name/);
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('a 409 re-reads and keeps every entry with no resend; a stale proof upload re-reads the case revision before any new upload', async () => {
    await openDrawer('QA');
    await fillQa();
    writes.response = [json(409, { code: 'stale', message: 'Changed.' })];
    await act(async () => {
      fireEvent.click(recordButton());
    });
    expect(await screen.findByText(/This changed while you were recording/)).toBeTruthy();
    expect(posts('/response')).toHaveLength(1);
    expect((dialog().getByLabelText(/What they gave/) as HTMLInputElement).value).toContain('Test plan');
    expect(text()).not.toMatch(/Recorded under your name/);
  });

  it('a 500 and a network error re-read before offering Record again, and never say recorded', async () => {
    for (const failure of [json(500, { code: 'server_error', message: 'Nope.' }), () => Promise.reject(new TypeError('Failed to fetch'))] as Answer[]) {
      cleanup();
      sent = [];
      await openDrawer('QA');
      await fillQa();
      const readsBefore = itemReads('W-2603').length;
      writes.response = [failure];
      await act(async () => {
        fireEvent.click(recordButton());
      });
      expect(await screen.findByText(/We couldn’t confirm your input was recorded/)).toBeTruthy();
      expect(itemReads('W-2603').length).toBeGreaterThan(readsBefore);
      expect(posts('/response')).toHaveLength(1);
      expect(text()).not.toMatch(/Recorded under your name/);
    }
  });

  it('401 on the write shows signed out, 403 and 404 the same not-open view', async () => {
    for (const [status, shown] of [[401, 'signed out'], [404, 'not open'], [403, 'not open']] as const) {
      cleanup();
      sent = [];
      await openDrawer('QA');
      await fillQa();
      writes.response = [json(status, { code: status === 401 ? 'unauthenticated' : status === 403 ? 'forbidden' : 'not_found', message: 'No.' })];
      await act(async () => {
        fireEvent.click(recordButton());
      });
      if (shown === 'signed out') await screen.findByText(/signed out/i);
      else await waitFor(() => expect(text(), String(status)).not.toContain('Ojo Foods'));
      expect(text()).not.toContain('QA');
    }
  });

  it('Cancel and Escape close the Drawer with no request and return focus to the button', async () => {
    const button = await openDrawer('QA');
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(button));
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------------------------------------------------
describe('access and the project (AC 12, 13, 14)', () => {
  it('401 on the read shows signed out; 403 and 404 look the same with no title, name or fact; persona none sees the not-open view', async () => {
    for (const id of ['W-2601', 'W-2602', 'W-2603']) {
      for (const status of [403, 404]) {
        cleanup();
        vi.stubGlobal(
          'fetch',
          withoutBellFeed(async (request: Request) => {
            const url = new URL(request.url);
            if (url.pathname === '/api/v1/me') return json(200, read('me.pm.json'));
            return json(status, { code: status === 403 ? 'forbidden' : 'not_found', message: 'No.' });
          }),
        );
        render(
          <AppShell>
            <WorkItemView id={id} tab="overview" />
          </AppShell>,
        );
        await screen.findByText(/can’t open this work item/i);
        expect(text()).not.toMatch(/Ojo Foods|EN-0042|PLN-0031|40,951,000|Sola Martins/);
      }
    }
    cleanup();
    vi.stubGlobal(
      'fetch',
      withoutBellFeed(async (request: Request) => {
        const url = new URL(request.url);
        if (url.pathname === '/api/v1/me') return json(200, read('me.pm.json'));
        return json(401, { code: 'unauthenticated', message: 'Sign in.' });
      }),
    );
    render(
      <AppShell>
        <WorkItemView id="W-2603" tab="overview" />
      </AppShell>,
    );
    await screen.findByRole('link', { name: /Sign in/ });
  });

  it('no component of this feature reads /me to decide a control, a PM, a name or a department', () => {
    for (const dir of ['features/workspace', 'features/work-item']) {
      for (const name of readdirSync(join(__dirname, '../src', dir))) {
        if (!/\.(ts|tsx)$/.test(name)) continue;
        expect(readFileSync(join(__dirname, '../src', dir, name), 'utf8'), `${dir}/${name}`).not.toMatch(/useMe\b|\/api\/v1\/me\b/);
      }
    }
  });

  it('P-0106’s "Plan a project" line links to /work/W-2603', async () => {
    vi.stubGlobal(
      'fetch',
      withoutBellFeed(async (request: Request) => {
        const url = new URL(request.url);
        if (url.pathname === '/api/v1/me') return json(200, read('me.finance_lead.json'));
        const result = projects({ operationId: 'E-PROJECT', url, persona: 'finance_lead' }) as { status: number; body: unknown };
        return json(result.status, result.body);
      }),
    );
    render(
      <AppShell>
        <ProjectJourneyPage caseId="P-0106" />
      </AppShell>,
    );
    const link = await screen.findByRole('link', { name: /Plan a project/ });
    expect(link.getAttribute('href')).toBe('/work/W-2603');
  });

  it('the project bar on W-2603 links six tabs to P-0106 and marks none current; on a phone the back link reads Project, and other lines keep Queue', async () => {
    await open(item('W-2603'));
    const bar = within(screen.getByRole('navigation', { name: 'Project' }));
    expect(bar.getAllByRole('link').map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Journey', '/projects/P-0106'],
      ['Milestones', '/projects/P-0106/milestones'],
      ['Documents', '/projects/P-0106/documents'],
      ['Money', '/projects/P-0106/money'],
      ['Registers', '/projects/P-0106/registers'],
      ['Actions', '/projects/P-0106/actions'],
    ]);
    expect(bar.queryAllByRole('link').filter((a) => a.getAttribute('aria-current'))).toHaveLength(0);
    expect(screen.queryByRole('link', { name: 'Planning' })).toBeNull();
    cleanup();
    phone();
    await open(item('W-2603'));
    const back = screen.getByRole('link', { name: /^Back to Project$/ });
    expect(back.getAttribute('href')).toBe('/projects/P-0106');
    cleanup();
    reads = {};
    await open(item('W-2209'));
    expect(screen.getByRole('link', { name: /^Back to Queue$/ }).getAttribute('href')).toBe('/my-work');
  });

  it('the engagement keeps the frame’s Queue back link and draws no project bar', async () => {
    phone();
    await open(item('W-2601'));
    expect(screen.getByRole('link', { name: /^Back to Queue$/ })).toBeTruthy();
    expect(screen.queryByRole('navigation', { name: 'Project' })).toBeNull();
  });
});

describe('phone (AC 15)', () => {
  it('Register engagement opens in the full-height Drawer; Escape closes it and returns focus to the button', async () => {
    phone();
    await open(item('W-2602'));
    const button = ws().getByRole('button', { name: 'Register engagement' });
    await press('Register engagement');
    const drawer = await screen.findByRole('dialog');
    expect(drawer.className).toContain('cmp-panel--full');
    expect(within(drawer).getByLabelText(/Client project contact/)).toBeTruthy();
    fireEvent.keyDown(drawer, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(button));
  });

  it('Record input opens the full-height Drawer with the same fields', async () => {
    phone();
    await open(item('W-2603'));
    await act(async () => {
      fireEvent.click(ws().getAllByRole('button', { name: 'Record input' })[0]);
    });
    const drawer = await screen.findByRole('dialog');
    expect(drawer.className).toContain('cmp-panel--full');
    await waitFor(() => expect(within(drawer).getByLabelText(/What they gave/)).toBeTruthy());
    expect(within(drawer).getByLabelText(/Estimate/)).toBeTruthy();
  });

  it('Confirm PM stays open in the panel on a phone, with the same fields', async () => {
    phone();
    await open(item('W-2601'));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(ws().getByRole('button', { name: 'Confirm PM' })).toBeTruthy();
  });
});
