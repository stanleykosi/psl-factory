// The Setup mock (frontend/mock/setup.mjs, evidence.mjs): scenarios, the save checks in order, overrides and reset,
// and the evidence case counter with a real sha256.
import { createHash } from 'node:crypto';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';

import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

type Row = { component: string; set: boolean; revision: number; can_change?: boolean; display_value?: string; holds_work?: boolean; effective_from?: string; editor?: { selected?: string[] } };
type Page = { items: Row[]; not_set_count?: number; roles_missing_count?: number; next_cursor?: string };

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  await fetch(`${base}/__mock/reset`, { method: 'POST' });
});

const cookie = (persona = 'admin', extra = '') => `psl_mock_persona=${persona}${extra ? `; ${extra}` : ''}`;
async function rules(query = '', persona = 'admin', extra = '') {
  const res = await fetch(`${base}/api/v1/setup/rules${query}`, { headers: { Cookie: cookie(persona, extra) } });
  return { status: res.status, body: (await res.json()) as Page };
}
async function put(component: string, body: unknown, opts: { persona?: string; extra?: string; csrf?: string | null } = {}) {
  const persona = opts.persona ?? 'admin';
  const headers: Record<string, string> = { Cookie: cookie(persona, opts.extra), 'Content-Type': 'application/json' };
  if (opts.csrf !== null) headers['X-CSRFToken'] = opts.csrf ?? `mock-csrf-${persona}`;
  const res = await fetch(`${base}/api/v1/setup/rules/${encodeURIComponent(component)}`, { method: 'PUT', headers, body: JSON.stringify(body) });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}
