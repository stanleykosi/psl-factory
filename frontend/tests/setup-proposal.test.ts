// PMO-0-2: the Setup proposal overlay. Fixtures and mock answers are valid against it, their v4 core is valid against
// v4, and the overlay equals the v7 proposal operations apart from F-11's proof_case.
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractRules } from '../mock/setup.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractEvidence } from '../mock/evidence.mjs';

type Schema = Record<string, unknown>;
type Op = { operationId: string; requestBody?: { content: { 'application/json': { schema: Schema } } }; responses: Record<string, { content?: { 'application/json': { schema: Schema } } }> };

const readJson = <T,>(path: string): T => JSON.parse(readFileSync(path, 'utf8')) as T;
const overlay = readJson<{ rules_response: Schema; save_body: Schema; evidence_response: Schema }>(join(__dirname, '../mock/proposals/setup.json'));
const opsOf = (path: string) => {
  const doc = readJson<{ paths: Record<string, Record<string, Op>> }>(path);
  const ops: Record<string, Op> = {};
  for (const methods of Object.values(doc.paths)) for (const op of Object.values(methods)) if (op?.operationId) ops[op.operationId] = op;
  return ops;
};
const v4 = opsOf(OPENAPI_PATH);
const v7 = opsOf(join(__dirname, '../../architecture/packages/v7/openapi.json'));
const response = (op: Op) => op.responses['200'].content!['application/json'].schema;
const request = (op: Op) => op.requestBody!.content['application/json'].schema;

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const check = (schema: Schema) => {
  const validate = ajv.compile(schema);
  return (body: unknown) => (validate(body) ? '' : ajv.errorsText(validate.errors));
};
const overlayRules = check(overlay.rules_response);
const overlaySave = check(overlay.save_body);
const overlayEvidence = check(overlay.evidence_response);
const v4Rules = check(response(v4['E-SETUP-RULES']));
const v4Save = check(request(v4['E-SETUP-RULE-SAVE']));
const v4Evidence = check(response(v4['E-EVIDENCE-UPLOAD']));

/** A UI save body is overlay-valid, and its v4 core (no starts/reason/evidence_id, revision at least 1) is v4-valid. */
function expectSaveBodyValid(body: Record<string, unknown>) {
  expect(overlaySave(body)).toBe('');
  const core = { expected_revision: Math.max(1, body.expected_revision as number), value: body.value };
  expect(v4Save(core)).toBe('');
}

const fixtureDir = join(__dirname, '../mock/fixtures/setup');

describe('Setup contract overlay (PMO-0-2)', () => {
  it('equals the v7 proposal schemas apart from proof_case', () => {
    const rules = structuredClone(overlay.rules_response) as { properties: { items: { items: { properties: Record<string, unknown> } } } };
    expect(rules.properties.items.items.properties).toHaveProperty('proof_case');
    delete rules.properties.items.items.properties.proof_case;
    expect(rules).toEqual(response(v7['E-SETUP-RULES']));
    expect(overlay.save_body).toEqual(request(v7['E-SETUP-RULE-SAVE']));
    expect(overlay.evidence_response).toEqual(response(v7['E-EVIDENCE-UPLOAD']));
  });

  it('every setup fixture is overlay-valid and its v4 core is v4-valid', () => {
    const files = readdirSync(fixtureDir).filter((name) => name.endsWith('.json'));
    expect(files.sort()).toEqual(['delivery.desktop.json', 'delivery.mobile.json', 'finance.desktop.json', 'finance.mobile.json', 'rules.desktop.json', 'rules.mobile.json']);
    for (const name of files) {
      const body = readJson(join(fixtureDir, name));
      expect(overlayRules(body), name).toBe('');
      expect(v4Rules(contractRules(body)), name).toBe('');
    }
  });

  it('a body with expected_revision 0 or the proposal fields is overlay-valid but not v4-valid', () => {
    const body = { expected_revision: 0, value: { roles: ['pmo_lead'] }, starts: '2026-11-14', reason: 'Agreed', evidence_id: 'EV-1' };
    expect(overlaySave(body)).toBe('');
    expect(v4Save(body)).not.toBe('');
    expectSaveBodyValid(body);
  });

  describe('mock answers', () => {
    let server: Server;
    let base: string;
    beforeAll(async () => {
      server = await startMockServer({ port: 0 });
      base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
    });
    afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

    const get = async (path: string, cookie: string) => {
      const res = await fetch(base + path, { headers: { Cookie: cookie } });
      return { status: res.status, body: (await res.json()) as Record<string, unknown> };
    };

    it('every scenario, area and page is overlay-valid and v4-valid once stripped', async () => {
      for (const scenario of ['desktop', 'mobile', 'readonly', 'empty', 'many']) {
        for (const query of ['', '?area=finance', '?area=delivery', '?area=other', '?cursor=o:50']) {
          const { status, body } = await get(`/api/v1/setup/rules${query}`, `psl_mock_persona=admin; psl_mock_setup=${scenario}`);
          expect(status).toBe(200);
          expect(overlayRules(body), `${scenario}${query}`).toBe('');
          expect(v4Rules(contractRules(body)), `${scenario}${query}`).toBe('');
        }
      }
    });

    it('a save answer and an upload answer are valid', async () => {
      const headers = { Cookie: 'psl_mock_persona=admin', 'X-CSRFToken': 'mock-csrf-admin', 'Content-Type': 'application/json' };
      const saved = await fetch(`${base}/api/v1/setup/rules/presale.rfp_assigner`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({ expected_revision: 0, value: { roles: ['pmo_lead'] }, starts: '2026-11-14' }),
      });
      expect(saved.status).toBe(200);
      expect(check(response(v7['E-SETUP-RULE-SAVE']))(await saved.json())).toBe('');
      const uploaded = await fetch(`${base}/api/v1/cases/C-SETUP-1/evidence`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ kind: 'rule_proof', filename: 'a.pdf', content_base64: 'aGVsbG8=', case_revision: 1 }),
      });
      const body = await uploaded.json();
      expect(overlayEvidence(body)).toBe('');
      expect(v4Evidence(contractEvidence(body))).toBe('');
    });
  });
});
