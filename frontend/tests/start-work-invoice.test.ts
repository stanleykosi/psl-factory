// F-94: Prepare an invoice (pmo-finance/v1) through the form engine: the served oneOf schema, the two modes, the body and the mock.
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

import { isStartable } from '@/features/start-work/LineChooser';
import { lineFormFor } from '@/features/start-work/lines';
import { pmoFinance } from '@/features/start-work/lines/pmoFinance';
import { leavesOf } from '@/features/start-work/engine/schema';
import type { Line } from '@/features/start-work/types';

// @ts-expect-error plain ESM module without type declarations
import { resetStartLive, startLive, startLiveLog } from '../mock/start-live.mjs';

const ajv = addFormats(new Ajv({ allErrors: true, strict: false }));
const CASE = '00000000-0000-4000-8000-000000000001';
const CTX = { caseId: CASE, caseRevision: 4, idempotencyKey: 'key-1' };
const pick = (id: number) => ({ value: String(id), label: `Row ${id}` });
const lines = (startLive({ method: 'get', url: new URL('http://m/api/v1/lines'), persona: 'pm' })[1] as { items: Line[] }).items;
const line = lines.find((l) => l.key === 'pmo-finance/v1') as Line;

describe('pmo-finance/v1 in the start drawer', () => {
  it('is registered, startable and reads "Start invoice"', () => {
    expect(lineFormFor('pmo-finance/v1')).toBe(pmoFinance);
    expect(isStartable(line)).toBe(true);
    expect(pmoFinance.startLabel).toBe('Start invoice');
  });

  it('reads the oneOf as one mode choice plus each branch leaf tagged with its mode', () => {
    const leaves = leavesOf(line.request_schema);
    expect(leaves).not.toBe('unsupported');
    const mapped = (leaves as { path: string; when?: string }[]).map((l) => `${l.when ?? '*'}:${l.path}`);
    expect(mapped).toEqual(['*:mode', 'completion:coverage_id', 'completion:handoff_id', 'preparation:preparation_id', 'preparation:due_date', 'preparation:invoice_id']);
  });

  it('is not available when the intake is a oneOf the engine cannot read', () => {
    const branch = (mode: string | undefined) => ({ type: 'object', properties: mode ? { mode: { const: mode }, a: { type: 'integer' } } : { a: { type: 'integer' } } });
    expect(leavesOf({ properties: { intake: { oneOf: [branch('x'), branch(undefined)] } } })).toBe('unsupported');
    expect(leavesOf({ properties: { intake: { oneOf: [branch('x'), branch('x')] } } })).toBe('unsupported');
    expect(leavesOf({ properties: { intake: { oneOf: [{ type: 'object', properties: { mode: { const: 'x' }, a: { type: 'array' } } }] } } })).toBe('unsupported');
  });

  it('asks for the way in first, then only the chosen mode and the reference', () => {
    expect(pmoFinance.missing({}, line)).toEqual([{ name: 'mode', label: 'Start from' }, { name: 'reference', label: 'Reference' }]);
    expect(pmoFinance.missing({ mode: 'completion' }, line).map((m) => m.name)).toEqual(['coverage_id', 'handoff_id', 'reference']);
    expect(pmoFinance.missing({ mode: 'preparation' }, line).map((m) => m.name)).toEqual(['preparation_id', 'reference']);
    expect(pmoFinance.missing({ mode: 'preparation', preparation_id: pick(32), reference: 'x' }, line)).toEqual([]);
  });

  it('completion sends mode, coverage and handoff only, and validates against the served schema', () => {
    const values = { mode: 'completion', coverage_id: pick(12), handoff_id: pick(22), preparation_id: pick(32), due_date: '2026-12-01', reference: ' INV ' };
    const body = pmoFinance.buildBody(values, CTX, line) as Record<string, unknown>;
    expect(body).toEqual({ line: 'pmo-finance/v1', case_id: CASE, case_revision: 4, idempotency_key: 'key-1', intake: { mode: 'completion', coverage_id: 12, handoff_id: 22 }, reference: 'INV' });
    expect(ajv.compile(line.request_schema as object)(body)).toBe(true);
  });

  it('preparation sends null for an unchosen invoice and due date, and the values when chosen', () => {
    const empty = pmoFinance.buildBody({ mode: 'preparation', preparation_id: pick(32), reference: 'x', coverage_id: pick(12) }, CTX, line) as { intake: unknown };
    expect(empty.intake).toEqual({ mode: 'preparation', preparation_id: 32, due_date: null, invoice_id: null });
    const full = pmoFinance.buildBody({ mode: 'preparation', preparation_id: pick(32), invoice_id: pick(42), due_date: '2026-12-01', reference: 'x' }, CTX, line) as object;
    expect((full as { intake: unknown }).intake).toEqual({ mode: 'preparation', preparation_id: 32, due_date: '2026-12-01', invoice_id: 42 });
    expect(ajv.compile(line.request_schema as object)(full)).toBe(true);
  });

  it('maps a 422 name to its control', () => {
    for (const [name, to] of [['intake.mode', 'mode'], ['intake.coverage_id', 'coverage_id'], ['intake.due_date', 'due_date'], ['reference', 'reference'], ['case_id', 'project']] as const) {
      expect(pmoFinance.target(name, line)).toBe(to);
    }
  });
});

describe('the mock start for pmo-finance/v1', () => {
  const post = (body: unknown) => startLive({ method: 'post', url: new URL('http://m/api/v1/work'), raw: JSON.stringify(body), csrfOk: true, persona: 'pm' }) as [number, { fields?: { name: string }[] }];

  it('accepts a valid body of each mode and refuses one that mixes modes', () => {
    resetStartLive();
    const ok = pmoFinance.buildBody({ mode: 'completion', coverage_id: pick(12), handoff_id: pick(22), reference: 'x' }, CTX, line);
    expect(post(ok)[0]).toBe(200);
    expect(startLiveLog().started).toHaveLength(1);
    const mixed = { ...(ok as object), idempotency_key: 'key-2', intake: { mode: 'completion', coverage_id: 12, handoff_id: 22, invoice_id: null } };
    expect(post(mixed)[0]).toBe(422);
  });
});
