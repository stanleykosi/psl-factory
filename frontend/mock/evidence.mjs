// Evidence upload mock (E-EVIDENCE-UPLOAD), held by F-11 for the Setup Proof field until a proof lane
// (FE-M2A-PROOF or FE-M2B-RESPONSE) takes it over. Sample data only; nothing is stored but a case counter.
// The case must be one a Setup row offers as proof_case (else 404) and case_revision must be its current revision
// (else 409). The answer carries the real sha256 of the decoded bytes and the case revision after the upload.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

import { OPENAPI_PATH, SCENARIO_BODIES } from './server.mjs';
import { caseRevisions, proofCaseRevision, SETUP_DENIED, setupScenario } from './setup.mjs';

const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
let validateBody;
let uploads = 0;

function bodyValidator() {
  if (validateBody) return validateBody;
  const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
  const op = openapi.paths['/api/v1/cases/{case_id}/evidence'].post;
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  validateBody = ajv.compile(op.requestBody.content['application/json'].schema);
  return validateBody;
}

const invalid = (fields) => ({ status: 422, body: { code: 'invalid', message: `Check these fields: ${[...new Set(fields)].join(', ')}.` } });

export function uploadEvidence({ url, raw, persona, cookies }) {
  if (SETUP_DENIED.has(persona)) return { status: 403, body: FORBIDDEN };
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalid(['body']);
  }
  const validate = bodyValidator();
  if (!validate(body)) {
    return invalid(validate.errors.map((e) => e.params.missingProperty ?? e.params.additionalProperty ?? (e.instancePath.split('/')[1] || 'body')));
  }
  const caseId = decodeURIComponent(url.pathname.split('/')[4] ?? '');
  const current = proofCaseRevision(persona, setupScenario(cookies), caseId);
  if (current === undefined) return { status: 404, body: NOT_FOUND };
  if (body.case_revision !== current) return { status: 409, body: SCENARIO_BODIES[409] };
  caseRevisions.set(`${persona}:${caseId}`, current + 1);
  uploads += 1;
  const sha256 = createHash('sha256').update(Buffer.from(body.content_base64, 'base64')).digest('hex');
  return { status: 200, body: { evidence_id: `EV-${uploads}`, sha256, case_revision: current + 1 } };
}

/** The v4 core of an upload answer: the v7 case_revision removed. */
export function contractEvidence(body) {
  const rest = { ...body };
  delete rest.case_revision;
  return rest;
}
