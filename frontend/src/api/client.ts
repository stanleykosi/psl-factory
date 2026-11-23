// Typed clients for the PSL Factory data API: `api` for the v7 contract (architecture/packages/v7/openapi.json),
// `liveApi` for the live contract (contracts/psl-factory.openapi.json). Both share one CSRF token.
// Same origin, session cookie included, X-CSRFToken on every write. Feature code calls
// `call(api.GET(...))` and gets data or an ApiError; it never reads a raw Response.
import createClient, { type Middleware } from 'openapi-fetch';

import { ApiError, errorFromResponse, networkError } from './errors';
import type { paths as livePaths } from './live-schema';
import type { paths } from './schema';

const WRITE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

let csrfToken: string | null = null;

/** Keeps the token from GET /api/v1/me in memory only. */
export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    if (!WRITE_METHODS.has(request.method)) return undefined;
    if (!csrfToken) {
      throw new ApiError(0, 'unauthenticated', 'csrf_unavailable', 'Your session is not ready yet. Reload and try again.');
    }
    request.headers.set('X-CSRFToken', csrfToken);
    return request;
  },
};

const clientOptions = {
  baseUrl: '',
  credentials: 'include',
  // Looked up per call so the current global fetch is used.
  fetch: (request: Request) => globalThis.fetch(request),
} as const;

export const api = createClient<paths>(clientOptions);
api.use(csrfMiddleware);

export const liveApi = createClient<livePaths>(clientOptions);
liveApi.use(csrfMiddleware);

/** The live contract names X-CSRFToken as a parameter of its writes; the middleware above sets the real value, so this only satisfies the types. */
export const csrfHeader = { header: { 'X-CSRFToken': '' } } as const;

/** GET /api/v1/session: stores the token it returns and gives back the body. Used before sign-in and after a stale token. */
export async function refreshSession() {
  const session = await call(liveApi.GET('/api/v1/session'), false);
  setCsrfToken(session.csrf_token);
  return session;
}

type ApiResult<T> = { data: T; error?: never; response: Response } | { data?: never; error: unknown; response: Response };

export async function call<T>(operation: Promise<ApiResult<T>>, refreshOnCsrf = true): Promise<Exclude<T, undefined>> {
  let result: ApiResult<T>;
  try {
    result = await operation;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw networkError();
  }
  if (result.response.ok) return result.data as Exclude<T, undefined>;
  const error = errorFromResponse(result.response.status, result.error);
  // A stale token: fetch a fresh one for the next press. The request itself is never repeated, and the session read does not refresh itself.
  if (error.kind === 'csrf' && refreshOnCsrf) await refreshSession().catch(() => undefined);
  throw error;
}
