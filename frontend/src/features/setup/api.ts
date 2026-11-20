// The Setup calls. The only casts between the v4 types and the proposal types live here.
import { api, call } from '@/api/client';
import { ApiError, errorFromResponse, networkError } from '@/api/errors';
import type { operations } from '@/api/schema';
import type { PageSize } from '@/components';

import type {
  DelegationBody,
  DelegationBodyV7,
  DelegationResult,
  DelegationsPage,
  EvidenceBody,
  EvidenceResult,
  RulesPage,
  SaveBody,
  SaveBodyV4,
  SaveResult,
} from './contract-proposal';

export type RulesArea = 'finance' | 'delivery';

/** One page of E-SETUP-RULES. `cursor` and `limit` are proposals: v4 returns next_cursor but declares neither parameter. */
export async function readRules(area: RulesArea | undefined, limit: PageSize, cursor?: string): Promise<RulesPage> {
  const query: { area?: string; cursor?: string; limit?: number } = { limit };
  if (area) query.area = area;
  if (cursor) query.cursor = cursor;
  return (await call(api.GET('/api/v1/setup/rules', { params: { query: query as { area?: string } } }))) as RulesPage;
}

/** E-SETUP-RULE-SAVE with the proposal body (expected_revision may be 0; starts, reason, evidence_id). */
export function saveRule(component: string, body: SaveBody): Promise<SaveResult> {
  return call(api.PUT('/api/v1/setup/rules/{component}', { params: { path: { component } }, body: body as SaveBodyV4 }));
}

/** E-EVIDENCE-UPLOAD; the v7 answer adds case_revision. */
export async function uploadEvidence(caseId: string, body: EvidenceBody): Promise<EvidenceResult> {
  return (await call(api.POST('/api/v1/cases/{case_id}/evidence', { params: { path: { case_id: caseId } }, body }))) as EvidenceResult;
}

export type TemplatesPage = operations['E-TEMPLATES']['responses'][200]['content']['application/json'];
export type TemplateRow = TemplatesPage['items'][number];
export type TemplateUploadBody = operations['E-TEMPLATE-VERSION']['requestBody']['content']['application/json'];
export type TemplateUploadResult = operations['E-TEMPLATE-VERSION']['responses'][200]['content']['application/json'];
export type FieldProblem = { name: string; message: string };
/** An ApiError that also carries the 422 body's fields[] (the shared client keeps only code and message). */
export type UploadError = ApiError & { fields?: FieldProblem[] };

/** One page of E-TEMPLATES. `cursor` and `limit` are proposals: v7 returns next_cursor but declares neither parameter. */
export async function readTemplates(limit: PageSize, cursor?: string): Promise<TemplatesPage> {
  const query = cursor ? { limit, cursor } : { limit };
  return await call(api.GET('/api/v1/setup/templates', { params: { query: query as never } }));
}

/** E-TEMPLATE-VERSION. Not sent through `call`, so a 422 keeps its fields[]. */
export async function uploadTemplateVersion(templateId: string, body: TemplateUploadBody): Promise<TemplateUploadResult> {
  let result;
  try {
    result = await api.POST('/api/v1/setup/templates/{template_id}/versions', { params: { path: { template_id: templateId } }, body });
  } catch (error) {
    throw error instanceof ApiError ? error : networkError();
  }
  if (result.response.ok) return result.data as TemplateUploadResult;
  const error: UploadError = errorFromResponse(result.response.status, result.error);
  const fields = (result.error as { fields?: unknown } | undefined)?.fields;
  if (error.kind === 'invalid' && Array.isArray(fields)) {
    error.fields = fields.filter((f): f is FieldProblem => typeof f?.name === 'string' && typeof f?.message === 'string');
  }
  throw error;
}

/** One page of E-DELEGATIONS with the overlay fields. */
export async function readDelegations(limit: PageSize, cursor?: string): Promise<DelegationsPage> {
  const query = cursor ? { limit, cursor } : { limit };
  return (await call(api.GET('/api/v1/setup/delegations', { params: { query } }))) as DelegationsPage;
}

/** E-DELEGATION with the overlay body. Not sent through `call`, so a 422 keeps its fields[]. */
export async function addDelegation(body: DelegationBody): Promise<DelegationResult> {
  let result;
  try {
    result = await api.PUT('/api/v1/setup/delegation', { body: body as DelegationBodyV7 });
  } catch (error) {
    throw error instanceof ApiError ? error : networkError();
  }
  if (result.response.ok) return result.data as DelegationResult;
  const error: UploadError = errorFromResponse(result.response.status, result.error);
  const fields = (result.error as { fields?: unknown } | undefined)?.fields;
  if (error.kind === 'invalid' && Array.isArray(fields)) {
    error.fields = fields.filter((f): f is FieldProblem => typeof f?.name === 'string' && typeof f?.message === 'string');
  }
  throw error;
}
