'use client';

// The proof field of SCR-16 and the SCR-02 reconcile panel: the shared FileUpload (one drop zone that says what is
// accepted), one row for each file with its state. A file may be added while no upload is running; each upload
// carries the case revision of the one before (useEvidenceUpload). A file that failed on the network keeps its
// own Try again, which reloads the item and sends the same bytes (the shared row's Try again asks for a new file).
import { Button, FileUpload, Icon, type FileState } from '@/components';

import type { EvidenceUpload, ProofFile } from './useEvidenceUpload';

const NO_UPLOAD = 'Proof can’t be uploaded for this item.';

function stateOf(file: ProofFile): FileState {
  if (file.status === 'uploading') return { status: 'uploading', name: file.name, total: undefined };
  if (file.status === 'uploaded') return { status: 'uploaded', name: file.name, size: file.size };
  return { status: 'error', name: file.name, message: file.problem ?? 'Not uploaded' };
}

/** A file that failed on the network: the row keeps its bytes, so Try again sends the same file again. */
function RetryRow({ file, proof }: { file: ProofFile; proof: EvidenceUpload }) {
  return (
    <div className="psl-file is-error">
      <Icon name="clip" />
      <span className="psl-file__name">
        <strong>{file.name}</strong>
        <small role="status">{file.problem}</small>
      </span>
      <Button kind="text" disabled={proof.uploading} onClick={() => proof.retry(file.key)}>
        Try again
      </Button>
      <Button kind="text" onClick={() => proof.remove(file.key)} aria-label={`Remove ${file.name}`}>
        Remove
      </Button>
    </div>
  );
}

/**
 * `prompt`: the zone's words where the default does not fit (the phone offers the camera too). `single`: one file
 * only (the signed copy, the outcome's proof): once a file is there no second zone is offered. `accept`: the file
 * types the zone takes (the shared proof types by default).
 */
export function ProofField({ proof, hint, label = 'Proof', prompt, single = false, accept }: { proof: EvidenceUpload; hint?: string; label?: string; prompt?: string; single?: boolean; accept?: string[] }) {
  const empty = proof.files.length === 0;
  const noop = () => {};
  return (
    <div className="resp-field resp-proof">
      {proof.files.map((file) =>
        file.status === 'failed' && file.retryable ? (
          <RetryRow key={file.key} file={file} proof={proof} />
        ) : (
          <FileUpload
            key={file.key}
            label={<span className="cmp-sr">{`${label}: ${file.name}`}</span>}
            state={stateOf(file)}
            onFile={proof.add}
            onRemove={() => proof.remove(file.key)}
            onCancel={noop}
            accept={accept}
          />
        ),
      )}
      {!proof.uploading && !(single && !empty) && (
        <FileUpload
          label={empty ? label : 'Add another file'}
          state={{ status: 'empty' }}
          onFile={proof.add}
          onRemove={noop}
          accept={accept}
          prompt={prompt ?? (empty ? 'Drop the proof here or' : 'Drop another file here or')}
          disabledReason={proof.available ? undefined : NO_UPLOAD}
        />
      )}
      {empty && <span className="resp-drop__empty">No proof added yet</span>}
      {proof.available && hint && <span className="psl-hint">{hint}</span>}
    </div>
  );
}
