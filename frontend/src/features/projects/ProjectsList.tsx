'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';
import { Button, Callout, EmptyState, FilterPanel, ListToolbar, PageTitle, ShowMore, Table, Tabs, Unknown, useIsPhone, usePagedRows, type Column, type ShowMoreProps } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';

import {
  buildProjectsQuery,
  countOf,
  isProjectList,
  LIST_TABS,
  nextMilestoneText,
  parseProjectsView,
  projectsSearch,
  type ProjectListView,
  type ProjectRowView,
  type ProjectsView,
} from './model';

type ListState =
  | { status: 'loading' }
  | { status: 'ready'; items: ProjectRowView[]; nextCursor?: string; counts?: ProjectListView['counts']; total?: number }
  | { status: 'error'; error: ApiError };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const malformed = () => new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);

/** A person-needed or stopped count (PROPOSAL); a count the response does not carry is Unknown, never 0. */
function Count({ value: sent }: { value: unknown }) {
  const value = countOf(sent);
  if (value === undefined) return <Unknown />;
  return <span className={value > 0 ? 'projects__count' : 'projects__zero'}>{value}</span>;
}

/**
 * D-94: a closed project has no next milestone to come, so the cell is "—" as SCR-22 draws it; an open project whose
 * next milestone the response did not send is Unknown. Open or closed comes from the API, never from text: the rows
 * carry no state of their own, so a row is known to be closed only when the list was asked for closed projects.
 */
function nextMilestoneCell(item: ProjectRowView, closed: boolean) {
  return nextMilestoneText(item.next_milestone) ?? (closed ? '—' : <Unknown />);
}

const columns = (closed: boolean): Column<ProjectRowView>[] => [
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
  { key: 'pm', header: 'PM', cell: (item) => item.pm },
  { key: 'stage', header: 'WHERE IT IS', cell: (item) => item.stage },
  { key: 'next', header: 'NEXT MILESTONE', cell: (item) => nextMilestoneCell(item, closed) },
  { key: 'needs', header: 'NEEDS A PERSON', cell: (item) => <Count value={item.needs_person} /> },
  { key: 'stopped', header: 'STOPPED', cell: (item) => <Count value={item.stopped} /> },
];

/** SCR-22 desktop: Project, PM, Where it is, Next milestone, Needs a person, Stopped. */
function ProjectTable({ items, closed, paging }: { items: ProjectRowView[]; closed: boolean; paging: ShowMoreProps }) {
  return <Table className="projects__table" caption="Projects" columns={columns(closed)} rows={items} rowKey={(item) => item.case_id} empty="No projects you can see yet." paging={paging} />;
}

/** The phone card's red line: "2 need a person · 1 stopped"; nothing when both are 0 or not carried. */
function attentionText(item: ProjectRowView) {
  const parts = [];
  const needsPerson = countOf(item.needs_person);
  const stopped = countOf(item.stopped);
  if (needsPerson) parts.push(`${needsPerson} need a person`);
  if (stopped) parts.push(`${stopped} stopped`);
  return parts.join(' · ');
}