async function upload(caseId: string, body: unknown, persona = 'admin') {
  const res = await fetch(`${base}/api/v1/cases/${caseId}/evidence`, {
    method: 'POST',
    headers: { Cookie: cookie(persona), 'Content-Type': 'application/json', 'X-CSRFToken': `mock-csrf-${persona}` },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}
const row = (page: Page, component: string) => page.items.find((r) => r.component === component)!;
const RFP = 'presale.rfp_assigner';

describe('E-SETUP-RULES scenarios', () => {
  it('serves the board fixtures per area, and the same data for finance_lead and admin', async () => {
    expect((await rules()).body.items).toHaveLength(10);
    expect((await rules('?area=finance')).body.items).toHaveLength(25);
    expect((await rules('?area=delivery')).body.items).toHaveLength(5);
    expect((await rules('', 'admin', 'psl_mock_setup=mobile')).body.items).toHaveLength(6);
    expect((await rules('?area=other')).body).toEqual({ items: [], as_of: expect.any(String) });
    expect((await rules('', 'finance_lead')).body).toEqual((await rules('', 'admin')).body);
  });

  it('pm and none get 403, and the forbidden scenario 403s everyone', async () => {
    for (const persona of ['pm', 'none']) expect((await rules('', persona)).status).toBe(403);
    expect((await rules('', 'admin', 'psl_mock_setup=forbidden')).status).toBe(403);
  });

  it('readonly turns every can_change off; empty has no rows and a zero count', async () => {
    const readonly = (await rules('', 'admin', 'psl_mock_setup=readonly')).body;
    expect(readonly.items).toHaveLength(10);
    expect(readonly.items.every((r) => r.can_change === false)).toBe(true);
    expect((await rules('', 'admin', 'psl_mock_setup=empty')).body).toEqual({ items: [], as_of: expect.any(String), not_set_count: 0 });
  });

  it('many pages 55 rows by 50 with an o:50 cursor', async () => {
    const first = (await rules('', 'admin', 'psl_mock_setup=many')).body;
    expect(first.items).toHaveLength(50);
    expect(first.next_cursor).toBe('o:50');
    const second = (await rules('?cursor=o%3A50', 'admin', 'psl_mock_setup=many')).body;
    expect(second.items).toHaveLength(5);
    expect(second.next_cursor).toBeUndefined();
  });
});

describe('E-SETUP-RULE-SAVE', () => {
  it('a first save at revision 0 creates version 1 and lowers not_set_count (A-SETUP-RULES-VIEW)', async () => {
    const saved = await put(RFP, { expected_revision: 0, value: { roles: ['pmo_lead', 'ceo'] }, starts: '2026-11-14', reason: 'Agreed' });
    expect(saved).toEqual({ status: 200, body: { component: RFP, revision: 1 } });
    const page = (await rules()).body;
    expect(page.not_set_count).toBe(7);
    expect(page.roles_missing_count).toBe(2);
    expect(row(page, RFP)).toMatchObject({ set: true, revision: 1, display_value: 'PMO Lead, CEO', holds_work: false, effective_from: '2026-11-14T00:00:00+01:00', editor: { selected: ['pmo_lead', 'ceo'] } });
    // Other personas and scenarios keep their own data.
    expect(row((await rules('', 'finance_lead')).body, RFP).set).toBe(false);
  });

  it('a mismatched revision answers 409 and changes nothing', async () => {
    const stale = await put('documents.client_reviewer', { expected_revision: 1, value: { roles: ['ceo'] } });
    expect(stale.status).toBe(409);
    expect(row((await rules()).body, 'documents.client_reviewer')).toMatchObject({ revision: 2, display_value: 'PMO Lead' });
  });

  it('checks the body, then the component, then the right, then the revision, then the roles', async () => {
    expect(await put(RFP, { expected_revision: -1, value: { roles: [] } })).toMatchObject({ status: 422 });
    expect(await put(RFP, { expected_revision: '0', value: { roles: [] } })).toMatchObject({ status: 422, body: { message: 'Check these fields: expected_revision.' } });
    expect(await put(RFP, { expected_revision: 0, value: { roles: [] }, extra: 1 })).toMatchObject({ status: 422 });
    expect(await put('no.such.rule', { expected_revision: 0, value: { roles: [] } })).toMatchObject({ status: 404 });
    expect(await put('finance.short_payments', { expected_revision: 0, value: { roles: [] } })).toMatchObject({ status: 403 });
    expect(await put('presale.costing_rule', { expected_revision: 4, value: { roles: [] } })).toMatchObject({ status: 403 });
    expect(await put(RFP, { expected_revision: 3, value: { roles: ['nobody'] } })).toMatchObject({ status: 409 });
    expect(await put(RFP, { expected_revision: 0, value: { roles: ['pmo_lead', 'nobody'] } })).toEqual({
      status: 422,
      body: { code: 'invalid', message: 'Check these fields: value.roles.' },
    });
    expect(row((await rules()).body, RFP).set).toBe(false);
  });

  it('readonly, pm and none answer 403 on any component', async () => {
    expect((await put(RFP, { expected_revision: 0, value: { roles: [] } }, { extra: 'psl_mock_setup=readonly' })).status).toBe(403);
    for (const persona of ['pm', 'none']) expect((await put(RFP, { expected_revision: 0, value: { roles: [] } }, { persona })).status).toBe(403);
  });

  it('needs the persona’s own CSRF token', async () => {
    expect(await put(RFP, { expected_revision: 0, value: { roles: [] } }, { csrf: null })).toMatchObject({ status: 403, body: { code: 'csrf_failed' } });
    expect(await put(RFP, { expected_revision: 0, value: { roles: [] } }, { csrf: 'mock-csrf-finance_lead' })).toMatchObject({ status: 403, body: { code: 'csrf_failed' } });
  });

  it('save cookie stale stores another person’s version then answers 409; invalid names reason and starts', async () => {
    const stale = await put(RFP, { expected_revision: 0, value: { roles: ['ceo'] } }, { extra: 'psl_mock_setup_save=stale' });
    expect(stale.status).toBe(409);
    expect(row((await rules()).body, RFP)).toMatchObject({ set: true, revision: 1, display_value: 'PMO Lead' });
    const invalid = await put(RFP, { expected_revision: 1, value: { roles: ['ceo'] } }, { extra: 'psl_mock_setup_save=invalid' });
    expect(invalid).toEqual({ status: 422, body: { code: 'invalid', message: 'Check these fields: reason, starts.' } });
  });

  it('/__mock/reset clears saves', async () => {
    await put(RFP, { expected_revision: 0, value: { roles: ['pmo'] } });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect(row((await rules()).body, RFP).set).toBe(false);
  });
});

describe('E-EVIDENCE-UPLOAD', () => {
  const content = Buffer.from('leadership minutes, 12 Nov');
  const body = (caseRevision: number) => ({ kind: 'rule_proof', filename: 'minutes.pdf', content_base64: content.toString('base64'), case_revision: caseRevision });

  it('answers the real sha256, moves the case revision on and serves it in the rules', async () => {
    const first = await upload('C-SETUP-1', body(1));
    expect(first.status).toBe(200);
    expect(first.body.sha256).toBe(createHash('sha256').update(content).digest('hex'));
    expect(first.body.case_revision).toBe(2);
    expect(String(first.body.evidence_id)).toMatch(/^EV-\d+$/);
    expect((await upload('C-SETUP-1', body(1))).status).toBe(409);
    expect((await upload('C-SETUP-1', body(2))).body.case_revision).toBe(3);
    expect((row((await rules()).body, RFP) as Row & { proof_case: { case_revision: number } }).proof_case.case_revision).toBe(3);
  });

  it('/__mock/reset restarts evidence ids at EV-1 (QA-1-2)', async () => {
    expect((await upload('C-SETUP-1', body(1))).body.evidence_id).toBe('EV-1');
    expect((await upload('C-SETUP-1', body(2))).body.evidence_id).toBe('EV-2');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await upload('C-SETUP-1', body(1))).body.evidence_id).toBe('EV-1');
  });

  it('unknown cases are 404, bad bodies 422, pm and none 403', async () => {
    expect((await upload('C-NOPE', body(1))).status).toBe(404);
    expect((await upload('C-SETUP-1', { kind: 'rule_proof' })).status).toBe(422);
    for (const persona of ['pm', 'none']) expect((await upload('C-SETUP-1', body(1), persona)).status).toBe(403);
  });
});
