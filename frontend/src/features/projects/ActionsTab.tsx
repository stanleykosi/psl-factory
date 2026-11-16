'use client';

// SCR-29 Actions: the project's actions from confirmed minutes, with the counts of summary.actions and a search.
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Button, EmptyState, ListToolbar, Table, Tag, Unknown, useIsPhone, type Column, type TagTone } from '@/components';

import { AsOf, OwnerValue, RowLink, RowsFooter, tabStateView } from './TabParts';
import { actionsSummaryText, dueText, fromText, parseTabView, tabSearch, type ActionRow } from './tabsModel';
import { useFocusAfterMore } from './useFocusAfterMore';
import { useProjectTab } from './useProjectTab';

const STATES: Record<ActionRow['state'], { text: string; tone: TagTone }> = {
  open: { text: 'OPEN', tone: 'waiting' },
  overdue: { text: 'OVERDUE', tone: 'person' },
  done: { text: 'DONE', tone: 'done' },
};

function StateValue({ state }: { state: ActionRow['state'] }) {
  const tag = Object.hasOwn(STATES, state) ? STATES[state] : { text: String(state).toUpperCase(), tone: 'neutral' as const };
  return <Tag tone={tag.tone}>{tag.text}</Tag>;
}

function Due({ due }: { due: ActionRow['due'] }) {
  return dueText(due) ?? <Unknown />;
}

const columns: Column<ActionRow>[] = [
  {
    key: 'action',
    header: 'ACTION',
    cell: (row) => (
      <>
        <RowLink workId={row.work_id}>{row.title}</RowLink>
        {fromText(row.from) && <span className="ptabs__block ptabs__hint">{fromText(row.from)}</span>}
      </>
    ),
  },
  { key: 'owner', header: 'OWNER', cell: (row) => <OwnerValue owner={row.owner} /> },
  { key: 'due', header: 'DUE', cell: (row) => <Due due={row.due} /> },
  { key: 'state', header: 'STATE', cell: (row) => <StateValue state={row.state} /> },
];

/** SCR-29 phone: the title with its state tag, then "owner · due date". */
function ActionCards({ rows }: { rows: ActionRow[] }) {
  return (
    <div role="list" className="ptabs__cards">
      {rows.map((row) => (
        <div key={row.action_id} role="listitem" className="ptabs__card">
          <span className="ptabs__cardhead">
            <strong>
              <RowLink workId={row.work_id}>{row.title}</RowLink>
            </strong>
            <StateValue state={row.state} />
          </span>
          <span className="ptabs__cardhint">
            <OwnerValue owner={row.owner} /> · due <Due due={row.due} />
          </span>
        </div>
      ))}
    </div>
  );
}

export function ActionsTab({ caseId, base }: { caseId: string; base: string }) {
  const phone = useIsPhone();
  const router = useRouter();
  const params = useSearchParams();
  const view = useMemo(() => parseTabView(new URLSearchParams(params?.toString() ?? ''), 'actions'), [params]);
  const path = `${base}/actions`;
  const { state, more, showMore, retry } = useProjectTab(caseId, 'actions', view);
  const rowsRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef(view);
  useEffect(() => {
    viewRef.current = view;
  });
  useFocusAfterMore(rowsRef, state.status === 'ready' ? state.rows.length : 0);

  const navigate = useCallback((q: string | undefined) => router.replace(`${path}${tabSearch({ ...viewRef.current, q })}`, { scroll: false }), [router, path]);

  const [text, setText] = useState(view.q ?? '');
  const [syncedQ, setSyncedQ] = useState(view.q);
  if (view.q !== syncedQ) {
    setSyncedQ(view.q);
    if ((text.trim() || undefined) !== view.q) setText(view.q ?? '');
  }
  const applySearch = (value: string) => {
    const q = value.trim() || undefined;
    if (q !== viewRef.current.q) navigate(q);
  };
  const clearSearch = () => {
    setText('');
    navigate(undefined);
  };

  let body = tabStateView(state, { retry, signInPath: `${path}${tabSearch(view)}` });
  if (state.status === 'ready') {
    const { rows } = state;
    body =
      rows.length === 0 ? (
        view.q ? (
          <EmptyState
            title="No actions match"
            action={
              <Button kind="secondary" onClick={clearSearch}>
                Clear search
              </Button>
            }
          >
            No actions match &ldquo;{view.q}&rdquo;.
          </EmptyState>
        ) : (
          <EmptyState title="No actions yet">No actions on this project yet.</EmptyState>
        )
      ) : (
        <>
          <div ref={rowsRef} className="ptabs__rows">
            {phone ? <ActionCards rows={rows} /> : <Table className="ptabs__table" caption="Actions" columns={columns} rows={rows} rowKey={(row) => row.action_id} empty="" />}
          </div>
          <RowsFooter shown={rows.length} hasMore={Boolean(state.nextCursor)} more={more} onMore={() => void showMore()} />
          <AsOf value={state.asOf} />
          <p className="ptabs__note">Actions come from confirmed minutes.</p>
        </>
      );
  }

  return (
    <>
      <div role="search">
        <ListToolbar
          className="ptabs__toolbar"
          search={{ label: 'Search', placeholder: 'Search actions', value: text, onChange: setText, onSearch: applySearch }}
          resultText={state.status === 'ready' ? actionsSummaryText(state.summary) : ''}
        />
      </div>
      {body}
    </>
  );
}
