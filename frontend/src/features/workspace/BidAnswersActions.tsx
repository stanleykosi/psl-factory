'use client';

// F-96: the RFP response panel's requirement rows and their controls, drawn under its sections (the adapter's `Actions` slot).
// A row shows the requirement key, how it is covered (disposition), where it stands (status), the saved answer and Tola's
// suggestion with its source. What may be done to a row is the server's answer (`can_write`, the row's `can_review` and
// `can_undo`); the client has no rule about who may review. Sending, locking and error words are useWorkCommand's. The result is
// told from the re-read, never from the 201.
//   Accept / Edit / Write your own  -> action review, one decision (verdicts accept, edit, replace; the contract has no refusal)
//   Ask Tola                         -> action suggest (with an earlier winning answer when one is picked)
//   Undo                             -> action undo
// HELD: "Send for review". The review of the response is a separate pack action (POST /work/{id}/bid-pack/review-request, which
// needs a pack_id and version_id that this panel does not carry); POST /reviews kind bid records the reviewer's verdict, not
// the PM's send. The button is drawn disabled with that reason.
import { useState } from 'react';

import type { LiveBidAnswerRow, LiveBidAnswers } from '@/api/types';
import { Button, Callout, Select, Tag, TextArea, useToastWhen, type TagTone } from '@/components';

import type { CommandDescriptor, LineActionsProps } from './adapter';
import { DISPOSITIONS, SEND_HELD, dispositionWords, statusWords } from './bidAnswersAdapter';
import { useWorkCommand } from './useWorkCommand';

const STATUS_TONE: Record<LiveBidAnswerRow['status'], TagTone> = {
  current: 'neutral',
  queued: 'agent',
  running: 'agent',
  held: 'waiting',
  suggested: 'person',
  reviewed: 'done',
  stale: 'waiting',
};
const ANSWER_LIMIT = 4000;
const NOTE_LIMIT = 2000;
const LOCKED = 'Check the page before trying again.';
const NO_PRIOR = '';
const HELD_ROW = 'Tola’s answer for this requirement is on hold.';

type Form = { key: string; verdict: 'edit' | 'replace'; answer: string; disposition: LiveBidAnswerRow['disposition']; note: string };

