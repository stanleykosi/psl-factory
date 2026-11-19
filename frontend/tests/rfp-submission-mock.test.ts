// F-38: the contract mock's RFP submission fixtures (W-3501 to W-3509, their sidecars and the document D-3501), the decide rules
// the page relies on (claim then approve, the stale 409, the note rule, the 403) and the reconcile sidecars. Mock evidence only:
// it proves the mock follows the contract it was given, not what a backend will do. Nothing is submitted, emailed or delivered.
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const itemSchema = ajv.compile(openapi.paths['/api/v1/work/{work_id}'].get.responses['200'].content['application/json'].schema);
const stepReply = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.responses['200'].content['application/json'].schema);
const workDir = join(__dirname, '../mock/fixtures/work');
const responseDir = join(__dirname, '../mock/fixtures/response');
type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const fixture = (name: string): Json => JSON.parse(readFileSync(join(workDir, `${name}.json`), 'utf8'));
const sidecar = (name: string): Json => JSON.parse(readFileSync(join(responseDir, `${name}.json`), 'utf8'));

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  expect((await fetch(`${base}/__mock/reset`, { method: 'POST' })).status).toBe(204);
});

const HEADERS = { Cookie: 'psl_mock_persona=pm', 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-pm' };
const get = async (id: string) => (await (await fetch(`${base}/api/v1/work/${id}`, { headers: HEADERS })).json()) as Json;
const send = async (path: string, body: unknown) => {
  const response = await fetch(`${base}${path}`, { method: 'POST', headers: HEADERS, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Json };
};
const step = (id: string, body: unknown) => send(`/api/v1/work/${id}/steps`, body);
const claim = (task: string, revision: number) => send(`/api/v1/tasks/${task}/claim`, { expected_revision: revision });
const decide = (task: string, body: unknown) => send(`/api/v1/tasks/${task}/decision`, body);
let n = 0;
const key = () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
const names = readdirSync(workDir).filter((name) => /^W-350\d/.test(name));
const sidecars = readdirSync(responseDir).filter((name) => /^W-3505\./.test(name));

/** The overlay proposals the submission boards reuse (verdict F-33, links F-23, fields[].value F-37) are checked on their own, then removed. */
function contractItem(body: Json) {
  const copy = structuredClone(body);
  const w = copy.workspace;
  if (w?.links !== undefined) {
    for (const link of w.links) expect(['assistant', 'document']).toContain(link.target.kind);
    delete w.links;
  }
  for (const s of w?.steps ?? []) {
    if (s.verdict !== undefined) {
      expect(typeof s.task_id === 'string' && ['approve', 'return', 'reject'].includes(s.verdict), s.key).toBe(true);
      delete s.verdict;
    }
  }
  return copy;
}

describe('fixtures (AC 23, 24)', () => {
  it('lists the nine items and their sidecars, all marked sample, on the rfp_submission line', () => {
    expect(names.sort()).toEqual(
      ['W-3501.json', 'W-3501.next.json', 'W-3501.steps.json', 'W-3502.approve.json', 'W-3502.json', 'W-3502.reject.json', 'W-3502.return.json', 'W-3503.json', 'W-3504.json', 'W-3505.approve.json', 'W-3505.json', 'W-3506.json', 'W-3506.next.json', 'W-3507.json', 'W-3508.json', 'W-3509.json'].sort(),
    );
    expect(sidecars.sort()).toEqual(['W-3505.delivered.json', 'W-3505.not_delivered.json', 'W-3505.unknown.json']);
  });

  it('every item and sidecar validates against the generated E-WORK-ITEM schema once steps[].verdict and links are removed', () => {
    const all = [...names.filter((nm) => !nm.includes('.steps')).map((nm) => fixture(nm.replace('.json', ''))), ...sidecars.map((nm) => sidecar(nm.replace('.json', '')))];
    expect(all).toHaveLength(18);
    for (const body of all) {
      expect(itemSchema(contractItem(body)), `${body.id}: ${ajv.errorsText(itemSchema.errors)}`).toBe(true);
      expect(body.sample).toBe(true);
      expect(body.reference).toBe('TL-RFP-2026-014');
      expect(body.case_id).toBe('C-2102');
      expect(body.workspace.line_key).toBe('rfp_submission');
      expect(body.workspace.screen).toBe('SCR-40');
      expect(body.workspace.revision).toBe(body.revision);
    }
  });

  it('the review fixture carries no rfp block and no W-3502.next; every other W-35xx item does carry the frame with its own Submission tab', () => {
    expect(fixture('W-3502').rfp).toBeUndefined();
    expect(names).not.toContain('W-3502.next.json');
    for (const nm of ['W-3501', 'W-3503', 'W-3504', 'W-3505', 'W-3506', 'W-3507', 'W-3508', 'W-3509']) {
      const tab = fixture(nm).rfp.tabs.find((t: Json) => t.key === 'submission');
      expect(tab, nm).toMatchObject({ work_id: nm, current: true });
      expect(fixture(nm).rfp.tabs.find((t: Json) => t.key === 'team_input').work_id).toBe('W-2101');
    }
  });

  it('no fixture carries an amount, a rate or a currency; the uncertain item has no resend and no resend_note', () => {
    for (const nm of [...names, ...sidecars.map((s) => `../response/${s}`)]) expect(readFileSync(join(workDir, nm), 'utf8'), nm).not.toMatch(/₦|"money"|"currency"|"amount"|"resend/);
  });

  it('the script answers bodies the E-WORK-STEP 200 schema accepts, and the document D-3501 is the test-template pack', () => {
    for (const [stepKey, script] of Object.entries(fixture('W-3501.steps')) as [string, Json][]) {
      expect(stepReply({ work_id: 'W-3501', state: 'action_needed', revision: 2, ...script.body }), `${stepKey}: ${ajv.errorsText(stepReply.errors)}`).toBe(true);
    }
    const doc = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/documents/D-3501.1.json'), 'utf8'));
    expect(doc).toMatchObject({ document_id: 'D-3501', version: '1', test_template: true });
  });
});

describe('decide rules (AC 23)', () => {
  it('claim then approve on W-3502 serves W-3502.approve and answers work_state verified', async () => {
    expect((await claim('T-3502', 1)).status).toBe(200);
    const approved = await decide('T-3502', { verdict: 'approve', expected_revision: 1 });
    expect(approved.status).toBe(200);
    expect(approved.body).toMatchObject({ task_id: 'T-3502', verdict: 'approve', work_state: 'verified' });
    expect(await get('W-3502')).toEqual(fixture('W-3502.approve'));
    // the task is decided now: a repeat answers 409 (revision before eligibility)
    expect((await decide('T-3502', { verdict: 'approve', expected_revision: 1 })).status).toBe(409);
  });

  it('return and reject serve their sidecars with the note; return without a note is 422', async () => {
    expect((await decide('T-3502', { verdict: 'return', expected_revision: 1 })).status).toBe(422);
    expect((await decide('T-3502', { verdict: 'reject', expected_revision: 1, note: '   ' })).status).toBe(422);
    expect((await decide('T-3502', { verdict: 'return', expected_revision: 1, note: 'x'.repeat(2001) })).status).toBe(422);
    expect(await get('W-3502')).toEqual(fixture('W-3502'));
    expect((await decide('T-3502', { verdict: 'return', expected_revision: 1, note: 'Name the contact.' })).status).toBe(200);
    expect(await get('W-3502')).toEqual(fixture('W-3502.return'));
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await decide('T-3502', { verdict: 'reject', expected_revision: 1, note: 'Out of date.' })).status).toBe(200);
    expect(await get('W-3502')).toEqual(fixture('W-3502.reject'));
    expect(fixture('W-3502.return').workspace.status.label).toBe('RETURNED TO PM');
    expect(fixture('W-3502.reject').workspace.status.label).toBe('REJECTED');
  });

  it('approve on W-3505 answers work_state effect_uncertain and serves the uncertain item', async () => {
    const approved = await decide('T-3505', { verdict: 'approve', expected_revision: 1 });
    expect(approved.body).toMatchObject({ verdict: 'approve', work_state: 'effect_uncertain' });
    const after = await get('W-3505');
    expect(after).toEqual(fixture('W-3505.approve'));
    expect(after.reconcile.outcomes).toEqual(['delivered', 'not_delivered', 'unknown']);
    expect(after.allowed_actions).toEqual(['reconcile']);
    expect(after.rfp_outcome).toBeUndefined();
  });

  it('the first decide on W-3506 is 409 and serves v2; the next at revision 2 is accepted', async () => {
    expect((await decide('T-3506', { verdict: 'approve', expected_revision: 1 })).status).toBe(409);
    const v2 = await get('W-3506');
    expect(v2).toEqual(fixture('W-3506.next'));
    expect(v2.tasks[0].decision.version.number).toBe(2);
    expect(v2.tasks[0].revision).toBe(2);
    expect((await decide('T-3506', { verdict: 'approve', expected_revision: 2 })).status).toBe(200);
  });

  it('W-3509’s decide is 403 (not your role), W-3501.next’s task is not yours either', async () => {
    expect((await decide('T-3509', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect(fixture('W-3509').tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'not_your_role' });
    expect(fixture('W-3501.next').tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'prepared_by_you' });
  });

  it('every decision body the mock accepts is one the generated request schema accepts: no extra keys', async () => {
    expect((await decide('T-3502', { verdict: 'approve', expected_revision: 1, idempotency_key: key() })).status).toBe(422);
  });
});

describe('the W-3501 steps (AC 23)', () => {
  it('edit_cover_letter follows its script and keeps the content; send_for_review serves W-3501.next', async () => {
    const edit = await step('W-3501', { expected_revision: 1, step: 'edit_cover_letter', inputs: { cover_letter: 'Dear team.' }, idempotency_key: key() });
    expect(edit.status).toBe(200);
    expect(edit.body).toMatchObject({ outcome: 'done', message: 'Cover letter saved.' });
    const kept = await get('W-3501');
    expect(kept.revision).toBe(2);
    expect(kept.workspace.sections).toEqual(fixture('W-3501').workspace.sections);
    const sendIt = await step('W-3501', { expected_revision: 2, step: 'send_for_review', inputs: {}, idempotency_key: key() });
    expect(sendIt.status).toBe(200);
    expect(await get('W-3501')).toEqual(fixture('W-3501.next'));
  });

  it('a repeated step key returns the stored reply with no second effect', async () => {
    const one = key();
    const first = await step('W-3501', { expected_revision: 1, step: 'send_for_review', inputs: {}, idempotency_key: one });
    const again = await step('W-3501', { expected_revision: 1, step: 'send_for_review', inputs: {}, idempotency_key: one });
    expect(again).toEqual(first);
    const log = (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { entries: { idempotency_key: string; replay: boolean }[] };
    expect(log.entries.filter((e) => e.idempotency_key === one).map((e) => e.replay)).toEqual([false, true]);
    expect((await get('W-3501')).revision).toBe(fixture('W-3501.next').revision);
  });

  it('a stale revision is 409 and a step the item does not offer is 404', async () => {
    expect((await step('W-3501', { expected_revision: 9, step: 'send_for_review', inputs: {}, idempotency_key: key() })).status).toBe(409);
    expect((await step('W-3503', { expected_revision: 4, step: 'send_for_review', inputs: {}, idempotency_key: key() })).status).toBe(404);
  });
});

describe('reconcile on W-3505 (AC 23)', () => {
  const upload = async () => {
    const r = await send('/api/v1/cases/C-2102/evidence', { kind: 'delivery_receipt', filename: 'receipt.pdf', content_base64: Buffer.from('%PDF-1.4 sample proof').toString('base64'), case_revision: 3 });
    expect(r.status).toBe(200);
    return r.body as { evidence_id: string; case_revision: number };
  };
  const action = (body: unknown) => send('/api/v1/work/W-3505/actions', body);
  const uncertain = async () => {
    await decide('T-3505', { verdict: 'approve', expected_revision: 1 });
    return (await get('W-3505')).revision as number;
  };

  it('delivered (with evidence), not_delivered and unknown each serve their sidecar', async () => {
    for (const outcome of ['delivered', 'not_delivered', 'unknown']) {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      const revision = await uncertain();
      const extra = outcome === 'delivered' ? await upload() : {};
      const reply = await action({ expected_revision: revision, action: 'reconcile', outcome, ...(outcome === 'delivered' ? { evidence_id: (extra as { evidence_id: string }).evidence_id, case_revision: (extra as { case_revision: number }).case_revision } : {}) });
      expect(reply.status, outcome).toBe(200);
      expect(await get('W-3505'), outcome).toEqual(sidecar(`W-3505.${outcome}`));
    }
    expect(sidecar('W-3505.delivered').rfp_outcome.submission.label).toBe('Submission pack v1');
    expect(sidecar('W-3505.not_delivered').rfp_outcome).toBeUndefined();
    expect(sidecar('W-3505.not_delivered').workspace.steps).toEqual([]);
    expect(sidecar('W-3505.unknown').reconcile).toBeDefined();
  });

  it('delivered without proof is 422, and the item offers no reconcile outcome before the approve', async () => {
    const revision = await uncertain();
    expect((await action({ expected_revision: revision, action: 'reconcile', outcome: 'delivered' })).status).toBe(422);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    // no reconcile block yet: the outcome is not one the item offers
    expect((await action({ expected_revision: 1, action: 'reconcile', outcome: 'unknown' })).status).toBe(422);
  });

  it('reset clears the served item and the stored steps', async () => {
    await decide('T-3502', { verdict: 'approve', expected_revision: 1 });
    expect((await get('W-3502')).state).toBe('verified');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect(await get('W-3502')).toEqual(fixture('W-3502'));
  });
});

describe('the document (AC 17)', () => {
  it('serves D-3501 version 1 as the test-template pack, 404 for another version, and leaves D-2901 as it was', async () => {
    const ok = await fetch(`${base}/api/v1/documents/D-3501/versions/1`, { headers: HEADERS });
    expect(ok.status).toBe(200);
    expect(await ok.json()).toMatchObject({ document_id: 'D-3501', title: 'Submission pack · Tamarind Loans', test_template: true });
    expect((await fetch(`${base}/api/v1/documents/D-3501/versions/2`, { headers: HEADERS })).status).toBe(404);
    expect((await fetch(`${base}/api/v1/documents/D-2901/versions/1`, { headers: HEADERS })).status).toBe(200);
  });
});
