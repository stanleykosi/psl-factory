// SCR-16 recorded RFP outcome, drawn only from rfp_outcome.recorded: the result heading, the recorded rows and the
// reminder, the lessons (lost), the engagement (won), the follow-up (unknown) and the next lines. A missing field
// leaves its element out; nothing from a board without a field behind it is drawn (Conflicts 12, 13). A pending or
// unknown outcome can be recorded again ("Record the outcome" shows the form on this route) while the block still
// offers results.
import Link from 'next/link';
import type { ReactNode } from 'react';

import { InfoIcon } from '@/features/response/icons';
import { Button, formatDayMonth, formatDayTime, useIsPhone } from '@/components';

import type { RecordedOutcome, RfpOutcome } from './contract';
import { recordedHeading } from './labels';

const work = (id: string) => `/work/${encodeURIComponent(id)}`;

function Row({ text, meta }: { text: string; meta?: string }) {
  return (
    <li className="rfp-row">
      <span>{text}</span>
      {meta && <span className="rfp-row__meta">{meta}</span>}
    </li>
  );
}

function Panel({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`psl-panel rfp-panel${className ? ` ${className}` : ''}`} aria-label={title}>
      <h2 className="psl-panel__head">{title}</h2>
      <div className="psl-panel__body">{children}</div>
    </section>
  );
}

/** `title`: h1 on the phone; h2 under the desktop frame (the frame holds the h1); none when the page header already shows it. */
export function RecordedView({ outcome, recorded, title, onReopen, followup }: {
  outcome: RfpOutcome;
  recorded: RecordedOutcome;
  title: 'h1' | 'h2' | 'none';
  onReopen: () => void;
  /** The follow-up card (unknown), drawn by the page with its own send flow. */
  followup?: ReactNode;
}) {
  const heading = recordedHeading(recorded.result);
  const rows = recorded.rows ?? [];
  const reminder = recorded.reminder;
  const engagement = recorded.engagement;
  const lessons = recorded.lessons ?? [];
  const debrief = recorded.debrief;
  const next = recorded.next ?? [];
  const again = (recorded.result === 'pending' || recorded.result === 'unknown') && outcome.results.length > 0;

  const phone = useIsPhone();
  // The boards: won has no "Next" panel (a sentence and an outlined button); the phone has none for any state, pins the
  // single action of won and pending, keeps unknown's as a secondary button and lost's as a quiet link.
  const pinned = phone && (recorded.result === 'won' || recorded.result === 'pending');
  const action = again ? (
    <Button kind={phone && recorded.result === 'unknown' ? 'secondary' : 'primary'} size="lg" block onClick={onReopen}>
      Record the outcome
    </Button>
  ) : recorded.result === 'won' && engagement?.work_id ? (
    <Link className={`psl-btn psl-btn--lg psl-btn--block${phone ? '' : ' psl-btn--secondary'}`} href={work(engagement.work_id)}>
      Open engagement {engagement.reference}
    </Link>
  ) : recorded.result === 'lost' ? (
    phone ? (
      <Link className="psl-link psl-link--quiet" href="/projects">
        Back to projects
      </Link>
    ) : (
      <Link className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block" href="/projects">
        Back to projects
      </Link>
    )
  ) : null;
  const nextBody = (
    <>
      {next.map((line, i) => (
        <p key={i} className="rfp-plain">
          {line}
        </p>
      ))}
      {action && <div className={pinned ? 'rfp-pin' : undefined}>{action}</div>}
    </>
  );

  const listed = rows.length > 0 || reminder || engagement;
  return (
    <div className="rfp-recorded">
      {title === 'h1' && <h1 className="shell-title">{heading}</h1>}
      {title === 'h2' && <h2 className="rfp-recorded__title">{heading}</h2>}
      <div className="resp-board">
        <div className="rfp-recorded__main">
          {listed && (
            <Panel title="What’s recorded" className="rfp-panel--rows">
              <ul className="rfp-rows">
                {rows.map((r, i) => (
                  <Row key={i} text={r.at ? `${r.label} · ${r.value}` : r.label} meta={r.at ? formatDayMonth(r.at) : r.value} />
                ))}
                {engagement && <Row text={`Engagement ${engagement.reference} created`} />}
                {reminder && <Row text={`Reminder for ${reminder.holder.name}`} meta={formatDayTime(reminder.at)} />}
              </ul>
            </Panel>
          )}
          {(lessons.length > 0 || debrief) && (
            <Panel title={recorded.lessons_by ? `Lessons · recorded by ${recorded.lessons_by.name}` : 'Lessons'}>
              {lessons.length > 0 && (
                <ul className="rfp-rows">
                  {lessons.map((l, i) => (
                    <li key={i} className="rfp-row">
                      <span>{l.category ? `${l.category.label} · ${l.text}` : l.text}</span>
                      {l.category && <span className="psl-tag psl-tag--neutral rfp-row__tag">{l.category.label}</span>}
                    </li>
                  ))}
                </ul>
              )}
              {debrief && (debrief.label || debrief.reference) && (
                <p className="rfp-debrief">
                  {debrief.work_id ? <Link href={work(debrief.work_id)}>{debrief.label ?? 'Debrief'}</Link> : <span>{debrief.label ?? 'Debrief'}</span>}
                  {debrief.reference && <span className="rfp-debrief__ref"> · {debrief.reference}</span>}
                </p>
              )}
            </Panel>
          )}
          {recorded.archive_reference &&
            (phone ? (
              <p className="psl-hint">Archived as {recorded.archive_reference}.</p>
            ) : (
              <p className="psl-callout psl-callout--info">
                <InfoIcon />
                <span>Archived as {recorded.archive_reference}.</span>
              </p>
            ))}
          {followup}
        </div>
        {(next.length > 0 || action) && (
          <aside className="rfp-recorded__aside" aria-label="Next">
            {phone || recorded.result === 'won' ? nextBody : <Panel title="Next">{nextBody}</Panel>}
          </aside>
        )}
      </div>
    </div>
  );
}
