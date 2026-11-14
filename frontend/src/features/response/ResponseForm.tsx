'use client';

// SCR-16 forms: client_response (pickers, pills, proof chips) and sow_signature (the "Signature" panel). Every
// option comes from tasks[].response; with exactly one responder, version or channel it is chosen, an action
// never is. Record stays off until everything the API asks for is there, and while a write is in flight.
import { useId, type ReactNode } from 'react';

import { formatWat } from '@/features/work-item/labels';

import type { ResponseTask, TaskResponse } from './contract';
import { AGENT_LABELS, NOTE_MAX, RESPONSE_LABELS, responderText } from './labels';
import { ProofField } from './ProofField';
import { missingLine, offeredActions, type Entries } from './useResponse';
import type { EvidenceUpload } from './useEvidenceUpload';

export type FormProps = {
  task: ResponseTask;
  response: TaskResponse;
  entries: Entries;
  setEntry: <K extends keyof Entries>(key: K, value: Entries[K]) => void;
  proof: EvidenceUpload;
  busy: boolean;
  /** Record is off whatever the entries (uncertain effect, reload failed). */
  locked: boolean;
  phone: boolean;
  /** The person has changed something: the missing-choices line becomes an alert. */
  touched: boolean;
  onRecord: () => void;
  /** Callouts that belong just above Record (422 message, claim warning). */
  notice?: ReactNode;
};

const CHOOSE = 'Choose…';

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; text: string }[] }) {
  return (
    <label className="resp-field">
      <span className="resp-label">{label}</span>
      <select className="psl-input resp-select" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.length !== 1 && <option value="">{CHOOSE}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.text}
          </option>
        ))}
      </select>
    </label>
  );
}

function WhenField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="resp-field">
      <span className="resp-label">{label}</span>
      <input type="datetime-local" className="psl-input" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function ChannelSelect({ response, entries, setEntry }: Pick<FormProps, 'response' | 'entries' | 'setEntry'>) {
  const channels = response.channels ?? [];
  // A single channel is sent without a control (it is the only one the API offers).
  if (channels.length < 2) return null;
  return (
    <Select
      label="How they responded"
      value={entries.channel}
      onChange={(v) => setEntry('channel', v)}
      options={channels.map((c) => ({ value: c.value, text: c.label }))}
    />
  );
}

function Actions({ response, entries, setEntry, segmented }: Pick<FormProps, 'response' | 'entries' | 'setEntry'> & { segmented: boolean }) {
  const labelId = useId();
  return (
    <div className="resp-field">
      <span id={labelId} className="resp-label">
        What they did
      </span>
      <div role="radiogroup" aria-labelledby={labelId} className={segmented ? 'psl-seg resp-seg' : 'resp-pills'}>
        {offeredActions(response).map((a) => (
          <label key={a.value} className={segmented ? 'psl-seg__opt resp-segopt' : 'resp-pill'}>
            <input type="radio" name={labelId} value={a.value} checked={entries.action === a.value} onChange={() => setEntry('action', a.value)} />
            {a.label}
          </label>
        ))}
      </div>
    </div>
  );
}

function Note({ entries, setEntry }: Pick<FormProps, 'entries' | 'setEntry'>) {
  const labelId = useId();
  const countId = useId();
  // One line high to start (no board draws it); it grows by dragging. The counter sits on the label line.
  return (
    <div className="resp-field">
      <span className="resp-notehead">
        <label id={labelId} htmlFor={`${labelId}-note`} className="resp-label">
          Note <span className="psl-opt">(optional)</span>
        </label>
        <span id={countId} className="psl-hint">
          {entries.note.length} / {NOTE_MAX}
        </span>
      </span>
      <textarea
        id={`${labelId}-note`}
        className="psl-input psl-input--area resp-note"
        rows={1}
        maxLength={NOTE_MAX}
        value={entries.note}
        aria-describedby={countId}
        onChange={(e) => setEntry('note', e.target.value)}
      />
    </div>
  );
}

function Attest({ entries, setEntry, short }: Pick<FormProps, 'entries' | 'setEntry'> & { short: boolean }) {
  return (
    <label className="psl-check resp-attest">
      <input type="checkbox" checked={entries.attested} onChange={(e) => setEntry('attested', e.target.checked)} />
      <span>{short ? 'I confirm this response is genuine.' : 'I confirm this response is genuine and came from the client contact named above.'}</span>
    </label>
  );
}

