// @vitest-environment jsdom
// F-99: the costing sheet (SCR-27) on the live work item, against the live-shaped mock (mock/costing-live.mjs).
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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
import { COSTING_PATH, costingLive, resetCostingLive } from '../mock/costing-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4700', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const sent = async () => Promise.all(posts().map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));

beforeEach(() => {
  resetScopedWriteLocks();
  resetCostingLive();
  scenario = undefined;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    if (!COSTING_PATH.test(url.pathname)) {
      return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    }
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const [status, body] = costingLive({ method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes }) as [number, unknown];
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = /Approvals/) => {
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


const spec = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, object>> };
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
ajv.addSchema({ $id: 'spec', ...spec });
const schemaOf = (path: string, method: string, status: string) => `spec#/paths/${path.replaceAll('/', '~1')}/${method}/responses/${status}/content/application~1json/schema`;
const reply = (path: string, method = 'get', extra: object = {}) => costingLive({ method, url: new URL(path, 'http://m.local'), scenario: undefined, csrfOk: true, persona: 'finance_lead', ...extra }) as [number, unknown];

describe('the contract and the mock agree', () => {
  it('every read answers its operation’s 200 shape', () => {
    const reads: [string, string][] = [
      ...[4700, 4701, 4702, 4703, 4704, 4705].map((id): [string, string] => [`/api/v1/work/${id}/bid-pricing`, '/api/v1/work/{work_id}/bid-pricing']),
      ['/api/v1/work/4700', '/api/v1/work/{work_id}'],
      ['/api/v1/projects/00000000-0000-4000-8000-000000004700/costing', '/api/v1/projects/{case_id}/costing'],
    ];
    for (const [url, path] of reads) {
      const [status, body] = reply(url);
      expect(status, url).toBe(200);
      const validate = ajv.compile({ $ref: schemaOf(path, 'get', '200') });
      expect(validate(body), `${url}: ${ajv.errorsText(validate.errors)}`).toBe(true);
    }
  });

  it('the bodies the mock accepts are the contract’s, and the mock refuses what the contract refuses', () => {
    const base = { expected_revision: 9, case_revision: 89 };
    const review = ajv.compile({ $ref: `spec#/paths/${'/api/v1/work/{work_id}/reviews'.replaceAll('/', '~1')}/post/requestBody/content/application~1json/schema` });
    const good = { ...base, kind: 'bid', subject: 'commercial', target_id: 5, role: 'PM', verdict: 'approve', evidence_id: null, note: '' };
    expect(review(good)).toBe(true);
    for (const bad of [{ ...good, verdict: 'maybe' }, { ...good, extra: 1 }, { ...good, evidence_id: undefined }, { ...good, role: 'Boss' }]) {
      const [status] = reply('/api/v1/work/4700/reviews', 'post', { rawBytes: Buffer.from(JSON.stringify(bad)) });
      expect(status, JSON.stringify(bad)).toBe(400);
    }
    const adjust = ajv.compile({ $ref: `spec#/paths/${'/api/v1/work/{work_id}/bid-pricing'.replaceAll('/', '~1')}/post/requestBody/content/application~1json/schema` });
    expect(adjust({ ...base, target: 'engineering', amount: '-1000.50', reason: 'x' })).toBe(true);
    expect(adjust({ ...base, action: 'approve', proposal_id: 8, reason: 'x' })).toBe(true);
    for (const bad of [{ ...base, target: 'engineering', amount: 'ten', reason: 'x' }, { ...base, action: 'approve', reason: 'x' }]) {
      const [status] = reply('/api/v1/work/4700/bid-pricing', 'post', { rawBytes: Buffer.from(JSON.stringify(bad)) });
      expect(status, JSON.stringify(bad)).toBe(400);
    }
  });
});

describe('costing reads (SCR-27)', () => {
  it('shows the inputs, each known figure as given, the rule with its label, the approvals in order, and the backend note', async () => {
    await open(4700);
    expect(screen.getByText('Delivery plan')).toBeTruthy();
    expect(screen.getByText('Not recorded')).toBeTruthy();
    expect(screen.getByText('25000000.00 NGN')).toBeTruthy();
    expect(screen.getByText('Project management')).toBeTruthy();
    expect(screen.getByText('Template rule (placeholder)')).toBeTruthy();
    expect(screen.getByText(/The engineering lead is a placeholder/)).toBeTruthy();
    const order = screen.getAllByText(/^(Project manager|Head of project management|Chief executive)$/).map((n) => n.textContent);
    expect(order.slice(0, 3)).toEqual(['Project manager', 'Head of project management', 'Chief executive']);
    expect(screen.getByText('Up to 2000000.00 NGN')).toBeTruthy();
    expect(posts()).toHaveLength(0);
  });

  it('an unknown figure reads Unknown, never 0', async () => {
    await open(4705);
    expect(screen.getAllByText('Unknown')).toHaveLength(2);
    expect(screen.queryByText(/^0(\.0+)? NGN/)).toBeNull();
  });

  it('a held costing says why and offers nothing to press; no rule reads when the rule read is refused', async () => {
    await open(4703);
    expect(screen.getByText('The engineering estimate is missing.')).toBeTruthy();
    expect(screen.getByText('The security estimate is missing.')).toBeTruthy();
    expect(screen.getByText('No calculated amounts are available yet.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Approve|Return|Refuse|Propose/ })).toBeNull();
    cleanup();
    await open(4701);
    expect(screen.queryByText('Costing rule used')).toBeNull();
    expect(screen.getByText('Chief executive')).toBeTruthy();
  });

  it('a settled costing has no approval controls', async () => {
    await open(4702);
    expect(screen.queryByRole('button', { name: /^Approve$|Return with a note|Refuse/ })).toBeNull();
  });
});

describe('costing writes (SCR-27)', () => {
  it('approves the step waiting now with the contract’s body, and tells the result from the re-read', async () => {
    await open(4701);
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(async () => expect(await sent()).toHaveLength(1));
    expect((await sent())[0]).toEqual({
      path: '/api/v1/work/4701/reviews',
      body: { expected_revision: 9, case_revision: 89, kind: 'bid', subject: 'commercial', target_id: 5, role: 'CEO', verdict: 'approve', evidence_id: null, note: '' },
    });
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull());
    expect(screen.getAllByText('Approved')).toHaveLength(3);
  });

  it('return and refuse need a note first and send nothing without it', async () => {
    await open(4700);
    fireEvent.click(screen.getByRole('button', { name: 'Return with a note' }));
    expect(screen.getByText('Write a note first.')).toBeTruthy();
    expect(await sent()).toEqual([]);
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: 'Check the engineering figure.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Return with a note' }));
    await waitFor(async () => expect(await sent()).toHaveLength(1));
    expect((await sent())[0]!.body).toMatchObject({ role: 'PM', verdict: 'return', note: 'Check the engineering figure.' });
    await waitFor(() => expect(screen.getByText('Returned')).toBeTruthy());
  });

  it('proposes a price change with the contract’s body and shows it waiting', async () => {
    await open(4700);
    fireEvent.click(screen.getByRole('button', { name: 'Propose the change' }));
    expect(screen.getByText('Choose what to adjust.')).toBeTruthy();
    expect(await sent()).toEqual([]);
    choose('What to adjust', 'Engineering');
    fireEvent.change(screen.getByLabelText(/^Amount/), { target: { value: '-500000' } });
    fireEvent.change(screen.getByLabelText(/^Reason/), { target: { value: 'The plan shortened.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Propose the change' }));
    await waitFor(async () => expect(await sent()).toHaveLength(1));
    expect(await sent()).toEqual([{ path: '/api/v1/work/4700/bid-pricing', body: { expected_revision: 9, case_revision: 89, target: 'engineering', amount: '-500000', reason: 'The plan shortened.' } }]);
    await waitFor(() => expect(screen.getByText('Price change waiting for a decision')).toBeTruthy());
  });

  it('decides a waiting price change with the contract’s body', async () => {
    await open(4704);
    fireEvent.click(screen.getByRole('button', { name: 'Approve the change' }));
    expect(await sent()).toEqual([]);
    fireEvent.change(screen.getByLabelText(/^Reason/), { target: { value: 'Agreed.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Approve the change' }));
    await waitFor(async () => expect(await sent()).toHaveLength(1));
    expect((await sent())[0]).toEqual({ path: '/api/v1/work/4704/bid-pricing', body: { expected_revision: 9, case_revision: 89, action: 'approve', proposal_id: 8, reason: 'Agreed.' } });
    await waitFor(() => expect(screen.getByText('Last price change decision')).toBeTruthy());
  });

  it('a stale write shows a lasting notice and the latest version', async () => {
    await open(4701);
    scenario = '409';
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(screen.getByText(/changed|Someone changed/)).toBeTruthy());
  });
});
