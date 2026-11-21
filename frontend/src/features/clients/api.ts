// The three client operations (E-CLIENTS, E-CLIENT, E-CLIENT-CONTACT), typed from the generated schema. The save
// reads the raw reply because a 422 names fields, which ApiError does not carry.
import { api, call } from '@/api/client';
import { ApiError } from '@/api/errors';
import type { PageSize } from '@/components';
import type { paths } from '@/api/schema';

export type ClientList = paths['/api/v1/clients']['get']['responses'][200]['content']['application/json'];
export type ClientRow = ClientList['items'][number];
export type ClientDetail = paths['/api/v1/clients/{client_id}']['get']['responses'][200]['content']['application/json'];
export type MoneyAmount = NonNullable<ClientRow['owed']>;
export type FieldMessage = { name: string; message: string };

export const fetchClients = (limit: PageSize, cursor?: string): Promise<ClientList> =>
  call(api.GET('/api/v1/clients', { params: { query: cursor ? { limit, cursor } : { limit } } }));

export const fetchClient = (clientId: string): Promise<ClientDetail> =>
  call(api.GET('/api/v1/clients/{client_id}', { params: { path: { client_id: clientId } } }));

export type SaveOutcome =
  | { kind: 'saved' }
  | { kind: 'invalid'; message: string; fields?: FieldMessage[] }
  | { kind: 'forbidden'; message: string }
  | { kind: 'stale' }
  | { kind: 'unauthenticated' }
  | { kind: 'not_found' }
  | { kind: 'uncertain' };

const messageOf = (body: unknown) => (typeof (body as { message?: unknown })?.message === 'string' ? (body as { message: string }).message : '');

/** One PUT, never repeated here. A network failure or a 5xx is "uncertain": the caller reads the client, it does not resend. */
export async function saveBillingContact(clientId: string, body: { expected_revision: number; name: string; email: string }): Promise<SaveOutcome> {
  let result;
  try {
    result = await api.PUT('/api/v1/clients/{client_id}/billing-contact', { params: { path: { client_id: clientId } }, body });
  } catch (error) {
    return error instanceof ApiError && error.kind === 'unauthenticated' && error.status === 401 ? { kind: 'unauthenticated' } : { kind: 'uncertain' };
  }
  const { status } = result.response;
  if (result.response.ok) return { kind: 'saved' };
  if (status === 401) return { kind: 'unauthenticated' };
  if (status === 403) return { kind: 'forbidden', message: messageOf(result.error) };
  if (status === 404) return { kind: 'not_found' };
  if (status === 409) return { kind: 'stale' };
  if (status === 422) {
    const fields = (result.error as { fields?: unknown })?.fields;
    const valid = Array.isArray(fields) ? fields.filter((f): f is FieldMessage => typeof f?.name === 'string' && typeof f?.message === 'string') : undefined;
    return { kind: 'invalid', message: messageOf(result.error), fields: valid };
  }
  return { kind: 'uncertain' };
}
