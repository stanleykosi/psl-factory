// @vitest-environment jsdom
// F-97: the engagement (SCR-41) and planning (SCR-42) panels on the live work item, against the live-shaped mock (mock/engagement-live.mjs).
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { ENGAGEMENT_PATH, engagementLive, resetEngagementLive } from '../mock/engagement-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4650', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const sent = async () => Promise.all(posts().map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));

beforeEach(() => {
  resetScopedWriteLocks();
  resetEngagementLive();
  scenario = undefined;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    if (!ENGAGEMENT_PATH.test(url.pathname)) {
      return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    }
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const [status, body] = engagementLive({ method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes }) as [number, unknown];
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = /Engagement steps|Departments/) => {
  render(
    <ToastProvider>
      <LiveWorkItemView id={String(id)} tab="overview" />
    </ToastProvider>,
  );
  await screen.findAllByText(wait);
};
const choose = (label: string, option: string) => {
  fireEvent.click(screen.getByRole('combobox', { name: label }));
  fireEvent.click(screen.getByRole('option', { name: new RegExp(`^${option}`) }));
};
const stepWord = (step: string) => screen.getAllByText(step).map((n) => n.closest('li')).find(Boolean)!.textContent!;

describe('the contract and the mock agree', () => {
  const spec = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, object>> };
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  ajv.addSchema({ $id: 'spec', ...spec });
  const schemaOf = (path: string, method: string, status: string) => `spec#/paths/${path.replaceAll('/', '~1')}/${method}/responses/${status}/content/application~1json/schema`;
  const reply = (path: string, method = 'get', extra: object = {}) => engagementLive({ method, url: new URL(path, 'http://m.local'), scenario: undefined, csrfOk: true, persona: 'finance_lead', ...extra }) as [number, unknown];
  const CASE = '00000000-0000-4000-8000-000000004650';

  it('every read answers its operation’s 200 shape', () => {
    const reads: [string, string][] = [
      ['/api/v1/work/4650/engagement', '/api/v1/work/{work_id}/engagement'],
      ['/api/v1/work/4653/engagement', '/api/v1/work/{work_id}/engagement'],
      ['/api/v1/work/4654/engagement', '/api/v1/work/{work_id}/engagement'],
      [`/api/v1/projects/${CASE}/engagement-intake`, '/api/v1/projects/{case_id}/engagement-intake'],
      ['/api/v1/work/4655/planning-owner-requests', '/api/v1/work/{work_id}/planning-owner-requests'],
      ['/api/v1/projects/00000000-0000-4000-8000-000000004655/planning', '/api/v1/projects/{case_id}/planning'],
      ['/api/v1/projects/00000000-0000-4000-8000-000000004657/planning', '/api/v1/projects/{case_id}/planning'],
      ['/api/v1/projects/00000000-0000-4000-8000-000000004655/planning/source-clarifications', '/api/v1/projects/{case_id}/planning/source-clarifications'],
      ['/api/v1/work/4650', '/api/v1/work/{work_id}'],
      ['/api/v1/work/4655', '/api/v1/work/{work_id}'],
    ];
    for (const [url, path] of reads) {
      const [status, body] = reply(url);
      expect(status, url).toBe(200);
      const validate = ajv.compile({ $ref: schemaOf(path, 'get', '200') });
      expect(validate(body), `${url}: ${ajv.errorsText(validate.errors)}`).toBe(true);
    }
  });

  it('the four bodies the mock accepts are the contract’s four bodies, and the mock refuses what the contract refuses', () => {
    const validate = ajv.compile({ $ref: `spec#/paths/${'/api/v1/work/{work_id}/engagement'.replaceAll('/', '~1')}/post/requestBody/content/application~1json/schema` });
    const base = { expected_revision: 5, case_revision: 89 };
    const bodies = [
      { ...base, action: 'assign', key: 'k1', evidence_id: 50, role: 'PM', pm_id: 31 },
      { ...base, action: 'details', key: 'k2', evidence_id: 50, capture_id: 1, reference: 'R', plan_id: 47, checked: true, planned_start: null, contact_id: null },
      { ...base, action: 'register', key: 'k3', evidence_id: 50, role: 'PM', value: 'PSL-1', plan_id: 47, details_id: 9 },
      { ...base, action: 'reassess', capture_id: 1, reason: 'x' },
    ];
    for (const body of bodies) expect(validate(body), JSON.stringify(body)).toBe(true);
    for (const bad of [{ ...bodies[0], extra: 1 }, { ...bodies[1], checked: false }, { ...bodies[2], role: 'Boss' }, { ...bodies[3], reason: '' }, { ...bodies[0], key: undefined }]) {
      expect(validate(bad), JSON.stringify(bad)).toBe(false);
      const [status] = reply('/api/v1/work/4650/engagement', 'post', { rawBytes: Buffer.from(JSON.stringify(bad)) });
      expect(status, JSON.stringify(bad)).toBe(400);
    }
  });
});

