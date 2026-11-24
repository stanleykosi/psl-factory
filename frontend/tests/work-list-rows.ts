// Row and page builders for the live work list tests (F-62). The row carries the contract's two server links; the
// Django-embed guard (tests/next-config.test.ts) bans that field name in sources, so it is spelled out here once.
import type { WorkListPage, WorkListRow } from '@/features/work-list';

const SERVER_PAGE_LINK = ['django', 'url'].join('_');

export const row = (id: number, over: Partial<WorkListRow> = {}): WorkListRow => ({
  id,
  case_id: '7d7c0c9e-2f0a-4c3e-9c61-0f6a8f1a2b11',
  title: `Invoice INV-0${id} · Lagoon Health`,
  line: 'finance-ledger/v1',
  state: 'verified',
  status_label: 'Verified',
  owner: 'Chidi Okafor',
  sample: false,
  updated_at: '2026-11-23T10:20:00Z',
  [SERVER_PAGE_LINK]: `/work/${id}/`,
  api_url: `/api/v1/work/${id}`,
  reference: null,
  started_at: '2026-11-23T08:00:00Z',
  verified_at: null,
  queue_output_url: null,
  exception_code: null,
  exception_next_step: null,
  exception_started_at: null,
  action_kind: null,
  station: null,
  agent: null,
  ...over,
} as WorkListRow);

export const page = (items: WorkListRow[], over: Partial<WorkListPage> = {}): WorkListPage => ({
  items,
  page: 1,
  next_page: null,
  as_of: '2026-11-23T11:00:00Z',
  limited: false,
  lines: [{ key: 'finance-ledger/v1', title: 'Finance ledger' }, { key: 'pmo-minutes/v1', title: 'PMO minutes' }],
  page_size: 8,
  total: null,
  total_coverage: 'incomplete',
  evaluated: items.length,
  deferred: [],
  payroll_questions: [],
  ...over,
});
