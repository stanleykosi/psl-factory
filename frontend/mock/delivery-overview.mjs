// Delivery overview in the contract mock (F-113, API 1.25.0, not in v7): GET /projects/{case_id}/delivery-overview, and the two reads
// behind the closure reason, GET /work/{id}/release-register (dossier_id only) and GET /projects/{case_id}/delivery/{dossier_id}/closure-checklist.
// P-0101 has four verified lines, handover needing action and closure not started; P-0099 answers 403; any other project has six lines not started.
// Sample data only; the mock never counts or decides anything.
export const OVERVIEW_PATTERN = /^\/api\/v1\/projects\/([^/]+)\/delivery-overview$/;
export const REGISTER_PATTERN = /^\/api\/v1\/work\/(\d+)\/release-register$/;
export const CHECKLIST_PATTERN = /^\/api\/v1\/projects\/([^/]+)\/delivery\/(\d+)\/closure-checklist$/;

const AS_OF = '2026-11-23T09:00:00Z';
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };

const TITLES = { 'delivery-release/v1': 'Release gates', 'delivery-go-live/v1': 'Go-live acceptance', 'delivery-hypercare/v1': 'Hypercare', 'delivery-handover/v1': 'Handover to Support', 'delivery-archive/v1': 'Archive', 'delivery-closure/v1': 'Closure' };
const idle = (key) => ({ key, title: TITLES[key], work_id: null, state: null, reference: null, updated_at: null, work_url: null, gate_state: 'not_started', gate_url: null });
const started = (key, work_id, state, reference, updated_at) => ({ key, title: TITLES[key], work_id, state, reference, updated_at, work_url: `/work/${work_id}`, gate_state: state, gate_url: `/api/v1/work/${work_id}/release-register` });

const P0101 = [
  // deliberately not in the fixed order: the page must sort them
  idle('delivery-closure/v1'),
  started('delivery-handover/v1', 2504, 'action_needed', 'HND-0048', '2026-11-20T10:00:00Z'),
  started('delivery-hypercare/v1', 2503, 'verified', 'HYP-0062', '2026-11-18T10:00:00Z'),
  started('delivery-release/v1', 2501, 'verified', 'REL-0091', '2026-03-25T10:00:00Z'),
  started('delivery-archive/v1', 2505, 'ready', 'ARC-0130', '2026-11-19T10:00:00Z'),
  started('delivery-go-live/v1', 2502, 'verified', 'GLV-0104', '2026-04-02T10:00:00Z'),
];

const CHECKLIST = {
  revision: 1,
  as_of: AS_OF,
  ready_to_prepare: false,
  recorded_closure_id: null,
  checks: [
    { key: 'handover', title: 'Handover to Support', status: 'held', summary: 'Handover is not verified.', references: [], finding: 'Support listed 2 gaps.' },
    { key: 'hypercare', title: 'Hypercare', status: 'current', summary: 'Verified.', references: [], finding: null },
    { key: 'retrospective', title: 'Retrospective', status: 'unknown', summary: 'No retrospective is saved.', references: [], finding: null },
  ],
  debt: null,
  retrospective_url: null,
};

/** The answer for a delivery read, or null when the path is not one of these three. */
export function deliveryRead({ pathname, idOf }) {
  let match = OVERVIEW_PATTERN.exec(pathname);
  if (match) {
    const caseId = idOf(decodeURIComponent(match[1]));
    if (caseId === 'P-0099') return [403, FORBIDDEN];
    const lines = caseId === 'P-0101' ? P0101 : Object.keys(TITLES).map(idle);
    return [200, { as_of: AS_OF, lines }];
  }
  match = REGISTER_PATTERN.exec(pathname);
  if (match) return match[1] === '2501' ? [200, { dossier_id: 52 }] : [404, NOT_FOUND];
  match = CHECKLIST_PATTERN.exec(pathname);
  if (match) return match[2] === '52' ? [200, CHECKLIST] : [404, NOT_FOUND];
  return null;
}