function RecordRow({ props, ready, line, children }: { props: FormProps; ready: boolean; line: string | null; children?: ReactNode }) {
  const text = props.busy ? RESPONSE_LABELS.busy : RESPONSE_LABELS.record[props.response.variant];
  const button = (
    <button type="button" className="psl-btn psl-btn--lg resp-record" disabled={!ready} onClick={props.onRecord}>
      {text}
    </button>
  );
  const alert =
    line &&
    !props.busy &&
    (props.touched ? (
      <div role="alert" className="resp-alert">
        {line}
      </div>
    ) : (
      <div className="resp-alert resp-alert--hint">{line}</div>
    ));
  if (props.phone) {
    return (
      <>
        {props.notice}
        {alert}
        {children}
        <div className="psl-actionbar resp-phonebar">{button}</div>
      </>
    );
  }
  return (
    <>
      {props.notice}
      {children}
      <div className="resp-actions">
        {alert}
        {button}
        {props.response.variant === 'client_response' && (
          <span className="resp-footnote">Recorded with your name and the time. It can&rsquo;t be edited later, only corrected by a new record.</span>
        )}
      </div>
    </>
  );
}

/** Whether Record may be pressed, and the alert line beside it when it may not. */
function readiness(props: FormProps) {
  const line = missingLine(props.entries, props.response, props.proof.evidenceIds.length);
  const ready = !line && !props.busy && !props.locked && !props.proof.uploading && props.entries.note.length <= NOTE_MAX;
  return { ready, line };
}

export function AgentAside({ response }: { response: TaskResponse }) {
  const note = response.agent_note;
  if (!note) return null;
  const agent = AGENT_LABELS[note.agent];
  return (
    <aside className="resp-agent" aria-label={`${agent.name}, ${agent.role}`}>
      <div className="resp-agent__head">
        {/* eslint-disable-next-line @next/next/no-img-element -- a fixed 36px avatar from public/agents */}
        <img src={`/agents/${note.agent}.png`} alt="" width={36} height={36} className="resp-agent__img" />
        <span className="resp-agent__name">
          {agent.name} <span className="resp-agent__role">· {agent.role}</span>
        </span>
      </div>
      <div className="resp-agent__body">
        {note.lines.map((line, i) => (
          <p key={i}>{line}</p>
        ))}
      </div>
    </aside>
  );
}

export function ClientResponseForm(props: FormProps) {
  const { response, entries, setEntry, proof, busy, phone } = props;
  const { ready, line } = readiness(props);
  const responders = response.responders;
  const versions = response.versions ?? [];
  const whoSelect = (
    <Select
      label="Who responded"
      value={entries.who}
      onChange={(v) => setEntry('who', v)}
      options={responders.map((r) => ({ value: r.id, text: responderText(r, response.variant) }))}
    />
  );
  const versionSelect = versions.length > 0 && (
    <Select
      label="For which version"
      value={entries.version}
      onChange={(v) => setEntry('version', v)}
      options={versions.map((v) => ({ value: v.id, text: v.note ? `${v.label} (${v.note})` : v.label }))}
    />
  );
  const when = <WhenField label="When they responded" value={entries.when} onChange={(v) => setEntry('when', v)} />;

  if (phone) {
    const collapse = responders.length === 1 && versions.length <= 1;
    const summary = collapse ? [responders[0].organisation, versions[0]?.label, responders[0].name].filter(Boolean).join(' · ') : '';
    return (
      <form className="resp-form resp-form--phone" aria-busy={busy} onSubmit={(e) => e.preventDefault()}>
        {collapse ? <p className="resp-summary">{summary}</p> : (
          <>
            {whoSelect}
            {versionSelect}
          </>
        )}
        <ChannelSelect response={response} entries={entries} setEntry={setEntry} />
        {when}
        <Actions response={response} entries={entries} setEntry={setEntry} segmented={false} />
        <ProofField proof={proof} layout="phone" />
        <Note entries={entries} setEntry={setEntry} />
        <Attest entries={entries} setEntry={setEntry} short />
        <RecordRow props={props} ready={ready} line={line} />
      </form>
    );
  }

  const channels = (response.channels?.length ?? 0) > 1;
  return (
    <form className="resp-form" aria-busy={busy} onSubmit={(e) => e.preventDefault()}>
      <div className={channels ? 'resp-row resp-row--3' : 'resp-row'}>
        {whoSelect}
        {when}
        <ChannelSelect response={response} entries={entries} setEntry={setEntry} />
      </div>
      <Actions response={response} entries={entries} setEntry={setEntry} segmented={false} />
      {/* No board draws the note, so it shares the version's row instead of pushing the board's rows down. */}
      <div className={versionSelect ? 'resp-row' : undefined}>
        {versionSelect}
        <Note entries={entries} setEntry={setEntry} />
      </div>
      <ProofField proof={proof} hint={response.proof_hint} />
      <Attest entries={entries} setEntry={setEntry} short={false} />
      <RecordRow props={props} ready={ready} line={line} />
    </form>
  );
}

