'use client';

// SCR-16 record the RFP outcome: Result (only the values in rfp_outcome.results, none chosen), then the fields of
// the chosen result. Reasons and "You are recording as" come from the block; a single record_as option is chosen
// without a select. Proof is required for every result, unknown included (D-60). An awarded amount that is blank
// is not sent, "Amount not known" sends unknown=true with no amount, and nothing is ever shown or sent as 0.
import { useId, type ReactNode } from 'react';

import { Button, Checkbox, DateField, TextArea, TextField } from '@/components';
import { NOTE_MAX } from '@/features/response/labels';
import { ProofField } from '@/features/response/ProofField';
import { Select, WhenField } from '@/features/response/ResponseForm';
import { Segmented } from '@/features/response/Segmented';
import type { EvidenceUpload } from '@/features/response/useEvidenceUpload';

import type { OutcomeResult, RfpOutcome } from './contract';
import { RECORD_LABELS, RESULT_LABELS } from './labels';
import { amountProblem, outcomeMissing, type OutcomeEntries } from './useOutcome';

type Props = {
  outcome: RfpOutcome;
  /** The client named in the line under the heading; the line is left out without one. */
  client: string | undefined;
  entries: OutcomeEntries;
  setEntry: <K extends keyof OutcomeEntries>(key: K, value: OutcomeEntries[K]) => void;
  proof: EvidenceUpload;
  busy: boolean;
  locked: boolean;
  phone: boolean;
  touched: boolean;
  onRecord: () => void;
  notice?: ReactNode;
};

function Amount({ entries, setEntry }: Pick<Props, 'entries' | 'setEntry'>) {
  const id = useId();
  const problem = amountProblem(entries);
  return (
    <>
      <TextField
        id={id}
        label="Awarded amount"
        inputMode="decimal"
        fieldClassName="resp-field"
        value={entries.amountUnknown ? '' : entries.amount}
        disabled={entries.amountUnknown}
        error={problem ? <span role="alert">{problem}</span> : undefined}
        aria-describedby={`${id}-hint`}
        onChange={(e) => setEntry('amount', e.target.value)}
      />
      {/* The board's hint line; "Amount not known" (not drawn) shares it so the board's rows stay in place. */}
      <div className="rfp-amountrow">
        <span id={`${id}-hint`} className="psl-hint">
          As stated in the award letter.
        </span>
        <Checkbox className="rfp-unknown" label="Amount not known" checked={entries.amountUnknown} onChange={(e) => setEntry('amountUnknown', e.target.checked)} />
      </div>
    </>
  );
}

