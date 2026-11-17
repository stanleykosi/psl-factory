'use client';

// SCR-11 Registers: Issues, Changes, Emergencies and RFPs, each with its count from summary.registers, a search and
// "Show more". The register and the search live in the URL; cursors never do.
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Button, ListToolbar, PriorityTag, Table, Tabs, Unknown, useIsPhone, type Column } from '@/components';
import { SampleLabel } from '@/shell/SampleLabel';

import { PANEL_ID } from './ProjectTabs';
import { AsOf, NONE, TabEmpty, OwnerValue, RowLink, RowsFooter, tabStateView } from './TabParts';
import {
  ageText,
  parseTabView,
  REGISTERS,
  registerCount,
  registerCountText,
  registerOf,
  tabSearch,
  type RegisterRow,
  type TabView,
} from './tabsModel';
import { useFocusAfterMore } from './useFocusAfterMore';
import { useProjectTab } from './useProjectTab';

function Severity({ value }: { value: RegisterRow['severity'] }) {
  return value === 'high' || value === 'medium' || value === 'low' ? <PriorityTag priority={value} /> : null;
}

const columns: Column<RegisterRow>[] = [
  { key: 'reference', header: 'ISSUE', mono: true, cell: (row) => row.reference },
  {
    key: 'what',
    header: 'WHAT',
    cell: (row) => (
      <>
        <RowLink workId={row.work_id}>{row.title}</RowLink><SampleLabel show={row.sample} />
      </>
    ),
  },
  { key: 'severity', header: 'SEVERITY', cell: (row) => <Severity value={row.severity} /> },
  { key: 'owner', header: 'OWNER', cell: (row) => <OwnerValue owner={row.owner} /> },
  { key: 'state', header: 'STATE', cell: (row) => row.state ?? NONE },
  { key: 'age', header: 'AGE', cell: (row) => ageText(row.age_seconds) ?? <Unknown /> },
];

/** SCR-11 phone: reference and severity, the title, then "state · owner". */
function RegisterCards({ rows }: { rows: RegisterRow[] }) {
  return (
    <div role="list" className="ptabs__cards">
      {rows.map((row, i) => (
        <div key={`${row.reference}-${i}`} role="listitem" className="ptabs__card">
          <span className="ptabs__cardhead">
            <span className="psl-mono ptabs__ref">{row.reference}</span>
            <Severity value={row.severity} />
          </span>
          <span className="ptabs__cardtitle">
            <RowLink workId={row.work_id}>{row.title}</RowLink><SampleLabel show={row.sample} />
          </span>
          <span className="ptabs__cardhint">
            {row.state && `${row.state} · `}
            <OwnerValue owner={row.owner} />
          </span>
        </div>
      ))}
    </div>
  );
}

export function RegistersTab({ caseId, base }: { caseId: string; base: string }) {
  const phone = useIsPhone();
  const router = useRouter();
  const params = useSearchParams();
  const view = useMemo(() => parseTabView(new URLSearchParams(params?.toString() ?? ''), 'registers'), [params]);
  const path = `${base}/registers`;
  const { state, more, showMore, retry } = useProjectTab(caseId, 'registers', view);
  const rowsRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef(view);
  useEffect(() => {
    viewRef.current = view;
  });
  useFocusAfterMore(rowsRef, state.status === 'ready' ? state.rows.length : 0);

  const navigate = useCallback((next: Partial<TabView>) => router.replace(`${path}${tabSearch({ ...viewRef.current, ...next })}`, { scroll: false }), [router, path]);

  // Search: the box keeps what the person typed; the URL takes the settled search (SearchField's pause).
  const [text, setText] = useState(view.q ?? '');
  const [syncedQ, setSyncedQ] = useState(view.q);
  if (view.q !== syncedQ) {
    setSyncedQ(view.q);
    if ((text.trim() || undefined) !== view.q) setText(view.q ?? '');
  }
  const applySearch = (value: string) => {
    const q = value.trim() || undefined;
    if (q !== viewRef.current.q) navigate({ q });
  };
  const clearSearch = () => {
    setText('');
    navigate({ q: undefined });
  };

  const summary = state.status === 'ready' ? state.summary : undefined;
  const { word } = registerOf(view.register);
  const shown = tabStateView(state, { retry, signInPath: `${path}${tabSearch(view)}` });

  let body = shown;
  if (state.status === 'ready') {
    const { rows } = state;
    body =
      rows.length === 0 ? (
        view.q ? (
          <TabEmpty
            action={
              <Button kind="secondary" onClick={clearSearch}>
                Clear search
              </Button>
            }
          >
            No {word} match &ldquo;{view.q}&rdquo;.
          </TabEmpty>
        ) : (
          <TabEmpty>No {word} on this project yet.</TabEmpty>
        )
      ) : (
        <>
          <div ref={rowsRef} className="ptabs__rows">
            {phone ? (
              <RegisterCards rows={rows} />
            ) : (
              <Table className="ptabs__table" tableClassName="ptabs__registers-table" caption={registerOf(view.register).label} columns={columns} rows={rows} rowKey={(row) => `${row.reference}-${row.title}`} empty="" />
            )}
          </div>
          <RowsFooter shown={rows.length} hasMore={Boolean(state.nextCursor)} more={more} onMore={() => void showMore()} />
          <AsOf value={state.asOf} />
          <p className="ptabs__note">Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval.</p>
        </>
      );
  }

  return (
    <>
      <Tabs
        label="Register"
        className="ptabs__registers"
        strip={phone}
        tabs={REGISTERS.map((r) => ({ key: r.key, label: r.label, href: `${path}${tabSearch({ register: r.key })}`, count: registerCount(summary, r.key) }))}
        selected={view.register}
        panelId={PANEL_ID}
      />
      <div role="search">
        <ListToolbar
          className="ptabs__toolbar"
          search={{ label: 'Search', placeholder: phone ? `Search ${word}` : `Search ${word} by title or reference`, value: text, onChange: setText, onSearch: applySearch }}
          resultText={registerCountText(summary, view.register)}
        />
      </div>
      {body}
    </>
  );
}
