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

const meBody = { name: 'Ada Okafor', roles: ['Finance Lead'], destinations: ['my_work'], startable_lines: [], csrf_token: 't1' };

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
