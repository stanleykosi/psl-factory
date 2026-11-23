'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';
import { Button, EmptyState, FilterPanel, ListToolbar, PageTitle, Table, Tabs, Unknown, useIsPhone, type Column } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';

import { MoreFooter } from './MoreFooter';
import {
  buildProjectsQuery,
  countOf,
  isProjectList,
  LIST_TABS,
  MAX_Q,
  parseProjectsView,
  projectsSearch,
  settledQ,
  shownText,
  textOf,
  whereText,
  type ProjectRow,
  type ProjectsView,
} from './model';

type ListState =
  | { status: 'loading' }
  | { status: 'ready'; items: ProjectRow[]; nextCursor: string | null }
  | { status: 'error'; error: ApiError };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const malformed = () => new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);

/** A needs-a-person or stopped count; a count the response carries as null is Unknown, never 0. */
function Count({ value: sent }: { value: unknown }) {
  const value = countOf(sent);
  if (value === undefined) return <Unknown />;
  return <span className={value > 0 ? 'projects__count' : 'projects__zero'}>{value}</span>;
}

const columns: Column<ProjectRow>[] = [
  {
    key: 'project',
    header: 'PROJECT',
    cell: (item) => (
      <span className="projects__titlecell">
        <Link href={`/projects/${encodeURIComponent(item.case_id)}`} className="projects__title" data-project-link="">
          {item.title}
        </Link>
        <SampleLabel show={item.sample} />
      </span>
    ),
  },
  { key: 'pm', header: 'PM', cell: (item) => textOf(item.manager) ?? 'No manager' },
  { key: 'where', header: 'WHERE IT IS', cell: (item) => whereText(item) },
  { key: 'needs', header: 'NEEDS A PERSON', cell: (item) => <Count value={item.reviews} /> },
  { key: 'stopped', header: 'STOPPED', cell: (item) => <Count value={item.exceptions} /> },
];

/** SCR-22 desktop: Project, PM, Where it is, Needs a person, Stopped. */
function ProjectTable({ items }: { items: ProjectRow[] }) {
  return <Table className="projects__table" caption="Projects" columns={columns} rows={items} rowKey={(item) => item.case_id} empty="No projects you can see yet." />;
}

/** The phone card's red line: "2 need a person · 1 stopped"; nothing when both are 0 or not carried. */
function attentionText(item: ProjectRow) {
  const parts = [];
  const needsPerson = countOf(item.reviews);
  const stopped = countOf(item.exceptions);
  if (needsPerson) parts.push(`${needsPerson} need a person`);
  if (stopped) parts.push(`${stopped} stopped`);
  return parts.join(' · ');
}

