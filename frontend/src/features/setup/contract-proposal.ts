// E-SETUP-RULES, E-SETUP-RULE-SAVE and E-EVIDENCE-UPLOAD as the Setup screens read them: the v4 core from the generated
// schema plus the v7 proposal fields (D-SETUP-RULES-VIEW r1, mock only) and F-11's proof_case (Assumption A-3).
// Every field outside v4 is optional and the screens work without it. Overlay: frontend/mock/proposals/setup.json.
import type { operations } from '@/api/schema';

export type RulesPageV4 = operations['E-SETUP-RULES']['responses'][200]['content']['application/json'];
export type RuleRowV4 = RulesPageV4['items'][number];

export type RoleOption = { role: string; label: string };
export type RuleEditor = { kind: 'role_set' | 'read_only'; options?: RoleOption[]; selected?: string[] };
export type ProofCase = { case_id: string; case_revision: number; evidence_kind: string };

export type RuleProposal = {
  area?: string;
  area_label?: string;
  group?: string;
  group_label?: string;
  used_by?: string[];
  display_value?: string;
  link?: string;
  holds_work?: boolean;
  effective_from?: string;
  can_change?: boolean;
  restricted?: boolean;
  editor?: RuleEditor;
  /** Beyond v7: the case a proof upload attaches to. Absent means Proof is disabled. */
  proof_case?: ProofCase;
};

export type RuleRow = RuleRowV4 & RuleProposal;
export type RulesPage = Omit<RulesPageV4, 'items'> & { items: RuleRow[]; not_set_count?: number; roles_missing_count?: number };

export type SaveBody = { expected_revision: number; value: { roles: string[] }; starts?: string; reason?: string; evidence_id?: string };
export type SaveBodyV4 = operations['E-SETUP-RULE-SAVE']['requestBody']['content']['application/json'];
export type SaveResult = operations['E-SETUP-RULE-SAVE']['responses'][200]['content']['application/json'];

export type EvidenceBody = operations['E-EVIDENCE-UPLOAD']['requestBody']['content']['application/json'];
export type EvidenceResult = operations['E-EVIDENCE-UPLOAD']['responses'][200]['content']['application/json'] & { case_revision?: number };

// E-DELEGATIONS and E-DELEGATION (v7) plus the F-27 overlay, mock only: from_options and from_person_id (G-SCR13A-1),
// delegate_options[].for_person_id (G-SCR13A-2), list-level can_add, the 200's delegation_id (G-SCR13A-4) and
// expected_revision 0. Every overlay field is optional and the Delegation tab works without each.
export type DelegationsPageV7 = operations['E-DELEGATIONS']['responses'][200]['content']['application/json'];
export type DelegationRowV7 = DelegationsPageV7['items'][number];
export type DelegationBodyV7 = operations['E-DELEGATION']['requestBody']['content']['application/json'];
export type DelegationResultV7 = operations['E-DELEGATION']['responses'][200]['content']['application/json'];

export type DelegationPerson = { person_id: string; name: string; role?: string };
export type DelegateOption = NonNullable<DelegationsPageV7['delegate_options']>[number] & { for_person_id?: string };
export type DelegationRow = Omit<DelegationRowV7, 'from' | 'delegate'> & {
  from: DelegationRowV7['from'] & { person_id?: string };
  delegate: DelegationRowV7['delegate'] & { person_id?: string };
};
export type DelegationsPage = Omit<DelegationsPageV7, 'items' | 'delegate_options'> & {
  items: DelegationRow[];
  delegate_options?: DelegateOption[];
  from_options?: DelegationPerson[];
  can_add?: boolean;
};
export type DelegationBody = DelegationBodyV7 & { from_person_id?: string };
export type DelegationResult = DelegationResultV7 & { delegation_id?: string };
