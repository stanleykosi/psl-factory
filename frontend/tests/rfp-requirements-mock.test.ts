// F-37: the contract mock's RFP requirements fixtures (W-3401 to W-3404), their `.next.<step>` sidecars and scripts, the
// per-step result rule and the item_ids rule of E-WORK-STEP. Mock evidence only: it proves the mock follows the contract
// it was given, not what the backend will do.
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
const overlay = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/rfp-response.json'), 'utf8')) as { $comment: string; step: { properties: Record<string, unknown> } };
const fixture = (name: string) => JSON.parse(readFileSync(join(workDir, `${name}.json`), 'utf8'));

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
type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const get = async (id: string) => (await (await fetch(`${base}/api/v1/work/${id}`, { headers: HEADERS })).json()) as Json;
const post = async (id: string, body: unknown) => {
  const response = await fetch(`${base}/api/v1/work/${id}/steps`, { method: 'POST', headers: HEADERS, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Json };
};
let n = 0;
const key = () => `00000000-0000-4000-9000-${String(++n).padStart(12, '0')}`;
const names = readdirSync(workDir).filter((name) => /^W-340[1-4]/.test(name));

/** The proposals this feature reuses are checked on their own, then removed before the generated-schema check. */
function contractItem(body: Json) {
  const copy = structuredClone(body);
  for (const step of copy.workspace?.steps ?? []) {
    if (step.submit_label !== undefined) {
      expect(typeof step.submit_label === 'string' && step.submit_label.trim() !== '', step.key).toBe(true);
      expect(Object.keys(overlay.step.properties)).toContain('submit_label');
      delete step.submit_label;
    }
  }
  for (const section of copy.workspace?.sections ?? []) for (const row of section.items) delete row.team_key;
  return copy;
}

describe('fixtures (AC 20)', () => {
  it('lists the four items, the four .next sidecars, W-3403’s .next, and two scripts, all marked sample', () => {
    expect(names.sort()).toEqual(
      ['W-3401.json', 'W-3402.json', 'W-3402.next.accept.json', 'W-3402.next.accept_selected.json', 'W-3402.next.edit_accept.json', 'W-3402.next.write_own.json', 'W-3402.steps.json', 'W-3403.json', 'W-3403.next.json', 'W-3403.steps.json', 'W-3404.json'].sort(),
    );
    expect(typeof overlay.$comment).toBe('string');
  });

  it('every item and sidecar is schema-valid and sample once the reused proposal keys are removed; revisions are numbers of at least 1 and move together', () => {
    for (const name of names.filter((nm) => !nm.includes('.steps'))) {
      const body = fixture(name.replace('.json', ''));
      expect(itemSchema(contractItem(body)), `${name}: ${ajv.errorsText(itemSchema.errors)}`).toBe(true);
      expect(body.sample, name).toBe(true);
      expect(body.revision).toBeGreaterThanOrEqual(1);
      expect(body.workspace.revision).toBe(body.revision);
      expect(body.line).toBe('Pre-sale / RFP');
    }
  });

  it('every script answers a body the E-WORK-STEP 200 schema accepts', () => {
    for (const name of ['W-3402.steps', 'W-3403.steps']) {
      for (const [stepKey, script] of Object.entries(fixture(name)) as [string, Json][]) {
        expect(script.status, `${name} ${stepKey}`).toBe(200);
        expect(stepReply({ work_id: 'W-3402', state: 'action_needed', revision: 8, ...script.body }), ajv.errorsText(stepReply.errors)).toBe(true);
      }
    }
  });

  it('no fixture carries an amount, a rate or a costing version', () => {
    for (const name of names) expect(readFileSync(join(workDir, name), 'utf8'), name).not.toMatch(/₦|"money"|costing|"currency"/i);
  });
});

describe('the .next.<step> rule (AC 20)', () => {
  const body = (stepKey: string, ids: string[], extra: Json = {}) => ({ expected_revision: 7, step: stepKey, item_ids: ids, idempotency_key: key(), ...extra });

  it('accept serves W-3402.next.accept, edit_accept, write_own and accept_selected each their own sidecar', async () => {
    for (const [stepKey, ids, inputs] of [
      ['accept', ['R-07'], undefined],
      ['edit_accept', ['R-07'], { answer: 'Two officers.', status: 'clarify' }],
      ['write_own', ['R-07'], { answer: 'Mine.', status: 'addressed' }],
      ['accept_selected', ['R-07', 'R-09'], undefined],
    ] as const) {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      const result = await post('W-3402', body(stepKey, [...ids], inputs ? { inputs } : {}));
      expect(result.status, stepKey).toBe(200);
      expect(await get('W-3402'), stepKey).toEqual(fixture(`W-3402.next.${stepKey}`));
    }
    expect(fixture('W-3402.next.accept').workspace.sections[0].total).toBe(40);
    expect(fixture('W-3402.next.accept_selected').workspace.sections[0].total).toBe(39);
  });

  it('a step without its own sidecar serves W-3403.next; F-28’s audience rule still wins over a step sidecar', async () => {
    const uncertain = await post('W-3403', body('accept', ['R-07']));
    expect(uncertain.body.outcome).toBe('effect_uncertain');
    expect((await get('W-3403')).state).toBe('effect_uncertain');
    expect(Object.keys((await get('W-3403')).reconcile ?? {})).toHaveLength(0);
    const internal = await post('W-2301', { expected_revision: 4, step: 'confirm_minutes', item_ids: ['A-1'], inputs: { audience: 'internal' }, idempotency_key: key() });
    expect(internal.status).toBe(200);
    expect(await get('W-2301')).toEqual(fixture('W-2301.next.internal'));
  });

  it('an item id the served item does not offer that step for is a 422 naming item_ids; an unknown id too; nothing is written', async () => {
    for (const ids of [['R-08'], ['R-07', 'R-99']]) {
      const result = await post('W-3402', body('write_own', ids, { inputs: { answer: 'x', status: 'addressed' } }));
      expect(result.status).toBe(422);
      expect(result.body.fields.map((f: Json) => f.name)).toEqual(['item_ids']);
    }
    const bulk = await post('W-3402', body('accept_selected', ['R-07', 'R-10']));
    expect(bulk.status).toBe(200);
    expect((await get('W-3402')).revision).toBe(8);
  });

  it('a 422 on item_ids is logged, takes no sidecar and reset clears a swapped item', async () => {
    await post('W-3402', body('accept', ['R-09']));
    expect((await get('W-3402')).revision).toBe(7);
    await post('W-3402', body('accept', ['R-07']));
    expect((await get('W-3402')).revision).toBe(8);
    const log = (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { entries: { status: number; step: string }[] };
    expect(log.entries.map((e) => e.status)).toEqual([422, 200]);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await get('W-3402')).revision).toBe(7);
  });

  it('a replay of the same key answers again without a second send', async () => {
    const same = body('accept', ['R-07']);
    await post('W-3402', same);
    await post('W-3402', same);
    const log = (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { sends: Record<string, number> };
    expect(log.sends[same.idempotency_key]).toBe(1);
  });
});
