// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type ClientModule = typeof import('@/api/client');
type ErrorsModule = typeof import('@/api/errors');

let client: ClientModule;
let errors: ErrorsModule;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const meBody = { name: 'Ada Okafor', work_desk_url: '/retired/', destinations: [{ key: 'my_work', title: 'My work', django_url: '/retired/' }], startable_lines: [], csrf_token: 't1', assistant_agents: [] };

beforeEach(async () => {
  // Fresh module state: no CSRF token set.
  vi.resetModules();
  client = await import('@/api/client');
  errors = await import('@/api/errors');
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function getMeError() {
  try {
    await client.call(client.api.GET('/api/v1/me'));
  } catch (error) {
    return error as InstanceType<ErrorsModule['ApiError']>;
  }
  throw new Error('expected an ApiError');
}

describe('error mapping', () => {
  it.each([
    [401, 'unauthenticated'],
    [403, 'forbidden'],
    [404, 'not_found'],
    [409, 'stale'],
    [422, 'invalid'],
  ] as const)('%i with a valid body gives kind %s and the body code and message', async (status, kind) => {
    fetchStub.mockResolvedValue(json(status, { code: `c${status}`, message: `m${status}` }));
    const error = await getMeError();
    expect(error).toBeInstanceOf(errors.ApiError);
    expect({ status: error.status, kind: error.kind, code: error.code, message: error.message }).toEqual({
      status,
      kind,
      code: `c${status}`,
      message: `m${status}`,
    });
  });

  it('500 with an HTML body is a server error with code unexpected_response', async () => {
    fetchStub.mockResolvedValue(new Response('<html><body>Oops</body></html>', { status: 500, headers: { 'Content-Type': 'text/html' } }));
    const error = await getMeError();
    expect([error.status, error.kind, error.code, error.message]).toEqual([500, 'server', 'unexpected_response', 'Something went wrong.']);
  });

  it('other statuses with a valid body are server errors carrying the body', async () => {
    fetchStub.mockResolvedValue(json(503, { code: 'down', message: 'Down for maintenance.' }));
    const error = await getMeError();
    expect([error.kind, error.code, error.message]).toEqual(['server', 'down', 'Down for maintenance.']);
  });

  it('403 with {} keeps kind forbidden with code unexpected_response', async () => {
    fetchStub.mockResolvedValue(json(403, {}));
    const error = await getMeError();
    expect([error.status, error.kind, error.code, error.message]).toEqual([403, 'forbidden', 'unexpected_response', 'Something went wrong.']);
  });

  it('a rejected fetch is a network error', async () => {
    fetchStub.mockRejectedValue(new TypeError('Failed to fetch'));
    const error = await getMeError();
    expect([error.status, error.kind, error.code]).toEqual([0, 'network', 'network_error']);
  });

  it('a 2xx response that is not JSON is a network error', async () => {
    fetchStub.mockResolvedValue(new Response('<html></html>', { status: 200, headers: { 'Content-Type': 'text/html' } }));
    const error = await getMeError();
    expect(error.kind).toBe('network');
  });

  it('returns data on 2xx', async () => {
    fetchStub.mockResolvedValue(json(200, meBody));
    await expect(client.call(client.api.GET('/api/v1/me'))).resolves.toEqual(meBody);
  });

  it('every request is same-origin under /api/v1/ with credentials included', async () => {
    fetchStub.mockImplementation(async () => json(200, meBody));
    client.setCsrfToken('t1');
    await client.call(client.api.GET('/api/v1/me'));
    await client.call(client.api.GET('/api/v1/work', { params: { query: { queue: 'needs_me' } } })).catch(() => undefined);
    await client.call(client.api.POST('/api/v1/tasks/{task_id}/claim', { params: { path: { task_id: 'T-1' } }, body: { expected_revision: 1 } })).catch(() => undefined);
    expect(fetchStub).toHaveBeenCalledTimes(3);
    for (const [request] of fetchStub.mock.calls) {
      const url = new URL(request.url);
      expect(url.origin).toBe(window.location.origin);
      expect(url.pathname.startsWith('/api/v1/')).toBe(true);
      expect(request.credentials).toBe('include');
    }
  });
});

describe('CSRF header', () => {
  it('after setCsrfToken, POST and PUT carry X-CSRFToken and GET does not', async () => {
    fetchStub.mockImplementation(async () => json(200, meBody));
    client.setCsrfToken('t1');
    await client.call(client.api.GET('/api/v1/me'));
    await client.call(client.api.POST('/api/v1/tasks/{task_id}/claim', { params: { path: { task_id: 'T-1' } }, body: { expected_revision: 1 } }));
    await client.call(client.api.PUT('/api/v1/setup/delegation', { body: {} as never }));
    const [get, post, put] = fetchStub.mock.calls.map(([request]) => request);
    expect(get.method).toBe('GET');
    expect(get.headers.has('X-CSRFToken')).toBe(false);
    expect(post.method).toBe('POST');
    expect(post.headers.get('X-CSRFToken')).toBe('t1');
    expect(put.method).toBe('PUT');
    expect(put.headers.get('X-CSRFToken')).toBe('t1');
  });

  it('a write before any token is set throws csrf_unavailable and sends nothing', async () => {
    const attempt = client.call(client.api.POST('/api/v1/tasks/{task_id}/claim', { params: { path: { task_id: 'T-1' } }, body: { expected_revision: 1 } }));
    await expect(attempt).rejects.toMatchObject({ status: 0, kind: 'unauthenticated', code: 'csrf_unavailable' });
    expect(fetchStub).not.toHaveBeenCalled();
  });

  it('the token never reaches browser storage or cookies', async () => {
    fetchStub.mockImplementation(async () => json(200, meBody));
    client.setCsrfToken('t1');
    await client.call(client.api.GET('/api/v1/me'));
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).toBe('');
  });
});

const liveWrite = () => client.liveApi.POST('/api/v1/me/alert-preferences', { params: { header: { 'X-CSRFToken': '' } }, body: { revision: 1, email_requested: true, whatsapp_requested: false } });
const requestsTo = (path: string) => fetchStub.mock.calls.map(([request]) => request).filter((request) => new URL(request.url).pathname === path);

describe('session (GET /api/v1/session)', () => {
  it('refreshSession stores the token it returns, and the next live write sends it', async () => {
    fetchStub.mockImplementation(async (request) =>
      new URL(request.url).pathname === '/api/v1/session' && request.method === 'GET' ? json(200, { csrf_token: 'fresh', signed_in: false, next_url: '/' }) : json(200, {}),
    );
    const session = await client.refreshSession();
    expect(session).toEqual({ csrf_token: 'fresh', signed_in: false, next_url: '/' });
    expect(requestsTo('/api/v1/session')).toHaveLength(1);
    expect(requestsTo('/api/v1/session')[0].headers.has('X-CSRFToken')).toBe(false);
    await client.call(liveWrite());
    const write = fetchStub.mock.calls.map(([request]) => request).find((request) => request.method === 'POST')!;
    expect(write.headers.get('X-CSRFToken')).toBe('fresh');
  });

  it('with no token a live write throws csrf_unavailable and sends nothing', async () => {
    await expect(client.call(liveWrite())).rejects.toMatchObject({ status: 0, kind: 'unauthenticated', code: 'csrf_unavailable' });
    expect(fetchStub).not.toHaveBeenCalled();
  });
});

describe('403 csrf_failed', () => {
  const sessionBody = { csrf_token: 'new-token', signed_in: true, next_url: '/' };
  const alertWrite = () => client.api.PUT('/api/v1/me/alert-preferences', { body: { channel: 'both', frequency: 'immediate' } });

  it('is its own kind, refreshes the token once, never repeats the write, and the next write uses the new token', async () => {
    client.setCsrfToken('old');
    fetchStub.mockImplementation(async (request) => {
      if (new URL(request.url).pathname === '/api/v1/session') return json(200, sessionBody);
      return request.headers.get('X-CSRFToken') === 'old' ? json(403, { code: 'csrf_failed', message: 'Server words.' }) : json(200, { channel: 'both', frequency: 'immediate' });
    });
    await expect(client.call(alertWrite())).rejects.toMatchObject({
      status: 403,
      kind: 'csrf',
      code: 'csrf_failed',
      message: 'Your session was refreshed. Press the action again. Nothing was changed.',
    });
    expect(requestsTo('/api/v1/me/alert-preferences')).toHaveLength(1);
    expect(requestsTo('/api/v1/session')).toHaveLength(1);
    await client.call(alertWrite());
    const writes = requestsTo('/api/v1/me/alert-preferences');
    expect(writes).toHaveLength(2);
    expect(writes[1].headers.get('X-CSRFToken')).toBe('new-token');
  });

  it('still throws csrf when the refresh itself fails', async () => {
    client.setCsrfToken('old');
    fetchStub.mockImplementation(async (request) =>
      new URL(request.url).pathname === '/api/v1/session' ? json(500, { code: 'x', message: 'y' }) : json(403, { code: 'csrf_failed', message: 'z' }),
    );
    await expect(client.call(alertWrite())).rejects.toMatchObject({ kind: 'csrf' });
    expect(requestsTo('/api/v1/me/alert-preferences')).toHaveLength(1);
  });

  it('does not loop when GET /session itself answers csrf_failed', async () => {
    fetchStub.mockResolvedValue(json(403, { code: 'csrf_failed', message: 'z' }));
    await expect(client.refreshSession()).rejects.toMatchObject({ kind: 'csrf' });
    expect(requestsTo('/api/v1/session')).toHaveLength(1);
  });

  it('a 403 forbidden stays forbidden and makes no session call', async () => {
    client.setCsrfToken('old');
    fetchStub.mockResolvedValue(json(403, { code: 'forbidden', message: 'Not yours.' }));
    await expect(client.call(alertWrite())).rejects.toMatchObject({ kind: 'forbidden', code: 'forbidden', message: 'Not yours.' });
    expect(requestsTo('/api/v1/session')).toHaveLength(0);
  });
});

describe('the live error table', () => {
  const body = (code: string) => ({ code, message: `body ${code}` });
  it.each([
    [400, body('bad_request'), 'bad_request', 'We could not read that request. Reload and try again.'],
    [401, body('unauthenticated'), 'unauthenticated', 'body unauthenticated'],
    [403, body('csrf_failed'), 'csrf', 'Your session was refreshed. Press the action again. Nothing was changed.'],
    [403, body('forbidden'), 'forbidden', 'body forbidden'],
    [404, body('not_found'), 'not_found', 'body not_found'],
    [409, body('idempotency_conflict'), 'stale', 'body idempotency_conflict'],
    [409, body('stale_version'), 'stale', 'body stale_version'],
    [413, body('too_large'), 'too_large', 'That is too large to send.'],
    [415, body('unsupported'), 'unsupported', 'That kind of file or request is not accepted.'],
    [429, body('rate_limited'), 'rate_limited', 'Too many requests. Try again shortly.'],
    [503, body('read_limited'), 'read_limited', 'This needs a closer look and could not load. Try again shortly.'],
    [503, body('down'), 'server', 'body down'],
    [500, body('server_error'), 'server', 'body server_error'],
  ] as const)('%i %j gives kind %s', (status, payload, kind, message) => {
    const error = errors.errorFromResponse(status, payload);
    expect([error.status, error.kind, error.code, error.message]).toEqual([status, kind, payload.code, message]);
    expect(error.fields).toEqual([]);
  });

  it('a 429 with Retry-After shows no retry value and the request is not repeated', async () => {
    fetchStub.mockResolvedValue(new Response(JSON.stringify(body('rate_limited')), { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '30' } }));
    const error = await getMeError();
    expect(error.kind).toBe('rate_limited');
    expect(error.message).not.toMatch(/\d/);
    expect(fetchStub).toHaveBeenCalledTimes(1);
  });

  it('a body that is not JSON keeps the status kind with code unexpected_response', async () => {
    fetchStub.mockResolvedValue(new Response('<html></html>', { status: 503, headers: { 'Content-Type': 'text/html' } }));
    expect(await getMeError()).toMatchObject({ kind: 'server', code: 'unexpected_response', message: 'Something went wrong.' });
    fetchStub.mockResolvedValue(new Response('nope', { status: 429 }));
    expect(await getMeError()).toMatchObject({ kind: 'rate_limited', code: 'unexpected_response', message: 'Too many requests. Try again shortly.' });
  });

  it('a network failure is the network kind', async () => {
    fetchStub.mockRejectedValue(new TypeError('Failed to fetch'));
    expect(await getMeError()).toMatchObject({ status: 0, kind: 'network' });
  });

  it('a 422 keeps its fields through call(), and gives [] when it has none', async () => {
    const fields = [{ name: 'x', message: 'm' }];
    fetchStub.mockResolvedValue(json(422, { code: 'invalid', message: 'Check it.', fields }));
    expect((await getMeError()).fields).toEqual(fields);
    fetchStub.mockResolvedValue(json(422, { code: 'invalid', message: 'Check it.' }));
    expect((await getMeError()).fields).toEqual([]);
  });
});
