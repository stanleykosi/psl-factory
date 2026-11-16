// The delegation mock (frontend/mock/delegations.mjs): scenarios, the PUT checks in order, the save cookies, in-memory
// rows and revision, reset, the cursor, and fixtures and replies validated against the generated contract plus the
// overlay (proposals/setup.json delegations_response, delegation_body).
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { contractDelegation, contractDelegations } from '../mock/delegations.mjs';
// @ts-expect-error plain ESM module without type declarations
import { M1_OPERATIONS, OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

import type { DelegationsPage } from '@/features/setup/contract-proposal';

type Op = { responses: Record<string, { content: { 'application/json': { schema: object } } }>; requestBody?: { content: { 'application/json': { schema: object } } } };

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, { get?: Op; put?: Op }> };
const overlay = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/setup.json'), 'utf8')) as Record<string, object>;
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const listOp = openapi.paths['/api/v1/setup/delegations'].get!;
const putOp = openapi.paths['/api/v1/setup/delegation'].put!;
const reply = (op: Op, status: number) => ajv.compile(op.responses[String(status)].content['application/json'].schema);
const validList = reply(listOp, 200);
const validOverlayList = ajv.compile(overlay.delegations_response);
const validOverlayBody = ajv.compile(overlay.delegation_body);
const validV7Body = ajv.compile(putOp.requestBody!.content['application/json'].schema);
const validAdded = reply(putOp, 200);
const validError = reply(putOp, 403);

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

const cookie = (persona = 'admin', extra = '') => `psl_mock_persona=${persona}${extra ? `; ${extra}` : ''}`;
async function list(query = '', persona = 'admin', extra = '') {
  const res = await fetch(`${base}/api/v1/setup/delegations${query}`, { headers: { Cookie: cookie(persona, extra) } });
  return { status: res.status, body: (await res.json()) as DelegationsPage };
}
const GOOD = { expected_revision: 2, from_person_id: 'P-KEMI', delegate: 'P-FEMI', starts: '2026-11-18', ends: '2026-11-25', reason: 'Annual leave' };
async function put(body: unknown, opts: { persona?: string; extra?: string; csrf?: string | null; raw?: string } = {}) {
  const persona = opts.persona ?? 'admin';
  const headers: Record<string, string> = { Cookie: cookie(persona, opts.extra), 'Content-Type': 'application/json' };
  if (opts.csrf !== null) headers['X-CSRFToken'] = opts.csrf ?? `mock-csrf-${persona}`;
  const res = await fetch(`${base}/api/v1/setup/delegation`, { method: 'PUT', headers, body: opts.raw ?? JSON.stringify(body) });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}
const names = (r: { body: Record<string, unknown> }) => ((r.body.fields ?? []) as { name: string }[]).map((f) => f.name);

