'use client';

// SCR-48 record (F-40): the PM records Support's reply to the handover, with proof. Support never logs in, so
// the record keeps the PM's name. Who replied, what Support said and the proof come only from tasks[].response;
// the gaps box is a PROPOSAL (G-48-1, contract mock only): one gap per non-blank line.
import { useId } from 'react';

import { TextArea, VisuallyHidden } from '@/components';

import { responderText } from './labels';
import { ProofField } from './ProofField';
import { Actions, Attest, RecordRow, Select, WhenField, type FormProps } from './ResponseForm';
import { gapLines, missingLine } from './useResponse';

export const GAPS_PROBLEM = 'Add at least one gap.';

export function SupportHandoverForm(props: FormProps & { gapsProblem?: boolean }) {
  const { response, entries, setEntry, proof, busy, locked, gapsProblem } = props;
  const gapsId = useId();
  const line = missingLine(entries, response, proof.evidenceIds.length);
  const ready = !line && !busy && !locked && !proof.uploading;
  const responders = response.responders;
  const gaps = entries.action === 'changes_requested';
  const next = response.next?.length ? (
    <div className="resp-nextline">
      <strong>What happens next:</strong> {response.next.join(' ')}
    </div>
  ) : null;

  return (
    <form className={props.phone ? 'resp-form resp-form--phone resp-form--handover' : 'resp-form resp-form--handover'} aria-busy={busy} onSubmit={(e) => e.preventDefault()}>
      {/* SCR-48 record: one field, who replied and when (UI-1-3); the date-time keeps its own accessible name */}
      <div className="resp-field" role="group" aria-labelledby={`${gapsId}-replied`}>
        <span id={`${gapsId}-replied`} className="resp-label resp-label--strong">
          Support replied
        </span>
        <div className="resp-replied">
          {responders.length === 1 ? (
            <span className="resp-static">{responderText(responders[0], response.variant)}</span>
          ) : (
            <Select label="Who replied" hideLabel value={entries.who} onChange={(v) => setEntry('who', v)} options={responders.map((r) => ({ value: r.id, text: responderText(r, response.variant) }))} />
          )}
          <WhenField label="When they replied" hideLabel value={entries.when} onChange={(v) => setEntry('when', v)} />
        </div>
      </div>
      <Actions response={response} entries={entries} setEntry={setEntry} label="What Support said" />
      {gaps && (
        <div className="resp-field">
          <TextArea
            id={`${gapsId}-gaps`}
            label="Gaps"
            className="resp-gaps"
            rows={3}
            value={entries.gaps}
            hint={<VisuallyHidden>One gap per line.{gapLines(entries.gaps).length > 0 && ` ${gapLines(entries.gaps).length} so far.`}</VisuallyHidden>}
            error={gapsProblem ? <span role="alert">{GAPS_PROBLEM}</span> : undefined}
            onChange={(e) => setEntry('gaps', e.target.value)}
          />
        </div>
      )}
      <ProofField proof={proof} layout="card" choose="Choose a file" label="Proof of the reply" hideLabel />
      <Attest entries={entries} setEntry={setEntry} short />
      {next}
      <RecordRow props={props} ready={ready} line={line} />
      {response.intro && <p className="resp-footnote">{response.intro}</p>}
    </form>
  );
}
