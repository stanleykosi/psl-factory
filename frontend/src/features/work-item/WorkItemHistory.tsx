'use client';

// SCR-02 History: read-only (INV-AUDIT). The only controls are the filter, the paging footer (rows per page, Show
// more) and Try again. Restricted entries show who and when only (INV-RESTRICTED).
import { Callout, EmptyState, formatDayTime, Panel, Segmented, ShowMore, Table, Tag, type Column } from '@/components';
import { LoadingState } from '@/shell/FrameStates';

import { ACTOR_TAGS, HISTORY_FILTERS, type HistoryKind } from './labels';
import type { BoardHistoryEntry, WorkItemPresentation } from './presentation';
import { useWorkHistory } from './useWorkHistory';
import { WorkErrorCard } from './WorkItemStates';

type Counts = WorkItemPresentation['history_counts'];

type FilterProps = { kind: HistoryKind; onChange: (kind: HistoryKind) => void; counts: Counts; phoneBoard: boolean };

function HistoryFilter({ kind, onChange, counts, phoneBoard }: FilterProps) {
  // the phone board draws three segments: All, Decisions, Agents (Evidence is on the desktop filter)
  const filters = phoneBoard ? HISTORY_FILTERS.filter((f) => f.kind !== 'evidence').map((f) => (f.kind === 'agent_work' ? { ...f, label: 'Agents' } : f)) : HISTORY_FILTERS;
  return (
    <Segmented
      label="Show"
      className="work-filter"
      value={kind}
      onChange={onChange}
      options={filters.map((f) => ({ value: f.kind, label: f.label, count: counts?.[f.kind] }))}
    />
  );
}

function Actor({ kind }: { kind: BoardHistoryEntry['actor_kind'] }) {
  const tag = ACTOR_TAGS[kind];
  return <Tag tone={tag.tone}>{tag.text}</Tag>;
}

function historyColumns(inline: boolean): Column<BoardHistoryEntry>[] {
  // On the boards the detail continues the event's line ("Approved invoice v2 for ₦4,250,000.00").
  const detailClass = inline ? 'work-detail work-detail--inline' : 'work-detail';
  return [
    { key: 'when', header: 'WHEN', mono: true, cell: (entry) => <time dateTime={entry.at}>{formatDayTime(entry.at)}</time> },
    {
      key: 'what',
      header: 'WHAT HAPPENED',
      cell: (entry) => (
        <div className="work-what">
          <span className="work-who">
            <Actor kind={entry.actor_kind} /> {entry.actor}
          </span>
          {entry.restricted ? (
            <strong className="work-event">Restricted</strong>
          ) : (
            <>
              <span className="work-eventline">
                <strong className="work-event">{entry.event}</strong>
                {entry.detail && inline && ' '}
                {entry.detail && <span className={detailClass}>{entry.detail}</span>}
              </span>
              {entry.lines?.map((line, i) => (
                <span key={i} className="work-line">
                  {line}
                </span>
              ))}
            </>
          )}
        </div>
      ),
    },
    {
      key: 'version',
      header: 'VERSION',
      mono: true,
      cell: (entry) => (
        <>
          <span className="cmp-sr">Version: </span>
          {(!entry.restricted && entry.version) || '—'}
        </>
      ),
    },
  ];
}

/** Phone: one card per entry, the time and version on its first line (SCR-02-mobile-history). */
function HistoryCard({ entry, board }: { entry: BoardHistoryEntry; board: boolean }) {
  const tag = ACTOR_TAGS[entry.actor_kind];
  return (
    <div role="listitem" className="work-hcard">
      <span className="work-hcard__when">
        <time dateTime={entry.at}>{formatDayTime(entry.at)}</time> · <span className="cmp-sr">Version: </span>
        {(!entry.restricted && entry.version) || '—'}
      </span>
      <div className="work-who">
        {/* the phone board draws the actor without the kind tag or the extra lines; they stay for screen readers */}
        <Tag tone={tag.tone} className={board ? 'cmp-sr' : undefined}>
          {tag.text}
        </Tag>
        <span>{entry.actor}</span>
      </div>
      {entry.restricted ? (
        <strong className="work-event">Restricted</strong>
      ) : (
        <>
          <span className="work-eventline">
            <strong className="work-event">{entry.event}</strong>
            {entry.detail && ` ${entry.detail}`}
          </span>
          {entry.lines?.map((line, i) => (
            <span key={i} className={board ? 'work-line cmp-sr' : 'work-line'}>
              {line}
            </span>
          ))}
        </>
      )}
    </div>
  );
}

type HistoryProps = { id: string; revision: number; counts?: Counts; phone?: boolean };

export function WorkItemHistory({ id, revision, counts, phone = false }: HistoryProps) {
  const { state, kind, setKind, limit, setLimit, retry, showMore } = useWorkHistory(id, revision);
  const ready = state.status === 'ready' ? state : undefined;
  const board = phone && counts !== undefined;

  // On the desktop board the as-of line sits in the side column, under the callout, where the board draws its own.
  const side = counts !== undefined && !phone;
  const paging = ready && {
    shown: ready.items.length,
    hasMore: Boolean(ready.nextCursor),
    busy: ready.more === 'loading',
    onMore: () => void showMore(),
    size: limit,
    onSize: setLimit,
  };
  const asOf = ready && ready.items.length > 0 && !board && <p className="work-note">As of {formatDayTime(ready.asOf)}</p>;

  let body;
  if (state.status === 'loading') body = <LoadingState />;
  else if (state.status === 'error') {
    body = (
      <WorkErrorCard
        message="We couldn’t load this item’s history. Your work is safe; nothing was changed."
        error={state.error}
        onRetry={() => void retry()}
      />
    );
  } else if (state.items.length === 0) {
    body = <EmptyState title="Nothing recorded for this filter yet.">Try another filter.</EmptyState>;
  } else if (phone) {
    body = (
      <>
        <div className="work-hcards" role="list" aria-label="History, newest first">
          {state.items.map((entry, i) => (
            <HistoryCard key={i} entry={entry} board={board} />
          ))}
        </div>
        {paging && <ShowMore solo {...paging} />}
      </>
    );
  } else {
    body = (
      <Table
        className="work-history"
        caption="History, newest first"
        columns={historyColumns(counts !== undefined)}
        rows={state.items}
        rowKey={(entry) => `${state.items.indexOf(entry)}`}
        empty="Nothing recorded for this filter yet."
        paging={paging || undefined}
      />
    );
  }

  return (
    <div className="work-columns">
      <div className="work-column">
        <div className="work-historybar">
          <HistoryFilter kind={kind} onChange={setKind} counts={counts} phoneBoard={board} />
        </div>
        {body}
        {ready?.more === 'failed' && (
          <Callout kind="warning">We couldn&rsquo;t load more entries. Choose Show more to try again.</Callout>
        )}
        {!side && asOf}
      </div>
      <aside className={board ? 'work-column cmp-sr' : 'work-column'} aria-label="About history">
        <Panel head="About history">
          <p className="work-plain">
            Every decision, agent step, piece of evidence and send is recorded here as it happens. Nothing can be
            edited or deleted; a correction is a new entry that points to the one it corrects.
          </p>
        </Panel>
        <Callout kind="info" announce={false}>
          Times are WAT. You see only entries on records you may open; restricted entries show as &ldquo;Restricted&rdquo;
          with who and when.
        </Callout>
        {side && <div className="work-historymeta">{asOf}</div>}
      </aside>
    </div>
  );
}
