// Maps the contract's {code, message} error bodies to one typed error. No business rules.
export type ApiErrorKind =
  | 'unauthenticated'
  | 'forbidden'
  | 'csrf'
  | 'not_found'
  | 'stale'
  | 'invalid'
  | 'rate_limited'
  | 'read_limited'
  | 'bad_request'
  | 'too_large'
  | 'unsupported'
  | 'server'
  | 'network';

const KIND_BY_STATUS: Record<number, ApiErrorKind> = {
  400: 'bad_request',
  401: 'unauthenticated',
  403: 'forbidden',
  404: 'not_found',
  409: 'stale',
  413: 'too_large',
  415: 'unsupported',
  422: 'invalid',
  429: 'rate_limited',
};

export const UNEXPECTED_MESSAGE = 'Something went wrong.';

// Client wording for kinds whose body message is not shown (the body is ignored for these).
const CSRF_MESSAGE = 'Your session was refreshed. Press the action again. Nothing was changed.';
const FIXED_MESSAGES: Partial<Record<ApiErrorKind, string>> = {
  csrf: CSRF_MESSAGE,
  bad_request: 'We could not read that request. Reload and try again.',
  too_large: 'That is too large to send.',
  unsupported: 'That kind of file or request is not accepted.',
  rate_limited: 'Too many requests. Try again shortly.',
  read_limited: 'This needs a closer look and could not load. Try again shortly.',
};

export type FieldError = { name: string; message: string };

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  readonly code: string;
  readonly fields: FieldError[];

  constructor(status: number, kind: ApiErrorKind, code: string, message: string, fields: FieldError[] = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
    this.code = code;
    this.fields = fields;
  }
}

function isErrorBody(body: unknown): body is { code: string; message: string } {
  if (typeof body !== 'object' || body === null) return false;
  const { code, message } = body as Record<string, unknown>;
  return typeof code === 'string' && code !== '' && typeof message === 'string' && message !== '';
}

function fieldsOf(body: unknown): FieldError[] {
  const fields = (body as { fields?: unknown } | null)?.fields;
  if (!Array.isArray(fields)) return [];
  return fields.filter(
    (f): f is FieldError => typeof f === 'object' && f !== null && typeof (f as FieldError).name === 'string' && typeof (f as FieldError).message === 'string',
  );
}

export function errorFromResponse(status: number, body: unknown): ApiError {
  const wellFormed = isErrorBody(body);
  const code = wellFormed ? body.code : 'unexpected_response';
  let kind: ApiErrorKind = KIND_BY_STATUS[status] ?? 'server';
  if (status === 403 && code === 'csrf_failed') kind = 'csrf';
  else if (status === 503 && code === 'read_limited') kind = 'read_limited';
  const fixed = FIXED_MESSAGES[kind];
  if (fixed) return new ApiError(status, kind, code, fixed);
  if (wellFormed) return new ApiError(status, kind, code, body.message, kind === 'invalid' ? fieldsOf(body) : []);
  return new ApiError(status, kind, code, UNEXPECTED_MESSAGE);
}

export function networkError(): ApiError {
  return new ApiError(0, 'network', 'network_error', 'We could not reach PSL Factory. Check your connection and try again.');
}