/** SCR-22 phone: each card is one link with the title, where it is and the PM, then what needs attention. */
function ProjectCards({ items }: { items: ProjectRow[] }) {
  return (
    <ul className="projects__cards">
      {items.map((item) => {
        const attention = attentionText(item);
        return (
          <li key={item.case_id}>
            <Link href={`/projects/${encodeURIComponent(item.case_id)}`} className="projects__card" data-project-link="">
              <span className="projects__title">{item.title}</span>
              <span className="projects__meta">
                {whereText(item)}
                {textOf(item.manager) && ` · PM ${item.manager}`}
              </span>
              {attention && <span className="projects__attention">{attention}</span>}
              <SampleLabel show={item.sample} />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

const LIST_PANEL_ID = 'projects-panel';

/** SCR-22 Projects: the projects the person's grants cover, from GET /projects, with search, status and Show more. */
export function ProjectsList() {
  const me = useMe();
  const params = useSearchParams();
  const router = useRouter();
  const view = useMemo(() => parseProjectsView(new URLSearchParams(params?.toString() ?? '')), [params]);
  const phone = useIsPhone();

  const [list, setList] = useState<ListState>({ status: 'loading' });
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const [signedOut, setSignedOut] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);

  const seq = useRef(0);
  const focusRow = useRef<number | null>(null);
  const viewRef = useRef(view);
  const rowsRef = useRef<HTMLDivElement>(null);

  const navigate = useCallback(
    (next: Partial<ProjectsView>) => router.replace(`/projects${projectsSearch({ ...viewRef.current, ...next })}`, { scroll: false }),
    [router],
  );

  const fetchPage = useCallback(async (v: ProjectsView, cursor?: string) => {
    const data = await call(liveApi.GET('/api/v1/projects', { params: { query: buildProjectsQuery(v, cursor) } }));
    if (!isProjectList(data)) throw malformed();
    return data;
  }, []);

  /** Page 1 of a view. A response for an older view is ignored. */
  const load = useCallback(
    async (v: ProjectsView) => {
      const mine = ++seq.current;
      setList({ status: 'loading' });
      setMore('idle');
      try {
        const data = await fetchPage(v);
        if (mine !== seq.current) return;
        setList({ status: 'ready', items: data.items, nextCursor: data.next_cursor });
      } catch (error) {
        if (mine !== seq.current) return;
        const e = asApiError(error);
        if (e.kind === 'unauthenticated') setSignedOut(true);
        else setList({ status: 'error', error: e });
      }
    },
    [fetchPage],
  );

  const showMore = async () => {
    if (list.status !== 'ready' || !list.nextCursor) return;
    const mine = seq.current;
    setMore('loading');
    try {
      const data = await fetchPage(view, list.nextCursor);
      if (mine !== seq.current) return;
      setList((prev) => (prev.status !== 'ready' ? prev : { ...prev, items: [...prev.items, ...data.items], nextCursor: data.next_cursor }));
      setMore('idle');
    } catch (error) {
      if (mine !== seq.current) return;
      if (asApiError(error).kind === 'unauthenticated') setSignedOut(true);
      else setMore('error');
    }
  };

  // A new search or tab reloads from page 1.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reloadView = useMemo(() => view, [view.q, view.tab]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(reloadView);
  }, [reloadView, load]);
  useEffect(() => {
    viewRef.current = view;
  }, [view]);

  // Show more: the keyboard moves to the first row it added.
  const onMore = () => {
    if (list.status === 'ready' && more !== 'error') focusRow.current = list.items.length;
    void showMore();
  };

  useEffect(() => {
    if (focusRow.current !== null && list.status === 'ready' && list.items.length > focusRow.current) {
      rowsRef.current?.querySelectorAll<HTMLElement>('[data-project-link]')[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [list]);

  // Search: the box keeps what the person typed; the URL takes the settled search (SearchField's pause).
  const [text, setText] = useState(view.q ?? '');
  const [syncedQ, setSyncedQ] = useState(view.q);
  if (view.q !== syncedQ) {
    setSyncedQ(view.q);
    if ((text.trim() || undefined) !== view.q) setText(view.q ?? '');
  }
  const applySearch = (value: string) => {
    const q = settledQ(value);
    if (q !== viewRef.current.q) navigate({ q });
  };
  const clearSearch = () => {
    setText('');
    navigate({ q: undefined });
  };

  const closeFilter = useCallback(() => setFilterOpen(false), []);

  if (signedOut) return <SignedOutState pathname="/projects" />;
  if (list.status === 'error' && list.error.kind === 'forbidden') {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }

  let body;
  if (list.status === 'loading') {
    body = <LoadingState />;
  } else if (list.status === 'error') {
    body = (
      <WorkErrorCard
        message="We couldn’t load your projects. Your work is safe; nothing was changed."
        error={list.error}
        onRetry={() => void load(view)}
      />
    );
  } else if (list.items.length === 0 && view.q) {
    body = (
      <EmptyState
        title="No projects match"
        action={
          <Button kind="link" onClick={clearSearch}>
            Show all projects
          </Button>
        }
      >
        No project you can see matches your search.
      </EmptyState>
    );
  } else if (list.items.length === 0) {
    body = <EmptyState title="No projects you can see yet.">You see projects your roles cover.</EmptyState>;
  } else {
    body = (
      <>
        <div ref={rowsRef}>
          {phone ? <ProjectCards items={list.items} /> : <ProjectTable items={list.items} />}
        </div>
        <MoreFooter hasMore={list.nextCursor !== null} busy={more === 'loading'} failed={more === 'error'} onMore={onMore} />
        <p className="projects__note">You see projects your roles cover. Open one for its journey, documents, money and registers.</p>
      </>
    );
  }

  return (
    <div className="projects__page">
      <p className="projects__eyebrow">PROJECTS</p>
      <PageTitle>Projects</PageTitle>
      <Tabs
        label="Projects"
        className="projects__listtabs"
        tabs={LIST_TABS.map((tab) => ({ key: tab.key, label: tab.label }))}
        selected={view.tab}
        onSelect={(tab) => navigate({ tab })}
        panelId={LIST_PANEL_ID}
      />
      <div role="search">
        <ListToolbar
          className="projects__toolbar"
          search={{ label: 'Search', placeholder: phone ? 'Search projects' : 'Search projects or clients', value: text, onChange: (value) => setText(value.slice(0, MAX_Q)), onSearch: applySearch }}
          filterCount={0}
          filterOpen={filterOpen}
          onFilterToggle={() => setFilterOpen((open) => !open)}
          filterPanel={
            <FilterPanel title="Filter projects" applyLabel="Close" onApply={closeFilter} onClear={closeFilter} onClose={closeFilter}>
              <strong>Filters come next</strong>
              <p>Search finds a project by its name or its client today.</p>
            </FilterPanel>
          }
          resultText={list.status === 'ready' ? shownText(list.items.length, list.nextCursor !== null) : ''}
        />
      </div>
      <div role="tabpanel" id={LIST_PANEL_ID} aria-label={LIST_TABS.find((tab) => tab.key === view.tab)?.label} className="projects__panel">
        {body}
      </div>
    </div>
  );
}
