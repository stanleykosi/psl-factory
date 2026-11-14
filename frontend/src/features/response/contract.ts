// The v7 shapes this feature reads and writes, declared once (architecture/packages/v7/openapi.json):
// tasks[].response (D-RESPONSE-VIEW r2), reconcile (D-WORK-ACTIONS-VIEW r2), E-EVIDENCE-UPLOAD, E-RESPONSE and
// E-WORK-ACTION. The base client is typed on v4, so api.ts widens it once. Every r2 field is optional; an
// element whose field is absent is left out. Remove this file's v7 copies when the client moves to v7 (F-13).
import type { WorkItem, WorkTask } from '@/api/types';

export type ResponseVariant = 'client_response' | 'sow_signature' | 'team_input' | 'go_live_acceptance' | 'support_handover';
export type ResponseActionValue = 'approved' | 'changes_requested' | 'signed' | 'rejected' | 'estimate' | 'input';
export type AgentKey = 'tola' | 'chidi' | 'zainab';
export type WorkState = WorkItem['state'];

export type Responder = { id: string; name: string; role?: string; organisation?: string };
export type ResponseAction = { value: ResponseActionValue; label?: string };
export type ResponseVersion = { id: string; label: string; note?: string; sent_at?: string };
export type ResponseChannel = { value: string; label: string };

export type Recorded = {
  by: { name: string; role?: string; is_you?: boolean };
  at: string;
  responded_at?: string;
  received_via?: string;
  proof_count?: number;
  summary?: string;
};

/** tasks[].response (openapi.json:1300-1593). F-09B's team_input fields (teams, blocking) are not read here. */
export type TaskResponse = {
  variant: ResponseVariant;
  responders: Responder[];
  actions: ResponseAction[];
  versions?: ResponseVersion[];
  evidence_kind?: string;
  claim_required?: boolean;
  intro?: string;
  proof_hint?: string;
  agent_note?: { agent: AgentKey; lines: string[] };
  channels?: ResponseChannel[];
  context?: {
    project?: { case_id: string; title: string };
    document?: { reference: string; label?: string; document_id?: string };
  };
  next?: string[];
  recorded?: Recorded;
};

export type ReconcileOutcome = 'delivered' | 'not_delivered' | 'unknown';

/** reconcile (openapi.json:1780-1830). */
export type Reconcile = {
  what?: string;
  sent_at?: string;
  checks?: { count: number; first_at?: string; last_at?: string; agent?: AgentKey };
  outcomes: ReconcileOutcome[];
  evidence_kind?: string;
  resend?: string;
  unknown_note?: string;
  resend_note?: string;
};

export type WorkAction = 'resume' | 'cancel' | 'reconcile';

export type ResponseTask = WorkTask & { response?: TaskResponse };

/** E-WORK-ITEM with the v7 fields this feature reads. A v4 WorkItem is assignable to it (all additions optional). */
export type ResponseWorkItem = Omit<WorkItem, 'tasks'> & {
  tasks: ResponseTask[];
  case_id?: string;
  case_revision?: number;
  allowed_actions?: WorkAction[];
  reconcile?: Reconcile;
};

export type EvidenceUploadBody = { kind: string; filename: string; content_base64: string; case_revision: number };
export type EvidenceUploadResult = { evidence_id: string; sha256: string; case_revision?: number };

/** E-RESPONSE (openapi.json:4623-4984). team, estimate_person_days and what belong to F-09B and are never sent. */
export type ResponseBody = {
  expected_revision: number;
  who: string;
  action: ResponseActionValue;
  responded_at: string;
  evidence_id: string;
  attested: boolean;
  case_revision?: number;
  version_id?: string;
  evidence_ids?: string[];
  note?: string;
  received_via?: string;
};
export type ResponseResult = { task_id: string; work_state: WorkState; revision?: number; recorded?: Recorded; next?: string[] };

export type WorkActionBody = {
  expected_revision: number;
  action: WorkAction;
  outcome?: ReconcileOutcome;
  evidence_id?: string;
  case_revision?: number;
};
export type WorkActionResult = { work_id: string; state: WorkState; revision: number };
