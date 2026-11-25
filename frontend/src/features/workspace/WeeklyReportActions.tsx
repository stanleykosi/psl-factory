'use client';

// F-89: the weekly report's own controls, drawn under its sections (the adapter's `Actions` slot): the report text and the
// agent's notes for the reviewer, the review block (Approve and send, Return with a note, Refuse) and the edit form after a
// return. Which verdicts and whether correcting is offered is the server's answer (commands are described by the adapter from
// `review_verdicts` and `can_correct`); the client has no rule about who may review. Sending, locking and error words are
// useWorkCommand's. The result is told from the re-read, never from the 200/201.
import { useState } from 'react';

import type { LiveWeeklyReport } from '@/api/types';
import { Button, Callout, TextArea, TextField } from '@/components';

import type { CommandDescriptor, LineActionsProps } from './adapter';
import { useWorkCommand } from './useWorkCommand';

const SECTION_NAMES: Record<string, string> = {
  executive_summary: 'Executive summary',
  scope: 'Scope',
  status: 'Status',
  timeline: 'Timeline',
  risks: 'Risks',
  dependencies: 'Dependencies',
  next_steps: 'Next steps',
};
const PARTS = [
  ['status', 'Status'],
  ['risks', 'Risks'],
  ['timeline', 'Timeline'],
  ['next_steps', 'Next steps'],
] as const;
const IDS = ['weekly-report.correct', 'weekly-report.approve', 'weekly-report.return', 'weekly-report.reject'];
const PART_LIMIT = 10000;
const REASON_LIMIT = 2000;
const NOTE_LIMIT = 4000;
const HELD = 'The report text isn’t available here yet, so it can’t be approved from this page.';
const LOCKED = 'Check the page before trying again.';
const cited = (n: number) => `${n} ${n === 1 ? 'record' : 'records'} cited`;

const lines = (text: string) => <span className="wr-text">{text}</span>;

function ReportText({ report }: { report: LiveWeeklyReport }) {
  const { preview, review_notes: notes } = report;
  if (!preview) return null;
  const shown = new Set(preview.sections.map((s) => s.key));
  const noteList = (items: typeof notes) =>
    items.map((n, i) => (
      <p key={i} className="wr-note">
        <strong>Note from the review</strong> {lines(n.text)} <time dateTime={n.recorded_at}>{new Date(n.recorded_at).toLocaleString('en-GB')}</time>
      </p>
    ));
  const other = notes.filter((n) => !shown.has(n.section));
  return (
    <section className="wr-block" aria-label="The report">
      <h3 className="wr-head">
        The report: {preview.title}, version {preview.number}
      </h3>
      {preview.sections.map((s) => (
        <div key={s.key} className="wr-section">
          <h4 className="wr-sub">{SECTION_NAMES[s.key] ?? s.key}</h4>
          {lines(s.text)}
          {noteList(notes.filter((n) => n.section === s.key))}
        </div>
      ))}
      {other.length > 0 && (
        <div className="wr-section">
          <h4 className="wr-sub">Other notes</h4>
          {noteList(other).map((n, i) => (
            <div key={i}>{n}</div>
          ))}
        </div>
      )}
    </section>
  );
}

