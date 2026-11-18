'use client';

// SCR-43 Delivery tab: the project's delivery lines as E-PROJECT `delivery[]` returns them (PROPOSAL fields in model.ts, contract
// mock only). Nothing is counted, ruled or composed here: rows are numbered by position, tags take their tone from the
// returned `tone`, and a row links only through its `work_id`. No second read and no write.
import Link from 'next/link';

import { EmptyState, formatDayMonth, formatDayTime, Panel, Tag, Unknown, VisuallyHidden, STATE_TAGS, type FactoryState } from '@/components';
import { AGENT_NAMES } from '@/features/decide/format';
import { AgentCard } from '@/features/work-item/WorkItemOverview';
import { tagTone } from '@/features/workspace/labels';

import { deliveryAgentOf, deliveryNoteOf, deliveryRowsOf, type DeliveryRow, type JourneyView } from './model';

import './project-tabs.css';

// Frontend-owned neutral wording (spec Assumptions); none of it is a business rule.
const TEXT = {
  heading: 'The delivery lines, in order',
  emptyTitle: 'No delivery lines',
  empty: 'No delivery lines yet.',
  checked: 'Checked',
  ask: 'Ask Tola',
  next: 'Next',
  noReference: '—',
} as const;

/** The sub-nav at 1440 (Conflicts 5): Overview is current; a row links only when it has a work id. Not drawn on phones. */
function DeliveryNav({ rows }: { rows: DeliveryRow[] }) {
  return (
    <nav aria-label="Delivery lines" className="psl-tabs delivery__nav">
      <span className="psl-tab" aria-current="page">
        Overview
      </span>
      {rows.map((row) =>
        row.workId ? (
          <Link key={row.key} className="psl-tab" href={`/work/${encodeURIComponent(row.workId)}`}>
            {row.shortTitle}
          </Link>
        ) : (
          <span key={row.key} className="psl-tab">
            {row.shortTitle}
          </span>
        ),
      )}
    </nav>
  );
}

function RowTag({ row }: { row: DeliveryRow }) {
  if (row.gate) return <Tag tone={tagTone(row.gate.tone)}>{row.gate.label}</Tag>;
  const state = row.state && Object.hasOwn(STATE_TAGS, row.state) ? STATE_TAGS[row.state as FactoryState].text : undefined;
  return (
    <Tag tone="neutral">
      Unknown{state && <VisuallyHidden>, {state}</VisuallyHidden>}
    </Tag>
  );
}

function RowWhen({ row }: { row: DeliveryRow }) {
  if (row.at?.date) return <> · {formatDayMonth(row.at.date)}</>;
  if (row.at?.unknown) return <> · <Unknown /></>;
  if (row.detail) return <> · {row.detail}</>;
  return null;
}

function Rows({ rows }: { rows: DeliveryRow[] }) {
  return (
    <ol className="delivery__rows">
      {rows.map((row) => (
        <li key={row.key} className="delivery__row">
          <span className="delivery__num psl-mono" aria-hidden="true">
            {row.number}
          </span>
          <span className="delivery__main">
            {row.workId ? (
              <Link className="delivery__title" href={`/work/${encodeURIComponent(row.workId)}`}>
                {row.title}
              </Link>
            ) : (
              <span className="delivery__title">{row.title}</span>
            )}
            <span className="delivery__ref psl-mono">{row.reference ?? TEXT.noReference}</span>
          </span>
          <span className="delivery__state">
            <RowTag row={row} />
            <span className="delivery__when">
              <RowWhen row={row} />
            </span>
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Tola's delivery check (G-43-3), or the project summary's text when no check is returned. */
function DeliveryAgent({ journey }: { journey: JourneyView }) {
  const check = deliveryAgentOf(journey);
  if (check) {
    return (
      <Panel kind="agent" as="aside" head={check.title ?? `${AGENT_NAMES[check.agent]}’s delivery check`} className="delivery__agent" aria-label={check.title ?? `${AGENT_NAMES[check.agent]}’s delivery check`}>
        <AgentCard agent={{ name: AGENT_NAMES[check.agent], status: check.status, steps: check.steps }} />
        {check.finishedAt && (
          <p className="delivery__checked">
            {TEXT.checked} <time dateTime={check.finishedAt}>{formatDayTime(check.finishedAt)}</time>
          </p>
        )}
        <p>
          <Link href="/assistant">{TEXT.ask}</Link>
        </p>
      </Panel>
    );
  }
  const text = journey.agent_summary?.text;
  if (!text) return null;
  return (
    <Panel kind="agent" as="aside" head={`${AGENT_NAMES[journey.agent_summary!.agent]}’s summary`} className="delivery__agent" aria-label={`${AGENT_NAMES[journey.agent_summary!.agent]}’s summary`}>
      {text.split(/\n\s*\n/).map((paragraph, i) => (
        <p key={i}>{paragraph}</p>
      ))}
    </Panel>
  );
}

export function DeliveryTab({ journey }: { journey: JourneyView }) {
  const rows = deliveryRowsOf(journey);
  const note = deliveryNoteOf(journey);
  return (
    <>
      {rows.length > 0 && <DeliveryNav rows={rows} />}
      <div className="delivery__body">
        <div className="delivery__lines">
          <Panel head={TEXT.heading} className="delivery__panel">
            {rows.length === 0 ? <EmptyState title={TEXT.emptyTitle}>{TEXT.empty}</EmptyState> : <Rows rows={rows} />}
            {note && <p className="delivery__note">{note}</p>}
          </Panel>
          <Panel head={TEXT.next} className="delivery__nextpanel">
            <p className="delivery__next">{journey.next}</p>
          </Panel>
        </div>
        <DeliveryAgent journey={journey} />
      </div>
    </>
  );
}
