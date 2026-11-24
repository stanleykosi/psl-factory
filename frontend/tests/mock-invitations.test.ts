import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, { responses: Responses }>>;
  components: { schemas: { Error: object } };
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const PREVIEW = '/api/v1/accounts/invitations/preview';
const ACCEPT = '/api/v1/accounts/invitations/accept';
const schemaOf = (path: string, status: string) => ajv.compile(contract.paths[path].post.responses[status].content['application/json'].schema);
const validPreview = schemaOf(PREVIEW, '200');
const validAccept = schemaOf(ACCEPT, '201');
const validError = ajv.compile(contract.components.schemas.Error);

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  await fetch(`${base}/__mock/reset`, { method: 'POST' });
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

const token = async () => ((await (await fetch(`${base}/api/v1/session`)).json()) as { csrf_token: string }).csrf_token;
const post = async (path: string, body: unknown, { csrf, scenario }: { csrf?: string; scenario?: string } = {}) => {
  const response = await fetch(base + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}), ...(scenario ? { 'X-Mock-Scenario': scenario } : {}) },
    body: JSON.stringify(body),
  });
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
};
const t = (letter: string) => letter.repeat(43);

describe('F-60: the mock speaks the live invitation shapes', () => {
  it('preview of the valid and two-group fixtures validates against the contract', async () => {
    const csrf = await token();
    const one = await post(PREVIEW, { token: t('v') }, { csrf });
    expect(one.status).toBe(200);
    expect(validPreview(one.body), JSON.stringify(validPreview.errors)).toBe(true);
    expect((one.body.workspaces as { access: string }[]).map((w) => w.access)).toEqual(['PMO', 'PMO']);
    const two = await post(PREVIEW, { token: t('m') }, { csrf });
    expect(validPreview(two.body)).toBe(true);
    expect((two.body.workspaces as { access: string }[]).map((w) => w.access)).toEqual(['PMO', 'Finance Lead']);
  });

  it.each(['e', 'u', 'x'])('an unusable token (%s) is 422 invitation_unavailable, the same body for every reason', async (letter) => {
    const reply = await post(PREVIEW, { token: t(letter) }, { csrf: await token() });
    expect(reply.status).toBe(422);
    expect(validError(reply.body)).toBe(true);
    expect(reply.body).toEqual({ code: 'invitation_unavailable', message: 'This invitation is unavailable.' });
  });

  it('a bad body is 422 invalid_input with fields; a missing or old token is 403 csrf_failed and changes nothing', async () => {
    const csrf = await token();
    for (const body of [{ token: 'short' }, { token: `${'v'.repeat(42)}+` }, {}, { token: t('v'), extra: 1 }]) {
      const reply = await post(PREVIEW, body, { csrf });
      expect(reply.status).toBe(422);
      expect(reply.body.code).toBe('invalid_input');
      expect(validError(reply.body)).toBe(true);
      expect((reply.body.fields as unknown[]).length).toBeGreaterThan(0);
    }
    for (const bad of [undefined, 'mock-csrf-old']) {
      const reply = await post(ACCEPT, { token: t('v'), password: 'a-long-enough-password', confirm: 'a-long-enough-password' }, { csrf: bad });
      expect([reply.status, reply.body.code]).toEqual([403, 'csrf_failed']);
      expect(validError(reply.body)).toBe(true);
    }
    expect((await post(PREVIEW, { token: t('v') }, { csrf })).status).toBe(200);
  });

  it('accept: mismatch and weak passwords are 422, a good pair is 201 once and the token is then used', async () => {
    const csrf = await token();
    const good = 'a-long-enough-password';
    const differ = await post(ACCEPT, { token: t('v'), password: good, confirm: 'other-long-password' }, { csrf });
    expect([differ.status, differ.body]).toEqual([422, { code: 'invalid_input', message: 'The passwords differ.' }]);
    const short = await post(ACCEPT, { token: t('v'), password: 'short', confirm: 'short' }, { csrf });
    expect([short.status, short.body.code]).toEqual([422, 'action_unavailable']);
    expect(validError(short.body)).toBe(true);
    const common = await post(ACCEPT, { token: t('v'), password: 'password1234', confirm: 'password1234' }, { csrf });
    expect(common.body).toEqual({ code: 'action_unavailable', message: 'This password is too common.' });
    const ok = await post(ACCEPT, { token: t('v'), password: good, confirm: good }, { csrf });
    expect([ok.status, ok.body]).toEqual([201, { complete: true, next_url: '/sign-in' }]);
    expect(validAccept(ok.body), JSON.stringify(validAccept.errors)).toBe(true);
    expect((await post(PREVIEW, { token: t('v') }, { csrf })).body.code).toBe('invitation_unavailable');
    expect((await post(ACCEPT, { token: t('v'), password: good, confirm: good }, { csrf })).body.code).toBe('invitation_unavailable');
  });

  it('the renewed token previews fine, then accept answers action_unavailable and every later preview is unavailable', async () => {
    const csrf = await token();
    const good = 'a-long-enough-password';
    expect((await post(PREVIEW, { token: t('r') }, { csrf })).status).toBe(200);
    const accept = await post(ACCEPT, { token: t('r'), password: good, confirm: good }, { csrf });
    expect([accept.status, accept.body]).toEqual([422, { code: 'action_unavailable', message: 'This invitation is unavailable.' }]);
    expect((await post(PREVIEW, { token: t('r') }, { csrf })).body.code).toBe('invitation_unavailable');
  });

  it.each(['429', '503', '500'])('scenario %s answers both routes with that status', async (scenario) => {
    const csrf = await token();
    expect((await post(PREVIEW, { token: t('m') }, { csrf, scenario })).status).toBe(Number(scenario));
    expect((await post(ACCEPT, { token: t('m'), password: 'x', confirm: 'x' }, { csrf, scenario })).status).toBe(Number(scenario));
  });
});
