'use client';

// SCR-16 team input (F-18): which team gave input, its estimate when the API says the team needs one, what it
// gave, the proof and when it arrived. Teams, the estimate need and who may have given it come only from
// tasks[].response; a team the API does not return is never shown. "Who gave it", the attestation and the note
// are not drawn on the boards but the request needs them (as F-09's forms keep them).
import { useId } from 'react';

import { Checkbox, TextField } from '@/components';

import { listWords, responderText } from './labels';
import { ProofField } from './ProofField';
import { Segmented } from './Segmented';
import { Note, RecordRow, Select, WhenField, type FormProps } from './ResponseForm';
import { estimateShown, missingLine } from './useResponse';

function Teams({ response, entries, setEntry }: Pick<FormProps, 'response' | 'entries' | 'setEntry'>) {
  return (
    <Segmented
      label="Team"
      className="resp-teams"
      options={(response.teams ?? []).map((t) => ({
        value: t.key,
        text: t.name,
        name: `${t.name}, ${t.given ? 'given' : 'missing'}`,
        className: t.given ? 'is-given' : undefined,
      }))}
      value={entries.team}
      onChange={(v) => setEntry('team', v)}
    />
  );
}

function Estimate({ response, entries, setEntry }: Pick<FormProps, 'response' | 'entries' | 'setEntry'>) {
  const id = useId();
  const needing = (response.teams ?? []).filter((t) => t.estimate_needed).map((t) => t.name);
  return (
    <TextField
      id={id}
      label="Estimate (person-days)"
      type="number"
      inputMode="decimal"
      min="0"
      step="0.5"
      fieldClassName="resp-field"
      value={entries.estimate}
      hint={`Needed for the costing sheet.${needing.length > 0 ? ` Shown for ${listWords(needing)}.` : ''}`}
      onChange={(e) => setEntry('estimate', e.target.value)}
    />
  );
}

export function TeamInputForm(props: FormProps & { heading: boolean }) {
  const { response, entries, setEntry, proof, busy, phone, heading } = props;
  const line = missingLine(entries, response, proof.evidenceIds.length);
  const ready = !line && !busy && !props.locked && !proof.uploading;
  const responders = response.responders;

  const attest = (
    <Checkbox className="resp-attest" label="I confirm this input came from the team named above." checked={entries.attested} onChange={(e) => setEntry('attested', e.target.checked)} />
  );
  const fields = (
    <>
      {/* The board's line under the panel head (no board draws a field for it; the spec is silent, so the board's words). */}
      {heading && <p className="resp-teamsub">For the RFP response and the costing sheet.</p>}
      <Teams response={response} entries={entries} setEntry={setEntry} />
      {response.blocking && <p className="resp-blocking">{response.blocking}</p>}
      {responders.length > 1 && (
        <Select
          label="Who gave it"
          value={entries.who}
          onChange={(v) => setEntry('who', v)}
          options={responders.map((r) => ({ value: r.id, text: responderText(r, response.variant) }))}
        />
      )}
      {estimateShown(entries, response) && <Estimate response={response} entries={entries} setEntry={setEntry} />}
      <TextField label="What they gave" fieldClassName="resp-field" value={entries.what} onChange={(e) => setEntry('what', e.target.value)} />
      {/*
        No board draws the attestation or the note. On desktop they share the proof and Received rows (as F-09's SOW
        form), so the board's rows keep their place; on the phone they follow the board's rows.
      */}
      <div className={phone ? 'resp-stack' : 'resp-row resp-row--proof'}>
        <ProofField proof={proof} />
        {!phone && attest}
      </div>
      <div className={phone ? 'resp-stack' : 'resp-row'}>
        <WhenField label="Received" value={entries.when} onChange={(v) => setEntry('when', v)} />
        <Note entries={entries} setEntry={setEntry} />
      </div>
      {phone && attest}
      <RecordRow props={props} ready={ready} line={line} />
    </>
  );

  return (
    <form className={phone ? 'resp-form resp-form--phone resp-form--team' : 'resp-form resp-form--team'} aria-busy={busy} onSubmit={(e) => e.preventDefault()}>
      {heading ? (
        <section className="psl-panel resp-teampanel" aria-labelledby="resp-team-head">
          <h2 id="resp-team-head" className="psl-panel__head">
            Record team input
          </h2>
          <div className="psl-panel__body">{fields}</div>
        </section>
      ) : (
        fields
      )}
    </form>
  );
}
