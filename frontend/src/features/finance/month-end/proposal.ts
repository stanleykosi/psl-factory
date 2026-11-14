// E-MONTH-END body as the SCR-36 boards need it. The v4 contract (src/api/schema.d.ts) carries only period, tasks
// {line, state, where, work_id?} and cash_received. The extra fields follow the v7 proposal D-MONTH-END-VIEW r1
// (architecture/packages/v7/openapi.json) name for name: they are a PROPOSAL, served by the contract mock only, and
// every one is optional so the page works on a pure v4 body. When the types are regenerated from v7 these
// intersections stay valid.
import type { operations } from '@/api/schema';

export type MonthEndBase = operations['E-MONTH-END']['responses'][200]['content']['application/json'];
export type AgentKey = 'tola' | 'chidi' | 'zainab';
export type MonthEndTone = 'neutral' | 'person' | 'agent' | 'stopped' | 'uncertain' | 'verified' | 'restricted';

export type MonthEndProposal = {
  /** date-time */
  as_of?: string;
  coverage?: string;
  /** Counts composed by the backend; the frontend never buckets task states itself. */
  summary?: { done?: number; waiting?: number; in_progress?: number; total?: number };
  /** Known part plus an Unknown marker ("₦4.7M + Unknown"); never 0 (INV-UNKNOWN). */
  cash_received_detail?: { known?: { amount?: string; currency: string; unknown: boolean }; has_unknown: boolean; unknown_note?: string };
  agent_note?: { agent: AgentKey; text: string };
  next_action?: { label: string; work_id?: string };
};

export type MonthEndTaskProposal = {
  title?: string;
  detail?: string;
  status_label?: string;
  tone?: MonthEndTone;
  restricted?: boolean;
  restricted_label?: string;
};

export type MonthEndTask = MonthEndBase['tasks'][number] & MonthEndTaskProposal;
export type MonthEnd = Omit<MonthEndBase, 'tasks'> & MonthEndProposal & { tasks: MonthEndTask[] };
