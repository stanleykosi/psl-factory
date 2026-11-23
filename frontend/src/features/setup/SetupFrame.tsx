'use client';

// The Setup frame (SCR-13-desktop-rules): SETUP eyebrow, title and the seven-tab bar, plus the pieces every Setup
// view shares (the destination gate, the read states, the phone bar's back link). Tabs are route links with
// aria-current (Assumption A-7); badges show only the counts the API sends.
import { usePathname } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import { EmptyState, PageTitle, Tabs, usePagedRows, type PageSize } from '@/components';
import { useMe, usePhoneBack } from '@/shell/AppShell';
import { hasDestination, visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';

import './setup.css';

export type SetupTab = 'roles' | 'rules' | 'costing-rule' | 'delegation' | 'payroll-visibility' | 'staff' | 'templates';

export const SETUP_TABS: readonly { key: SetupTab; label: string; href: string }[] = [
  { key: 'roles', label: 'Roles', href: '/setup/roles' },
  { key: 'rules', label: 'Rules', href: '/setup/rules' },
  { key: 'costing-rule', label: 'Costing rule', href: '/setup/costing-rule' },
  { key: 'delegation', label: 'Delegation', href: '/setup/delegation' },
  { key: 'payroll-visibility', label: 'Payroll visibility', href: '/setup/payroll-visibility' },
  { key: 'staff', label: 'Staff accounts', href: '/setup/staff' },
  { key: 'templates', label: 'Templates', href: '/setup/templates' },
];

export function SetupFrame({ current, rolesMissing, notSet }: { current: SetupTab; rolesMissing?: number; notSet?: number }) {
  const badges: Partial<Record<SetupTab, number | undefined>> = { roles: rolesMissing, rules: notSet };
  return (
    <>
      <p className="psl-crumb setup-eyebrow">SETUP</p>
      <PageTitle size={34}>Roles, rules and delegation</PageTitle>
      <Tabs label="Setup" tabs={SETUP_TABS.map((tab) => ({ ...tab, count: badges[tab.key] }))} selected={current} className="setup-tabs" />
    </>
  );
}

/** What a Setup tab's page reports about its own read; the frame around the tabs follows it (INV-ACCESS). */
type SetupRead = { status: 'loading' | 'ready' | 'error'; counts?: { rolesMissing?: number; notSet?: number } };
const SetupReadContext = createContext<(read: SetupRead) => void>(() => {});

/** Tabs without a screen yet draw the frame on a phone too, as their page does; the other tabs draw it on desktop only. */
const PHONE_FRAME: SetupTab[] = ['roles', 'costing-rule', 'payroll-visibility', 'staff'];

/**
 * The layout of the Setup tabs: the frame stays across a tab change and only the tab's body loads. The frame shows only
 * once a Setup read has allowed it, and goes when a later read fails or loses access; a tab count not read yet is blank.
 */
export function SetupLayoutFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? '';
  const tab = SETUP_TABS.find((t) => pathname === t.href || pathname.startsWith(`${t.href}/`))?.key ?? 'rules';
  const [frame, setFrame] = useState<{ open: boolean; rolesMissing?: number; notSet?: number }>({ open: false });
  const report = useCallback((read: SetupRead) => {
    setFrame((prev) => {
      if (read.status === 'error') return prev.open || prev.rolesMissing !== undefined || prev.notSet !== undefined ? { open: false } : prev;
      if (read.status === 'loading') return prev;
      const next = { open: true, ...(read.counts ?? { rolesMissing: prev.rolesMissing, notSet: prev.notSet }) };
      return prev.open && prev.rolesMissing === next.rolesMissing && prev.notSet === next.notSet ? prev : next;
    });
  }, []);
  return (
    <SetupGate>
      <SetupReadContext.Provider value={report}>
        {frame.open && (
          <div className={PHONE_FRAME.includes(tab) ? 'setup-page setup-frame' : 'setup-page setup-frame setup-frame--desktop'}>
            <SetupFrame current={tab} rolesMissing={frame.rolesMissing} notSet={frame.notSet} />
          </div>
        )}
        {children}
      </SetupReadContext.Provider>
    </SetupGate>
  );
}

