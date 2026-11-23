'use client';

// SCR-04 Proof box (FE-M2A-PROOF): ProofField and useEvidenceUpload on the line's case, as StepForm's
// EvidenceField hosts them. A chosen file uploads at once; its row reads "Uploaded" only once the backend returns an
// evidence_id, and only those ids are sent with the start. There is no size or type rule here: the backend's 422
// message is the only one. Until a project gives the case, the zone is closed. The uploader is keyed by
// case, so another project starts it again empty; what was uploaded stays on the old case and is never sent.
// 403 and 404 read the same: the file is dropped from the start and the drawer says proof can't be added.
import { useEffect, useId, useRef } from 'react';

import type { ApiError } from '@/api/errors';
import { FileUpload, Icon } from '@/components';
import { ProofField, useEvidenceUpload } from '@/features/response';
import '@/features/response/response.css';

import type { CaseRef } from './intake';
import { CANT_ADD, PROOF_MOVED } from './labels';
import type { Field } from './types';
import type { ProofState } from './useStartWork';

type UploaderProps = {
  field: Field;
  caseId: string;
  caseRevision: number;
  reread: () => Promise<number | undefined>;
  onState: (name: string, state: ProofState) => void;
  onSignedOut: () => void;
  onRefused: () => void;
};

function Uploader({ field, caseId, caseRevision, reread, onState, onSignedOut, onRefused }: UploaderProps) {
  // A 404 (or 401) from the upload or from Try again's re-read: the file it was for is dropped.
  const denied = useRef(false);
  const proof = useEvidenceUpload({
    caseId,
    caseRevision,
    kind: field.evidence_kind,
    reloadCaseRevision: reread,
    onAccessError: (error: ApiError) => {
      denied.current = true;
      if (error.kind === 'unauthenticated') onSignedOut();
    },
  });
  const { files, sync, remove } = proof;

  // The form's revision moved (a start's 409 re-read): carry it from now on.
  useEffect(() => {
    if (proof.caseRevision() !== caseRevision) sync(caseRevision);
    // only the form's revision matters
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseRevision, sync]);

  // 403 (the hook's sentence) and 401/404 (no sentence): drop the file and say so once, the same way for both.
  useEffect(() => {
    if (proof.uploading) return;
    const refused = files.filter((f) => (f.status === 'failed' && (f.problem === CANT_ADD || !f.problem)) || (denied.current && f.status === 'uploading'));
    denied.current = false;
    if (refused.length === 0) return;
    for (const f of refused) remove(f.key);
    onRefused();
  }, [files, onRefused, proof.uploading, remove]);

  const busy = proof.uploading || files.some((f) => f.status === 'uploading');
  const failed = files.some((f) => f.status === 'failed');
  const signature = JSON.stringify([proof.evidenceIds, files.map((f) => f.status), busy]);
  const reported = useRef(false);
  useEffect(() => {
    // The first run is the empty box: nothing changed yet.
    if (!reported.current) {
      reported.current = true;
      return;
    }
    onState(field.name, { ids: proof.evidenceIds, count: files.length, busy, failed, revision: proof.caseRevision() });
    // the signature carries everything reported
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  return (
    <>
      <ProofField proof={proof} label={field.label} multiple={field.multiple} />
      {/* The card's reason is plain text in F-09's ProofField: a failure is also announced here, as Callout announces
          a problem (role="alert", inserted with its words), and shown to sight only on the row. */}
      {files
        .filter((f) => f.status === 'failed' && f.problem && f.problem !== CANT_ADD)
        .map((f) => (
          <span key={f.key} role="alert" className="sw-announce">
            {`${f.name}: Not uploaded. ${f.problem}`}
          </span>
        ))}
    </>
  );
}

type Props = Omit<UploaderProps, 'caseId' | 'caseRevision'> & {
  /** The case and the revision to upload at; null until a project is chosen. */
  sendCase: CaseRef | null;
  readOnly: boolean;
  error: string | undefined;
  /** The help of the field before this one, drawn under the box (SCR-04-*-change). */
  movedHelp?: { id: string; text?: string };
  /** The project changed after proof was added. */
  moved: boolean;
};

/** The closed zone: no picker. */
function Unavailable({ field, text }: { field: Field; text: string }) {
  return <FileUpload label={field.label} state={{ status: 'empty' }} onFile={() => {}} onRemove={() => {}} disabledReason={text} />;
}

export function StartProof({ field, sendCase, readOnly, error, movedHelp, moved, ...uploader }: Props) {
  const id = useId();
  const box = field.restricted ? (
    <Unavailable field={field} text="Proof can’t be uploaded for this item." />
  ) : sendCase ? (
    <Uploader key={sendCase.case_id} field={field} caseId={sendCase.case_id} caseRevision={sendCase.case_revision} {...uploader} />
  ) : (
    <Unavailable field={field} text="Choose the project first." />
  );
  return (
    // A disabled fieldset locks the picker and "×" while the start is sent or unconfirmed; a 422 for this field
    // describes it, as IntakeField links a field's error.
    <fieldset
      className="psl-field sw-field sw-prooffield"
      data-field={field.name}
      disabled={readOnly}
      aria-describedby={error ? `${id}-error` : undefined}
      aria-invalid={error ? true : undefined}
    >
      {box}
      {moved && (
        <span className="psl-hint" role="status">
          {PROOF_MOVED}
        </span>
      )}
      {movedHelp?.text && (
        <span className="psl-hint" id={movedHelp.id}>
          {movedHelp.text}
        </span>
      )}
      {error && (
        <span className="psl-error" id={`${id}-error`}>
          <Icon name="warn" />
          <span>{error}</span>
        </span>
      )}
    </fieldset>
  );
}
