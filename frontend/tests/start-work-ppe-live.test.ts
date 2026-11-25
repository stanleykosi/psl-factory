// F-102: Start schedule (finance-ppe/v1) through the form engine: the body, the required checks and the mock's answers.
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

import { isStartable } from '@/features/start-work/LineChooser';
import { financePpe } from '@/features/start-work/lines/financePpe';
import { lineFormFor } from '@/features/start-work/lines';
import type { Line } from '@/features/start-work/types';

// @ts-expect-error plain ESM module without type declarations
import { resetStartLive, startLive, startLiveLog } from '../mock/start-live.mjs';

const ajv = addFormats(new Ajv({ allErrors: true, strict: false }));
const CASE = '00000000-0000-4000-8000-000000000001';
const CTX = { caseId: CASE, caseRevision: 4, idempotencyKey: 'key-1' };
const pick = (id: number) => ({ value: String(id), label: `Row ${id}` });
const lines = (startLive({ method: 'get', url: new URL('http://m/api/v1/lines'), persona: 'pm' })[1] as { items: Line[] }).items;
const line = lines.find((l) => l.key === 'finance-ppe/v1') as Line;

describe('finance-ppe/v1 in the start drawer', () => {
  it('is registered, startable and reads "Start schedule"', () => {
    expect(lineFormFor('finance-ppe/v1')).toBe(financePpe);
    expect(isStartable(line)).toBe(true);
    expect(financePpe.startLabel).toBe('Start schedule');
  });

  it('needs the register and a reference; the prior schedule and ledger mapping are optional', () => {
    expect(financePpe.missing({}, line)).toEqual([{ name: 'register_id', label: 'Register' }, { name: 'reference', label: 'Reference' }]);
    expect(financePpe.missing({ register_id: pick(33), reference: 'FY25' }, line)).toEqual([]);
  });

  it('sends line, case, revision, key, reference and intake with null for an unchosen prior and ledger', () => {
    const body = financePpe.buildBody({ register_id: pick(33), reference: ' FY25 ' }, CTX, line) as Record<string, unknown>;
    expect(body).toEqual({ line: 'finance-ppe/v1', case_id: CASE, case_revision: 4, idempotency_key: 'key-1', intake: { register_id: 33, prior_id: null, ledger_id: null }, reference: 'FY25' });
    expect(ajv.compile(line.request_schema as object)(body)).toBe(true);
    const chosen = financePpe.buildBody({ register_id: pick(33), prior_id: pick(41), ledger_id: pick(51), reference: 'FY25' }, CTX, line) as { intake: unknown };
    expect(chosen.intake).toEqual({ register_id: 33, prior_id: 41, ledger_id: 51 });
  });

  it('the same attempt sends the same key (the body is built from the one key it is given)', () => {
    const a = financePpe.buildBody({ register_id: pick(33), reference: 'x' }, CTX, line) as { idempotency_key: string };
    const b = financePpe.buildBody({ register_id: pick(33), reference: 'x' }, CTX, line) as { idempotency_key: string };
    expect(a.idempotency_key).toBe(b.idempotency_key);
  });
});

describe('the mock start for finance-ppe/v1 (AC17, AC18)', () => {
  const post = (body: unknown, scenario?: string) => startLive({ method: 'post', url: new URL('http://m/api/v1/work'), raw: JSON.stringify(body), scenario, csrfOk: true, persona: 'pm' }) as [number, { fields?: { name: string; message: string }[] }];
  const good = () => financePpe.buildBody({ register_id: pick(33), reference: 'FY25' }, { ...CTX, caseRevision: 4 }, line) as object;

  it('answers the work id once per key, and a stale revision 409', () => {
    resetStartLive();
    expect(post(good())[0]).toBe(200);
    expect(post(good())[0]).toBe(200);
    expect(startLiveLog().started).toHaveLength(1);
    expect(post({ ...good(), case_revision: 3, idempotency_key: 'other' })[0]).toBe(409);
  });

  it('a 422 names the field; a csrf_failed is a 403 and is not resent by the mock', () => {
    resetStartLive();
    const [status, body] = post({ ...good(), intake: { register_id: 0, prior_id: null, ledger_id: null } });
    expect(status).toBe(422);
    expect(body.fields?.some((f) => f.name === 'intake.register_id')).toBe(true);
    expect(post(good(), 'csrf_failed')[0]).toBe(403);
  });
});