/** A Setup tab's page tells the frame how its read stands (before the first paint, so the frame never flashes in or out). */
export function useSetupRead(status: SetupRead['status'], counts?: SetupRead['counts']) {
  const report = useContext(SetupReadContext);
  const { rolesMissing, notSet } = counts ?? {};
  const hasCounts = counts !== undefined;
  useLayoutEffect(() => report({ status, counts: hasCounts ? { rolesMissing, notSet } : undefined }), [report, status, hasCounts, rolesMissing, notSet]);
}

/** The setup destination gate: without it nothing below renders and no Setup call is made. */
export function SetupGate({ children }: { children: ReactNode }) {
  const me = useMe();
  if (!hasDestination(me, 'setup')) return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  return <>{children}</>;
}

type ReadState = { status: 'loading' | 'ready' } | { status: 'error'; error: ApiError };

/** Loading and failed reads. 403 and 404 look the same, so nothing about a hidden rule shows (INV-ACCESS). */
export function RulesReadState({ state, retry, what = 'rules' }: { state: ReadState; retry: () => void; what?: string }) {
  const pathname = usePathname() ?? '/setup/rules';
  const me = useMe();
  if (state.status === 'loading') return <LoadingState />;
  if (state.status !== 'error') return null;
  const { error } = state;
  if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
  if (error.kind === 'forbidden' || error.kind === 'not_found') return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  return <WorkErrorCard message={`We couldn’t load the ${what}. Your work is safe; nothing was changed.`} error={error} onRetry={retry} />;
}

/** "← Setup" in the phone bar, to Setup rules until a phone Setup home is drawn (D-68(c)), with the board's mono note. */
export function useSetupPhoneBack(note?: string) {
  usePhoneBack({ label: 'Setup', href: '/setup/rules', note });
}

export function RulesEmpty() {
  return <EmptyState title="No rules to show.">Rules your role may read will appear here.</EmptyState>;
}

/** What the paging window reads of a list state; rules, templates and delegations all fit it. */
type PagedState<T> = { status: 'loading' | 'error' } | { status: 'ready'; items: T[]; nextCursor?: string; more: 'idle' | 'loading' | 'failed' };

/** The paging window over a setup list (10 rows first, grown in place by the footer) and what to say beside it. */
export function useSetupPaging<T>(state: PagedState<T>, loadMore: (limit: PageSize) => Promise<void>, noun = 'rules') {
  const ready = state.status === 'ready' ? state : undefined;
  const [pressed, setPressed] = useState(false);
  const { rows, paging } = usePagedRows({
    items: ready?.items ?? [],
    next: Boolean(ready?.nextCursor),
    busy: ready?.more === 'loading',
    failed: ready?.more === 'failed',
    loadMore: (limit) => void loadMore(limit),
  });
  const total = ready?.items.length ?? 0;
  return {
    items: rows,
    paging: { ...paging, onMore: () => { setPressed(true); paging.onMore(); } },
    notes: { failed: ready?.more === 'failed', last: Boolean(ready) && !paging.hasMore, pressed, total, noun },
  };
}

type Notes = ReturnType<typeof useSetupPaging>['notes'];

/** A failed page keeps the loaded rows and says so; after the last Show more the end of the list takes focus. */
export function PagingNotes({ notes }: { notes: Notes }) {
  const end = useRef<HTMLSpanElement>(null);
  const done = notes.pressed && notes.last;
  // The last Show more unmounts its own button, which would drop focus to the page top; the end of the list takes it (QA-3-1).
  useEffect(() => {
    if (done) end.current?.focus();
  }, [done]);
  return (
    <>
      {done && (
        <span ref={end} tabIndex={-1} className="cmp-sr">
          All {notes.total} {notes.noun} are shown.
        </span>
      )}
    </>
  );
}
