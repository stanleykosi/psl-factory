// The three Setup calls. The only casts between the v4 types and the proposal types live here.
import { api, call } from '@/api/client';

import type { EvidenceBody, EvidenceResult, RulesPage, SaveBody, SaveBodyV4, SaveResult } from './contract-proposal';

export type RulesArea = 'finance' | 'delivery';

/** One page of E-SETUP-RULES. `cursor` is a proposal: v4 returns next_cursor but declares no cursor parameter. */
export async function readRules(area?: RulesArea, cursor?: string): Promise<RulesPage> {
  const query: { area?: string; cursor?: string } = {};
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
