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
  components: { schemas: { Error: object } };
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path: string) => ajv.compile(contract.paths[path].get.responses['200'].content['application/json'].schema);
const validMe = schemaOf('/api/v1/me');
const validSession = schemaOf('/api/v1/session');
const validDashboard = schemaOf('/api/v1/role-dashboard');
const validOnboarding = schemaOf('/api/v1/me/onboarding');
const postSchema = (path: string, status: string) => ajv.compile(contract.paths[path].post.responses[status].content['application/json'].schema);
const validSignIn = postSchema('/api/v1/session', '200');
const validSignOut = postSchema('/api/v1/session/logout', '200');
// The 4xx responses of the contract are all its Error schema.
const validError = ajv.compile(contract.components.schemas.Error);
const validCsrfError = validError;

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

describe('F-58: sign-in and sign-out in the live shape', () => {
  const post = async (path: string, body: unknown, { persona = 'finance_lead', token, cookie = '', scenario }: { persona?: string; token?: string; cookie?: string; scenario?: string } = {}) => {
    const response = await fetch(base + path, {
      method: 'POST',
      headers: { Cookie: `psl_mock_persona=${persona}${cookie}`, 'Content-Type': 'application/json', ...(token ? { 'X-CSRFToken': token } : {}), ...(scenario ? { 'X-Mock-Scenario': scenario } : {}) },
      body: JSON.stringify(body),
    });
    return { status: response.status, body: (await response.json()) as Record<string, unknown>, setCookie: response.headers.get('set-cookie') };
  };
  const SAMPLE = { username: 'sample.user', password: 'sample-password' };
  const OUT = '; psl_mock_session=out';

  it('the right pair signs in: 200 in the live shape, the persona\'s token, the next_url as live returns it, the session cookie', async () => {
    const ok = await post('/api/v1/session', { ...SAMPLE, remember: true, next_url: '/my-work' }, { token: 'mock-csrf-finance_lead' });
    expect(ok.status).toBe(200);
    expect(ok.body).toEqual({ csrf_token: 'mock-csrf-finance_lead', signed_in: true, next_url: '/my-work' });
    expect(validSignIn(ok.body), JSON.stringify(validSignIn.errors)).toBe(true);
    expect(ok.setCookie).toContain('psl_mock_session=in');
    for (const next_url of ['//evil.example', 'https://evil.example/x', 'x']) {
      expect((await post('/api/v1/session', { ...SAMPLE, next_url }, { token: 'mock-csrf-finance_lead' })).body.next_url).toBe('/');
    }
    expect((await post('/api/v1/session', SAMPLE, { token: 'mock-csrf-finance_lead' })).body.next_url).toBe('/');
  });

  it('a wrong pair and an unknown name are the same 422 sign_in_failed with no fields', async () => {
    const wrong = await post('/api/v1/session', { username: 'sample.user', password: 'nope' }, { token: 'mock-csrf-finance_lead' });
    const unknown = await post('/api/v1/session', { username: 'nobody', password: 'nope' }, { token: 'mock-csrf-finance_lead' });
    expect(wrong).toEqual(unknown);
    expect(wrong.status).toBe(422);
    expect(wrong.body).toEqual({ code: 'sign_in_failed', message: 'Check the sign-in details.' });
    expect(validError(wrong.body), JSON.stringify(validError.errors)).toBe(true);
  });

  it('an empty or odd body is 422 invalid_input with fields', async () => {
    const empty = await post('/api/v1/session', {}, { token: 'mock-csrf-finance_lead' });
    expect([empty.status, empty.body.code]).toEqual([422, 'invalid_input']);
    expect((empty.body.fields as { name: string }[]).map((f) => f.name)).toEqual(['username', 'password']);
    expect(validError(empty.body), JSON.stringify(validError.errors)).toBe(true);
    expect((await post('/api/v1/session', { ...SAMPLE, remember: 'yes', extra: 1 }, { token: 'mock-csrf-finance_lead' })).status).toBe(422);
  });

  it('a token that is not the current one is 403 csrf_failed, on sign-in and on sign-out', async () => {
    for (const path of ['/api/v1/session', '/api/v1/session/logout']) {
      for (const token of [undefined, 'stale', 'mock-csrf-signed-out']) {
        const refused = await post(path, path.endsWith('logout') ? {} : SAMPLE, { token });
        expect([refused.status, refused.body.code]).toEqual([403, 'csrf_failed']);
        expect(validCsrfError(refused.body), JSON.stringify(validCsrfError.errors)).toBe(true);
      }
    }
  });

  it('sign-out rotates the token and signs the session out: other reads answer 401 and GET /session says signed out', async () => {
    const out = await post('/api/v1/session/logout', {}, { token: 'mock-csrf-finance_lead' });
    expect(out.status).toBe(200);
    expect(out.body).toEqual({ csrf_token: 'mock-csrf-signed-out-2', signed_in: false, next_url: '/accounts/login/' });
    expect(validSignOut(out.body), JSON.stringify(validSignOut.errors)).toBe(true);
    expect(out.setCookie).toContain('psl_mock_session=out');
    const read = (path: string) => fetch(base + path, { headers: { Cookie: `psl_mock_persona=finance_lead${OUT}` } });
    expect((await read('/api/v1/me')).status).toBe(401);
    expect((await read('/api/v1/role-dashboard')).status).toBe(401);
    expect((await read('/api/v1/me/onboarding')).status).toBe(401);
    expect((await read('/api/v1/notifications')).status).toBe(401);
    const session = (await (await read('/api/v1/session')).json()) as Record<string, unknown>;
    expect(session).toEqual({ csrf_token: 'mock-csrf-signed-out-2', signed_in: false, next_url: '/' });
    expect(validSession(session)).toBe(true);
    // Signing in again needs the token the signed-out read gave, and the persona's token comes back.
    expect((await post('/api/v1/session', SAMPLE, { token: 'mock-csrf-finance_lead', cookie: OUT })).status).toBe(403);
    const again = await post('/api/v1/session', SAMPLE, { token: 'mock-csrf-signed-out-2', cookie: OUT });
    expect([again.status, again.body.csrf_token]).toEqual([200, 'mock-csrf-finance_lead']);
  });

  it('the scenario cookies 429, 500 and 503 answer sign-in and sign-out; 401 expects the signed-out token', async () => {
    for (const scenario of ['429', '500', '503']) {
      expect((await post('/api/v1/session', SAMPLE, { token: 'mock-csrf-finance_lead', scenario })).status).toBe(Number(scenario));
      expect((await post('/api/v1/session/logout', {}, { token: 'mock-csrf-finance_lead', scenario })).status).toBe(Number(scenario));
    }
    expect((await post('/api/v1/session', SAMPLE, { token: 'mock-csrf-signed-out', scenario: '401' })).status).toBe(200);
  });

  it('GET /me/onboarding validates: persona none is not admitted, everyone else is', async () => {
    for (const persona of PERSONAS as string[]) {
      const { status, body } = await get('/api/v1/me/onboarding', persona);
      expect(status).toBe(200);
      expect(validOnboarding(body), JSON.stringify(validOnboarding.errors)).toBe(true);
      expect(body).toEqual(persona === 'none' ? { admitted: false, can_create_workspace: false, next_url: '/getting-started/' } : { admitted: true, can_create_workspace: false, next_url: '/' });
    }
  });
});
