'use client';

// F-96: the RFP response panel's requirement rows, drawn under its sections (the adapter's `Actions` slot). Each row shows the
// requirement key, how it is covered (disposition), where it stands (status), the saved answer and Tola's suggestion with its
// source. What may be done to a row is the server's answer (`can_write`, the row's `can_review` and `can_undo`); the client has
// no rule about who may review. Sending, locking and error words are useWorkCommand's.
import type { LiveBidAnswerRow, LiveBidAnswers } from '@/api/types';
import { Tag, type TagTone } from '@/components';

import type { LineActionsProps } from './adapter';
import { dispositionWords, statusWords } from './bidAnswersAdapter';

const STATUS_TONE: Record<LiveBidAnswerRow['status'], TagTone> = {
  current: 'neutral',
  queued: 'agent',
  running: 'agent',
  held: 'waiting',
  suggested: 'person',
  reviewed: 'done',
  stale: 'waiting',
};

export function BidAnswersActions({ readback }: LineActionsProps<LiveBidAnswers>) {
  if (readback.rows.length === 0) return <p className="wr-line">No requirements are listed for this response yet.</p>;
  return (
    <ul className="bid-rows" aria-label="Requirements">
      {readback.rows.map((row) => (
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
        </li>
      ))}
    </ul>
  );
}
