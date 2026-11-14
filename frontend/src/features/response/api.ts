// The only module that calls the API for responses and reconcile. Every call goes through the shared client
// (`api`, `call`), so CSRF on writes and ApiError come from there. No call here messages a client: the only
// writes are proof, claim, the recorded response and the reconcile answer.
import { api, call } from '@/api/client';
import type { WorkItem } from '@/api/types';

import type {
  EvidenceUploadBody,
  EvidenceUploadResult,
  ResponseBody,
  ResponseResult,
  ResponseWorkItem,
  WorkActionBody,
  WorkActionResult,
} from './contract';

/** An item (from F-03's useWorkItem or E-WORK-ITEM) read with the response fields. A task whose response names no variant has no response to show. */
export function asResponseItem(item: WorkItem): ResponseWorkItem {
  return {
    ...item,
    tasks: item.tasks.map(({ response, ...task }) => (response?.variant ? { ...task, response: { ...response, variant: response.variant } } : task)),
  };
}

export function getWorkItem(workId: string) {
  return call(api.GET('/api/v1/work/{work_id}', { params: { path: { work_id: workId } } })).then(asResponseItem);
}

export function uploadEvidence(caseId: string, body: EvidenceUploadBody) {
  return call(api.POST('/api/v1/cases/{case_id}/evidence', { params: { path: { case_id: caseId } }, body }));
}

export function claimTask(taskId: string, expectedRevision: number) {
  return call(api.POST('/api/v1/tasks/{task_id}/claim', { params: { path: { task_id: taskId } }, body: { expected_revision: expectedRevision } }));
}

export function recordResponse(taskId: string, body: ResponseBody) {
  return call(api.POST('/api/v1/tasks/{task_id}/response', { params: { path: { task_id: taskId } }, body }));
}

export function workAction(workId: string, body: WorkActionBody) {
  return call(api.POST('/api/v1/work/{work_id}/actions', { params: { path: { work_id: workId } }, body }));
}
