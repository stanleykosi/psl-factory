'use client';

// CMP proof field (SCR-16, SCR-02 reconcile): the uploaded files and one button that opens the file picker.
// Layouts follow the boards: "drop" is the dashed area with chips, "phone" the large dashed button, "card" the
// SOW board's uploaded-file card. The hidden file input has no `capture`, so the phone offers camera or files.
import { useId, useRef } from 'react';

import { fileSize } from './labels';
import type { EvidenceUpload, ProofFile } from './useEvidenceUpload';

type Layout = 'drop' | 'phone' | 'card';

const BUTTON_TEXT: Record<Layout, string> = {
  drop: 'Add another file',
  phone: 'Take a photo or choose a file',
  card: 'Choose the signed copy',
};

function PaperclipIcon() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" className="resp-clip">
      <path d="M12.5 5.5L6.5 11.5a1.8 1.8 0 0 0 2.5 2.5l6.5-6.5a3.5 3.5 0 0 0-5-5L4 9a5 5 0 0 0 7 7l4.5-4.5" />
    </svg>
  );
}

function FileProblem({ file, proof }: { file: ProofFile; proof: EvidenceUpload }) {
  if (!file.problem) return null;
  return (
    <span className="resp-chip__problem">
      {file.problem}
      {file.retryable && (
        <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" disabled={proof.uploading} onClick={() => proof.retry(file.key)}>
          Try again
        </button>
      )}
    </span>
  );
}

function Chip({ file, proof }: { file: ProofFile; proof: EvidenceUpload }) {
  return (
    <span className={file.problem ? 'resp-chip resp-chip--problem' : 'resp-chip'}>
      <span className="resp-chip__name">
        {file.name} · {fileSize(file.size)}
        {file.status === 'uploading' && <span className="resp-chip__state"> · Uploading…</span>}
      </span>
      {file.status !== 'uploading' && (
        <button type="button" className="resp-chip__remove" aria-label={`Remove ${file.name}`} onClick={() => proof.remove(file.key)}>
          <span aria-hidden="true">×</span>
        </button>
      )}
      <FileProblem file={file} proof={proof} />
    </span>
  );
}

function Card({ file, proof }: { file: ProofFile; proof: EvidenceUpload }) {
  const state = file.status === 'uploading' ? 'Uploading…' : file.status === 'uploaded' ? 'Uploaded' : 'Not uploaded';
  return (
    <div className={file.problem ? 'resp-card resp-card--problem' : 'resp-card'}>
      <PaperclipIcon />
      <span className="resp-card__text">
        <strong>{file.name}</strong>
        <span className="resp-card__meta">
          {state} · {fileSize(file.size)}
        </span>
        <FileProblem file={file} proof={proof} />
      </span>
      {file.status !== 'uploading' && (
        <button type="button" className="resp-chip__remove" aria-label={`Remove ${file.name}`} onClick={() => proof.remove(file.key)}>
          <span aria-hidden="true">×</span>
        </button>
      )}
    </div>
  );
}

export function ProofField({ proof, hint, layout = 'drop', label = 'Proof' }: { proof: EvidenceUpload; hint?: string; layout?: Layout; label?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const labelId = useId();
  const hintId = useId();
  const disabled = !proof.available || proof.uploading;
  const shownHint = proof.available ? hint : 'Proof can’t be uploaded for this item.';
  const empty = proof.files.length === 0;
  // The phone and card layouts leave proof_hint out (as the boards do) but keep the can't-upload hint.
  const hintShown = shownHint !== undefined && (layout === 'drop' || !proof.available);

  const picker = (
    <>
      <input
        ref={input}
        type="file"
        hidden
        aria-labelledby={labelId}
        disabled={!proof.available}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (file) proof.add(file);
        }}
      />
      <button
        type="button"
        className={layout === 'phone' && empty ? 'resp-filebtn resp-filebtn--phone' : 'resp-filebtn'}
        aria-describedby={hintShown ? hintId : undefined}
        disabled={disabled}
        onClick={() => input.current?.click()}
      >
        {empty || layout === 'drop' ? BUTTON_TEXT[layout] : BUTTON_TEXT.drop}
      </button>
    </>
  );

  return (
    <div className="resp-field" role="group" aria-labelledby={labelId}>
      <span id={labelId} className="resp-label">
        {label}
      </span>
      {layout === 'drop' && (
        <div className={proof.available ? 'resp-drop' : 'resp-drop is-disabled'}>
          {empty && <span className="resp-drop__empty">No proof added yet</span>}
          {proof.files.map((f) => (
            <Chip key={f.key} file={f} proof={proof} />
          ))}
          {picker}
          {hintShown && (
            <span id={hintId} className="psl-hint">
              {shownHint}
            </span>
          )}
        </div>
      )}
      {layout === 'phone' && (
        <>
          {proof.files.map((f) => (
            <Chip key={f.key} file={f} proof={proof} />
          ))}
          {picker}
          {hintShown && (
            <span id={hintId} className="psl-hint">
              {shownHint}
            </span>
          )}
        </>
      )}
      {layout === 'card' && (
        <>
          {proof.files.map((f) => (
            <Card key={f.key} file={f} proof={proof} />
          ))}
          {empty && picker}
          {hintShown && (
            <span id={hintId} className="psl-hint">
              {shownHint}
            </span>
          )}
        </>
      )}
    </div>
  );
}
