// F-40: the handover items W-3701 to W-3711 and W-3720 in the contract mock (SCR-48, contract mock only). Each validates against
// the generated schema once the proposed `work` link kind is removed; the recorded bodies validate against the v7 E-RESPONSE body
// once the proposed `gaps` is removed; and the writes behave as the page needs: one send per key, gaps checked on their own,
// the state per action, the refusal on a task this person cannot act on. Nothing is sent to Support.
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

type Schema = Record<string, unknown>;
type Op = { operationId: string; responses: Record<string, { content: { 'application/json': { schema: Schema } } }>; requestBody?: { content: { 'application/json': { schema: Schema } } } };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Op>> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const workSchema = ajv.compile(openapi.paths['/api/v1/work/{work_id}'].get.responses['200'].content['application/json'].schema);
const responseBody = ajv.compile(openapi.paths['/api/v1/tasks/{task_id}/response'].post.requestBody!.content['application/json'].schema);

const work = join(__dirname, '../mock/fixtures/work');
const sidecars = join(__dirname, '../mock/fixtures/response');
const readJson = (dir: string, name: string) => JSON.parse(readFileSync(join(dir, name), 'utf8'));
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Body = Record<string, any>;

/** The `work` link kind is a proposal (F-32): checked on its own, removed before the schema check. */
function withoutLinks(body: Body): Body {
  const copy = structuredClone(body);
  for (const link of copy.workspace?.links ?? []) if (link.target.kind === 'work') expect(link.target.work_id).toMatch(/^W-\d+$/);
  delete copy.workspace?.links;
  return copy;
}

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

async function send(method: string, path: string, persona = 'pm', body?: unknown, extra: Record<string, string> = {}) {
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}`, ...extra };
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    headers['X-CSRFToken'] = `mock-csrf-${persona}`;
  }
  const response = await fetch(`${base}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: response.status, body: (await response.json().catch(() => ({}))) as Body };
}
const upload = async () => (await send('POST', '/api/v1/cases/P-0101/evidence', 'pm', { kind: 'proof', filename: 'support-reply-10apr.pdf', content_base64: 'JVBERi0xLjQK', case_revision: 2 })).body;
const reply = (task: string, evidence: string, extra: Body = {}) =>
  send('POST', `/api/v1/tasks/${task}/response`, 'pm', {
    expected_revision: 1,
    who: 'R-3701',
    action: 'changes_requested',
    responded_at: '2026-04-10T11:00:00+01:00',
    evidence_id: evidence,
    attested: true,
    case_revision: 3,
    version_id: 'V-3701',
    gaps: ['No contact for the credit bureau outage', 'Runbook misses the nightly export restart'],
    ...extra,
  });
const step = (id: string, key: string, revision: number, idempotency = `key-${id}-${key}`) =>
  send('POST', `/api/v1/work/${id}/steps`, 'pm', { expected_revision: revision, step: key, idempotency_key: idempotency });

const names = readdirSync(work).filter((n) => /^W-37(0\d|1[01]|20)(\.[a-z]+)?\.json$/.test(n) && !n.includes('.steps'));
const sidecarNames = readdirSync(sidecars).filter((n) => /^W-37\d\d\./.test(n));

describe('handover fixtures', () => {
  it('has W-3701 to W-3711, W-3720 and their sidecars', () => {
    expect(names.filter((n) => /^W-37\d\d\.json$/.test(n))).toHaveLength(12);
    expect(names.filter((n) => n.includes('.next')).sort()).toEqual(['W-3701.next.json', 'W-3704.next.json', 'W-3706.next.json', 'W-3707.next.json', 'W-3708.next.json']);
    expect(sidecarNames.filter((n) => n.startsWith('W-3706.') && !n.includes('recorded')).sort()).toEqual(['W-3706.delivered.json', 'W-3706.not_delivered.json', 'W-3706.unknown.json']);
    expect(sidecarNames.filter((n) => n.startsWith('W-3703.recorded.')).sort()).toEqual(['W-3703.recorded.approved.json', 'W-3703.recorded.changes_requested.json']);
  });

  for (const name of [...names.map((n) => [work, n] as const), ...sidecarNames.map((n) => [sidecars, n] as const)]) {
    it(`${name[1]} validates against the E-WORK-ITEM schema and is sample data`, () => {
      const body = readJson(name[0], name[1]);
      expect(body.sample).toBe(true);
      expect(workSchema(withoutLinks(body)), ajv.errorsText(workSchema.errors)).toBe(true);
      if (name[1].startsWith('W-3720')) return expect(body.workspace).toBeUndefined();
      expect(body.workspace).toMatchObject({ line_key: 'delivery_handover', screen: 'SCR-48', context: { project: { case_id: 'P-0101', title: 'Lagoon Health · patient app' } } });
      expect([body.reference, body.case_id, body.case_revision]).toEqual(['HND-0048', 'P-0101', expect.any(Number)]);
      expect(body.revision).toBe(body.workspace.revision);
    });
  }

  it('the work link is only on W-3705 and names W-3720; a task’s only variant is support_handover', () => {
    const links = names.flatMap((n) => (readJson(work, n).workspace?.links ?? []).map((l: Body) => [n, l.target]));
    expect(links.filter(([, t]) => t.kind === 'work')).toEqual([['W-3705.json', { kind: 'work', work_id: 'W-3720' }]]);
    const tasks = names.flatMap((n) => readJson(work, n).tasks ?? []);
    expect(tasks.length).toBeGreaterThan(0);
    expect(new Set(tasks.map((t: Body) => t.response.variant))).toEqual(new Set(['support_handover']));
  });

  it('the hold has no steps and no links; W-3709 cannot record; T-3703 and T-3709 are the board task ids', () => {
    const hold = readJson(work, 'W-3702.json');
    expect([hold.workspace.steps, hold.workspace.links]).toEqual([undefined, undefined]);
    expect(readJson(work, 'W-3702.json').workspace.sections[0].items[1]).toMatchObject({ text: 'Review needed?', status: 'unknown' });
    expect(readJson(work, 'W-3709.json').tasks[0]).toMatchObject({ id: 'T-3709', you_can_act: false, cannot_act_reason: 'not_your_role', required_role: 'PM' });
    expect(readJson(work, 'W-3703.json').tasks[0].id).toBe('T-3703');
  });

  it('serves W-3703 to personas pm and finance_lead the same', async () => {
    const pm = await send('GET', '/api/v1/work/W-3703', 'pm');
    expect(pm.body).toEqual((await send('GET', '/api/v1/work/W-3703', 'finance_lead')).body);
  });

});