function Fixed({ label, text, note }: { label: string; text: string; note?: string }) {
  return (
    <div className="resp-field">
      <span className="resp-label resp-label--strong">{label}</span>
      <span className="resp-static">{text}</span>
      {note && <span className="psl-hint">{note}</span>}
    </div>
  );
}

export function SowSignatureForm(props: FormProps) {
  const { response, entries, setEntry, proof, busy, phone } = props;
  const { ready, line } = readiness(props);
  const versions = response.versions ?? [];
  const responders = response.responders;
  const sent = (v: (typeof versions)[number]) => (v.sent_at ? `${v.label} · sent ${formatWat(v.sent_at)}` : v.label);

  const fields = (
    <>
      {versions.length === 1 && <Fixed label="Document" text={sent(versions[0])} note={versions[0].note} />}
      {versions.length > 1 && (
        <Select
          label="Document"
          value={entries.version}
          onChange={(v) => setEntry('version', v)}
          options={versions.map((v) => ({ value: v.id, text: v.note ? `${sent(v)} (${v.note})` : sent(v) }))}
        />
      )}
      {responders.length === 1 ? (
        <Fixed label="Who signed" text={responderText(responders[0], response.variant)} />
      ) : (
        <Select
          label="Who signed"
          value={entries.who}
          onChange={(v) => setEntry('who', v)}
          options={responders.map((r) => ({ value: r.id, text: responderText(r, response.variant) }))}
        />
      )}
      {/* The SOW boards draw no note: it shares the When row (on the phone it follows the board's rows). */}
      <div className={phone ? undefined : 'resp-row'}>
        <WhenField label="When" value={entries.when} onChange={(v) => setEntry('when', v)} />
        {!phone && <Note entries={entries} setEntry={setEntry} />}
      </div>
      <ChannelSelect response={response} entries={entries} setEntry={setEntry} />
      <Actions response={response} entries={entries} setEntry={setEntry} segmented />
      {/* Nor the attestation: it sits beside the proof it vouches for (on the phone, after the board's rows). */}
      {phone ? (
        <ProofField proof={proof} layout="card" />
      ) : (
        <div className="resp-row resp-row--proof">
          <ProofField proof={proof} layout="card" />
          <Attest entries={entries} setEntry={setEntry} short={false} />
        </div>
      )}
    </>
  );
  const nextLine = response.next?.length ? (
    <div className="resp-nextline">
      <strong>What happens next:</strong> {response.next.join(' ')}
    </div>
  ) : null;
  const next = phone ? (
    <>
      {nextLine}
      <Note entries={entries} setEntry={setEntry} />
      <Attest entries={entries} setEntry={setEntry} short={false} />
    </>
  ) : (
    nextLine
  );

  return (
    <form className={phone ? 'resp-form resp-form--phone resp-form--sow' : 'resp-form resp-form--sow'} aria-busy={busy} onSubmit={(e) => e.preventDefault()}>
      <section className="psl-panel resp-signature" aria-labelledby="resp-signature-head">
        <h2 id="resp-signature-head" className="psl-panel__head">
          Signature
        </h2>
        <div className="psl-panel__body">
          {fields}
          <RecordRow props={props} ready={ready} line={line}>
            {next}
          </RecordRow>
        </div>
      </section>
    </form>
  );
}
