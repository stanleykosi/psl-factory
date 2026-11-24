'use client';

// SCR-11 Registers on the live sectioned project tab: Issues, Changes, Emergencies and RFPs, each with the count the server
// sends (`total`), a search and "Show more". The register and the search live in the URL; the page never does.
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Button, ListToolbar, PriorityTag, Table, Tabs, Tag, useIsPhone, type Column } from '@/components';

import { MoreFooter } from './MoreFooter';
import { PANEL_ID } from './ProjectTabs';
import { ageText, availableRegisters, knownPriority, NO_OWNER, parseSectionView, registerCountText, sectionSearch, selectedRegister, type RegisterId, type SectionItem, type SectionView } from './sectionsModel';
import { AsOf, NONE, TabEmpty, TabNoAccess, tabStateView } from './TabParts';
import { useFocusAfterMore } from './useFocusAfterMore';
import { useProjectSections } from './useProjectSections';

function Severity({ value }: { value: string | null }) {
  const priority = knownPriority(value);
  if (priority) return <PriorityTag priority={priority} />;
  return value ? <Tag tone="neutral">{value}</Tag> : NONE;
}

/** The owner as sent. A null owner is "Owner needed" on Issues (in signal ink) and not applicable ("—") on the other registers. */
function Owner({ value, issues }: { value: string | null; issues: boolean }) {
  const owner = value ?? (issues ? NO_OWNER : null);
  if (owner === null) return NONE;
  return owner === NO_OWNER ? <span className="ptabs__noowner">{owner}</span> : <>{owner}</>;
}

const rowKey = (row: SectionItem) => `${row.api_url ?? ''}|${row.record_id}`;

const columnsOf = (issues: boolean): Column<SectionItem>[] => [
  { key: 'reference', header: 'ISSUE', mono: true, cell: (row) => row.title },
  { key: 'what', header: 'WHAT', cell: (row) => row.detail ?? NONE },
  { key: 'severity', header: 'SEVERITY', cell: (row) => <Severity value={row.severity} /> },
  { key: 'owner', header: 'OWNER', cell: (row) => <Owner value={row.owner} issues={issues} /> },
  { key: 'state', header: 'STATE', cell: (row) => row.state },
  { key: 'age', header: 'AGE', num: true, cell: (row) => ageText(row.age_days) },
];

/** SCR-11 phone: reference and severity, the WHAT text (else the reference), then "state · owner · age" without a part that reads "—". */
function RegisterCards({ rows, issues }: { rows: SectionItem[]; issues: boolean }) {
  return (
    <div role="list" className="ptabs__cards">
      {rows.map((row) => {
        const owner = row.owner ?? (issues ? NO_OWNER : null);
        const age = ageText(row.age_days);
        return (
          <div key={rowKey(row)} role="listitem" className="ptabs__card">
            <span className="ptabs__cardhead">
              <span className="psl-mono ptabs__ref">{row.title}</span>
              <Severity value={row.severity} />
            </span>
            <span className="ptabs__cardtitle">{row.detail ?? row.title}</span>
            <span className="ptabs__cardhint">{[row.state, owner, age === '—' ? null : age].filter(Boolean).join(' · ')}</span>
          </div>
        );
      })}
    </div>
  );
}

export function RegistersTab({ caseId, base }: { caseId: string; base: string }) {
  const phone = useIsPhone();
  const router = useRouter();
  const params = useSearchParams();
  const view = useMemo(() => parseSectionView(new URLSearchParams(params?.toString() ?? ''), 'registers'), [params]);
  const path = `${base}/registers`;
  const { state, more, showMore, retry } = useProjectSections(caseId, 'registers', view.q);
  const rowsRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef(view);
  useEffect(() => {
    viewRef.current = view;
  });

  const ready = state.status === 'ready' ? state : undefined;
  const available = useMemo(() => availableRegisters(ready?.sections ?? []), [ready]);
  const selected = selectedRegister(available, view.register);
  const section = ready && selected ? ready.sections.find((s) => s.key === selected.key) : undefined;
  const rows = section?.items ?? [];
  useFocusAfterMore(rowsRef, rows.length);

  const navigate = useCallback((next: Partial<SectionView>) => router.replace(`${path}${sectionSearch({ ...viewRef.current, ...next })}`, { scroll: false }), [router, path]);

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

  const word = selected?.word ?? 'issues';
  let body = tabStateView(state, { retry, signInPath: `${path}${sectionSearch(view)}` });
  if (ready) {
    const issues = selected?.id === 'issues';
    if (!selected || !section) body = <TabNoAccess />;
    else if (rows.length === 0)
      body = view.q ? (
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
      );
    else
      body = (
        <>
          <div ref={rowsRef} className="ptabs__rows">
            {phone ? <RegisterCards rows={rows} issues={issues} /> : <Table className="ptabs__table" tableClassName="ptabs__registers-table" caption={selected.label} columns={columnsOf(issues)} rows={rows} rowKey={rowKey} empty="" />}
          </div>
          <MoreFooter hasMore={section.has_more} busy={more === 'loading'} failed={more === 'error'} onMore={showMore} />
          <AsOf value={ready.asOf} />
          {issues && <p className="ptabs__note">Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval.</p>}
        </>
      );
  }

  const countOf = (key: string) => ready?.sections.find((s) => s.key === key)?.total;
  const tabs = available.map((r) => ({ key: r.id as RegisterId, label: r.label, href: `${path}${sectionSearch({ register: r.id, q: view.q })}`, count: countOf(r.key) }));
  return (
    <>
      {selected && tabs.length > 0 && <Tabs label="Register" className="ptabs__registers" strip={phone} tabs={tabs} selected={selected.id} panelId={PANEL_ID} />}
      <div role="search">
        <ListToolbar
          className="ptabs__toolbar"
          search={{ label: 'Search', placeholder: phone ? `Search ${word}` : `Search ${word} by title or reference`, value: text, onChange: setText, onSearch: applySearch }}
          resultText={selected && section ? registerCountText(selected, section.total) : ''}
        />
      </div>
      {body}
    </>
  );
}
