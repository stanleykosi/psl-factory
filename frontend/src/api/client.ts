// Typed client for the PSL Factory data API (architecture/packages/v4/openapi.json).
// Same origin, session cookie included, X-CSRFToken on every write. Feature code calls
// `call(api.GET(...))` and gets data or an ApiError; it never reads a raw Response.
import createClient, { type Middleware } from 'openapi-fetch';

import { ApiError, errorFromResponse, networkError } from './errors';
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

export const api = createClient<paths>({
  baseUrl: '',
  credentials: 'include',
  // Looked up per call so the current global fetch is used.
  fetch: (request) => globalThis.fetch(request),
});
api.use(csrfMiddleware);

type ApiResult<T> = { data: T; error?: never; response: Response } | { data?: never; error: unknown; response: Response };

export async function call<T>(operation: Promise<ApiResult<T>>): Promise<Exclude<T, undefined>> {
  let result: ApiResult<T>;
  try {
    result = await operation;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw networkError();
  }
  if (result.response.ok) return result.data as Exclude<T, undefined>;
  throw errorFromResponse(result.response.status, result.error);
}