/** SCR-22 phone: each card is one link with the title, where it is and the PM, then what needs attention. */
function ProjectCards({ items }: { items: ProjectRowView[] }) {
  return (
    <ul className="projects__cards">
      {items.map((item) => {
        const attention = attentionText(item);
        return (
          <li key={item.case_id}>
            <Link href={`/projects/${encodeURIComponent(item.case_id)}`} className="projects__card" data-project-link="">
              <span className="projects__title">{item.title}</span>
              <span className="projects__meta">
                {item.stage} · PM {item.pm}
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

/** SCR-22 Projects: the projects the person's grants cover, from E-PROJECTS, with search and paging. */
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
    const data = await call(api.GET('/api/v1/projects', { params: { query: buildProjectsQuery(v, cursor) } }));
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
        setList({ status: 'ready', items: data.items, nextCursor: data.next_cursor, counts: data.counts, total: countOf(data.total) });
      } catch (error) {
        if (mine !== seq.current) return;
        const e = asApiError(error);
        if (e.kind === 'unauthenticated') setSignedOut(true);
        else setList({ status: 'error', error: e });
      }
    },
    [fetchPage],
  );

  const showMore = async (limit: ProjectsView['limit']) => {
    if (list.status !== 'ready' || !list.nextCursor) return;
    const mine = seq.current;
    const before = list.items.length;
    setMore('loading');
    try {
      const data = await fetchPage({ ...view, limit }, list.nextCursor);
      if (mine !== seq.current) return;
      focusRow.current = before;
      setList((prev) => (prev.status !== 'ready' ? prev : { ...prev, items: [...prev.items, ...data.items], nextCursor: data.next_cursor }));
      setMore('idle');
    } catch (error) {
      if (mine !== seq.current) return;
      if (asApiError(error).kind === 'unauthenticated') setSignedOut(true);
      else setMore('error');
    }
  };

  // A new search or tab reloads from page 1; a new rows-per-page choice only grows or trims the shown rows.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reloadView = useMemo(() => view, [view.q, view.tab]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(reloadView);
  }, [reloadView, load]);
  useEffect(() => {
    viewRef.current = view;
  }, [view]);

  const listReady = list.status === 'ready' ? list : undefined;
  const { rows, paging } = usePagedRows({
    items: listReady?.items ?? [],
    next: Boolean(listReady?.nextCursor),
    busy: more === 'loading',
    failed: more === 'error',
    loadMore: (limit) => void showMore(limit),
    resetKey: `${view.q ?? ''}|${view.tab}`,
    total: listReady?.total,
    size: view.limit,
    onSize: (limit) => navigate({ limit }),
  });

  useEffect(() => {
    if (focusRow.current !== null && list.status === 'ready') {
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
    const q = value.trim() || undefined;
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
          {phone ? (
            <>
              <ProjectCards items={rows} />
              <ShowMore solo {...paging} />
            </>
          ) : (
            <ProjectTable items={rows} closed={view.tab === 'closed'} paging={paging} />
          )}
        </div>
        <div className="projects__foot">
          {more === 'error' && (
            <Callout kind="problem" className="projects__morefail">
              We couldn&rsquo;t load more. Nothing was changed.{' '}
              <Button kind="secondary" size="sm" onClick={() => paging.onMore()}>
                Try again
              </Button>
            </Callout>
          )}
        </div>
        <p className="projects__note">You see projects your roles cover. Open one for its journey, documents, money and registers.</p>
      </>
    );
  }

  const counts = list.status === 'ready' ? list.counts : undefined;
  // The count beside the search is the result's (UX-2-1): `total` matches the tab and the search; without it, the
  // tab's count stands in only when no search is active.
  const total = list.status !== 'ready' ? undefined : (list.total ?? (view.q ? undefined : countOf(counts?.[view.tab])));

  return (
    <div className="projects__page">
      <p className="projects__eyebrow">PROJECTS</p>
      <PageTitle>Projects</PageTitle>
      <Tabs
        label="Projects"
        className="projects__listtabs"
        tabs={LIST_TABS.map((tab) => ({ key: tab.key, label: tab.label, count: countOf(counts?.[tab.key]) }))}
        selected={view.tab}
        onSelect={(tab) => navigate({ tab })}
        panelId={LIST_PANEL_ID}
      />
      <div role="search">
        <ListToolbar
          className="projects__toolbar"
          search={{ label: 'Search', placeholder: phone ? 'Search projects' : 'Search projects or clients', value: text, onChange: setText, onSearch: applySearch }}
          filterCount={0}
          filterOpen={filterOpen}
          onFilterToggle={() => setFilterOpen((open) => !open)}
          filterPanel={
            <FilterPanel title="Filter projects" applyLabel="Close" onApply={closeFilter} onClear={closeFilter} onClose={closeFilter}>
              <strong>Filters come next</strong>
              <p>Search finds a project by its name or its client today.</p>
            </FilterPanel>
          }
          resultText={list.status === 'ready' ? (total === undefined ? `${list.items.length} shown` : `${total} ${total === 1 ? 'PROJECT' : 'PROJECTS'}`) : ''}
        />
      </div>
      <div role="tabpanel" id={LIST_PANEL_ID} aria-label={LIST_TABS.find((tab) => tab.key === view.tab)?.label} className="projects__panel">
        {body}
      </div>
    </div>
  );
}