describe('E-DELEGATIONS scenarios', () => {
  it('is part of the mock; every fixture validates against the overlay and, overlay removed, the generated schema', () => {
    expect(M1_OPERATIONS).toEqual(expect.arrayContaining(['E-DELEGATIONS', 'E-DELEGATION']));
    const dir = join(__dirname, '../mock/fixtures/delegations');
    const files = readdirSync(dir).sort();
    expect(files).toEqual(['authority.json', 'default.json', 'empty.json', 'many.json', 'readonly.json', 'single.json']);
    for (const file of files) {
      const page = JSON.parse(readFileSync(join(dir, file), 'utf8'));
      expect(validOverlayList(page), `${file}: ${ajv.errorsText(validOverlayList.errors)}`).toBe(true);
      expect(validList(contractDelegations(page)), `${file}: ${ajv.errorsText(validList.errors)}`).toBe(true);
    }
  });

  it('default: the two board rows, can_add, two From options and paired To options, no authorities, revision 2; the same for admin, finance_lead and ceo', async () => {
    const { status, body } = await list();
    expect(status).toBe(200);
    expect(validOverlayList(body)).toBe(true);
    expect(body.items.map((r) => [r.from.name, r.delegate.name, r.starts, r.ends, r.reason, r.status])).toEqual([
      ['Kemi Adebayo', 'Femi Ade', '2026-11-18', '2026-11-25', 'Annual leave', 'scheduled'],
      ['Ada Okafor', 'Chika Obi', '2026-11-02', '2026-11-04', 'Conference', 'ended'],
    ]);
    expect(body).toMatchObject({ can_add: true, revision: 2 });
    expect(body.from_options!.map((o) => o.name)).toEqual(['Kemi Adebayo', 'Ada Okafor']);
    expect(body.delegate_options!.map((o) => [o.name, o.for_person_id])).toEqual([
      ['Femi Ade', 'P-KEMI'],
      ['Chika Obi', 'P-ADA'],
    ]);
    expect(body.authorities).toBeUndefined();
    expect((await list('', 'finance_lead')).body).toEqual(body);
    expect((await list('', 'ceo')).body).toEqual(body);
  });

  it('pm and none get 403 on both calls, and the forbidden scenario 403s everyone', async () => {
    for (const persona of ['pm', 'none']) {
      expect((await list('', persona)).status).toBe(403);
      expect((await put(GOOD, { persona })).status).toBe(403);
    }
    const denied = await list('', 'admin', 'psl_mock_delegations=forbidden');
    expect(denied.status).toBe(403);
    expect(validError(denied.body)).toBe(true);
    expect((await put(GOOD, { extra: 'psl_mock_delegations=forbidden' })).status).toBe(403);
  });

  it('readonly: rows, no can_add and no options; empty: no rows, can_add and revision 0', async () => {
    const readonly = (await list('', 'admin', 'psl_mock_delegations=readonly')).body;
    expect(readonly.items).toHaveLength(2);
    expect(readonly.can_add).toBeUndefined();
    expect(readonly.from_options ?? readonly.delegate_options ?? readonly.authorities).toBeUndefined();
    const empty = (await list('', 'admin', 'psl_mock_delegations=empty')).body;
    expect(empty).toMatchObject({ items: [], can_add: true, revision: 0 });
  });

  it('many: 45 rows over pages of 20, 20 and 5; one row without ends, active rows', async () => {
    const extra = 'psl_mock_delegations=many';
    const first = (await list('', 'admin', extra)).body;
    expect(first.items).toHaveLength(20);
    const second = (await list(`?cursor=${encodeURIComponent(first.next_cursor!)}`, 'admin', extra)).body;
    expect(second.items).toHaveLength(20);
    const third = (await list(`?cursor=${encodeURIComponent(second.next_cursor!)}`, 'admin', extra)).body;
    expect(third.items).toHaveLength(5);
    expect(third.next_cursor).toBeUndefined();
    const all = [...first.items, ...second.items, ...third.items];
    expect(new Set(all.map((r) => r.delegation_id)).size).toBe(45);
    expect(all.filter((r) => r.ends === undefined)).toHaveLength(1);
    expect(all.some((r) => r.status === 'active')).toBe(true);
  });

  it('authority: one From option, two authorities and rows with authority; single: no From options, unpaired To options, one authority', async () => {
    const authority = (await list('', 'admin', 'psl_mock_delegations=authority')).body;
    expect(authority.from_options).toHaveLength(1);
    expect(authority.authorities).toHaveLength(2);
    expect(authority.items.every((r) => r.authority !== undefined)).toBe(true);
    const single = (await list('', 'admin', 'psl_mock_delegations=single')).body;
    expect(single.from_options).toBeUndefined();
    expect(single.delegate_options!.every((o) => o.for_person_id === undefined)).toBe(true);
    expect(single.authorities).toHaveLength(1);
  });
});