describe('engagement reads (SCR-41)', () => {
  it('a registered engagement: route in words, what was agreed, links to the project and planning, the receipt, and no forms', async () => {
    await open(4653);
    expect(screen.getByText('Route A · converted from a won bid')).toBeTruthy();
    expect(screen.getAllByText('PSL-DEMO-KORA').length).toBeGreaterThan(0);
    expect(stepWord('Register the engagement')).toContain('Done');
    expect(screen.getByRole('link', { name: 'Kora Logistics · fleet tracker' }).getAttribute('href')).toBe('/projects/00000000-0000-4000-8000-000000004653');
    expect(screen.getByRole('link', { name: 'Project planning' }).getAttribute('href')).toBe('/work/4655');
    expect(screen.getByText('Receipt recorded')).toBeTruthy();
    expect(screen.getByText('Not on file')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Confirm the project manager|Record the details|Register the engagement|Check again/ })).toBeNull();
    expect(posts()).toHaveLength(0);
  });

  it('a held engagement shows the finding and offers nothing to press', async () => {
    await open(4654);
    expect(screen.getByText('The prior identity or planning handoff needs current-source review')).toBeTruthy();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByRole('button', { name: /Confirm|Record|Register|Check again/ })).toBeNull();
  });
});

describe('engagement writes (SCR-41)', () => {
  it('confirm the PM, record the details, register: each body is the contract’s, and each result is told from the re-read', async () => {
    await open(4650);
    const press = screen.getByRole('button', { name: 'Confirm the project manager' });
    fireEvent.click(press);
    expect(await sent()).toEqual([]);
    expect(screen.getByText('Choose the project manager.')).toBeTruthy();
    choose('Project manager', 'Amaka Obi');
    choose('Role', 'PMO Lead');
    choose('Source for this choice', 'Engagement source, version 2');
    fireEvent.click(press);
    await screen.findByRole('button', { name: 'Record the details' });
    const [assign] = await sent();
    expect(assign.path).toBe('/api/v1/work/4650/engagement');
    expect(assign.body).toMatchObject({ action: 'assign', expected_revision: 5, case_revision: 89, evidence_id: 50, role: 'PMO Lead', pm_id: 32 });
    expect(assign.body.key).toMatch(/^[0-9a-f-]{36}$/);
    expect(Object.keys(assign.body).sort()).toEqual(['action', 'case_revision', 'evidence_id', 'expected_revision', 'key', 'pm_id', 'role']);
    expect(stepWord('Confirm the project manager')).toContain('Done');

    // details: the box must be ticked first
    fireEvent.click(screen.getByRole('button', { name: 'Record the details' }));
    expect(posts()).toHaveLength(1);
    choose('Source you checked', 'Product input');
    choose('Plan', 'RFP outcome');
    fireEvent.change(screen.getByLabelText(/Planned start/), { target: { value: '2026-12-01' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Record the details' }));
    await screen.findByRole('button', { name: 'Register the engagement' });
    const details = (await sent())[1].body;
    expect(details).toMatchObject({ action: 'details', expected_revision: 6, case_revision: 90, capture_id: 1, reference: 'PSL-DEMO-KORA', plan_id: 44, evidence_id: 47, checked: true, planned_start: '2026-12-01', contact_id: null });
    expect(Object.keys(details).sort()).toEqual(['action', 'capture_id', 'case_revision', 'checked', 'contact_id', 'evidence_id', 'expected_revision', 'key', 'plan_id', 'planned_start', 'reference']);
    expect(screen.getByText('2026-12-01')).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/Official project identifier/), { target: { value: 'PSL-2026-014' } });
    choose('Role', 'Head of PMO');
    choose('Source for the registration', 'Engagement source, version 2');
    fireEvent.click(screen.getByRole('button', { name: 'Register the engagement' }));
    await waitFor(() => expect(screen.getByText('Receipt recorded')).toBeTruthy());
    const register = (await sent())[2].body;
    expect(register).toMatchObject({ action: 'register', expected_revision: 7, case_revision: 91, role: 'Head of PMO', value: 'PSL-2026-014', plan_id: 44, details_id: 9, evidence_id: 50 });
    expect(stepWord('Register the engagement')).toContain('Done');
    expect(screen.getByRole('link', { name: 'Project planning' }).getAttribute('href')).toBe('/work/4655');
    expect(screen.queryByRole('button', { name: 'Register the engagement' })).toBeNull();
  });

  it('check again sends its reason and the capture, with no key and no checked box', async () => {
    await open(4651);
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }));
    expect(posts()).toHaveLength(0);
    fireEvent.change(screen.getByLabelText('Why'), { target: { value: 'The client changed the start date.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect((await sent())[0].body).toEqual({ action: 'reassess', expected_revision: 5, case_revision: 89, capture_id: 1, reason: 'The client changed the start date.' });
    await screen.findByText('Checked again; nothing changed.');
  });

  it('register is held with its reason until the details are recorded', async () => {
    resetEngagementLive();
    await open(4652);
    expect(screen.getByRole('button', { name: 'Register the engagement' })).toBeTruthy();
    expect(screen.queryByText('Record the details first.')).toBeNull();
  });

  it('a 409 shows the lasting notice and the latest version, and sends nothing more', async () => {
    scenario = 'w409';
    await open(4650);
    choose('Project manager', 'Tunde Bello');
    choose('Role', 'PMO Lead');
    choose('Source for this choice', 'Product input');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm the project manager' }));
    await screen.findByText(/This changed while you were working\. Showing the latest version\./);
    expect(posts()).toHaveLength(1);
    expect(screen.queryByText(/The project manager is recorded/)).toBeNull();
  });

  it('a 422 says what the server said and records nothing', async () => {
    scenario = 'w422';
    await open(4650);
    choose('Project manager', 'Tunde Bello');
    choose('Role', 'PMO Lead');
    choose('Source for this choice', 'Product input');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm the project manager' }));
    await screen.findByText(/The request was not accepted\./);
    expect(screen.getByText(/Choose a current source\./)).toBeTruthy();
    expect(stepWord('Confirm the project manager')).not.toContain('Done');
  });
});

describe('planning reads (SCR-42)', () => {
  it('each department with its status and estimate; unknown effort is not zero, not applicable is not unknown', async () => {
    await open(4655);
    const row = (name: string) => screen.getByRole('cell', { name }).closest('tr')!;
    expect(row('Engineering').textContent).toContain('Changed from costing');
    expect(row('Engineering').textContent).toContain('42.5 person-days');
    expect(row('QA').textContent).toContain('Effort unknown');
    expect(row('QA').textContent).not.toMatch(/person-days|\b0\b/);
    expect(row('QA').textContent).toContain('Unknown');
    expect(row('Security').textContent).toContain('Not applicable');
    expect(row('Product').textContent).toContain('Waiting for an estimate');
    expect(row('Infrastructure').textContent).toContain('8.0 person-days');
  });

  it('what is holding it, who receives each request, the department’s waiting request, readiness and the review', async () => {
    await open(4655);
    expect(screen.getByText(/Where the client data must be stored is not yet settled\./)).toBeTruthy();
    expect(screen.getByText(/The scope source names a different product than the PRD\./)).toBeTruthy();
    expect(screen.getByText(/Nobody is set to receive the Product request\./)).toBeTruthy();
    expect(screen.getByText('Nobody set to receive it')).toBeTruthy();
    expect(screen.getByText('Source access held')).toBeTruthy();
    expect(screen.getByText(/REQ-0077 · scope breakdown/)).toBeTruthy();
    expect(screen.getByText('Kora delivery dossier, version 1')).toBeTruthy();
    expect(screen.getByText('Not reviewed yet')).toBeTruthy();
    expect(screen.getByText('new costing')).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('a packet the person cannot read says so; the department’s own requests still draw', async () => {
    await open(4656, /isn’t available to you here/);
    expect(screen.getByText('The planning packet isn’t available to you here.')).toBeTruthy();
    expect(within(document.body).queryByText('Departments')).toBeTruthy();
  });

  it('no department asked yet says so', async () => {
    await open(4657, /No department has been asked/);
    expect(screen.getByText('Not prepared yet')).toBeTruthy();
  });
});