/** F-09's note field (one line to start, the counter on the label line); no board draws it. */
function OutcomeNote({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return <TextArea label="Note" optional oneLine fieldClassName="resp-field" className="resp-note" maxLength={NOTE_MAX} limit={NOTE_MAX} value={value} onChange={(e) => onChange(e.target.value)} />;
}

function ResultFields({ outcome, entries, setEntry }: Pick<Props, 'outcome' | 'entries' | 'setEntry'>) {
  const remind = <WhenField label="Remind me on" value={entries.remind} onChange={(v) => setEntry('remind', v)} />;
  if (entries.result === 'won') return <Amount entries={entries} setEntry={setEntry} />;
  if (entries.result === 'lost') {
    return (
      <>
        {(outcome.reasons?.length ?? 0) > 0 && (
          <Segmented
            label="Main reason they gave"
            options={outcome.reasons!.map((r) => ({ value: r.value, text: r.label }))}
            value={entries.reason}
            onChange={(v) => setEntry('reason', v)}
          />
        )}
        <TextArea
          label="Lessons (what we’d do differently)"
          fieldClassName="resp-field"
          className="rfp-lessons"
          maxLength={NOTE_MAX}
          value={entries.lessons}
          onChange={(e) => setEntry('lessons', e.target.value)}
        />
      </>
    );
  }
  if (entries.result === 'pending') {
    return (
      <>
        <DateField
          label="Expected decision date"
          hint="What the client told us. Use Unknown if they didn’t say."
          fieldClassName="resp-field"
          value={entries.expected}
          onChange={(v) => setEntry('expected', v)}
        />
        {remind}
      </>
    );
  }
  if (entries.result === 'unknown') return remind;
  return null;
}

export function OutcomeForm(props: Props) {
  const { outcome, client, entries, setEntry, proof, busy, locked, phone, touched } = props;
  const line = outcomeMissing(entries, proof.evidenceIds.length);
  const ready = !line && !amountProblem(entries) && !busy && !locked && !proof.uploading && entries.note.length <= NOTE_MAX;
  const submission = outcome.submission;
  const roles = outcome.record_as;
  // The phone boards draw no "You are recording as"; it shows there only when there is a choice to make.
  const showRole = roles.length > 1 || !phone;

  const button = (
    <Button size="lg" className="resp-record rfp-record" disabled={!ready} onClick={props.onRecord}>
      {busy ? 'Recording…' : entries.result ? RECORD_LABELS[entries.result] : 'Record the outcome'}
    </Button>
  );
  const alert =
    line && !busy ? (
      touched ? (
        <div role="alert" className="resp-alert">
          {line}
        </div>
      ) : (
        <div className="resp-alert resp-alert--hint">{line}</div>
      )
    ) : null;

  const fields = (
    <>
      {!phone && client && <p className="rfp-sub">What {client} decided about our response.</p>}
      {!phone && (
        <div className="resp-field">
          <span className="resp-label">Submission</span>
          <span className="resp-static">{[submission.label, submission.delivery].filter(Boolean).join(' · ')}</span>
        </div>
      )}
      <Segmented<OutcomeResult>
        label="Result"
        options={outcome.results.map((r) => ({ value: r, text: RESULT_LABELS[r] }))}
        value={entries.result}
        onChange={(v) => setEntry('result', v)}
      />
      {entries.result && (
        <WhenField
          label={entries.result === 'unknown' ? 'Last contact with the client' : 'When you learned it'}
          value={entries.learned}
          onChange={(v) => setEntry('learned', v)}
        />
      )}
      <ResultFields outcome={outcome} entries={entries} setEntry={setEntry} />
      <ProofField proof={proof} layout="card" choose="Choose a file" />
      {showRole &&
        (roles.length === 1 ? (
          <div className="resp-field">
            <span className="resp-label">You are recording as</span>
            <span className="resp-static">{roles[0].label}</span>
            <span className="psl-hint">A role PSL allows to record outcomes</span>
          </div>
        ) : (
          <div className="resp-field">
            <Select
              label="You are recording as"
              value={entries.recordAs}
              onChange={(v) => setEntry('recordAs', v)}
              options={roles.map((r) => ({ value: r.value, text: r.label }))}
            />
            <span className="psl-hint">
              A role PSL allows to record outcomes
            </span>
          </div>
        ))}
      <OutcomeNote value={entries.note} onChange={(v) => setEntry('note', v)} />
      {props.notice}
      {phone ? (
        <>
          {alert}
          <div className="psl-actionbar resp-phonebar">{button}</div>
        </>
      ) : (
        <div className="rfp-actions">
          {alert}
          {button}
        </div>
      )}
    </>
  );

  return (
    <form className={phone ? 'resp-form resp-form--phone rfp-form' : 'resp-form rfp-form'} aria-busy={busy} onSubmit={(e) => e.preventDefault()}>
      {phone ? (
        fields
      ) : (
        <section className="psl-panel rfp-panel" aria-labelledby="rfp-outcome-head">
          <h2 id="rfp-outcome-head" className="psl-panel__head">
            Record the outcome
          </h2>
          <div className="psl-panel__body">{fields}</div>
        </section>
      )}
    </form>
  );
}
