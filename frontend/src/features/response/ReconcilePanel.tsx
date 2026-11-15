'use client';

// SCR-02 awaiting reconciliation: "Confirm what happened". Shown only when the item carries `reconcile` and
// the backend lists "reconcile" in allowed_actions; otherwise nothing renders and nothing is sent. The answer
// goes through E-WORK-ACTION once per press; the page then reloads. Nothing here resends anything: a resend,
// if the answer allows one, is the backend's step.
import { useCallback, useId, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';
import { Button, Callout, Panel, RadioGroup, useIsPhone, VisuallyHidden } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';
import { NoAccessState } from '@/features/work-item/WorkItemStates';

import { getWorkItem, workAction } from './api';
import type { Reconcile, ReconcileOutcome, ResponseWorkItem, WorkActionBody } from './contract';
import { checksSentence, outcomeWords, plural, RESPONSE_LABELS, sentence } from './labels';
import { ProofField } from './ProofField';
import { reloadPage } from './reload';
import { useEvidenceUpload } from './useEvidenceUpload';

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
  // Phone: the pinned button is pressable before a choice; a press then asks for one and shows the options.
  const [asked, setAsked] = useState(false);
  const options = useRef<HTMLDivElement>(null);
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
  // The phone bar is pinned while the options may still be below the fold, so it does not look disabled there.
  const askFirst = phone && outcome === null && !locked;

  const ask = () => {
    setAsked(true);
    // Focus scrolls the first option into view.
    options.current?.querySelector('input')?.focus();
  };

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

  const outcomeOptions = reconcile.outcomes.map((value) => {
    const words = outcomeWords(value, reconcile);
    return { value, label: words.lead, detail: words.rest };
  });
  const body = (
    <div className="resp-reconcile__body" aria-busy={status.kind === 'busy'}>
      {phone ? (
        <Callout kind="warning">
          {reconcile.checks ? `No receipt found after ${plural(reconcile.checks.count, 'check')}. ` : ''}Confirm what happened before anything is
          resent.
        </Callout>
      ) : (
        <p className="resp-plain">
          {checks ? `${checks} ` : ''}The factory won&rsquo;t resend until a person confirms what happened, so the client is never invoiced
          twice.
        </p>
      )}
      <div ref={options}>
        <RadioGroup
          legend={<VisuallyHidden>Confirm what happened</VisuallyHidden>}
          name={`${headId}-outcome`}
          cards
          className="resp-options"
          options={outcomeOptions.map((o) => ({ ...o, disabledReason: undefined }))}
          value={outcome ?? undefined}
          onChange={(value) => !locked && setOutcome(value as ReconcileOutcome)}
        />
      </div>
      {needsProof && <ProofField proof={proof} />}
      {askFirst && asked && (
        <div role="alert" className="resp-alert">
          Choose what happened to continue.
        </div>
      )}
      {status.kind === 'problem' && <Callout kind="problem">{status.message}</Callout>}
      {(status.kind === 'stale' || status.kind === 'uncertain') && (
        <div role="alert">
          <Callout kind="warning">
            {status.kind === 'stale'
              ? 'This item changed. Reload it to see the latest.'
              : 'We couldn’t confirm your answer. Reload the work item to see whether it was recorded.'}{' '}
            <Button kind="secondary" size="sm" onClick={() => reloadPage()}>
              Reload the work item
            </Button>
          </Callout>
        </div>
      )}
      {status.kind === 'done' && <Callout kind="success">Recorded. Reloading the work item…</Callout>}
      <div className="psl-actionbar resp-actionbar">
        <Button
          size="lg"
          block
          disabled={!ready && !askFirst && status.kind !== 'busy'}
          busy={status.kind === 'busy'}
          busyLabel={RESPONSE_LABELS.busy}
          onClick={askFirst ? ask : () => void submit()}
        >
          Record and continue
        </Button>
      </div>
      <p className="resp-footnote">Your choice is recorded with your name.{resendNote}</p>
    </div>
  );

  return (
    <div className="work-column">
      {phone ? (
        <aside className="resp-reconcile" aria-label="Confirm what happened">
          {body}
        </aside>
      ) : (
        <Panel kind="decide" head="Confirm what happened" className="resp-reconcile">
          {body}
        </Panel>
      )}
    </div>
  );
}
