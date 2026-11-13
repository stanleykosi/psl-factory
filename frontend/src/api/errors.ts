// Maps the contract's {code, message} error bodies to one typed error. No business rules.
export type ApiErrorKind = 'unauthenticated' | 'forbidden' | 'not_found' | 'stale' | 'invalid' | 'server' | 'network';

const KIND_BY_STATUS: Record<number, ApiErrorKind> = {
  401: 'unauthenticated',
  403: 'forbidden',
  404: 'not_found',
  409: 'stale',
  422: 'invalid',
};

export const UNEXPECTED_MESSAGE = 'Something went wrong.';

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  readonly code: string;

  constructor(status: number, kind: ApiErrorKind, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
    this.code = code;
  }
}

function isErrorBody(body: unknown): body is { code: string; message: string } {
  if (typeof body !== 'object' || body === null) return false;
  const { code, message } = body as Record<string, unknown>;
  return typeof code === 'string' && code !== '' && typeof message === 'string' && message !== '';
}

export function errorFromResponse(status: number, body: unknown): ApiError {
  const kind = KIND_BY_STATUS[status] ?? 'server';
  if (isErrorBody(body)) return new ApiError(status, kind, body.code, body.message);
  return new ApiError(status, kind, 'unexpected_response', UNEXPECTED_MESSAGE);
}

export function networkError(): ApiError {
  return new ApiError(0, 'network', 'network_error', 'We could not reach PSL Factory. Check your connection and try again.');
}
