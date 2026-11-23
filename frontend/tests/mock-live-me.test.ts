import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { PERSONAS, startMockServer } from '../mock/server.mjs';

type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, { responses: Responses }>>;
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path: string) => ajv.compile(contract.paths[path].get.responses['200'].content['application/json'].schema);
const validMe = schemaOf('/api/v1/me');
const validSession = schemaOf('/api/v1/session');
const validDashboard = schemaOf('/api/v1/role-dashboard');

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as Record<string, unknown>;

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

const get = async (path: string, persona: string, scenario?: string) => {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}`, ...(scenario ? { 'X-Mock-Scenario': scenario } : {}) } });
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
};

describe('the mock speaks the live /me, /session and /role-dashboard shapes', () => {
  it('has a fixture of each kind for every persona, and no stray me or role-dashboard fixture', () => {
    const names = readdirSync(fixtures);
    expect(names.filter((n) => n.startsWith('me.')).sort()).toEqual([...PERSONAS].map((p: string) => `me.${p}.json`).sort());
    expect(names.filter((n) => n.startsWith('role-dashboard.')).sort()).toEqual([...PERSONAS].map((p: string) => `role-dashboard.${p}.json`).sort());
  });

  it.each(PERSONAS as string[])('%s: fixtures and served bodies validate against the live contract, with no roles', async (persona) => {
    const me = read(`me.${persona}.json`);
    expect(validMe(me), JSON.stringify(validMe.errors)).toBe(true);
    expect('roles' in me).toBe(false);
    const dashboard = read(`role-dashboard.${persona}.json`);
    expect(validDashboard(dashboard), JSON.stringify(validDashboard.errors)).toBe(true);

    const served = await get('/api/v1/me', persona);
    expect(served.status).toBe(200);
    expect(served.body).toEqual(me);
    expect(validMe(served.body), JSON.stringify(validMe.errors)).toBe(true);
    const session = await get('/api/v1/session', persona);
    expect(session.status).toBe(200);
    expect(session.body).toEqual({ csrf_token: me.csrf_token, signed_in: true, next_url: '/' });
    expect(validSession(session.body), JSON.stringify(validSession.errors)).toBe(true);
    const roles = await get('/api/v1/role-dashboard', persona);
    expect(roles.status).toBe(200);
    expect(roles.body).toEqual(dashboard);
    expect(validDashboard(roles.body), JSON.stringify(validDashboard.errors)).toBe(true);
  });

  it('a fixture with an extra key or a string destination fails the same check', () => {
    const me = read('me.finance_lead.json');
    expect(validMe({ ...me, roles: ['Finance Lead'] })).toBe(false);
    expect(validMe({ ...me, destinations: ['my_work'] })).toBe(false);
    expect(validMe({ ...me, destinations: [{ key: 'my_work', title: 'My work', django_url: '/retired/', extra: 1 }] })).toBe(false);
  });

  it('persona none has no positions; the others each carry the role words their bar showed', async () => {
    expect((await get('/api/v1/role-dashboard', 'none')).body.positions).toEqual([]);
    const words = async (persona: string) => ((await get('/api/v1/role-dashboard', persona)).body.positions as { name: string }[]).map((p) => p.name);
    expect(await words('finance_lead')).toEqual(['Finance Lead']);
    expect(await words('pmo_lead')).toEqual(['PMO Lead']);
    expect(await words('hr_lead')).toEqual(['HR Lead']);
  });

  it('scenario 401 signs the session out with a fixed token; role-dashboard answers the scenario', async () => {
    const session = await get('/api/v1/session', 'finance_lead', '401');
    expect(session.body).toEqual({ csrf_token: 'mock-csrf-signed-out', signed_in: false, next_url: '/' });
    expect(validSession(session.body)).toBe(true);
    expect((await get('/api/v1/role-dashboard', 'finance_lead', '401')).status).toBe(401);
  });

  it('scenario csrf_failed answers 403 csrf_failed on /me and on a write, and nothing else changes', async () => {
    const me = await get('/api/v1/me', 'finance_lead', 'csrf_failed');
    expect([me.status, me.body.code]).toEqual([403, 'csrf_failed']);
    const write = await fetch(`${base}/api/v1/me/alert-preferences`, {
      method: 'PUT',
      headers: { Cookie: 'psl_mock_persona=finance_lead', 'X-Mock-Scenario': 'csrf_failed', 'X-CSRFToken': 'mock-csrf-finance_lead', 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel: 'both', frequency: 'immediate' }),
    });
    expect([write.status, ((await write.json()) as { code: string }).code]).toEqual([403, 'csrf_failed']);
    expect((await get('/api/v1/session', 'finance_lead', 'csrf_failed')).status).toBe(200);
  });
});
