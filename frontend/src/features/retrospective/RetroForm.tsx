'use client';

// The retrospective form: three boxes, who took part, the notes file, decisions, and one Save. Every save is a recorded
// version; there is no draft. Typed values stay through any failed save.
import { useEffect, useRef, useState, type FocusEvent } from 'react';

import { Button, Callout, Checkbox, DateField, Select, TextArea, TextField, useIsPhone } from '@/components';

import { carriedDecisions, DECISION_TEXT_MAX, DECISIONS_MAX, localStamp, moreThanShown, NO_PROOFS, REFERENCE_MAX, saveBody, saveProblems, type MeetingDetail, type MeetingOptions, type SaveDraft } from './model';
import { parseSummary, BOX_KEYS, BOX_LABELS, EMPTY_BOXES, SUMMARY_LIMIT, writeSummary, type BoxKey } from './summary';
import { FailureNotice } from './FailureNotice';
import type { Failure } from './failure';

/** The failure fields this form has a control for. */
const DRAWN = ['reference', 'occurredAt', 'boxes', 'evidence'];

import './retrospective.css';

/** The form's first values: empty for a first save, the saved version's text and decisions for a new version. */
export function initialDraft(from: MeetingDetail | null, reference: string, now: Date): SaveDraft {
  if (!from) return { reference, occurredAt: localStamp(now), whole: null, boxes: { ...EMPTY_BOXES }, other: '', participantIds: [], decisions: [], evidenceId: '', meetingId: null };
  const parsed = parseSummary(from.summary);
  return {
    reference: from.reference,
    occurredAt: localStamp(now),
    whole: parsed.recognised ? null : from.summary,
    boxes: parsed.boxes,
    other: parsed.recognised ? parsed.other : '',
    participantIds: from.participants.map((p) => p.id),
    decisions: carriedDecisions(from.decisions),
    evidenceId: '',
    meetingId: from.id,
  };
}

