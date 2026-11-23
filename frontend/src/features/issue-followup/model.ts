// F-111: the issue follow-up panel (SCR-30 part 1), read only. Turns the three live reads into the Section objects the workspace
// renderer draws. Presentation only: overdue, no owner, verified and who may act come from the response, never from dates.
import type { ApiError } from '@/api/errors';
import type { paths } from '@/api/live-schema';
import { formatDayTime } from '@/components';
import type { Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Followup = Get<'/api/v1/work/{work_id}/issue-followup'>;
export type IssueDetail = Get<'/api/v1/projects/{case_id}/issues/{issue_id}'>;
export type IssueMessages = Get<'/api/v1/projects/{case_id}/issues/{issue_id}/messages'>;
/** A read that failed on its own; the other sections still draw. */
export type ReadFailed = { error: ApiError };

export type Readback = {
  followup: Followup;
  /** The work item's served state ('verified' draws the lead sentence). */
  workState: string;
  detail: IssueDetail | ReadFailed;
  messages: IssueMessages | ReadFailed;
};

export const NOT_RECORDED = 'Not recorded';
export const NO_MESSAGE = 'No message has been sent to the owner.';
export const NO_TIMELINE = 'Nothing has happened yet.';
export const OVERDUE_DEFAULT = 'The owner has not responded in time.';
export const UNAVAILABLE = 'This record is unavailable.';

const failed = (r: object): r is ReadFailed => 'error' in r;

const STATUS_TONE = { Open: 'uncertain', 'In Progress': 'agent', Resolved: 'verified', Closed: 'neutral' } as const;
const KIND_WORDS: Record<string, string> = { state: 'Status changed', acknowledgement: 'Owner acknowledged', request: 'Update requested', reminder: 'Reminder' };
const CHASE_WORDS: Record<string, string> = { request: 'Asked', reminder: 'Reminder' };

export const ageText = (days: number | null) => (days === null ? NOT_RECORDED : days === 0 ? 'Today' : days === 1 ? '1 day' : `${days} days`);
const when = (value: string | null | undefined) => (value ? formatDayTime(value) : NOT_RECORDED);
const dateOrNotSet = (value: string | null) => (value ? formatDayTime(value) : 'Not set');

/** The words for a failed read; a 403 on the messages read is its own sentence. */
export function errorText(error: ApiError, forbidden = 'You don’t have access to this.'): string {
  if (error.kind === 'forbidden') return forbidden;
  if (error.kind === 'csrf') return 'Refresh your session and try again.';
  if (error.kind === 'not_found') return UNAVAILABLE;
  if (error.kind === 'unauthenticated') return 'You are signed out. Sign in to see this.';
  if (error.kind === 'network') return 'We couldn’t reach the server.';
  if (error.kind === 'rate_limited' || error.kind === 'read_limited' || error.status === 503) return 'Try again shortly.';
  return 'We couldn’t load this part of the page.';
}

/** What the person may do, from the follow-up read only. No write control is drawn until F-111B. */
export function allowedActions(f: Followup) {
  return { requestUpdate: f.can_request_update, record: f.team.can_record, resolve: f.team.can_resolve, hasResponseTask: f.response_task !== null };
}

export const noOwner = (f: Followup) => f.team.assignment_id === null && f.issue.status !== 'Resolved' && f.issue.status !== 'Closed';

export function timelineItems(detail: IssueDetail): Item[] {
  return detail.timeline.map((row, i): Item => {
    const word = Object.hasOwn(KIND_WORDS, row.kind) ? KIND_WORDS[row.kind] : undefined;
    return {
      id: `${row.kind}-${row.id ?? i}`,
      ...(word ? { label: word, text: row.status } : { text: [row.kind, row.status].filter(Boolean).join(' ') }),
      at: row.at,
    };
  });
}

function chasingItems(m: IssueMessages): Item[] {
  return m.items.map((it): Item => {
    const receipt = it.receipt ? `Receipt recorded ${formatDayTime(it.receipt.recorded_at)}` : 'No receipt yet';
    return {
      id: `draft-${it.draft_id}`,
      label: Object.hasOwn(CHASE_WORDS, it.kind) ? CHASE_WORDS[it.kind] : it.kind,
      text: it.status,
      detail: [receipt, it.finding].filter(Boolean).join(' · '),
    };
  });
}

const note = (key: string, text: string): Section => ({ key, kind: 'text', items: [], note: text });

export function sections(r: Readback, caseId: string): Section[] {
  const { followup: f, detail, messages } = r;
  const { issue, team } = f;
  const out: Section[] = [];

  const timing = !failed(messages) ? messages.timing : null;
  if (timing && (timing.reminder_overdue || timing.escalation_overdue)) out.push(note('overdue', timing.finding || OVERDUE_DEFAULT));
  if (noOwner(f)) out.push(note('no-owner', [team.finding, f.next_action].filter(Boolean).join(' ')));
  if (r.workState === 'verified' && f.finding) out.push(note('verified', f.finding));

  const facts: Item[] = [{ id: 'reference', label: 'Reference', value: issue.reference }];
  if (issue.severity) facts.push({ id: 'severity', label: 'Severity', tag: { label: issue.severity, tone: 'neutral' } });
  facts.push({ id: 'status', label: 'Status', tag: { label: issue.status, tone: STATUS_TONE[issue.status] } });
  if (team.label) facts.push({ id: 'owner', label: 'Owner', value: team.label });
  facts.push({ id: 'raised', label: 'Raised', value: when(issue.opened_at) }, { id: 'age', label: 'Age', value: ageText(issue.age_days) });
  const planned = f.blocked_milestone ? null : f.blocked_planned_milestone;
  if (planned) facts.push({ id: 'blocks', label: 'Blocks', value: `${planned.name} (planned ${planned.stage === 'uat' ? 'UAT' : 'completion'})` });
  out.push({ key: 'issue', kind: 'facts', items: facts });
  // The shared renderer draws a link only to a project, so the milestone name links to the project.
  if (f.blocked_milestone) out.push({ key: 'blocks', kind: 'text', items: [{ id: 'blocks', label: 'Blocks', cites: [{ case_id: caseId, label: f.blocked_milestone.name }] }] });

  if (failed(detail)) {
    out.push({ key: 'happened', kind: 'text', title: 'What has happened', items: [{ id: 'error', text: errorText(detail.error) }] });
  } else {
    const rows = timelineItems(detail);
    out.push({ key: 'happened', kind: 'timeline', title: 'What has happened', items: rows.length ? rows : [{ id: 'none', text: NO_TIMELINE }] });
    const ack = detail.acknowledgement;
    out.push({
      key: 'ack',
      kind: 'text',
      items: [{ id: 'ack', text: ack.at ? ack.status : 'Not acknowledged yet', ...(ack.at ? { detail: [formatDayTime(ack.at), ack.basis].filter(Boolean).join(' · ') } : {}) }],
    });
  }

  if (failed(messages)) {
    out.push({ key: 'chasing', kind: 'text', title: 'Chasing', items: [{ id: 'error', text: errorText(messages.error, 'Chasing is not available to you') }] });
  } else {
    const rows = chasingItems(messages);
    if (rows.length) out.push({ key: 'chasing', kind: 'timeline', title: 'Chasing', items: rows });
    else if (!messages.timing) out.push({ key: 'chasing', kind: 'text', title: 'Chasing', items: [{ id: 'none', text: NO_MESSAGE }] });
    if (messages.timing) {
      const t = messages.timing;
      const times: Item[] = [
        { id: 'reminder', label: 'Reminder due', value: dateOrNotSet(t.reminder_due_at) },
        { id: 'escalate', label: 'Escalate by', value: dateOrNotSet(t.escalation_due_at) },
      ];
      if (t.escalation_target) times.push({ id: 'target', label: 'Escalation goes to', value: t.escalation_target });
      out.push({ key: 'timing', kind: 'facts', ...(rows.length ? {} : { title: 'Chasing' }), items: times });
    }
  }

  const next = [f.next_action, r.workState === 'verified' ? '' : f.finding].filter(Boolean);
  if (next.length) out.push({ key: 'next', kind: 'text', title: 'Next', items: next.map((text, i) => ({ id: `next-${i}`, text })) });
  return out;
}
