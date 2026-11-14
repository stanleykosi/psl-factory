'use client';

// SCR-02 History: read-only (INV-AUDIT). The only controls are the filter, rows per page, Show more and
// Try again. Restricted entries show who and when only (INV-RESTRICTED).
import { useRef, type KeyboardEvent } from 'react';

import { LoadingState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';

import { InfoIcon } from './InfoIcon';
import { ACTOR_TAGS, formatWat, HISTORY_FILTERS, HISTORY_LIMITS, type HistoryKind, type HistoryLimit } from './labels';
import type { BoardHistoryEntry, WorkItemPresentation } from './presentation';
import { useWorkHistory } from './useWorkHistory';
import { WorkErrorCard } from './WorkItemStates';

type Counts = WorkItemPresentation['history_counts'];

function HistoryFilter({ kind, onChange, counts }: { kind: HistoryKind; onChange: (kind: HistoryKind) => void; counts: Counts }) {
  const options = useRef<(HTMLButtonElement | null)[]>([]);
  const index = HISTORY_FILTERS.findIndex((f) => f.kind === kind);

  // Radio-group keys: arrows move and choose, Home and End jump to the ends.
  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const last = HISTORY_FILTERS.length - 1;
    const keys: Record<string, number> = {
      ArrowRight: index === last ? 0 : index + 1,
      ArrowDown: index === last ? 0 : index + 1,
      ArrowLeft: index === 0 ? last : index - 1,
      ArrowUp: index === 0 ? last : index - 1,
      Home: 0,
      End: last,
    };
    if (!(event.key in keys)) return;
    event.preventDefault();
    const next = keys[event.key];
    onChange(HISTORY_FILTERS[next].kind);
    options.current[next]?.focus();
  }

  return (
    <div className="psl-seg work-filter" role="radiogroup" aria-label="Show">
      {HISTORY_FILTERS.map((f, i) => (
        <button
          key={f.kind}
          ref={(el) => {
            options.current[i] = el;
          }}
          type="button"
          role="radio"
          aria-checked={f.kind === kind}
          tabIndex={f.kind === kind ? 0 : -1}
          className="psl-seg__opt"
          onClick={() => onChange(f.kind)}
          onKeyDown={onKeyDown}
        >
          {f.label}
          {counts && (
            <>
              {' '}
              <span className="psl-badge">{counts[f.kind]}</span>
            </>
          )}
        </button>
      ))}
    </div>
  );
}

function HistoryRow({ entry, inline }: { entry: BoardHistoryEntry; inline: boolean }) {
  const tag = ACTOR_TAGS[entry.actor_kind];
  // On the boards the detail continues the event's line ("Approved invoice v2 for ₦4,250,000.00").
  const detailClass = inline ? 'work-detail work-detail--inline' : 'work-detail';
  return (
    <tr>
      <td className="work-when psl-mono">
        <time dateTime={entry.at}>{formatWat(entry.at)}</time>
      </td>
      <td>
        <div className="work-what">
          <span className="work-who">
            <span className={tag.className}>{tag.text}</span> {entry.actor}
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
      </td>
      <td className="work-version psl-mono">
        <span className="work-sr">Version: </span>
        {(!entry.restricted && entry.version) || '—'}
      </td>
    </tr>
  );
}

/** Phone: one card per entry, the time and version on its first line (SCR-02-mobile-history). */
function HistoryCard({ entry }: { entry: BoardHistoryEntry }) {
  const tag = ACTOR_TAGS[entry.actor_kind];
  return (
    <div role="listitem" className="work-hcard">
      <span className="work-hcard__when">
        <time dateTime={entry.at}>{formatWat(entry.at)}</time> · <span className="work-sr">Version: </span>
        {(!entry.restricted && entry.version) || '—'}
      </span>
      <div className="work-who">
        <span className={tag.className}>{tag.text}</span>
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
            <span key={i} className="work-line">
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
    body = (
      <div className="psl-empty">
        <h3>Nothing recorded for this filter yet.</h3>
      </div>
    );
  } else if (phone) {
    body = (
      <div className="work-hcards" role="list" aria-label="History, newest first">
        {state.items.map((entry, i) => (
          <HistoryCard key={i} entry={entry} />
        ))}
      </div>
    );
  } else {
    body = (
      <div className="psl-tablewrap work-history">
        <table className="psl-table">
          <caption className="work-sr">History, newest first</caption>
          <thead>
            <tr>
              <th scope="col">WHEN</th>
              <th scope="col">WHAT HAPPENED</th>
              <th scope="col">VERSION</th>
            </tr>
          </thead>
          <tbody>
            {state.items.map((entry, i) => (
              <HistoryRow key={i} entry={entry} inline={counts !== undefined} />
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="work-columns work-columns--history">
      <div className="work-column">
        <div className="work-historybar">
          <HistoryFilter kind={kind} onChange={setKind} counts={counts} />
        </div>
        {body}
        {/* rows per page, then Show more: the approved paging footer (D-PAGING r2), under the list */}
        <div className="work-historyfoot">
          <label className="work-limit">
            <span>Rows per page</span>
            <select className="psl-input" value={limit} onChange={(e) => setLimit(Number(e.target.value) as HistoryLimit)}>
              {HISTORY_LIMITS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          {ready?.nextCursor && (
            <div className="psl-showmore">
              <span>Showing {ready.items.length}</span>
              <button
                type="button"
                className={ready.more === 'loading' ? 'psl-btn psl-btn--text is-busy' : 'psl-btn psl-btn--text'}
                aria-disabled={ready.more === 'loading' || undefined}
                onClick={() => {
                  if (ready.more !== 'loading') void showMore();
                }}
              >
                {phone && counts ? `+ ${counts[kind] - ready.items.length} earlier entries` : 'Show more'}
              </button>
            </div>
          )}
        </div>
        {ready?.more === 'failed' && (
          <div className="psl-callout psl-callout--warning">
            <WarningIcon />
            <span>We couldn&rsquo;t load more entries. Choose Show more to try again.</span>
          </div>
        )}
        {ready && ready.items.length > 0 && <p className="work-note">As of {formatWat(ready.asOf)}</p>}
      </div>
      <aside className="work-column" aria-label="About history">
        <section className="psl-panel">
          <h2 className="psl-panel__head">About history</h2>
          <div className="psl-panel__body">
            <p className="work-plain">
              Every decision, agent step, piece of evidence and send is recorded here as it happens. Nothing can be
              edited or deleted; a correction is a new entry that points to the one it corrects.
            </p>
          </div>
        </section>
        <div className="psl-callout psl-callout--info">
          <InfoIcon />
          <span>
            Times are WAT. You see only entries on records you may open; restricted entries show as &ldquo;Restricted&rdquo;
            with who and when.
          </span>
        </div>
      </aside>
    </div>
  );
}