export function RetroForm({ options, optionsProblem, revision, initial, busy, failure, onSave, onCheckAgain, onReloadNotice }: {
  options: MeetingOptions | null;
  /** Why the people and files could not be read, when they could not. */
  optionsProblem: string | null;
  revision: number;
  initial: SaveDraft;
  busy: boolean;
  failure: Failure | null;
  onSave: (body: ReturnType<typeof saveBody>) => void;
  onCheckAgain: () => void;
  onReloadNotice: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [now] = useState(() => new Date());
  const phone = useIsPhone();
  const bar = useRef<HTMLDivElement>(null);
  // The phone bar's real height (its reason line can wrap) feeds the page's scroll and bottom padding in the css.
  useEffect(() => {
    const el = bar.current;
    if (!phone || !el || typeof ResizeObserver === 'undefined') return;
    const root = document.documentElement;
    const measure = () => root.style.setProperty('--retro-bar', `${Math.ceil(el.getBoundingClientRect().height)}px`);
    measure();
    const watch = new ResizeObserver(measure);
    watch.observe(el);
    return () => {
      watch.disconnect();
      root.style.removeProperty('--retro-bar');
    };
  }, [phone]);
  /** Phone: a focused control ends fully above the fixed bar. The browser does not scroll for a control that is partly in view. */
  function clearOfBar(event: FocusEvent<HTMLFormElement>) {
    const el = bar.current;
    const target = event.target;
    if (!phone || !el || el.contains(target)) return;
    requestAnimationFrame(() => {
      const gap = target.getBoundingClientRect().bottom - (el.getBoundingClientRect().top - 8);
      if (gap > 0) window.scrollBy(0, gap);
    });
  }
  const proofs = options?.proofs ?? [];
  const problems = saveProblems(draft, proofs.length, now);
  const set = (patch: Partial<SaveDraft>) => setDraft((d) => ({ ...d, ...patch }));
  const total = (draft.whole ?? writeSummary(draft.boxes, draft.other)).length;
  const unconfirmed = failure?.kind === 'unconfirmed';
  const first = draft.meetingId === null;
  const serverFields = failure?.kind === 'invalid' ? failure.fields : {};
  const firstProblem = problems.boxes ?? Object.values(problems.boxLines)[0] ?? problems.evidence ?? problems.occurredAt ?? problems.reference ?? Object.values(problems.decisions)[0];
  const disabled = busy || unconfirmed || optionsProblem !== null || problems.any;
  const reasonText = busy ? undefined : (optionsProblem ?? (unconfirmed ? 'Waiting to see whether the last save was recorded.' : firstProblem));

  function setBox(key: BoxKey, value: string) {
    set({ boxes: { ...draft.boxes, [key]: value } });
  }

  const decisions = (
      <div className="retro__stack">
        <p className="retro__heading">Decisions</p>
        {draft.decisions.map((row, at) => (
          <div key={row.key} className="retro__decision">
            <TextArea
              label={`Decision ${at + 1}`}
              value={row.text}
              limit={DECISION_TEXT_MAX}
              onChange={(e) => set({ decisions: draft.decisions.map((d) => (d.key === row.key ? { ...d, text: e.target.value } : d)) })}
              error={problems.decisions[row.key] && (row.text === '' || row.text.length > DECISION_TEXT_MAX) ? problems.decisions[row.key] : undefined}
              rows={2}
            />
            <Select
              label={`Supporting file for decision ${at + 1}`}
              placeholder="Choose a file"
              value={row.evidenceId || undefined}
              onChange={(evidenceId) => set({ decisions: draft.decisions.map((d) => (d.key === row.key ? { ...d, evidenceId } : d)) })}
              options={proofs.map((p) => ({ value: String(p.id), label: p.label }))}
              error={problems.decisions[row.key] && row.text !== '' && row.evidenceId === '' ? problems.decisions[row.key] : undefined}
            />
            <div className="retro__decisionbar">
              <Button kind="secondary" onClick={() => set({ decisions: draft.decisions.filter((d) => d.key !== row.key) })}>
                Remove decision {at + 1}
              </Button>
            </div>
          </div>
        ))}
        <span>
          <Button
            kind="secondary"
            disabled={draft.decisions.length >= DECISIONS_MAX || proofs.length === 0}
            reason={draft.decisions.length >= DECISIONS_MAX ? `At most ${DECISIONS_MAX} decisions.` : proofs.length === 0 ? 'A decision needs a supporting file; none is recorded.' : undefined}
            onClick={() => set({ decisions: [...draft.decisions, { key: Math.max(-1, ...draft.decisions.map((d) => d.key)) + 1, text: '', evidenceId: '', changeEvidenceId: null }] })}
          >
            Add a decision
          </Button>
        </span>
      </div>
  );

  const saveBar = (
      <div ref={bar} className="retro__actions retro__savebar">
        <Button type="submit" kind="primary" size="lg" className="retro__save" busy={busy} busyLabel="Saving…" disabled={disabled} reason={reasonText}>
          {first ? 'Save retrospective' : 'Save new version'}
        </Button>
      </div>
  );

  return (
    <form
      className="retro__stack"
      noValidate
      onFocus={clearOfBar}
      onSubmit={(event) => {
        event.preventDefault();
        if (disabled) return;
        onSave(saveBody(draft, revision));
      }}
    >
      <div className="retro__pair">
      <DateField
        time
        label="When it was held"
        value={draft.occurredAt}
        onChange={(occurredAt) => set({ occurredAt })}
        unavailable={(iso) => (iso > localStamp(now).slice(0, 10) ? "That day hasn't happened yet." : undefined)}
        error={problems.occurredAt && draft.occurredAt !== '' ? problems.occurredAt : serverFields.occurredAt}
      />

      <TextField label="Reference" value={draft.reference} readOnly={!first} onChange={(e) => set({ reference: e.target.value })} hint={first ? undefined : 'Every version of a retrospective keeps its reference.'} error={serverFields.reference ?? (draft.reference.length > REFERENCE_MAX ? problems.reference : undefined)} />

      </div>
      {draft.whole !== null ? (
        <TextArea label="Retrospective" value={draft.whole} onChange={(e) => set({ whole: e.target.value })} error={problems.boxes ? undefined : serverFields.boxes} rows={6} fieldClassName="retro__box" />
      ) : (
        BOX_KEYS.map((key) => (
          <TextArea key={key} label={BOX_LABELS[key]} value={draft.boxes[key]} onChange={(e) => setBox(key, e.target.value)} error={problems.boxLines[key] ?? (key === 'well' ? serverFields.boxes : undefined)} rows={3} fieldClassName="retro__box" />
        ))
      )}
      {draft.other !== '' && (
        <div className="retro__stack">
          <p className="retro__heading">Other notes</p>
          <p className="retro__text">{draft.other}</p>
          <p className="retro__muted">Kept as saved with the new version.</p>
        </div>
      )}
      {total >= SUMMARY_LIMIT * 0.9 && (
        <p className={total > SUMMARY_LIMIT ? 'retro__count is-over' : 'retro__count'} role="status">
          {total} / {SUMMARY_LIMIT}
        </p>
      )}

      <fieldset className="retro__checks">
        <legend>Who took part</legend>
        {(options?.participants ?? []).length === 0 && <p className="retro__muted">No people are listed for this project.</p>}
        {(options?.participants ?? []).map((person) => (
          <Checkbox
            key={person.id}
            label={person.label}
            checked={draft.participantIds.includes(person.id)}
            onChange={(e) => set({ participantIds: e.target.checked ? [...draft.participantIds, person.id] : draft.participantIds.filter((id) => id !== person.id) })}
          />
        ))}
      </fieldset>

      <Select
        label="Notes file"
        placeholder={proofs.length === 0 ? 'No files to choose' : 'Choose the notes file'}
        value={draft.evidenceId || undefined}
        onChange={(evidenceId) => set({ evidenceId })}
        options={proofs.map((p) => ({ value: String(p.id), label: p.label }))}
        disabled={proofs.length === 0}
        hint={proofs.length === 0 && options ? NO_PROOFS : undefined}
        error={serverFields.evidence}
      />
      {options && moreThanShown(options) && <p className="retro__muted">More are available than shown.</p>}


      <FailureNotice failure={failure} drawn={DRAWN}>
        {failure?.kind === 'stale' && (
          <>
            {' '}
            <Button kind="link" onClick={onReloadNotice}>
              Reload
            </Button>
          </>
        )}
      </FailureNotice>
      {unconfirmed && (
        <Callout kind="warning">
          <strong>{"We couldn't confirm it saved."}</strong> Nothing is sent again by itself.{' '}
          <Button kind="link" disabled={busy} onClick={onCheckAgain}>
            Check again
          </Button>
        </Callout>
      )}


      {phone ? <>{decisions}{saveBar}</> : <>{saveBar}{decisions}</>}
    </form>
  );
}
