'use client';

// SCR-16 record the RFP outcome: Result (only the values in rfp_outcome.results, none chosen), then the fields of
// the chosen result. Reasons and "You are recording as" come from the block; a single record_as option is chosen
// without a select. Proof is required for every result, unknown included (D-60). An awarded amount that is blank
// is not sent, "Amount not known" sends unknown=true with no amount, and nothing is ever shown or sent as 0.
import { useId, type ReactNode } from 'react';

import { Button, DateField, MoneyField, Panel, Segmented, TextArea } from '@/components';
import { NOTE_MAX } from '@/features/response/labels';
import { ProofField } from '@/features/response/ProofField';
import { Select, WhenField } from '@/features/response/ResponseForm';
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

/** The awarded amount: blank is not sent, "Mark as unknown" sends unknown with no amount, and nothing is ever shown as 0. */
function Amount({ entries, setEntry }: Pick<Props, 'entries' | 'setEntry'>) {
  const problem = amountProblem(entries);
  return (
    <MoneyField
      label="Awarded amount"
      allowUnknown
      value={entries.amountUnknown ? null : entries.amount}
      error={problem ?? undefined}
      hint="As stated in the award letter."
      fieldClassName="resp-field"
      onChange={(value) => {
        if (value === null) {
          setEntry('amountUnknown', true);
          setEntry('amount', '');
        } else {
          setEntry('amountUnknown', false);
          setEntry('amount', value);
        }
      }}
    />
  );
}

/** F-09's note field (a limit and the counter under the box); no board draws it. */
function OutcomeNote({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return <TextArea label="Note" optional limit={NOTE_MAX} value={value} onChange={(e) => onChange(e.target.value)} fieldClassName="resp-field" />;
}

function ResultFields({ outcome, entries, setEntry }: Pick<Props, 'outcome' | 'entries' | 'setEntry'>) {
  const reasonId = useId();
  const remind = <WhenField label="Remind me on" value={entries.remind} onChange={(v) => setEntry('remind', v)} />;
  if (entries.result === 'won') return <Amount entries={entries} setEntry={setEntry} />;
  if (entries.result === 'lost') {
    return (
      <>
        {(outcome.reasons?.length ?? 0) > 0 && (
          <div className="resp-field">
            <span id={reasonId} className="resp-label">
              Main reason they gave
            </span>
            <Segmented
              labelledBy={reasonId}
              options={outcome.reasons!.map((r) => ({ value: r.value, label: r.label }))}
              value={entries.reason || undefined}
              onChange={(v) => setEntry('reason', v)}
            />
          </div>
        )}
        <TextArea
          label="Lessons (what we’d do differently)"
          limit={NOTE_MAX}
          className="rfp-lessons"
          fieldClassName="resp-field"
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
          value={entries.expected}
          onChange={(iso) => setEntry('expected', iso)}
          fieldClassName="resp-field"
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
    <Button size="lg" className="resp-record rfp-record" disabled={!ready && !busy} busy={busy} busyLabel="Recording…" onClick={props.onRecord}>
      {entries.result ? RECORD_LABELS[entries.result] : 'Record the outcome'}
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
          <span className="psl-label">Submission</span>
          <span className="resp-static">{[submission.label, submission.delivery].filter(Boolean).join(' · ')}</span>
        </div>
      )}
      <div className="resp-field">
        <span id="rfp-result-label" className="resp-label">
          Result
        </span>
        <Segmented<OutcomeResult>
          labelledBy="rfp-result-label"
          phone={phone}
          options={outcome.results.map((r) => ({ value: r, label: RESULT_LABELS[r] }))}
          value={entries.result || undefined}
          onChange={(v) => setEntry('result', v)}
        />
      </div>
      {entries.result && (
        <WhenField
          label={entries.result === 'unknown' ? 'Last contact with the client' : 'When you learned it'}
          value={entries.learned}
          onChange={(v) => setEntry('learned', v)}
        />
      )}
      <ResultFields outcome={outcome} entries={entries} setEntry={setEntry} />
      <ProofField proof={proof} prompt={phone ? "Take a photo or" : undefined} single />
      {showRole &&
        (roles.length === 1 ? (
          <div className="resp-field">
            <span className="psl-label">You are recording as</span>
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
        <Panel head="Record the outcome" className="rfp-panel">
          {fields}
        </Panel>
      )}
    </form>
  );
}
