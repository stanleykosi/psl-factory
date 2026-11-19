// F-34: the hypercare items W-3101 to W-3112 and W-3120 in the contract mock (SCR-46, contract mock only). Each validates against
// the generated schema once the proposed link kinds are removed, the proposed keys match mock/proposals/delivery-hypercare.json,
// and the writes behave as the page needs: a proof upload for a workspace step, one send per key, a re-read that shows the hold.
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
type Op = { operationId: string; responses: Record<string, { content: { 'application/json': { schema: Schema } } }> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Op>> };
const overlay = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/delivery-hypercare.json'), 'utf8')) as { $comment: string; setup_rules_link: Schema };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const workSchema = ajv.compile(openapi.paths['/api/v1/work/{work_id}'].get.responses['200'].content['application/json'].schema);
const projectSchema = ajv.compile(openapi.paths['/api/v1/projects/{case_id}'].get.responses['200'].content['application/json'].schema);
const setupLink = ajv.compile(overlay.setup_rules_link);

const dir = join(__dirname, '../mock/fixtures/work');
const readJson = (name: string) => JSON.parse(readFileSync(join(dir, name), 'utf8'));
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Body = Record<string, any>;

/** The `setup_rules` and `work` link kinds are proposals: checked on their own, removed before the schema check. */
function withoutLinks(body: Body): Body {
  const copy = structuredClone(body);
  for (const link of copy.workspace?.links ?? []) {
    if (link.target.kind === 'setup_rules') expect(setupLink(link), ajv.errorsText(setupLink.errors)).toBe(true);
  }
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
const step = (id: string, key: string, revision: number, idempotency = `key-${id}-${key}`, extra: Body = {}) =>
  send('POST', `/api/v1/work/${id}/steps`, 'pm', { expected_revision: revision, step: key, idempotency_key: idempotency, ...extra });
const upload = (kind: string, persona = 'pm', caseRevision = 2) =>
  send('POST', '/api/v1/cases/P-0101/evidence', persona, { kind, filename: 'release-1.0.0-log.pdf', content_base64: 'JVBERi0xLjQK', case_revision: caseRevision });
const log = async () => (await send('GET', '/__mock/workspace-log')).body;

const names = readdirSync(dir).filter((name) => /^W-31\d\d(\.[a-z]+)?\.json$/.test(name) && !name.includes('.steps'));

describe('hypercare items', () => {
  it('has W-3101 to W-3112, W-3120 and their sidecars', () => {
    expect(names.filter((n) => /^W-31\d\d\.json$/.test(n))).toHaveLength(13);
    expect(names.filter((n) => n.includes('.next')).sort()).toEqual(['W-3101.next.json', 'W-3102.next.json', 'W-3106.next.json', 'W-3108.next.json', 'W-3112.next.json']);
  });

  for (const name of names) {
    it(`${name} validates against the E-WORK-ITEM schema and is sample data`, () => {
      const body = readJson(name);
      expect(body.sample).toBe(true);
      expect(workSchema(withoutLinks(body)), ajv.errorsText(workSchema.errors)).toBe(true);
      if (name.startsWith('W-3120')) {
        expect(body.workspace).toBeUndefined();
        return;
      }
      expect(body.workspace).toMatchObject({ line_key: 'delivery_hypercare', screen: 'SCR-46', context: { project: { case_id: 'P-0101', title: 'Lagoon Health · patient app' } } });
      expect([body.reference, body.case_id]).toEqual(['HYP-0062', 'P-0101']);
      expect(body.revision).toBe(body.workspace.revision);
    });
  }

  it('the setup_rules link is only on the hold, and the work link only on W-3104 and names W-3120', () => {
    const links = names.flatMap((n) => (readJson(n).workspace?.links ?? []).map((l: Body) => [n, l.target]));
    expect(links.filter(([, t]) => t.kind === 'setup_rules').map(([n]) => n)).toEqual(['W-3102.next.json', 'W-3103.json', 'W-3106.next.json']);
    expect(links.filter(([, t]) => t.kind === 'work')).toEqual([['W-3104.json', { kind: 'work', work_id: 'W-3120' }]]);
  });

  it('the hold has no steps and no criteria; the qualified item has no steps; an unavailable step carries its reason', () => {
    for (const id of ['W-3103', 'W-3104']) expect(readJson(`${id}.json`).workspace.steps).toBeUndefined();
    expect(readJson('W-3103.json').workspace.sections.map((s: Body) => s.key)).toEqual(['note', 'observations']);
    expect(readJson('W-3109.json').workspace.steps[0].disabled_reason).toBe("Only the project's PM logs observations.");
  });

  it('serves W-3101 to every persona the same', async () => {
    const bodies = await Promise.all(['pm', 'finance_lead', 'ceo'].map((p) => send('GET', '/api/v1/work/W-3101', p)));
    expect(bodies[0].body).toEqual(bodies[1].body);
    expect(bodies[0].body).toEqual(bodies[2].body);
  });
});

describe('P-0101 Hypercare row', () => {
  it('carries work_id W-3101, and the project still validates against E-PROJECT without the proposed keys', async () => {
    const { status, body } = await send('GET', '/api/v1/projects/P-0101');
    expect(status).toBe(200);
    expect(body.delivery.find((r: Body) => r.line_key === 'delivery_hypercare').work_id).toBe('W-3101');
    const stripped = structuredClone(body);
    for (const row of stripped.delivery) for (const key of ['reference', 'at', 'detail', 'short_title']) delete row[key];
    delete stripped.delivery_agent;
    delete stripped.delivery_summary;
    expect(projectSchema(stripped), ajv.errorsText(projectSchema.errors)).toBe(true);
  });
});

describe('proof upload for a workspace step (shared fix 3)', () => {
  it('takes a deployment_log upload on the case and moves the case revision on', async () => {
    const first = await upload('deployment_log');
    expect(first.status).toBe(200);
    expect(first.body).toMatchObject({ evidence_id: expect.any(String), case_revision: 3 });
    expect((await send('GET', '/api/v1/work/W-3102')).body.case_revision).toBe(3);
  });

  it('takes a hypercare_observation upload', async () => {
    expect((await upload('hypercare_observation')).status).toBe(200);
  });

  it('refuses a kind no step names (422), a stale case revision (409) and the none persona (403)', async () => {
    expect((await upload('something_else')).status).toBe(422);
    expect((await upload('deployment_log', 'pm', 7)).status).toBe(409);
    expect((await upload('deployment_log', 'none')).status).toBe(403);
  });
});

describe('record the release (W-3102)', () => {
  const inputs = { version: 'Build 1.0.0', released_at: '2026-04-01T21:00:00.000Z', environment: 'Production · Lagoon Health' };

  it('sends once per key and the re-read is the setup-needed hold; a repeated key gets the stored reply with no second send', async () => {
    const proof = await upload('deployment_log');
    const body = { inputs, evidence_ids: [proof.body.evidence_id] };
    const first = await step('W-3102', 'record_release', 1, 'k-record', body);
    expect(first.status).toBe(200);
    expect(first.body.outcome).toBe('done');
    const after = (await send('GET', '/api/v1/work/W-3102')).body;
    expect(after.state).toBe('setup_needed');
    expect(after.workspace.steps).toBeUndefined();
    expect(after.workspace.links[0].target).toEqual({ kind: 'setup_rules', area: 'delivery' });
    expect((await step('W-3102', 'record_release', 1, 'k-record', body)).body).toEqual(first.body);
    expect((await log()).sends['k-record']).toBe(1);
  });

  it('W-3105: 500 and nothing written', async () => {
    expect((await step('W-3105', 'record_release', 1)).status).toBe(500);
    expect((await send('GET', '/api/v1/work/W-3105')).body.workspace.status.label).toBe('Hypercare · release not recorded');
  });

  it('W-3106: 500, but written: the re-read is the hold', async () => {
    expect((await step('W-3106', 'record_release', 1)).status).toBe(500);
    expect((await send('GET', '/api/v1/work/W-3106')).body.state).toBe('setup_needed');
  });

  it('W-3107: effect_uncertain', async () => {
    const reply = await step('W-3107', 'record_release', 1);
    expect([reply.status, reply.body.outcome]).toEqual([200, 'effect_uncertain']);
  });

  it('W-3108: 409, and the item is served again at revision 2', async () => {
    expect((await step('W-3108', 'record_release', 1)).status).toBe(409);
    expect((await send('GET', '/api/v1/work/W-3108')).body.workspace.revision).toBe(2);
  });

  it('a step the item does not offer is 404, and a blank body is 422', async () => {
    expect((await step('W-3103', 'record_release', 1)).status).toBe(404);
    expect((await send('POST', '/api/v1/work/W-3102/steps', 'pm', { step: 'record_release' })).status).toBe(422);
  });
});

describe('log an observation', () => {
  it('W-3101: the re-read shows OBS-0013', async () => {
    expect((await step('W-3101', 'log_observation', 1, 'k-obs', { inputs: { what: 'Checkout page slow once on day 10' } })).status).toBe(200);
    const rows = (await send('GET', '/api/v1/work/W-3101')).body.workspace.sections[0].items.map((i: Body) => i.id);
    expect(rows).toEqual(['ISS-0301', 'OBS-0012', 'OBS-0013', 'INC']);
  });

  it('W-3112: 500, but written: the re-read shows OBS-0013', async () => {
    expect((await step('W-3112', 'log_observation', 1, 'k-obs-2', { inputs: { what: 'x' } })).status).toBe(500);
    expect((await send('GET', '/api/v1/work/W-3112')).body.workspace.sections[0].items.map((i: Body) => i.id)).toContain('OBS-0013');
  });
});
