'use client';

// CMP proof field (SCR-16, SCR-02 reconcile): the design system's FileUpload on useEvidenceUpload. A chosen file
// uploads at once; its row reads "Uploaded" only once the backend returns an evidence_id. `multiple` is where the
// form takes more than one file; the others take one (the zone returns when it is removed). The phone offers a
// photo or a file: the hidden input has no `capture`.
import { FileUpload, type FileRowState } from '@/components';

import type { EvidenceUpload, ProofFile } from './useEvidenceUpload';

function rowOf(file: ProofFile): FileRowState {
  if (file.status === 'uploading') return { key: file.key, status: 'uploading', name: file.name };
  if (file.status === 'uploaded') return { key: file.key, status: 'uploaded', name: file.name, size: file.size };
  return { key: file.key, status: 'error', name: file.name, message: file.problem ?? 'Not uploaded', retry: file.retryable ?? false, remove: true };
}

export function ProofField({ proof, hint, label = 'Proof', hideLabel, multiple }: { proof: EvidenceUpload; hint?: string; label?: string; hideLabel?: boolean; multiple?: boolean }) {
  return (
    <FileUpload
      label={label}
      hideLabel={hideLabel}
      files={proof.files.map(rowOf)}
      multiple={multiple}
      pending={proof.uploading}
      accept={[]}
      maxBytes={null}
      hint={hint}
      disabledReason={proof.available ? undefined : 'Proof can’t be uploaded for this item.'}
      onFile={proof.add}
      onRemove={(key) => proof.remove(key as number)}
      onRetry={(key) => proof.retry(key as number)}
    />
  );
}
