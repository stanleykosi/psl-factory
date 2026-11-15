'use client';

// The Setup frame (SCR-13-desktop-rules): SETUP eyebrow, title and the seven-tab bar, plus the pieces every Setup
// view shares (the destination gate, the read states, the phone bar's back link). Tabs are route links with
// aria-current (Assumption A-7); badges show only the counts the API sends.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import { useMe, usePhoneBack } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
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
      <h1 className="setup-title">Roles, rules and delegation</h1>
      <nav aria-label="Setup" className="psl-tabs setup-tabs">
        {SETUP_TABS.map((tab) => {
          const badge = badges[tab.key];
          return (
            <Link key={tab.key} href={tab.href} className="psl-tab" aria-current={tab.key === current ? 'page' : undefined}>
              {tab.label}
              {badge !== undefined && <span className="psl-badge">{badge}</span>}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

/** The setup destination gate: without it nothing below renders and no Setup call is made. */
export function SetupGate({ children }: { children: ReactNode }) {
  const me = useMe();
  if (!me.destinations.includes('setup')) return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
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

/** "← Setup" in the phone bar, back to the phone Setup home (SCR-13-mobile), with the board's mono note. */
export function useSetupPhoneBack(note?: string) {
  usePhoneBack({ label: 'Setup', href: '/setup/roles', note });
}

export function RulesEmpty() {
  return (
    <div className="psl-empty">
      <h2>No rules to show.</h2>
      <p>Rules your role may read will appear here.</p>
    </div>
  );
}

/** What ShowMore reads of a list state; rules and templates both fit it. */
type PagedState = { status: 'loading' | 'error' } | { status: 'ready'; items: unknown[]; nextCursor?: string; more: 'idle' | 'loading' | 'failed' };

/** Appends the next page; a failed page keeps the loaded rows and says so. */
export function ShowMore({ state, onMore, noun = 'rules' }: { state: PagedState; onMore: () => void; noun?: string }) {
  const [pressed, setPressed] = useState(false);
  const end = useRef<HTMLSpanElement>(null);
  const last = state.status === 'ready' && !state.nextCursor;
  // The last Show more unmounts its own button, which would drop focus to the page top; the end of the list takes it (QA-3-1).
  useEffect(() => {
    if (pressed && last) end.current?.focus();
  }, [pressed, last]);
  if (state.status !== 'ready') return null;
  return (
    <>
      {state.more === 'failed' && (
        <div className="psl-callout psl-callout--warning" role="alert">
          <WarningIcon />
          <span>We couldn’t load more {noun}. Choose Show more to try again.</span>
        </div>
      )}
      {state.nextCursor && (
        <div className="psl-showmore setup-showmore">
          <span>{state.items.length} shown</span>
          <button
            type="button"
            className="psl-btn psl-btn--secondary psl-btn--sm"
            disabled={state.more === 'loading'}
            onClick={() => {
              setPressed(true);
              onMore();
            }}
          >
            Show more
          </button>
        </div>
      )}
      {pressed && last && (
        <span ref={end} tabIndex={-1} className="setup-sr">
          All {state.items.length} {noun} are shown.
        </span>
      )}
    </>
  );
}
