'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type FormEvent, type KeyboardEvent, type RefObject } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';
import { CloseIcon, FilterIcon, SearchIcon } from '@/features/my-work/icons';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';

import {
  allShowingText,
  buildProjectsQuery,
  isProjectList,
  LIMITS,
  LIST_TABS,
  parseProjectsView,
  projectsSearch,
  shownText,
  type Limit,
  type ListTab,
  type ProjectListView,
  type ProjectRowView,
  type ProjectsView,
} from './model';

const SEARCH_DEBOUNCE_MS = 300;
const PHONE_QUERY = '(max-width: 719.98px)';

type ListState =
  | { status: 'loading' }
  | { status: 'ready'; items: ProjectRowView[]; nextCursor?: string; counts?: ProjectListView['counts'] }
  | { status: 'error'; error: ApiError };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const malformed = () => new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);

function subscribePhone(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {};
  const media = window.matchMedia(PHONE_QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}
const isPhoneNow = () => typeof window.matchMedia === 'function' && window.matchMedia(PHONE_QUERY).matches;

/** Below 720px the list is cards (SCR-22-mobile). */
function useIsPhone() {
  return useSyncExternalStore(subscribePhone, isPhoneNow, () => false);
}

/** A person-needed or stopped count (PROPOSAL); a count the response does not carry shows a dash, never 0. */
function Count({ value }: { value?: number }) {
  if (value === undefined) return <span className="projects__none">—</span>;
  return <span className={value > 0 ? 'projects__count' : 'projects__zero'}>{value}</span>;
}

/** SCR-22 desktop: Project, PM, Where it is, Next milestone, Needs a person, Stopped. */
function ProjectTable({ items }: { items: ProjectRowView[] }) {
  return (
    <div className="psl-tablewrap">
      <table className="psl-table projects__table">
        <thead>
          <tr>
            <th scope="col">PROJECT</th>
            <th scope="col">PM</th>
            <th scope="col">WHERE IT IS</th>
            <th scope="col">NEXT MILESTONE</th>
            <th scope="col">NEEDS A PERSON</th>
            <th scope="col">STOPPED</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.case_id}>
              <td>
                <span className="projects__titlecell">
                  <Link href={`/projects/${encodeURIComponent(item.case_id)}`} className="projects__title" data-project-link="">
                    {item.title}
                  </Link>
                  <SampleLabel show={item.sample} />
                </span>
              </td>
              <td>{item.pm}</td>
              <td>{item.stage}</td>
              <td>{item.next_milestone ?? '—'}</td>
              <td>
                <Count value={item.needs_person} />
              </td>
              <td>
                <Count value={item.stopped} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The phone card's red line: "2 need a person · 1 stopped"; nothing when both are 0 or not carried. */
function attentionText(item: ProjectRowView) {
  const parts = [];
  if (item.needs_person) parts.push(`${item.needs_person} need a person`);
  if (item.stopped) parts.push(`${item.stopped} stopped`);
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

/** The Filter button's panel. Project filters are not in the contract yet, so it says what works today. */
function FilterSoon({ onClose, anchor }: { onClose: () => void; anchor: RefObject<HTMLButtonElement | null> }) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    panel.current?.querySelector<HTMLElement>('button')?.focus();
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    const onPointer = (event: MouseEvent) => {
      const target = event.target as Node;
      if (panel.current?.contains(target) || anchor.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onPointer);
    };
  }, [anchor, onClose]);
  return (
    <div ref={panel} role="dialog" aria-label="Filter projects" className="psl-pop projects__filterpop">
      <div className="projects__filterhead">
        <strong>Filters come next</strong>
        <button type="button" className="psl-iconbtn psl-iconbtn--bare" aria-label="Close" onClick={onClose}>
          <CloseIcon />
        </button>
      </div>
      <p>Search finds a project by its name or its client today.</p>
    </div>
  );
}