describe('E-DELEGATION', () => {
  it('appends the row with the status from the mock clock, bumps the revision, returns delegation_id; reset clears it', async () => {
    expect(validOverlayBody(GOOD)).toBe(true);
    const result = await put(GOOD);
    expect(result.status).toBe(200);
    expect(result.body).toEqual({ revision: 3, delegation_id: 'DL-9001' });
    expect(validAdded(contractDelegation(result.body))).toBe(true);
    const after = (await list()).body;
    expect(after.revision).toBe(3);
    expect(validOverlayList(after)).toBe(true);
    expect(validList(contractDelegations(after))).toBe(true);
    expect(after.items.at(-1)).toMatchObject({
      delegation_id: 'DL-9001',
      from: { name: 'Kemi Adebayo', role: 'PMO Lead' },
      delegate: { name: 'Femi Ade', role: 'PMO Lead' },
      status: 'scheduled',
      reason: 'Annual leave',
    });
    const now = await put({ ...GOOD, expected_revision: 3, starts: '2026-11-16', ends: '2026-11-16' });
    expect(now.status).toBe(200);
    expect((await list()).body.items.at(-1)!.status).toBe('active');
    expect((await list('', 'ceo')).body.revision).toBe(2);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await list()).body.items).toHaveLength(2);
    expect((await list()).body.revision).toBe(2);
  });

  it('accepts expected_revision 0 on the first delegation (proposal) and a body without From when none is offered', async () => {
    const empty = await put({ ...GOOD, expected_revision: 0 }, { extra: 'psl_mock_delegations=empty' });
    expect(empty.status).toBe(200);
    expect(validV7Body({ ...GOOD, expected_revision: 0 })).toBe(false);
    const single = await put({ expected_revision: 1, delegate: 'P-CHIKA', starts: '2026-11-20', ends: '2026-11-21', authority: 'approve_milestones' }, { extra: 'psl_mock_delegations=single' });
    expect(single.status).toBe(200);
    const row = (await list('', 'admin', 'psl_mock_delegations=single')).body.items.at(-1)!;
    expect(row.from).toEqual({ name: 'Ada Okafor', is_you: true });
    expect(row.authority).toBe('approve_milestones');
  });

  it('422 from the overlay schema: unknown property, bad date, empty value, missing field, idempotency_key, bad JSON', async () => {
    const check = async (body: unknown, expected: string[], raw?: string) => {
      const r = await put(body, { raw });
      expect(r.status).toBe(422);
      expect(names(r)).toEqual(expected);
      expect(r.body.message).toEqual(expect.any(String));
    };
    await check({ ...GOOD, extra: 1 }, ['extra']);
    await check({ ...GOOD, idempotency_key: 'k-1' }, ['idempotency_key']);
    await check({ ...GOOD, starts: '18/11/2026' }, ['starts']);
    await check({ ...GOOD, delegate: '' }, ['delegate']);
    await check({ ...GOOD, reason: '' }, ['reason']);
    const noEnds: Partial<typeof GOOD> = { ...GOOD };
    delete noEnds.ends;
    await check(noEnds, ['ends']);
    await check(null, ['body'], '{not json');
  });

  it('checks in order: CSRF, persona, schema, ends before starts, from, paired delegate, authority, revision 409', async () => {
    expect((await put(GOOD, { csrf: null })).status).toBe(403);
    expect((await put(GOOD, { csrf: 'wrong' })).body.code).toBe('csrf_failed');
    expect((await put({ nonsense: true }, { persona: 'pm' })).status).toBe(403);
    expect(names(await put({ ...GOOD, extra: 1, ends: '2026-11-01', delegate: 'P-NOBODY' }))).toEqual(['extra']);
    expect(names(await put({ ...GOOD, ends: '2026-11-17', from_person_id: 'P-NOBODY' }))).toEqual(['ends']);
    expect(names(await put({ ...GOOD, from_person_id: 'P-NOBODY', delegate: 'P-NOBODY' }))).toEqual(['from_person_id']);
    const noFrom: Partial<typeof GOOD> = { ...GOOD };
    delete noFrom.from_person_id;
    expect(names(await put(noFrom))).toEqual(['from_person_id']);
    // Chika is offered only for Ada: the pairing is the backend's key, checked exactly.
    expect(names(await put({ ...GOOD, delegate: 'P-CHIKA', authority: 'nope', expected_revision: 9 }))).toEqual(['delegate']);
    expect(names(await put({ ...GOOD, authority: 'approve_milestones', expected_revision: 9 }))).toEqual(['authority']);
    const authority = 'psl_mock_delegations=authority';
    expect(names(await put({ ...GOOD, authority: 'nope', expected_revision: 9 }, { extra: authority }))).toEqual(['authority']);
    expect((await put({ ...GOOD, authority: 'approve_invoices', expected_revision: 9 }, { extra: authority })).status).toBe(409);
    const stale = await put({ ...GOOD, expected_revision: 1 });
    expect(stale.status).toBe(409);
    expect(validError(stale.body)).toBe(true);
    // readonly offers no options at all, so its add is refused at the From check, before can_add is reached.
    expect(names(await put({ ...GOOD, expected_revision: 2 }, { extra: 'psl_mock_delegations=readonly' }))).toEqual(['from_person_id']);
    expect((await list()).body.revision).toBe(2);
  });

  it('save cookies: stale bumps the revision then 409; invalid names delegate and ends; uncertain writes nothing; uncertain_written writes then 500', async () => {
    const stale = await put(GOOD, { extra: 'psl_mock_delegations_save=stale' });
    expect(stale.status).toBe(409);
    expect((await list()).body.revision).toBe(3);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });

    const invalid = await put(GOOD, { extra: 'psl_mock_delegations_save=invalid' });
    expect(invalid.status).toBe(422);
    expect(names(invalid)).toEqual(['delegate', 'ends']);

    const uncertain = await put(GOOD, { extra: 'psl_mock_delegations_save=uncertain' });
    expect(uncertain.status).toBe(500);
    expect((await list()).body).toMatchObject({ revision: 2, items: [expect.anything(), expect.anything()] });

    const written = await put(GOOD, { extra: 'psl_mock_delegations_save=uncertain_written' });
    expect(written.status).toBe(500);
    const after = (await list()).body;
    expect(after.revision).toBe(3);
    expect(after.items).toHaveLength(3);
  });
});
