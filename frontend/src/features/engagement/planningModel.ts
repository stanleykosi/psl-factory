// F-97: the planning panel (SCR-42), read only. Turns the department-owner requests, the project's planning packet and its source
// clarifications into Sections. Unknown effort stays apart from "not applicable" and from zero. Writes (department inputs, effort
// review, readiness, handoff, owner assignment) are not drawn here yet.
import type { ApiError } from '@/api/errors';
import type { paths } from '@/api/live-schema';
import { formatDayTime } from '@/components';
import type { Cell, Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type OwnerRequests = Get<'/api/v1/work/{work_id}/planning-owner-requests'>;
export type Planning = Get<'/api/v1/projects/{case_id}/planning'>;
export type Sources = Get<'/api/v1/projects/{case_id}/planning/source-clarifications'>;
export type ReadFailed = { error: ApiError };
export type PlanningReadback = { requests: OwnerRequests; planning: Planning | ReadFailed; sources: Sources | ReadFailed };

type Input = NonNullable<Planning['departments'][number]['input']>;

export const NOT_RECORDED = 'Not recorded';
const failed = (r: object): r is ReadFailed => 'error' in r;
const cell = (column: string, value: string | null | undefined): Cell => ({ column, text: value ?? '' });

/** Why a read the person cannot have is not drawn: no access, or a failure. */
export const unreadable = (what: string, error: ApiError) => (error.kind === 'not_found' || error.kind === 'forbidden' ? `${what} isn’t available to you here.` : `We couldn’t load ${what.toLowerCase()}.`);

const EFFORT: Record<Input['effort_state'], string> = { known: 'Estimated', unknown: 'Effort unknown', not_applicable: 'Not applicable' };
const days = (n: string) => `${n} person-days`;

/** The estimate as words: a number only when the department gave one; unknown reads empty (drawn Unknown), never 0. */
export function estimate(input: Input): string {
  if (input.effort_state === 'not_applicable') return 'Not applicable';
  return input.effort_state === 'known' && input.person_days !== null ? days(input.person_days) : '';
}

function departments(p: Planning): Section[] {
  if (p.departments.length === 0) return [{ key: 'departments', kind: 'text', title: 'Departments', items: [{ id: 'none', text: 'No department has been asked for an estimate yet.' }] }];
  const rows = p.departments.map(
    (d): Item => ({
      id: d.department,
      cells: [
        cell('department', d.department),
        d.input === null
          ? { column: 'status', tag: { label: 'Waiting for an estimate', tone: 'neutral' } }
          : { column: 'status', tag: d.input.changed_effort ? { label: 'Changed from costing', tone: 'uncertain' } : { label: EFFORT[d.input.effort_state], tone: d.input.effort_state === 'known' ? 'verified' : 'neutral' } },
        d.input === null ? { column: 'estimate', text: '' } : cell('estimate', estimate(d.input)),
        d.input === null ? { column: 'received', date: { unknown: true } } : { column: 'received', date: { date: d.input.received_at.slice(0, 10), unknown: false } },
      ],
    }),
  );
  const said = p.departments.flatMap((d): Item[] => (d.input ? [{ id: d.department, label: d.department, text: d.input.summary, detail: `From ${d.input.source_party}, received ${formatDayTime(d.input.received_at)}` }] : []));
  const out: Section[] = [
    {
      key: 'departments',
      kind: 'table',
      title: 'Departments',
      columns: [
        { key: 'department', label: 'Department', kind: 'text' },
        { key: 'status', label: 'Status', kind: 'tag' },
        { key: 'estimate', label: 'Estimate', kind: 'text' },
        { key: 'received', label: 'Received', kind: 'date' },
      ],
      items: rows,
    },
  ];
  if (said.length > 0) out.push({ key: 'said', kind: 'text', title: 'What each department said', items: said });
  if (p.departments.some((d) => d.input?.changed_effort)) {
    out.push({
      key: 'effort',
      kind: 'facts',
      title: 'Changed effort',
      items: [
        { id: 'reviewed', label: 'Reviewed against costing', ...(p.effort_reviewed ? { tag: { label: 'Reviewed', tone: 'verified' as const } } : { value: 'Not reviewed yet' }) },
        ...(p.review_roles.length > 0 ? [{ id: 'roles', label: 'Reviewed by', value: p.review_roles.join(', ') }] : []),
      ],
    });
  }
  return out;
}

function held(p: Planning, s: Sources | ReadFailed): Section[] {
  const items: Item[] = [];
  if (p.finding) items.push({ id: 'finding', text: p.finding, severity: 'medium' });
  for (const q of p.packet?.questions ?? []) if (q.state === 'unresolved') items.push({ id: `q-${q.key}`, label: q.key, text: q.detail, severity: 'medium' });
  for (const c of p.packet?.source_correlations ?? []) if (c.state !== 'current') items.push({ id: `c-${c.key}`, label: c.key, text: c.detail, detail: c.state === 'conflicting' ? 'Conflicts with another source' : 'Left out of the packet', severity: 'high' });
  if (!failed(s)) for (const f of s.findings) items.push({ id: `f-${f.key}`, label: f.key, text: f.detail, severity: 'medium' });
  return items.length === 0 ? [] : [{ key: 'held', kind: 'findings', title: 'What is holding this', items }];
}

const OWNER: Record<string, { label: string; tone: 'neutral' | 'uncertain' | 'verified' }> = {
  unassigned: { label: 'Nobody set to receive it', tone: 'uncertain' },
  assigned: { label: 'Owner set', tone: 'verified' },
  source_access_held: { label: 'Source access held', tone: 'uncertain' },
};

function clarifications(s: Sources): Section[] {
  const out: Section[] = [];
  if (s.clarifications.length > 0) {
    out.push({
      key: 'owners',
      kind: 'table',
      title: 'Who receives the department requests',
      columns: [
        { key: 'what', label: 'Request', kind: 'text' },
        { key: 'owner', label: 'Owner', kind: 'tag' },
        { key: 'status', label: 'Status', kind: 'text' },
      ],
      items: s.clarifications.map((c): Item => ({ id: c.key, cells: [cell('what', c.key), { column: 'owner', tag: OWNER[c.owner_status] ?? { label: c.owner_status, tone: 'neutral' } }, cell('status', c.status.replaceAll('_', ' '))] })),
    });
  }
  if (s.reviewed_costing) out.push({ key: 'costing', kind: 'facts', title: 'Reviewed costing', items: [{ id: 'disposition', label: 'Decision', value: s.reviewed_costing.disposition.replaceAll('_', ' ') }] });
  return out;
}

function requests(r: OwnerRequests): Section[] {
  if (r.requests.length === 0) return [];
  return [
    {
      key: 'requests',
      kind: 'text',
      title: 'Requests waiting for this department',
      items: r.requests.map((q): Item => ({ id: String(q.request_id), label: q.role, text: `${q.reference} · ${q.kind.replaceAll('_', ' ')}`, detail: `Requested ${formatDayTime(q.requested_at)} · source received ${formatDayTime(q.source_received_at)}` })),
    },
  ];
}

function readiness(p: Planning): Section[] {
  if (!p.readiness) return [{ key: 'readiness', kind: 'facts', title: 'Readiness', items: [{ id: 'state', label: 'Readiness', value: 'Not prepared yet' }] }];
  const out: Section[] = [{ key: 'readiness', kind: 'facts', title: 'Readiness', items: [{ id: 'state', label: 'Readiness', tag: { label: 'Prepared', tone: 'verified' } }] }];
  if (p.readiness.delivery_dossiers.length > 0) out.push({ key: 'dossiers', kind: 'text', title: 'Delivery handoff', items: p.readiness.delivery_dossiers.map((d) => ({ id: String(d.id), text: d.label })) });
  return out;
}

export function planningSections({ requests: r, planning, sources }: PlanningReadback): Section[] {
  const out: Section[] = [];
  if (failed(planning)) out.push({ key: 'unavailable', kind: 'text', title: 'Departments', items: [{ id: 'planning', text: unreadable('The planning packet', planning.error) }] });
  else out.push(...departments(planning), ...held(planning, sources), ...requests(r), ...readiness(planning));
  if (failed(planning)) out.push(...requests(r));
  if (failed(sources)) out.push({ key: 'sources-unavailable', kind: 'text', items: [{ id: 'sources', text: unreadable('The list of who receives each request', sources.error) }] });
  else out.push(...clarifications(sources));
  return out;
}
