// F-88: the five received-bid calls of contract 1.26.0, typed from the live contract. SCR-23 logs a received RFP
// (organisations, one multipart POST, the receipt read); SCR-24 assigns its accountable PM (the Unassigned list, the
// assignment read, the assign POST). Nothing here decides who may be chosen: the server names them.
import { call, csrfHeader, liveApi } from '@/api/client';
import type { paths } from '@/api/live-schema';
import { START_TIMEOUT_MS } from '@/features/start-work/useStartWork';

type Json<P extends keyof paths, M extends 'get' | 'post'> = paths[P][M] extends { responses: { 200: { content: { 'application/json': infer T } } } } ? T : never;

export type Organisation = Json<'/api/v1/received-bids/organisations', 'get'>['items'][number];
export type Receipt = Json<'/api/v1/received-bids/{case_id}/receipts/{receipt_id}', 'get'>;
export type LoggedBid = Json<'/api/v1/received-bids', 'post'>;
export type BidRow = Json<'/api/v1/received-bids/assignments', 'get'>['items'][number];
export type BidPage = Json<'/api/v1/received-bids/assignments', 'get'>;
export type AssignmentRead = Json<'/api/v1/received-bids/{case_id}/assignment', 'get'>;
export type AssignBody = paths['/api/v1/received-bids/{case_id}/assignment']['post']['requestBody']['content']['application/json'];
export type Assigned = paths['/api/v1/received-bids/{case_id}/assignment']['post']['responses'][201]['content']['application/json'];

export const DOCUMENT_MAX_BYTES = 5 * 1024 * 1024;
export const DOCUMENT_TYPES = ['.pdf', '.doc', '.docx'];
export const NOTE_MAX = 4000;
export const REASON_MAX = 4000;
export const NAME_MAX = 160;

export type DeadlineStatus = 'unknown' | 'stated' | 'not_stated';
export type SubmissionMethod = 'email' | 'portal' | 'by_hand' | 'not_stated';

/** What one log of a received RFP sends. `receivedAt` and `deadlineAt` are already offset date-times. */
export type LogInput = {
  authority: number;
  startKey: string;
  reference: string;
  receivedAt: string;
  deadlineStatus: DeadlineStatus;
  /** Only with `stated`. */
  deadlineAt?: string;
  note?: string;
  prospectName?: string;
  submissionMethod?: SubmissionMethod;
  submissionTarget?: string;
  /** Sent as true only when ticked. */
  contextAttested?: boolean;
  document: File;
};

/** The multipart body: an optional field is present only when it has a value; `definition` is never sent. */
export function logFormData(input: LogInput): FormData {
  const form = new FormData();
  form.append('authority', String(input.authority));
  form.append('start_key', input.startKey);
  form.append('reference', input.reference);
  form.append('received_at', input.receivedAt);
  form.append('deadline_status', input.deadlineStatus);
  if (input.deadlineStatus === 'stated' && input.deadlineAt) form.append('deadline_at', input.deadlineAt);
  if (input.note) form.append('note', input.note);
  if (input.prospectName) form.append('prospect_name', input.prospectName);
  if (input.submissionMethod) form.append('submission_method', input.submissionMethod);
  if (input.submissionTarget) form.append('submission_target', input.submissionTarget);
  if (input.contextAttested) form.append('context_attested', 'true');
  form.append('document', input.document);
  return form;
}

export async function fetchOrganisations(): Promise<Organisation[]> {
  return (await call(liveApi.GET('/api/v1/received-bids/organisations'))).items;
}

/** One POST per call, never repeated here. The same `startKey` and input answer the original receipt. */
export function logReceivedBid(input: LogInput): Promise<LoggedBid> {
  const body = logFormData(input);
  return call(
    liveApi.POST('/api/v1/received-bids', {
      params: csrfHeader,
      // The body is multipart; the browser sets its Content-Type with the boundary.
      body: { document: '' } as never,
      bodySerializer: () => body,
      signal: AbortSignal.timeout(START_TIMEOUT_MS),
    }),
  );
}

export function fetchReceipt(caseId: string, receiptId: number): Promise<Receipt> {
  return call(liveApi.GET('/api/v1/received-bids/{case_id}/receipts/{receipt_id}', { params: { path: { case_id: caseId, receipt_id: receiptId } } }));
}

export function fetchBids(cursor?: string): Promise<BidPage> {
  return call(liveApi.GET('/api/v1/received-bids/assignments', { params: { query: { cursor } } }));
}

export function fetchAssignment(caseId: string): Promise<AssignmentRead> {
  return call(liveApi.GET('/api/v1/received-bids/{case_id}/assignment', { params: { path: { case_id: caseId } } }));
}

/** One POST per call, with no idempotency key: a caller re-reads the assignment before it ever offers another. */
export function assignPm(caseId: string, body: AssignBody): Promise<Assigned> {
  return call(
    liveApi.POST('/api/v1/received-bids/{case_id}/assignment', {
      params: { path: { case_id: caseId }, ...csrfHeader },
      body,
      signal: AbortSignal.timeout(START_TIMEOUT_MS),
    }),
  );
}
