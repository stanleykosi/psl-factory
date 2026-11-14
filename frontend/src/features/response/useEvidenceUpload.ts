'use client';

// Proof goes up first (E-EVIDENCE-UPLOAD), one file per upload, the moment it is chosen. Each upload carries the
// case revision returned by the previous one (else the item's). Nothing retries on its own: a failed upload
// waits for a deliberate Try again, which reloads the item for the current case revision before it uploads.
// Evidence is append-only, so removing a file only drops it from what is sent; the proof stays on the case.
import { useCallback, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';

import { uploadEvidence } from './api';

export type ProofFile = {
  key: number;
  name: string;
  size: number;
  status: 'uploading' | 'uploaded' | 'failed';
  evidenceId?: string;
  problem?: string;
  /** Network or server failure: the chip offers Try again. */
  retryable?: boolean;
};

type Options = {
  caseId: string | undefined;
  /** The item's case_revision. */
  caseRevision: number | undefined;
  kind: string | undefined;
  /** Re-reads the item and returns its case_revision. */
  reloadCaseRevision: () => Promise<number | undefined>;
  /** 401 or 404: the page or panel shows the signed-out or no-access state. */
  onAccessError: (error: ApiError) => void;
};

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result ?? '');
      resolve(url.slice(url.indexOf(',') + 1));
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function useEvidenceUpload({ caseId, caseRevision, kind, reloadCaseRevision, onAccessError }: Options) {
  const [files, setFiles] = useState<ProofFile[]>([]);
  const nextKey = useRef(1);
  // The case revision returned by the last upload or reload; undefined means "use the item's".
  const revision = useRef<number | undefined>(undefined);
  // The File behind each chip, kept so Try again can send the same bytes.
  const sources = useRef(new Map<number, File>());
  // One upload at a time, so each one carries the revision the previous one returned.
  const busy = useRef(false);
  const [uploading, setUploading] = useState(false);

  const available = Boolean(caseId && caseRevision && kind);
  const update = (key: number, patch: Partial<ProofFile>) => setFiles((fs) => fs.map((f) => (f.key === key ? { ...f, ...patch } : f)));

  const send = useCallback(
    async (key: number, file: File) => {
      if (!caseId || !kind) return;
      const current = revision.current ?? caseRevision;
      if (!current) return;
      try {
        const content = await readBase64(file);
        const result = await uploadEvidence(caseId, { kind, filename: file.name, content_base64: content, case_revision: current });
        revision.current = result.case_revision;
        update(key, { status: 'uploaded', evidenceId: result.evidence_id, problem: undefined, retryable: false });
      } catch (error) {
        const apiError = asApiError(error);
        if (apiError.kind === 'unauthenticated' || apiError.kind === 'not_found') {
          update(key, { status: 'failed' });
          onAccessError(apiError);
          return;
        }
        if (apiError.kind === 'forbidden') {
          update(key, { status: 'failed', problem: 'You can’t add proof to this item.' });
          return;
        }
        if (apiError.kind === 'invalid') {
          update(key, { status: 'failed', problem: apiError.message });
          return;
        }
        if (apiError.kind === 'stale') {
          update(key, { status: 'failed', problem: 'This item changed. Add the file again.' });
          try {
            revision.current = await reloadCaseRevision();
          } catch {
            // The next upload or Try again reads the item again.
          }
          return;
        }
        update(key, { status: 'failed', problem: 'Couldn’t upload. Try again.', retryable: true });
      }
    },
    [caseId, caseRevision, kind, onAccessError, reloadCaseRevision],
  );

  const run = useCallback(
    async (key: number, file: File, reloadFirst: boolean) => {
      busy.current = true;
      setUploading(true);
      try {
        if (reloadFirst) {
          try {
            revision.current = await reloadCaseRevision();
          } catch (error) {
            const apiError = asApiError(error);
            if (apiError.kind === 'unauthenticated' || apiError.kind === 'not_found') onAccessError(apiError);
            else update(key, { status: 'failed', problem: 'Couldn’t upload. Try again.', retryable: true });
            return;
          }
        }
        await send(key, file);
      } finally {
        busy.current = false;
        setUploading(false);
      }
    },
    [send, reloadCaseRevision, onAccessError],
  );

  const add = useCallback(
    (file: File) => {
      if (!available || busy.current) return;
      const key = nextKey.current++;
      sources.current.set(key, file);
      setFiles((fs) => [...fs, { key, name: file.name, size: file.size, status: 'uploading' }]);
      void run(key, file, false);
    },
    [available, run],
  );

  /** Try again on a chip: reload the item, then upload the same file with the current case revision. */
  const retry = useCallback(
    (key: number) => {
      const file = sources.current.get(key);
      if (!file || busy.current) return;
      update(key, { status: 'uploading', problem: undefined, retryable: false });
      void run(key, file, true);
    },
    [run],
  );

  const remove = useCallback((key: number) => {
    sources.current.delete(key);
    setFiles((fs) => fs.filter((f) => f.key !== key));
  }, []);

  /** After the owner reloads the item: carry the reloaded case_revision from now on. */
  const sync = useCallback((reloaded: number | undefined) => {
    revision.current = reloaded;
  }, []);

  const evidenceIds = files.flatMap((f) => (f.status === 'uploaded' && f.evidenceId ? [f.evidenceId] : []));

  return {
    files,
    available,
    uploading,
    evidenceIds,
    /** The case_revision to send with the write that follows: the last upload's, else the item's. */
    caseRevision: () => revision.current ?? caseRevision,
    sync,
    add,
    retry,
    remove,
  };
}

export type EvidenceUpload = ReturnType<typeof useEvidenceUpload>;
