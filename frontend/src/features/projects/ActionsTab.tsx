'use client';

// SCR-29 Actions on the live sectioned project tab: the project's actions from confirmed minutes, with the counts the server
// sends (`counts`, `total`) and a search. Nothing is counted from the rows loaded.
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Button, ListToolbar, Table, Tag, Unknown, useIsPhone, type Column } from '@/components';

import { MoreFooter } from './MoreFooter';
import { ACTIONS_SECTION_KEY, actionsHeaderText, dueText, fromText, NO_OWNER, parseSectionView, sectionSearch, stateTone, type SectionItem } from './sectionsModel';
import { AsOf, TabEmpty, TabNoAccess, tabStateView } from './TabParts';
import { useFocusAfterMore } from './useFocusAfterMore';
import { useProjectSections } from './useProjectSections';

const rowKey = (row: SectionItem) => `${row.api_url ?? ''}|${row.record_id}`;

function StateValue({ row }: { row: SectionItem }) {
  return <Tag tone={stateTone(row.state_code)}>{row.state.toUpperCase()}</Tag>;
}

function Due({ due }: { due: string | null }) {
  return dueText(due) ?? <Unknown />;
}

/** The owner as sent (`detail`); "Owner needed" in signal ink when it is missing or says so. */
function ActionOwner({ value }: { value: string | null }) {
  return value && value !== NO_OWNER ? <>{value}</> : <span className="ptabs__noowner">{NO_OWNER}</span>;
}

const columns: Column<SectionItem>[] = [
  {
    key: 'action',
    header: 'ACTION',
    cell: (row) => (
      <>
        {row.title}
        {fromText(row.origin_meeting) && <span className="ptabs__block ptabs__hint">{fromText(row.origin_meeting)}</span>}
      </>
    ),
  },
  { key: 'owner', header: 'OWNER', cell: (row) => <ActionOwner value={row.detail} /> },
  { key: 'due', header: 'DUE', cell: (row) => <Due due={row.due} /> },
  { key: 'state', header: 'STATE', cell: (row) => <StateValue row={row} /> },
];

/** SCR-29 phone: the title with its state tag, the From line, then "owner · due date". */
function ActionCards({ rows }: { rows: SectionItem[] }) {
  return (
    <div role="list" className="ptabs__cards">
      {rows.map((row) => (
        <div key={rowKey(row)} role="listitem" className="ptabs__card">
          <span className="ptabs__cardhead">
            <strong>{row.title}</strong>
            <StateValue row={row} />
          </span>
          {fromText(row.origin_meeting) && <span className="ptabs__cardhint">{fromText(row.origin_meeting)}</span>}
          <span className="ptabs__cardhint">
            <ActionOwner value={row.detail} /> · due <Due due={row.due} />
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
  const view = useMemo(() => parseSectionView(new URLSearchParams(params?.toString() ?? ''), 'actions'), [params]);
  const path = `${base}/actions`;
  const { state, more, showMore, retry } = useProjectSections(caseId, 'actions', view.q);
  const rowsRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef(view);
  useEffect(() => {
    viewRef.current = view;
  });

  const ready = state.status === 'ready' ? state : undefined;
  const section = ready?.sections.find((s) => s.key === ACTIONS_SECTION_KEY);
  const rows = section?.items ?? [];
  useFocusAfterMore(rowsRef, rows.length);

  const navigate = useCallback((q: string | undefined) => router.replace(`${path}${sectionSearch({ ...viewRef.current, q })}`, { scroll: false }), [router, path]);

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

  let body = tabStateView(state, { retry, signInPath: `${path}${sectionSearch(view)}` });
  if (ready) {
    if (!section) body = <TabNoAccess />;
    else if (rows.length === 0)
      body = view.q ? (
        <TabEmpty
          action={
            <Button kind="secondary" onClick={clearSearch}>
              Clear search
            </Button>
          }
        >
          No actions match &ldquo;{view.q}&rdquo;.
        </TabEmpty>
      ) : (
        <TabEmpty>No actions on this project yet.</TabEmpty>
      );
    else
      body = (
        <>
          <div ref={rowsRef} className="ptabs__rows">
            {phone ? <ActionCards rows={rows} /> : <Table className="ptabs__table" tableClassName="ptabs__actions-table" caption="Actions" columns={columns} rows={rows} rowKey={rowKey} empty="" />}
          </div>
          <MoreFooter hasMore={section.has_more} busy={more === 'loading'} failed={more === 'error'} onMore={showMore} />
          <AsOf value={ready.asOf} />
          <p className="ptabs__note">Actions come from confirmed minutes.</p>
        </>
      );
  }

  // The header counts follow the search, so with a search set the line is the matching total; a null `counts` draws no line.
  const header = !section ? '' : view.q ? `${section.total} actions match “${view.q}”` : actionsHeaderText(section.counts);
  return (
    <>
      <div role="search">
        <ListToolbar
          className="ptabs__toolbar"
          search={{ label: 'Search', placeholder: 'Search actions', value: text, onChange: setText, onSearch: applySearch }}
          resultText={header}
        />
      </div>
      {body}
    </>
  );
}