describe('P-0101 Handover row', () => {
  it('carries work_id W-3704', async () => {
    const { body } = await send('GET', '/api/v1/projects/P-0101');
    expect(body.delivery.find((r: Body) => r.line_key === 'delivery_handover').work_id).toBe('W-3704');
  });
});

describe('Publish', () => {
  it('sends once per key: a repeat gets the stored reply with no second send', async () => {
    const first = await step('W-3701', 'publish', 1, 'k-pub');
    expect([first.status, first.body.outcome]).toEqual([200, 'done']);
    expect((await send('GET', '/api/v1/work/W-3701')).body.workspace.status.label).toBe('Handover · published 08 Apr');
    expect((await step('W-3701', 'publish', 1, 'k-pub')).body).toEqual(first.body);
    expect((await send('GET', '/__mock/workspace-log')).body.sends['k-pub']).toBe(1);
  });

  it('W-3706: effect_uncertain, and the re-read offers reconcile only', async () => {
    expect((await step('W-3706', 'publish', 1)).body.outcome).toBe('effect_uncertain');
    const after = (await send('GET', '/api/v1/work/W-3706')).body;
    expect([after.state, after.allowed_actions]).toEqual(['effect_uncertain', ['reconcile']]);
  });

  it('W-3707: 502, but written; W-3708: 409 and the item moves on; W-3702 offers no step (404)', async () => {
    expect((await step('W-3707', 'publish', 1)).status).toBe(502);
    expect((await send('GET', '/api/v1/work/W-3707')).body.state).toBe('effect_uncertain');
    expect((await step('W-3708', 'publish', 1)).status).toBe(409);
    expect((await send('GET', '/api/v1/work/W-3708')).body.workspace.status.label).toBe('Handover · published 08 Apr');
    expect((await step('W-3702', 'publish', 1)).status).toBe(404);
  });

  it('W-3706 reconcile: delivered serves the record state, not_delivered offers Publish again, unknown stays unconfirmed', async () => {
    const outcomes: [string, string][] = [
      ['delivered', 'Handover · published 08 Apr'],
      ['not_delivered', 'Handover · not delivered'],
      ['unknown', 'Handover · delivery unconfirmed'],
    ];
    for (const [outcome, label] of outcomes) {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      await step('W-3706', 'publish', 1);
      const proof = await upload();
      const done = await send('POST', '/api/v1/work/W-3706/actions', 'pm', { expected_revision: 2, action: 'reconcile', outcome, evidence_id: proof.evidence_id, case_revision: proof.case_revision });
      expect(done.status).toBe(200);
      const after = (await send('GET', '/api/v1/work/W-3706')).body;
      expect(after.workspace.status.label).toBe(label);
      expect(after.workspace.steps?.map((s: Body) => s.key)).toEqual(outcome === 'not_delivered' ? ['publish'] : outcome === 'delivered' ? ['record_reply'] : undefined);
    }
  });

  it('W-3704: draft_v2 queues and the re-read is Drafting v2 with no step', async () => {
    expect((await step('W-3704', 'draft_v2', 1)).body).toMatchObject({ outcome: 'queued', message: 'Tola is drafting v2.' });
    const after = (await send('GET', '/api/v1/work/W-3704')).body;
    expect([after.workspace.status.label, after.workspace.steps]).toEqual(['Drafting v2', undefined]);
  });
});

