// The client reads on the live contract (clients_directory, clients_group, workspaces_client, clients_contact_history).
// Nothing here writes: recording a billing contact is held (no proof upload route yet).
import { call, liveApi } from '@/api/client';
import type { paths } from '@/api/live-schema';

type Json<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer T } } } } } ? T : never;

export type Directory = Json<'/api/v1/clients'>;
export type GroupRow = Directory['groups'][number];
export type ProjectRow = Directory['projects'][number];
export type Group = Json<'/api/v1/clients/groups/{group}'>;
export type Debt = NonNullable<Group['debt']>;
export type Workspace = Json<'/api/v1/clients/{case_id}'>;
export type Contact = Workspace['contacts'][number];
export type History = Json<'/api/v1/clients/{case_id}/contacts/history'>;
export type Billing = ProjectRow['billing'];

export type DirectoryQuery = { q?: string; billing?: Billing; clients_page?: number; page?: number };

export const fetchDirectory = (query: DirectoryQuery): Promise<Directory> => call(liveApi.GET('/api/v1/clients', { params: { query } }));

export const fetchGroup = (group: string, page?: number): Promise<Group> =>
  call(liveApi.GET('/api/v1/clients/groups/{group}', { params: { path: { group }, query: page ? { page } : {} } }));

export const fetchWorkspace = (caseId: string): Promise<Workspace> => call(liveApi.GET('/api/v1/clients/{case_id}', { params: { path: { case_id: caseId } } }));

export const fetchHistory = (caseId: string, customer?: string, page?: number): Promise<History> =>
  call(liveApi.GET('/api/v1/clients/{case_id}/contacts/history', { params: { path: { case_id: caseId }, query: { purpose: 'billing', ...(customer ? { customer } : {}), ...(page ? { page } : {}) } } }));
