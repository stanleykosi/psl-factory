// The only module that calls the API for responses and reconcile. Every call goes through the shared client
// (`api`, `call`), so CSRF on writes and ApiError come from there. No call here messages a client: the only
// writes are proof, claim, the recorded response and the reconcile answer.
import type { Client } from 'openapi-fetch';

import { api, call } from '@/api/client';
import type { WorkItem } from '@/api/types';
import type { paths } from '@/api/schema';

import type {
  EvidenceUploadBody,
  EvidenceUploadResult,
  ResponseBody,
  ResponseResult,
  ResponseWorkItem,
  WorkActionBody,
  WorkActionResult,
} from './contract';

type Json<T> = { headers: { [name: string]: unknown }; content: { 'application/json': T } };
type Op<P extends keyof paths, M extends 'get' | 'post'> = NonNullable<paths[P][M]>;
type WithPost<P extends keyof paths, Body, Result> = Omit<paths[P], 'post'> & {
  post: Omit<Op<P, 'post'>, 'requestBody' | 'responses'> & {
    requestBody: { content: { 'application/json': Body } };
    responses: Omit<Op<P, 'post'>['responses'], 200> & { 200: Json<Result> };
  };
};
type ItemPath = '/api/v1/work/{work_id}';

/** The v4 paths this feature uses, with the v7 bodies and results from contract.ts. */
type ResponsePaths = {
  [P in ItemPath]: Omit<paths[P], 'get'> & {
    get: Omit<Op<P, 'get'>, 'responses'> & { responses: Omit<Op<P, 'get'>['responses'], 200> & { 200: Json<ResponseWorkItem> } };
  };
} & {
  '/api/v1/cases/{case_id}/evidence': WithPost<'/api/v1/cases/{case_id}/evidence', EvidenceUploadBody, EvidenceUploadResult>;
  '/api/v1/tasks/{task_id}/claim': paths['/api/v1/tasks/{task_id}/claim'];
  '/api/v1/tasks/{task_id}/response': WithPost<'/api/v1/tasks/{task_id}/response', ResponseBody, ResponseResult>;
  '/api/v1/work/{work_id}/actions': WithPost<'/api/v1/work/{work_id}/actions', WorkActionBody, WorkActionResult>;
};

// The one widening cast for this feature: the shared client is typed on v4 paths, whose bodies and results for
// these operations lack the v7 fields (case_revision, evidence_ids, received_via, recorded, next, reconcile...).
// Same client and middleware at runtime. Remove with RESPONSE_OPENAPI_PATH once the client is on v7 (F-13).
const v7 = api as unknown as Client<ResponsePaths>;

/** A v4-typed item (from F-03's useWorkItem) read with the v7 fields; no conversion, only the wider type. */
export function asResponseItem(item: WorkItem): ResponseWorkItem {
  return item;
}

export function getWorkItem(workId: string) {
  return call(v7.GET('/api/v1/work/{work_id}', { params: { path: { work_id: workId } } }));
}

export function uploadEvidence(caseId: string, body: EvidenceUploadBody) {
  return call(v7.POST('/api/v1/cases/{case_id}/evidence', { params: { path: { case_id: caseId } }, body }));
}

export function claimTask(taskId: string, expectedRevision: number) {
  return call(v7.POST('/api/v1/tasks/{task_id}/claim', { params: { path: { task_id: taskId } }, body: { expected_revision: expectedRevision } }));
}

export function recordResponse(taskId: string, body: ResponseBody) {
  return call(v7.POST('/api/v1/tasks/{task_id}/response', { params: { path: { task_id: taskId } }, body }));
}

export function workAction(workId: string, body: WorkActionBody) {
  return call(v7.POST('/api/v1/work/{work_id}/actions', { params: { path: { work_id: workId } }, body }));
}
