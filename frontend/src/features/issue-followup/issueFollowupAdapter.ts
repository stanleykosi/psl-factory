// F-111: the issue follow-up panel (key 'issue-followup', line pmo-issues/v1), read only. Every write (owner update, reply, set owner,
// message owner, refresh, restart, raise an escalation) is F-111B, so `commands()` describes none. The revision tokens stay in the
// readback (followup.expected_revision, followup.case_revision) for F-111B; they are drawn nowhere.
import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { registerLineAdapter, readPanel, type LineAdapter } from '@/features/workspace/adapter';

import { sections, type Followup, type IssueDetail, type IssueMessages, type Readback } from './model';

const WORK_ID = /^\/api\/v1\/work\/(\d+)\/issue-followup$/;

/** A read that failed on its own keeps the rest of the page; a lost session or record replaces the page (rethrown). */
async function alone<T>(read: Promise<T>): Promise<T | { error: ApiError }> {
  try {
    return await read;
  } catch (error) {
    const e = error instanceof ApiError ? error : networkError();
    if (e.kind === 'unauthenticated' || e.kind === 'not_found') throw e;
    return { error: e };
  }
}

/** The follow-up read, then the issue detail and the messages together. The case id is the work item's own `case_id`. */
async function read(ref: { key: string; url: string }): Promise<Readback> {
  const workId = Number(WORK_ID.exec(ref.url)?.[1]);
  if (!Number.isInteger(workId)) throw new Error('Not an issue follow-up route.');
  const [followup, work] = await Promise.all([
    readPanel<Followup>(ref),
    call(liveApi.GET('/api/v1/work/{work_id}', { params: { path: { work_id: workId } } })),
  ]);
  const path = { case_id: work.case_id, issue_id: followup.issue.id };
  const [detail, messages] = await Promise.all([
    alone<IssueDetail>(call(liveApi.GET('/api/v1/projects/{case_id}/issues/{issue_id}', { params: { path } })) as Promise<IssueDetail>),
    alone<IssueMessages>(call(liveApi.GET('/api/v1/projects/{case_id}/issues/{issue_id}/messages', { params: { path } })) as Promise<IssueMessages>),
  ]);
  return { followup, workState: work.state, detail, messages };
}

export const issueFollowupAdapter: LineAdapter<Readback> = {
  key: 'issue-followup',
  read,
  sections: (readback, ctx) => sections(readback, ctx.caseId),
  commands: () => [],
};

registerLineAdapter(issueFollowupAdapter as LineAdapter);
