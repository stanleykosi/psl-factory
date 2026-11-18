// F-32: the delivery rows on P-0101 and the release items W-2501 to W-2510 in the contract mock. Each validates against the
// generated schema once the proposed keys are removed, the proposed keys match mock/proposals/delivery-release.json, and the
// decision rules hold (one apply of the approve sidecar, a repeat is 409, a task the person can't act on is 403).
import { readFileSync } from 'node:fs';
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
const overlay = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/delivery-release.json'), 'utf8')) as { $comment: string; project_extra: Schema; work_link: Schema };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path: string) => openapi.paths[path].get.responses['200'].content['application/json'].schema;
const workSchema = ajv.compile(schemaOf('/api/v1/work/{work_id}'));
const projectSchema = ajv.compile(schemaOf('/api/v1/projects/{case_id}'));
const extra = ajv.compile(overlay.project_extra);
const workLink = ajv.compile(overlay.work_link);

const dir = join(__dirname, '../mock/fixtures/work');
const readJson = (name: string) => JSON.parse(readFileSync(join(dir, name), 'utf8'));
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Body = Record<string, any>;

/** The `work` link kind is a proposal: it is checked on its own and removed before the schema check. */
function withoutLinks(body: Body): Body {
  const copy = structuredClone(body);
  for (const link of copy.workspace?.links ?? []) {
    if (link.target.kind === 'work') expect(workLink(link), ajv.errorsText(workLink.errors)).toBe(true);
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

async function send(method: string, path: string, persona = 'pm', body?: unknown) {
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}` };
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    headers['X-CSRFToken'] = `mock-csrf-${persona}`;
  }
  const response = await fetch(`${base}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Body };
}
const decide = (task: string, body: unknown) => send('POST', `/api/v1/tasks/${task}/decision`, 'pm', body);

describe('release items', () => {
  const ids = ['W-2501', 'W-2502', 'W-2503', 'W-2504', 'W-2505', 'W-2506', 'W-2507', 'W-2508', 'W-2510', 'W-2502.approve'];
  for (const id of ids) {
    it(`${id} validates against the E-WORK-ITEM schema and is sample data`, () => {
      const body = readJson(`${id}.json`);
      expect(body.sample).toBe(true);
      expect(workSchema(withoutLinks(body)), ajv.errorsText(workSchema.errors)).toBe(true);
      if (id !== 'W-2510') {
        expect(body.workspace.line_key).toBe('delivery_release');
        expect(body.reference).toBe('REL-0091');
        expect(body.workspace.context.project).toEqual({ case_id: 'P-0101', title: 'Lagoon Health · patient app' });
      }
    });
  }

  it('the go-live item has no workspace', () => {
    expect(readJson('W-2510.json').workspace).toBeUndefined();
  });

  it('a task with you_can_act true appears only in a "Your decision" fixture', () => {
    for (const id of ids) {
      const body = readJson(`${id}.json`);
      const acting = (body.tasks as { you_can_act: boolean }[]).some((t) => t.you_can_act);
      if (acting) expect([id, body.workspace.status.label]).toEqual([id, 'Your decision']);
    }
  });

  it('the work link kind is only on W-2503 and its approve sidecar, and names W-2510', () => {
    const links = ids.flatMap((id) => (readJson(`${id}.json`).workspace?.links ?? []).map((l: Body) => [id, l.target]));
    expect(links.filter(([, target]) => target.kind === 'work')).toEqual([
      ['W-2503', { kind: 'work', work_id: 'W-2510' }],
      ['W-2502.approve', { kind: 'work', work_id: 'W-2510' }],
    ]);
  });

  it('serves W-2502 to every persona the same', async () => {
    const bodies = await Promise.all(['pm', 'finance_lead', 'ceo'].map((p) => send('GET', '/api/v1/work/W-2502', p)));
    expect(bodies[0].body).toEqual(bodies[1].body);
    expect(bodies[0].body).toEqual(bodies[2].body);
  });
});

describe('the decision on T-2502', () => {
  it('claims, then an approve applies the sidecar once, and a repeat answers 409', async () => {
    expect((await send('POST', '/api/v1/tasks/T-2502/claim', 'pm', { expected_revision: 1 })).status).toBe(200);
    const first = await decide('T-2502', { expected_revision: 1, verdict: 'approve' });
    expect(first.status).toBe(200);
    const after = await send('GET', '/api/v1/work/W-2502');
    expect(after.body).toEqual(readJson('W-2502.approve.json'));
    expect(after.body.workspace.status).toEqual({ label: 'Release ready', tone: 'verified' });
    expect(after.body.tasks[0]).toMatchObject({ id: 'T-2502', you_can_act: false, cannot_act_reason: 'already_decided' });
    expect((await decide('T-2502', { expected_revision: 1, verdict: 'approve' })).status).toBe(409);
  });

  it('a return without a note is refused with 422 and changes nothing', async () => {
    expect((await decide('T-2502', { expected_revision: 1, verdict: 'return' })).status).toBe(422);
    expect((await send('GET', '/api/v1/work/W-2502')).body.workspace.status.label).toBe('Your decision');
  });

  it('a decide on T-2504, which this person may not act on, answers 403', async () => {
    expect((await decide('T-2504', { expected_revision: 1, verdict: 'approve' })).status).toBe(403);
  });
});

describe('P-0101 delivery rows', () => {
  const stripped = (body: Body) => {
    const copy = structuredClone(body);
    for (const row of copy.delivery) for (const key of ['reference', 'at', 'detail', 'short_title']) delete row[key];
    delete copy.delivery_agent;
    delete copy.delivery_summary;
    return copy;
  };

  it('validates against the E-PROJECT schema without the proposed keys, and the proposed keys match the overlay', async () => {
    expect(overlay.$comment).toMatch(/PROPOSED/);
    const { status, body } = await send('GET', '/api/v1/projects/P-0101');
    expect(status).toBe(200);
    expect(projectSchema(stripped(body)), ajv.errorsText(projectSchema.errors)).toBe(true);
    expect(extra(body), ajv.errorsText(extra.errors)).toBe(true);
  });

  it('has the six rows in order; only Release and Go-live carry a work id', async () => {
    const { body } = await send('GET', '/api/v1/projects/P-0101');
    expect(body.delivery.map((r: Body) => [r.title, r.work_id])).toEqual([
      ['Release gates', 'W-2503'],
      ['Go-live acceptance', 'W-2510'],
      ['Hypercare', undefined],
      ['Archive', undefined],
      ['Handover to Support', undefined],
      ['Closure', undefined],
    ]);
  });

  it('leaves the journey keys as they were', async () => {
    const { body } = await send('GET', '/api/v1/projects/P-0101');
    expect(body.lines).toHaveLength(8);
    expect(body.next).toBe('Client UAT response, then Finance review of the milestone 2 invoice.');
  });
});