const listTabId = (key: ListTab) => `projects-tab-${key}`;
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
  const filterButton = useRef<HTMLButtonElement>(null);

  const seq = useRef(0);
  const focusRow = useRef<number | null>(null);
  const focusLimit = useRef(false);
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
        setList({ status: 'ready', items: data.items, nextCursor: data.next_cursor, counts: data.counts });
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
    const before = list.items.length;
    setMore('loading');
    try {
      const data = await fetchPage(view, list.nextCursor);
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

  useEffect(() => {
    viewRef.current = view;
    // A new view (search or rows per page) reloads from page 1.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(view);
  }, [view, load]);

  useEffect(() => {
    if (focusRow.current !== null && list.status === 'ready') {
      rowsRef.current?.querySelectorAll<HTMLElement>('[data-project-link]')[focusRow.current]?.focus();
      focusRow.current = null;
    }
    // The footer is redrawn after a rows-per-page reload; the keyboard stays on the chosen option.
    if (focusLimit.current && list.status !== 'loading') {
      document.querySelector<HTMLElement>('.projects__rows [role="radio"][aria-checked="true"]')?.focus();
      focusLimit.current = false;
    }
  }, [list]);

  // Search: the box keeps what the person typed; the URL takes it 300 ms after the last keystroke.
  const [text, setText] = useState(view.q ?? '');
  const [syncedQ, setSyncedQ] = useState(view.q);
  if (view.q !== syncedQ) {
    setSyncedQ(view.q);
    if ((text.trim() || undefined) !== view.q) setText(view.q ?? '');
  }
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(debounce.current), []);
  const applySearch = (value: string) => {
    clearTimeout(debounce.current);
    const q = value.trim() || undefined;
    if (q !== viewRef.current.q) navigate({ q });
  };
  const onSearchInput = (value: string) => {
    setText(value);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => applySearch(value), SEARCH_DEBOUNCE_MS);
  };
  const onSearchSubmit = (event: FormEvent) => {
    event.preventDefault();
    applySearch(text);
  };
  const clearSearch = () => {
    clearTimeout(debounce.current);
    setText('');
    navigate({ q: undefined });
  };

  const onLimitKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const next = LIMITS[(index + step + LIMITS.length) % LIMITS.length];
    event.currentTarget.parentElement?.querySelectorAll<HTMLElement>('[role="radio"]')[LIMITS.indexOf(next)]?.focus();
    focusLimit.current = true;
    navigate({ limit: next });
  };

  const onTabKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = LIST_TABS.length - 1;
    const next = { ArrowRight: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, Home: 0, End: last }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    document.getElementById(listTabId(LIST_TABS[next].key))?.focus();
    navigate({ tab: LIST_TABS[next].key });
  };
  const closeFilter = useCallback(() => {
    setFilterOpen(false);
    filterButton.current?.focus();
  }, []);

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
      <div className="psl-empty">
        <h3>No projects match</h3>
        <p>No project you can see matches your search.</p>
        <button type="button" className="psl-link projects__linkbutton" onClick={clearSearch}>
          Clear search
        </button>
      </div>
    );
  } else if (list.items.length === 0) {
    body = (
      <div className="psl-empty">
        <h3>No projects you can see yet.</h3>
        <p>You see projects your roles cover.</p>
      </div>
    );
  } else {
    body = (
      <>
        <div ref={rowsRef}>{phone ? <ProjectCards items={list.items} /> : <ProjectTable items={list.items} />}</div>
        <div className="projects__foot">
          <div className="psl-showmore projects__showmore">
            <span>{list.nextCursor ? '' : allShowingText(list.items.length)}</span>
            <span className="projects__rows">
              <span className="projects__rowslabel" aria-hidden="true">
                ROWS PER PAGE
              </span>
              <span role="radiogroup" aria-label="Rows per page" className={phone ? 'psl-seg psl-seg--phone' : 'psl-seg'}>
                {LIMITS.map((n: Limit, i) => (
                  <button
                    key={n}
                    type="button"
                    role="radio"
                    aria-checked={n === view.limit}
                    tabIndex={n === view.limit ? 0 : -1}
                    className="psl-seg__opt"
                    onClick={() => navigate({ limit: n })}
                    onKeyDown={(e) => onLimitKey(e, i)}
                  >
                    {n}
                  </button>
                ))}
              </span>
            </span>
            {list.nextCursor && (
              <button
                type="button"
                className="psl-btn psl-btn--secondary psl-btn--sm projects__more"
                disabled={more === 'loading'}
                aria-busy={more === 'loading'}
                onClick={() => void showMore()}
              >
                Show more
              </button>
            )}
          </div>
          {more === 'error' && (
            <div className="psl-callout psl-callout--problem projects__morefail">
              <span>We couldn&rsquo;t load more. Nothing was changed.</span>
              <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" onClick={() => void showMore()}>
                Try again
              </button>
            </div>
          )}
        </div>
        <p className="projects__note">You see projects your roles cover. Open one for its journey, documents, money and registers.</p>
      </>
    );
  }

  const counts = list.status === 'ready' ? list.counts : undefined;
  const total = counts?.[view.tab];
  const filterProps = {
    ref: filterButton,
    type: 'button' as const,
    'aria-haspopup': 'dialog' as const,
    'aria-expanded': filterOpen,
    onClick: () => (filterOpen ? closeFilter() : setFilterOpen(true)),
  };

  return (
    <div className="projects__page">
      <p className="projects__eyebrow">PROJECTS</p>
      <h1 className="shell-title">Projects</h1>
      <div role="tablist" aria-label="Projects" className="psl-tabs projects__listtabs">
        {LIST_TABS.map((tab, i) => {
          const selected = tab.key === view.tab;
          const count = counts?.[tab.key];
          return (
            <button
              key={tab.key}
              id={listTabId(tab.key)}
              type="button"
              role="tab"
              className="psl-tab projects__listtab"
              aria-selected={selected}
              aria-controls={selected ? LIST_PANEL_ID : undefined}
              tabIndex={selected ? 0 : -1}
              onClick={() => navigate({ tab: tab.key })}
              onKeyDown={(e) => onTabKey(e, i)}
            >
              {tab.label}
              {count !== undefined && <span className="psl-badge">{count}</span>}
            </button>
          );
        })}
      </div>
      <form role="search" className="psl-toolbar" onSubmit={onSearchSubmit}>
        <div className="psl-search projects__search">
          <SearchIcon />
          <label className="projects__sr" htmlFor="projects-q">
            Search
          </label>
          <input
            id="projects-q"
            type="search"
            className="psl-input"
            placeholder={phone ? 'Search projects' : 'Search projects or clients'}
            value={text}
            onChange={(e) => onSearchInput(e.target.value)}
          />
        </div>
        <div className="projects__filter">
          {phone ? (
            <button {...filterProps} className="psl-iconbtn projects__iconbtn" aria-label="Filter">
              <FilterIcon />
            </button>
          ) : (
            <button {...filterProps} className="psl-btn psl-btn--secondary">
              <FilterIcon />
              Filter
            </button>
          )}
          {filterOpen && <FilterSoon onClose={closeFilter} anchor={filterButton} />}
        </div>
        {list.status === 'ready' && (
          <span className="psl-resultcount projects__total">{total === undefined ? shownText(list.items.length) : `${total} PROJECTS`}</span>
        )}
      </form>
      <div role="tabpanel" id={LIST_PANEL_ID} aria-labelledby={listTabId(view.tab)} className="projects__panel">
        {body}
      </div>
    </div>
  );
}
