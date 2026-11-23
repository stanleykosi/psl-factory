// F-85: the shared evidence upload. An `upload_id` is a file the server holds for a case; it is NOT an evidence id. The two
// are different branded numbers so one cannot be passed for the other.
import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { PROOF_MAX_BYTES, PROOF_TYPES } from '@/components';

export type UploadId = number & { readonly __brand: 'UploadId' };
export type EvidenceId = number & { readonly __brand: 'EvidenceId' };

// The contract lists the token as a header parameter; the client's middleware sets the real one on every write.
const CSRF_HEADER = { 'X-CSRFToken': '' };

export type UploadedFile = { upload_id: UploadId; name: string; size: number; sha256: string; download_url: string };

/** The reason a file is refused before any request is sent, or null. The service stays the final rule. */
export function refuseFile(file: Pick<File, 'name' | 'size'>): string | null {
  const lower = file.name.toLowerCase();
  if (!PROOF_TYPES.some((t) => lower.endsWith(t))) return 'That file type isn’t accepted.';
  if (file.size > PROOF_MAX_BYTES) return 'That file is too large.';
  return null;
}

/** POST /cases/{case_id}/files (multipart `file`). Not retried here; the case is only ever the loaded item's. */
export async function uploadCaseFile(caseId: string, file: File): Promise<UploadedFile> {
  const refused = refuseFile(file);
  if (refused) throw new ApiError(0, 'invalid', 'refused_before_sending', refused);
  const body = new FormData();
  body.append('file', file);
  const sent = await call(
    liveApi.POST('/api/v1/cases/{case_id}/files', {
      params: { path: { case_id: caseId }, header: CSRF_HEADER },
      // The body is multipart; the browser sets its Content-Type with the boundary.
      body: { file: '' },
      bodySerializer: () => body,
    }),
  );
  return { ...sent, upload_id: sent.upload_id as UploadId };
}

/** The upload's error in the words of the row. 403 csrf_failed: the session was refreshed, the file was not sent. */
export function uploadErrorMessage(error: unknown): string {
  const e = error instanceof ApiError ? error : networkError();
  if (e.kind === 'network') return 'We couldn’t reach the server. Nothing was uploaded.';
  if (e.code === 'refused_before_sending') return e.message;
  if (e.kind === 'csrf') return 'Press upload again.';
  if (e.kind === 'too_large') return 'That file is too large.';
  if (e.kind === 'unsupported') return 'That file type isn’t accepted.';
  if (e.kind === 'invalid') return e.fields[0]?.message ?? e.message;
  if (e.kind === 'rate_limited') return 'Try again shortly.';
  if (e.kind === 'not_found') return 'This record is unavailable.';
  return e.message;
}

/** PROPOSAL (backend question 1, unconfirmed): the only route in the contract that turns an upload into an evidence id is the
 *  file-draft review. A file agent drafts the file (202), a person reviews the draft, and the review answers
 *  `reviewed_evidence_id`. Nothing calls this yet and no `role` default is chosen; null means "not evidence yet" and stays null. */
export type FileAgentRole = 'A01' | 'A02' | 'A03' | 'A04' | 'A05' | 'A06' | 'A07' | 'A08';
export type ReviewedDraft = { draft: string; summary: string; gaps: string[]; note: string };

export async function fileToEvidence(caseId: string, uploadId: UploadId, role: FileAgentRole, review: (job: { job_id: number; draft: unknown }) => Promise<ReviewedDraft>): Promise<EvidenceId | null> {
  const job = await call(
    liveApi.POST('/api/v1/cases/{case_id}/files/{upload_id}/drafts', { params: { path: { case_id: caseId, upload_id: uploadId }, header: CSRF_HEADER }, body: { role } }),
  );
  const reviewed = await review({ job_id: job.job_id, draft: job.draft });
  const done = await call(
    liveApi.POST('/api/v1/cases/{case_id}/file-drafts/{job_id}/review', { params: { path: { case_id: caseId, job_id: job.job_id }, header: CSRF_HEADER }, body: reviewed }),
  );
  return done.reviewed_evidence_id === null ? null : (done.reviewed_evidence_id as EvidenceId);
}
