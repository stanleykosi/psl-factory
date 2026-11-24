// One saved version, read-only: its boxes (or the whole text), who took part, decisions, the notes file and the
// follow-up actions the API lists. Supporting files are named only by their id; no file name is made up.
import type { ReactNode } from 'react';

import { formatDate, formatDateTime, Tag } from '@/components';

import { deadlineText, NOT_RECORDED, ownerText, STATUS_ACTION_WORDS, TIMING_WORDS, type MeetingDetail } from './model';
import { BOX_KEYS, BOX_LABELS, parseSummary } from './summary';

export function SavedBoxes({ summary }: { summary: string }) {
  const parsed = parseSummary(summary);
  if (!parsed.recognised) {
    return (
      <div className="retro__stack">
        <p className="retro__heading">Retrospective</p>
        <p className="retro__text">{summary}</p>
      </div>
    );
  }
  return (
    <>
      {BOX_KEYS.map((key) => (
        <div key={key} className="retro__stack">
          <p className="retro__heading">{BOX_LABELS[key]}</p>
          <p className="retro__text">{parsed.boxes[key] || NOT_RECORDED}</p>
        </div>
      ))}
      {parsed.other !== '' && (
        <div className="retro__stack">
          <p className="retro__heading">Other notes</p>
          <p className="retro__text">{parsed.other}</p>
        </div>
      )}
    </>
  );
}

export function SavedVersion({ detail, actionsLead }: { detail: MeetingDetail; actionsLead?: ReactNode }) {
  return (
    <>
      <div className="retro__row">
        <p className="retro__plain">
          <strong>{detail.reference}</strong> · Version {detail.version} · held {formatDateTime(detail.occurred_at)}
        </p>
        {!detail.current && <Tag tone="neutral">Version {detail.version}, not the current version</Tag>}
      </div>
      <SavedBoxes summary={detail.summary} />
      <div className="retro__stack">
        <p className="retro__heading">Who took part</p>
        {detail.participants.length === 0 ? (
          <p className="retro__plain">{NOT_RECORDED}</p>
        ) : (
          <ul className="retro__people">
            {detail.participants.map((p) => (
              <li key={p.id}>{p.label}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="retro__stack">
        <p className="retro__heading">Notes file</p>
        <p className="retro__plain">Supporting file {detail.evidence_id}</p>
      </div>
      {detail.decisions.length > 0 && (
        <div className="retro__stack">
          <p className="retro__heading">Decisions</p>
          <ul className="retro__followups">
            {detail.decisions.map((d, at) => (
              <li key={at} className="retro__followup">
                <span className="retro__plain">{d.text}</span>
                <span className="retro__muted">Supporting file {d.evidence_id}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {detail.current && (
        <div className="retro__stack">
          <p className="retro__heading">Follow-up actions</p>
          {detail.actions.length === 0 ? (
            <p className="retro__plain">No follow-up actions yet.</p>
          ) : (
            <ul className="retro__followups">
              {detail.actions.map((a) => (
                <li key={a.id} className="retro__followup">
                  <span className="retro__plain">{a.current.description}</span>
                  <span className="retro__muted">
                    {a.reference} · {ownerText(a)} · {deadlineText(a, formatDate)} · {STATUS_ACTION_WORDS[a.current.status]} · {TIMING_WORDS[a.current.timing]}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {detail.next_page !== null && <p className="retro__muted">More follow-up actions exist than are shown.</p>}
          {actionsLead}
        </div>
      )}
    </>
  );
}