describe('Record the reply (G-48-1, G-F40-1)', () => {
  it('the recorded body validates against the v7 E-RESPONSE body once gaps is removed; the 200 serves the state for the action', async () => {
    const proof = await upload();
    const { gaps, ...rest } = { gaps: ['a'], expected_revision: 1, who: 'R-3701', action: 'changes_requested', responded_at: '2026-04-10T11:00:00+01:00', evidence_id: proof.evidence_id, attested: true, case_revision: 3, version_id: 'V-3701' };
    expect(gaps).toHaveLength(1);
    expect(responseBody(rest), ajv.errorsText(responseBody.errors)).toBe(true);
    expect((await reply('T-3703', proof.evidence_id)).status).toBe(200);
    expect((await send('GET', '/api/v1/work/W-3703')).body.workspace.status.label).toBe('Gaps · 2');
  });

  it('approved without gaps serves the acknowledged state', async () => {
    const proof = await upload();
    const ok = await send('POST', '/api/v1/tasks/T-3703/response', 'pm', {
      expected_revision: 1,
      who: 'R-3701',
      action: 'approved',
      responded_at: '2026-04-10T11:00:00+01:00',
      evidence_id: proof.evidence_id,
      attested: true,
      case_revision: 3,
      version_id: 'V-3701',
    });
    expect(ok.status).toBe(200);
    expect((await send('GET', '/api/v1/work/W-3703')).body.workspace.status.label).toBe('Handover acknowledged');
  });

  it('changes_requested without gaps, with blank gaps or with an empty list is 422 gaps', async () => {
    const proof = await upload();
    const without = await send('POST', '/api/v1/tasks/T-3703/response', 'pm', {
      expected_revision: 1, who: 'R-3701', action: 'changes_requested', responded_at: '2026-04-10T11:00:00+01:00', evidence_id: proof.evidence_id, attested: true, case_revision: 3, version_id: 'V-3701',
    });
    expect([without.status, without.body.message]).toEqual([422, 'Check these fields: gaps.']);
    for (const gaps of [[], [' '], ['ok', ''], 'text', [1]]) expect((await reply('T-3703', proof.evidence_id, { gaps })).body.message).toBe('Check these fields: gaps.');
  });

  it('approved with gaps is 422 gaps', async () => {
    const proof = await upload();
    const refused = await reply('T-3703', proof.evidence_id, { action: 'approved' });
    expect([refused.status, refused.body.message]).toEqual([422, 'Check these fields: gaps.']);
  });

  it('still refuses the rest of the body under the v7 schema (an extra key is 422)', async () => {
    const proof = await upload();
    const refused = await reply('T-3703', proof.evidence_id, { colour: 'red' });
    expect(refused.status).toBe(422);
  });

  it('a record on T-3709 answers 403 and changes nothing', async () => {
    const proof = await upload();
    const refused = await reply('T-3709', proof.evidence_id);
    expect(refused.status).toBe(403);
    expect((await send('GET', '/api/v1/work/W-3709')).body.workspace.status.label).toBe('Handover · published 08 Apr');
  });

  it('a stale revision is 409 and record-then-fail writes, then answers 502', async () => {
    const proof = await upload();
    expect((await reply('T-3703', proof.evidence_id, { expected_revision: 9 })).status).toBe(409);
    const bodyOf = (extra: Body) => ({ expected_revision: 1, who: 'R-3701', action: 'changes_requested', responded_at: '2026-04-10T11:00:00+01:00', evidence_id: proof.evidence_id, attested: true, case_revision: 3, version_id: 'V-3701', gaps: ['a'], ...extra });
    const failed = await send('POST', '/api/v1/tasks/T-3703/response', 'pm', bodyOf({}), { 'X-Mock-Scenario': 'record-then-fail' });
    expect(failed.status).toBe(502);
    expect((await send('GET', '/api/v1/work/W-3703')).body.workspace.status.label).toBe('Gaps · 2');
  });

  it('a task that is not a support handover still takes no gaps (team input is unchanged)', async () => {
    const refused = await send('POST', '/api/v1/tasks/T-2603/response', 'pm', {
      expected_revision: 4, who: 'R-QA', action: 'estimate', responded_at: '2026-04-10T11:00:00+01:00', evidence_id: 'EV-x', attested: true, gaps: ['a'],
    });
    expect(refused.status).toBe(422);
    expect(refused.body.message).toContain('gaps');
  });
});

describe('round 2: who can open a handover item (UX-1-3)', () => {
  it('a persona not on P-0101’s list gets 404 on the item and its history; the PM still reads it', async () => {
    for (const id of ['W-3701', 'W-3704', 'W-3705']) {
      expect((await send('GET', `/api/v1/work/${id}`, 'ceo')).status).toBe(404);
      expect((await send('GET', `/api/v1/work/${id}`, 'none')).status).toBe(404);
      expect((await send('GET', `/api/v1/work/${id}`, 'pm')).status).toBe(200);
    }
  });
});