export function BidAnswersActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<LiveBidAnswers>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [form, setForm] = useState<Form | null>(null);
  const [priors, setPriors] = useState<Record<string, string>>({});
  const [last, setLast] = useState<{ id: string; key: string } | null>(null);

  const byId = (id: string) => commands.find((c) => c.id === id);
  const review = byId('bid-answers.review');
  const undo = byId('bid-answers.undo');
  const anyLocked = commands.some((c) => send.lockedReason(c.id) !== null);

  const press = async (command: CommandDescriptor, key: string, inputs: Record<string, unknown>) => {
    setLast({ id: command.id, key });
    await send.run(command, inputs);
  };
  const reasonFor = (c: CommandDescriptor | undefined) => (c ? (c.disabledReason ?? send.lockedReason(c.id) ?? (anyLocked ? LOCKED : null)) : null);
  const button = (c: CommandDescriptor | undefined, label: string, kind: 'primary' | 'secondary', onClick: () => void, invalid = false) => {
    if (!c) return null;
    const reason = reasonFor(c);
    return (
      <Button kind={kind} disabled={send.busy || invalid || reason !== null} busy={send.pending === c.id && !send.lockedReason(c.id)} busyLabel="Working…" reason={reason} onClick={onClick}>
        {label}
      </Button>
    );
  };

  const decide = (row: LiveBidAnswerRow, verdict: 'accept' | 'edit' | 'replace', answer: string, disposition: LiveBidAnswerRow['disposition'], note: string) => {
    if (!review || row.suggestion_id === null) return;
    // `predecessor` is the review this suggestion's latest one follows: none yet is 0
    const decision = { suggestion: row.suggestion_id, predecessor: row.review_id ?? 0, verdict, answer, disposition, note };
    void press(review, row.key, { decisions: [decision] });
  };

  const answerError = form ? (form.answer.trim() === '' ? 'Write the answer first.' : form.answer.length > ANSWER_LIMIT ? `The answer is over ${ANSWER_LIMIT} characters.` : null) : null;
  const noteError = form && form.note.length > NOTE_LIMIT ? `The note is over ${NOTE_LIMIT} characters.` : null;

  const notice = send.notice;
  const said = (): string | null => {
    if (notice?.kind !== 'success' || !last) return null;
    const what = last.id === 'bid-answers.review' ? `Your answer for ${last.key} was saved.` : last.id === 'bid-answers.undo' ? `The earlier answer for ${last.key} is back.` : `Tola was asked for ${last.key}.`;
    return notice.text.replace(/^Done\./, what);
  };
  // D-151: what a press did is a toast; only a problem stays on the page as a Callout.
  useToastWhen(said());

  return (
    <div className="wr-actions">
      {readback.rows.length === 0 ? (
        <p className="wr-line">No requirements are listed for this response yet.</p>
      ) : (
        <ul className="bid-rows" aria-label="Requirements">
          {readback.rows.map((row) => {
            const ask = byId(`bid-answers.suggest.${row.key}`);
            const canAsk = readback.can_write && ['current', 'stale', 'reviewed'].includes(row.status) && !(row.status === 'reviewed' && row.can_undo);
            // the form stays (with the person's words) until the re-read says the row can no longer be reviewed
            const open = form?.key === row.key && row.can_review ? form : null;
            return (
              <li key={row.key} className="bid-row">
                <div className="bid-head">
                  <h3 className="bid-key">{row.key}</h3>
                  <Tag tone="neutral">{dispositionWords(row.disposition)}</Tag>
                  <Tag tone={STATUS_TONE[row.status] ?? 'neutral'} pulse={row.status === 'running'}>
                    {statusWords(row.status)}
                  </Tag>
                </div>
                {row.citation && (
                  <p className="bid-quote">
                    “{row.citation.wording}”{row.citation.page !== null && <> (page {row.citation.page})</>}
                  </p>
                )}
                <p className={row.response ? 'bid-answer' : 'wr-line'}>{row.response ?? 'No answer saved.'}</p>
                {row.suggested_answer && row.status !== 'reviewed' && (
                  <div className="bid-suggest">
                    <strong>Tola suggests</strong>
                    <p className="bid-answer">{row.suggested_answer}</p>
                    {row.source && <p className="wr-line">Source: {row.source.reference}, version {row.source.version}</p>}
                  </div>
                )}
                {row.status === 'held' && <p className="wr-line">{HELD_ROW}</p>}
                {!open && (
                  <div className="wr-buttons">
                    {row.can_review && (
                      <>
                        {button(review, 'Accept', 'primary', () => decide(row, 'accept', row.suggested_answer ?? '', row.disposition, ''))}
                        {button(review, 'Edit', 'secondary', () => setForm({ key: row.key, verdict: 'edit', answer: row.suggested_answer ?? '', disposition: row.disposition, note: '' }))}
                        {button(review, 'Write your own', 'secondary', () => setForm({ key: row.key, verdict: 'replace', answer: '', disposition: row.disposition, note: '' }))}
                      </>
                    )}
                    {row.can_undo && row.review_id !== null && button(undo, 'Undo', 'secondary', () => {
                      setForm(null);
                      void press(undo!, row.key, { review_id: row.review_id });
                    })}
                    {canAsk && (
                      <>
                        {readback.prior_options.length > 0 && (
                          <Select
                            label="Start from an earlier answer"
                            placeholder="Start fresh"
                            value={priors[row.key] ?? NO_PRIOR}
                            options={[{ value: NO_PRIOR, label: 'Start fresh' }, ...readback.prior_options.map((o) => ({ value: o.token, label: o.label }))]}
                            onChange={(value) => setPriors({ ...priors, [row.key]: value })}
                          />
                        )}
                        {button(ask, 'Ask Tola', 'secondary', () => {
                          setForm(null);
                          void press(ask!, row.key, priors[row.key] ? { prior_answer: priors[row.key] } : {});
                        })}
                      </>
                    )}
                  </div>
                )}
                {open && review && (
                  <div className="bid-form" role="group" aria-label={`Your reply for ${row.key}`}>
                    <TextArea label="Answer" limit={ANSWER_LIMIT} value={open.answer} error={answerError ?? undefined} onChange={(e) => setForm({ ...open, answer: e.target.value })} />
                    <Select
                      label="How it is covered"
                      placeholder="Choose"
                      value={open.disposition}
                      options={DISPOSITIONS.map(([value, label]) => ({ value, label }))}
                      onChange={(value) => setForm({ ...open, disposition: value as Form['disposition'] })}
                    />
                    <TextArea label="Note" optional hint="For the record, not sent to the client" limit={NOTE_LIMIT} value={open.note} error={noteError ?? undefined} onChange={(e) => setForm({ ...open, note: e.target.value })} />
                    <div className="wr-buttons">
                      {button(review, 'Save answer', 'primary', () => decide(row, open.verdict, open.answer, open.disposition, open.note), !!(answerError || noteError))}
                      <Button kind="secondary" disabled={send.busy} onClick={() => setForm(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {readback.can_write && (
        <div className="wr-buttons">
          <Button kind="primary" disabled reason={SEND_HELD}>
            Send for review
          </Button>
        </div>
      )}
      {notice?.kind === 'error' && (
        <Callout kind="problem">
          {notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
