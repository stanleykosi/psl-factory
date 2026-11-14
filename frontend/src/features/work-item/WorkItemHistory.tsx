'use client';

// SCR-02 History: read-only (INV-AUDIT). The only controls are the filter, rows per page, Show more and
// Try again. Restricted entries show who and when only (INV-RESTRICTED).
import { useRef, type KeyboardEvent } from 'react';

import { LoadingState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';

import { ACTOR_TAGS, formatWat, HISTORY_FILTERS, HISTORY_LIMITS, type HistoryEntry, type HistoryKind, type HistoryLimit } from './labels';
import { useWorkHistory } from './useWorkHistory';
import { WorkErrorCard } from './WorkItemStates';

function HistoryFilter({ kind, onChange }: { kind: HistoryKind; onChange: (kind: HistoryKind) => void }) {
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
        </button>
      ))}
    </div>
  );
}

function HistoryRow({ entry }: { entry: HistoryEntry }) {
  const tag = ACTOR_TAGS[entry.actor_kind];
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
              <strong className="work-event">{entry.event}</strong>
              {entry.detail && <span className="work-detail">{entry.detail}</span>}
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

export function WorkItemHistory({ id, revision }: { id: string; revision: number }) {
  const { state, kind, setKind, limit, setLimit, retry, showMore } = useWorkHistory(id, revision);

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
  } else {
    body = (
      <>
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
                <HistoryRow key={i} entry={entry} />
              ))}
            </tbody>
          </table>
          {state.nextCursor && (
            <div className="psl-showmore">
              <span>Showing {state.items.length}</span>
              <button
                type="button"
                className={state.more === 'loading' ? 'psl-btn psl-btn--text is-busy' : 'psl-btn psl-btn--text'}
                aria-disabled={state.more === 'loading' || undefined}
                onClick={() => {
                  if (state.more !== 'loading') void showMore();
                }}
              >
                Show more
              </button>
            </div>
          )}
        </div>
        {state.more === 'failed' && (
          <div className="psl-callout psl-callout--warning">
            <WarningIcon />
            <span>We couldn&rsquo;t load more entries. Choose Show more to try again.</span>
          </div>
        )}
        <p className="work-note">As of {formatWat(state.asOf)}</p>
      </>
    );
  }

  return (
    <div className="work-columns work-columns--history">
      <div className="work-column">
        <div className="work-historybar">
          <HistoryFilter kind={kind} onChange={setKind} />
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
        </div>
        {body}
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
        <p className="psl-callout psl-callout--info">
          Times are WAT. You see only entries on records you may open; restricted entries show as &ldquo;Restricted&rdquo;
          with who and when.
        </p>
      </aside>
    </div>
  );
}
