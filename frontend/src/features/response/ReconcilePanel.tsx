'use client';

// SCR-02 awaiting reconciliation: "Confirm what happened". Shown only when the item carries `reconcile` and
// the backend lists "reconcile" in allowed_actions; otherwise nothing renders and nothing is sent. The answer
// goes through E-WORK-ACTION once per press; the page then reloads. Nothing here resends anything: a resend,
// if the answer allows one, is the backend's step.
import { useCallback, useId, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';
import { SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { NoAccessState } from '@/features/work-item/WorkItemStates';

import { getWorkItem, workAction } from './api';
import type { Reconcile, ReconcileOutcome, ResponseWorkItem, WorkActionBody } from './contract';
import { checksSentence, outcomeWords, plural, RESPONSE_LABELS, sentence } from './labels';
import { ProofField } from './ProofField';
import { reloadPage } from './reload';
import { useEvidenceUpload } from './useEvidenceUpload';
import { useIsPhone } from './usePhone';

import './response.css';

type Status =
  | { kind: 'idle' }
  | { kind: 'busy' }
  | { kind: 'done' }
  | { kind: 'problem'; message: string }
  | { kind: 'stale' }
  | { kind: 'uncertain' };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

export function ReconcilePanel({ id, item }: { id: string; item: ResponseWorkItem }) {
  const reconcile = item.reconcile;
  if (!reconcile || !item.allowed_actions?.includes('reconcile')) return null;
  return <ReconcileForm id={id} item={item} reconcile={reconcile} />;
}

function ReconcileForm({ id, item, reconcile }: { id: string; item: ResponseWorkItem; reconcile: Reconcile }) {
  const phone = useIsPhone();
  const headId = useId();
  const [outcome, setOutcome] = useState<ReconcileOutcome | null>(null);
  const [status, setStatus] = useState<Status>({ kind: 'idle' });
  const [accessError, setAccessError] = useState<ApiError | null>(null);
  // One write at a time, checked synchronously so a double click cannot send two answers.
  const writing = useRef(false);

  const reloadCaseRevision = useCallback(async () => (await getWorkItem(id)).case_revision, [id]);
  const proof = useEvidenceUpload({
    caseId: item.case_id,
    caseRevision: item.case_revision,
    kind: reconcile.evidence_kind,
    reloadCaseRevision,
    onAccessError: setAccessError,
  });

  if (accessError?.kind === 'unauthenticated') {
    return (
      <div className="work-column">
        <SignedOutState pathname={`/work/${encodeURIComponent(id)}`} />
      </div>
    );
  }
  if (accessError) {
    return (
      <div className="work-column">
        <NoAccessState />
      </div>
    );
  }

  const locked = status.kind === 'busy' || status.kind === 'done' || status.kind === 'stale' || status.kind === 'uncertain';
  const needsProof = outcome === 'delivered';
  const ready = outcome !== null && !locked && !proof.uploading && (!needsProof || proof.evidenceIds.length > 0);

  const submit = async () => {
    if (writing.current || !ready || !outcome) return;
    writing.current = true;
    setStatus({ kind: 'busy' });
    const body: WorkActionBody = { expected_revision: item.revision, action: 'reconcile', outcome };
    if (outcome === 'delivered') {
      body.evidence_id = proof.evidenceIds[0];
      const caseRevision = proof.caseRevision();
      if (caseRevision !== undefined) body.case_revision = caseRevision;
    }
    try {
      await workAction(id, body);
      setStatus({ kind: 'done' });
      reloadPage();
    } catch (error) {
      const apiError = asApiError(error);
      if (apiError.kind === 'unauthenticated' || apiError.kind === 'not_found') setAccessError(apiError);
      else if (apiError.kind === 'forbidden' || apiError.kind === 'invalid') setStatus({ kind: 'problem', message: apiError.message });
      else if (apiError.kind === 'stale') setStatus({ kind: 'stale' });
      // Network or server: the answer may or may not be recorded, so it is never sent again from here.
      else setStatus({ kind: 'uncertain' });
    } finally {
      writing.current = false;
    }
  };

  const checks = checksSentence(reconcile.checks);
  const resendNote = reconcile.resend_note ? ` ${sentence(reconcile.resend_note)}` : '';

  return (
    <div className="work-column">
      <section className="resp-reconcile" aria-labelledby={phone ? undefined : headId} aria-label={phone ? 'Confirm what happened' : undefined}>
        {!phone && (
          <h2 id={headId} className="resp-reconcile__head">
            Confirm what happened
          </h2>
        )}
        <div className="resp-reconcile__body" aria-busy={status.kind === 'busy'}>
          {phone ? (
            <div className="psl-callout psl-callout--warning">
              <WarningIcon />
              <span>
                {reconcile.checks ? `No receipt found after ${plural(reconcile.checks.count, 'check')}. ` : ''}Confirm what happened before anything
                is resent.
              </span>
            </div>
          ) : (
            <p className="resp-plain">
              {checks ? `${checks} ` : ''}The factory won&rsquo;t resend until a person confirms what happened, so the client is never invoiced
              twice.
            </p>
          )}
          <div role="radiogroup" aria-label="Confirm what happened" className="resp-options">
            {reconcile.outcomes.map((value) => {
              const words = outcomeWords(value, reconcile);
              return (
                <label key={value} className="resp-option">
                  <input
                    type="radio"
                    name={`${headId}-outcome`}
                    value={value}
                    checked={outcome === value}
                    disabled={locked}
                    onChange={() => setOutcome(value)}
                  />
                  <span>
                    <strong>{words.lead}</strong>
                    {words.rest ? ` ${words.rest}` : ''}
                  </span>
                </label>
              );
            })}
          </div>
          {needsProof && <ProofField proof={proof} />}
          {status.kind === 'problem' && (
            <div className="psl-callout psl-callout--problem" role="alert">
              <WarningIcon />
              <span>{status.message}</span>
            </div>
          )}
          {(status.kind === 'stale' || status.kind === 'uncertain') && (
            <div className="psl-callout psl-callout--warning resp-retry" role="alert">
              <WarningIcon />
              <span>
                {status.kind === 'stale'
                  ? 'This item changed. Reload it to see the latest.'
                  : 'We couldn’t confirm your answer. Reload the work item to see whether it was recorded.'}
              </span>
              <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" onClick={() => reloadPage()}>
                Reload the work item
              </button>
            </div>
          )}
          {status.kind === 'done' && (
            <p className="psl-callout psl-callout--success" role="status">
              <span>Recorded. Reloading the work item…</span>
            </p>
          )}
          <div className="psl-actionbar resp-actionbar">
            <button type="button" className="psl-btn psl-btn--lg psl-btn--block" disabled={!ready} onClick={() => void submit()}>
              {status.kind === 'busy' ? RESPONSE_LABELS.busy : 'Record and continue'}
            </button>
          </div>
          <p className="resp-footnote">Your choice is recorded with your name.{resendNote}</p>
        </div>
      </section>
    </div>
  );
}