export function WeeklyReportActions({ readback: report, ctx, commands, reload, onAccessLost }: LineActionsProps<LiveWeeklyReport>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [parts, setParts] = useState<Record<string, string>>({});
  const [reason, setReason] = useState('');
  const [last, setLast] = useState<string | null>(null);

  const byId = (id: string) => commands.find((c) => c.id === id);
  const correct = byId('weekly-report.correct');
  const reviews = IDS.slice(1).map(byId).filter((c): c is CommandDescriptor => !!c);
  const approveHeld = report.review_verdicts.includes('approve') && report.document_version_id !== null && !byId('weekly-report.approve');
  const locked = IDS.some((id) => send.lockedReason(id) !== null);
  const editable = report.editable_parts;
  const canEdit = !!correct && !correct.disabledReason && !!editable;
  const editBlocked = report.can_correct && correct?.disabledReason && (!editable || ctx.revision === null) ? correct.disabledReason : null;

  const text = (key: (typeof PARTS)[number][0]) => parts[key] ?? editable?.[key].text ?? '';
  const partErrors = PARTS.map(([key, label]) => {
    const v = text(key);
    return v.trim() === '' ? `${label} can’t be blank.` : v.length > PART_LIMIT ? `${label} is over ${PART_LIMIT} characters.` : null;
  });
  const reasonError = reason.trim() === '' ? 'Say why you are changing it.' : reason.length > REASON_LIMIT ? `The reason is over ${REASON_LIMIT} characters.` : null;
  const formError = partErrors.find(Boolean) ?? reasonError;

  const press = async (command: CommandDescriptor, inputs: Record<string, unknown>) => {
    setLast(command.id);
    await send.run(command, inputs);
  };
  const review = (command: CommandDescriptor) => {
    if (command.id !== 'weekly-report.approve' && note.trim() === '') {
      setNoteError('Write a note first.');
      return;
    }
    setNoteError(null);
    void press(command, { note });
  };
  const sendCorrection = () => {
    if (!correct || !editable || formError) return;
    void press(correct, {
      draft_id: report.draft?.id ?? null,
      selection: report.selection,
      parts: Object.fromEntries(PARTS.map(([key]) => [key, { text: text(key), evidence_ids: editable[key].evidence_ids }])),
      reason,
    });
  };

  // the words the re-read confirms, said once the press has been re-read
  const notice = send.notice;
  const done = notice?.kind === 'success' ? notice.text.replace(/^Done\./, last === 'weekly-report.correct' ? 'Your update was sent for review.' : 'Recorded.') : null;
  const button = (c: CommandDescriptor, kind: 'primary' | 'secondary' | 'reject', onClick: () => void, invalid = false) => {
    const lockedReason = send.lockedReason(c.id) ?? (locked ? LOCKED : null);
    const reasonText = c.disabledReason ?? lockedReason;
    return (
      <Button key={c.id} kind={kind} disabled={send.busy || invalid || reasonText !== null} busy={send.pending === c.id && !lockedReason} busyLabel="Working…" reason={reasonText} onClick={onClick}>
        {c.label}
      </Button>
    );
  };

  return (
    <div className="wr-actions">
      <ReportText report={report} />
      {reviews.length > 0 && (
        <section className="wr-block" aria-label="Your review">
          <h3 className="wr-head">Your review</h3>
          <p className="wr-line">Approving sends this exact version to the client.</p>
          <TextArea label="Note" hint="Needed to return or refuse" limit={NOTE_LIMIT} value={note} error={noteError ?? undefined} onChange={(e) => setNote(e.target.value)} />
          <div className="wr-buttons">{reviews.map((c) => button(c, c.id === 'weekly-report.approve' ? 'primary' : c.id === 'weekly-report.reject' ? 'reject' : 'secondary', () => review(c)))}</div>
        </section>
      )}
      {approveHeld && <p className="wr-line">{HELD}</p>}
      {canEdit && !editing && (
        <section className="wr-block" aria-label="Edit your update">
          <Button kind="secondary" onClick={() => setEditing(true)} disabled={send.busy}>
            Edit your update
          </Button>
        </section>
      )}
      {editBlocked && <p className="wr-line">{editBlocked}</p>}
      {canEdit && editing && editable && (
        <section className="wr-block" aria-label="Edit your update">
          <h3 className="wr-head">Edit your update</h3>
          <p className="wr-line">Edit your part, then Tola reassembles it and it goes back for review.</p>
          {PARTS.map(([key, label], i) => (
            <div key={key}>
              <TextArea label={label} limit={PART_LIMIT} value={text(key)} error={partErrors[i] ?? undefined} onChange={(e) => setParts({ ...parts, [key]: e.target.value })} />
              <p className="wr-line">{cited(editable[key].evidence_ids.length)}</p>
            </div>
          ))}
          <TextField label="Reason for the change" value={reason} error={reasonError ?? undefined} maxLength={REASON_LIMIT + 1} onChange={(e) => setReason(e.target.value)} />
          <div className="wr-buttons">
            {button(correct, 'primary', sendCorrection, !!formError)}
            <Button
              kind="secondary"
              disabled={send.busy}
              onClick={() => {
                setEditing(false);
                setParts({});
                setReason('');
              }}
            >
              Cancel
            </Button>
          </div>
        </section>
      )}
      {done && <Callout kind="success">{done}</Callout>}
      {notice?.kind === 'error' && (
        <Callout kind="problem">
          {notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
