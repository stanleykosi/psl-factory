// F-29: E-DOCUMENT for the statement of work D-2901 in the contract mock. Every variant keeps the typed core valid
// against the generated 200 schema, the proposed fields match mock/proposals/document-review.json, and the rules
// (visibility, versions, the decision showing in the re-read, the minutes document untouched) hold.
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
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, { get: { responses: Record<string, { content: { 'application/json': { schema: Schema } } }> } }> };
const overlay = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/document-review.json'), 'utf8')) as { $comment: string; document_response: Schema };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const core = ajv.compile(openapi.paths['/api/v1/documents/{document_id}/versions/{version}'].get.responses['200'].content['application/json'].schema);
const proposed = ajv.compile(overlay.document_response);
const TYPED = ['document_id', 'version', 'title', 'status', 'template', 'body_url', 'test_template'];
/** The typed core: the contract has no other field yet (the overlay's fields are proposals). */
const typedCore = (body: Record<string, unknown>) => Object.fromEntries(Object.entries(body).filter(([key]) => TYPED.includes(key)));

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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Body = Record<string, any>;
async function get(path: string, init: { persona?: string; variant?: string; scenario?: string } = {}) {
  const cookie = [`psl_mock_persona=${init.persona ?? 'pm'}`, init.variant && `psl_mock_document=${init.variant}`, init.scenario && `psl_mock_scenario=${init.scenario}`].filter(Boolean).join('; ');
  const response = await fetch(`${base}${path}`, { headers: { Cookie: cookie } });
  return { status: response.status, body: (await response.json()) as Body };
}
const doc = (v: string, init: Parameters<typeof get>[1] = {}) => get(`/api/v1/documents/D-2901/versions/${v}`, init);

describe('the document fixtures', () => {
  it('says it is a proposal, and every variant is valid against the typed core and the overlay', async () => {
    expect(overlay.$comment).toMatch(/proposed/i);
    for (const variant of ['default', 'returned', 'returned-hidden', 'cannot-act', 'amount-unknown', 'no-review', 'no-sections', 'empty-sections', 'hostile']) {
      const { status, body } = await doc('2', { variant });
      expect([variant, status]).toEqual([variant, 200]);
      expect(core(typedCore(body)), `${variant} core: ${ajv.errorsText(core.errors)}`).toBe(true);
      expect(proposed(body), `${variant} overlay: ${ajv.errorsText(proposed.errors)}`).toBe(true);
    }
    const v1 = await doc('1');
    expect(core(typedCore(v1.body)) && proposed(v1.body)).toBe(true);
  });

  it('the default is the board: five sections, section 4 changed with the agent note, three checks, one review task', async () => {
    const { body } = await doc('2');
    expect([body.reference, body.test_template, body.sections.length, body.sections[3].changed_since, body.sections[3].notes[0].agent]).toEqual(['SOW-0198', true, 5, true, 'tola']);
    expect(body.checks.map((c: Body) => [c.key, c.status])).toEqual([['template', 'done'], ['amounts', 'done'], ['sections', 'done']]);
    expect(body.review).toEqual({ role_label: 'PMO Lead', work_id: 'W-2901', task_id: 'T-2901' });
  });

  it('variants change only what they name', async () => {
    expect((await doc('2', { variant: 'amount-unknown' })).body.checks[1].status).toBe('unknown');
    expect((await doc('2', { variant: 'returned' })).body.returned.note).toMatch(/^Section 4/);
    expect((await doc('2', { variant: 'returned-hidden' })).body.returned).toEqual({ by: 'Kemi Adebayo', role: 'PMO Lead', at: '2026-11-17T13:20:00Z' });
    expect((await doc('2', { variant: 'cannot-act' })).body.review.task_id).toBe('T-2902');
    expect((await doc('2', { variant: 'no-review' })).body.review).toEqual({ role_label: 'PMO Lead' });
    expect('sections' in (await doc('2', { variant: 'no-sections' })).body).toBe(false);
    expect((await doc('2', { variant: 'empty-sections' })).body.sections).toEqual([]);
  });
});

describe('rules', () => {
  it('v1 has its own state and no review task; an unknown version, id or non-number is not found; the minutes document is unchanged', async () => {
    const v1 = (await doc('1')).body;
    expect([v1.version, v1.status, v1.review.task_id]).toEqual(['1', 'Replaced by v2', undefined]);
    expect((await doc('3')).status).toBe(404);
    expect((await doc('latest')).status).toBe(404);
    expect((await get('/api/v1/documents/D-2999/versions/1')).status).toBe(501);
    expect((await get('/api/v1/documents/D-2304/versions/1')).body.document_id).toBe('D-2304');
  });

  it('a persona who cannot see the project gets 404 and no text; scenarios still win', async () => {
    const hidden = await doc('2', { persona: 'ceo' });
    expect(hidden.status).toBe(404);
    expect(JSON.stringify(hidden.body)).not.toMatch(/Statement|Scope|Lagoon/);
    expect((await doc('2', { scenario: '403' })).status).toBe(403);
    expect((await doc('2', { scenario: '401' })).status).toBe(401);
  });

  it('a recorded decision shows in the re-read: approve as Approved, return as returned with the note; v1 is untouched', async () => {
    const csrf = { 'X-CSRFToken': 'mock-csrf-pm', Cookie: 'psl_mock_persona=pm', 'Content-Type': 'application/json' };
    const send = (path: string, body: object) => fetch(`${base}${path}`, { method: 'POST', headers: csrf, body: JSON.stringify(body) });
    expect((await send('/api/v1/tasks/T-2901/claim', { expected_revision: 2 })).status).toBe(200);
    expect((await send('/api/v1/tasks/T-2901/decision', { expected_revision: 2, verdict: 'return' })).status).toBe(422);
    expect((await send('/api/v1/tasks/T-2901/decision', { expected_revision: 2, verdict: 'return', note: 'Fix section 4' })).status).toBe(200);
    const after = (await doc('2')).body;
    expect([after.status, after.returned.by, after.returned.role]).toEqual(['Returned to PM', 'Kemi Adebayo', 'PMO Lead']);
    expect((await doc('1')).body.returned).toBeUndefined();
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await doc('2')).body.status).toBe('Awaiting PMO Lead review');
    expect((await send('/api/v1/tasks/T-2901/decision', { expected_revision: 2, verdict: 'approve' })).status).toBe(200);
    expect((await doc('2')).body.status).toBe('Approved');
  });
});

describe('the work items behind the review', () => {
  it('the actionable item can act, the other cannot because the person prepared it', async () => {
    const actionable = (await get('/api/v1/work/W-2901')).body.tasks[0];
    expect([actionable.you_can_act, actionable.revision]).toEqual([true, 2]);
    const own = (await get('/api/v1/work/W-2902')).body.tasks[0];
    expect([own.you_can_act, own.cannot_act_reason]).toEqual([false, 'prepared_by_you']);
  });
});
