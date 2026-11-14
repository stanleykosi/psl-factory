'use client';

// The Setup frame (SCR-13-desktop-rules): SETUP eyebrow, title and the seven-tab bar, plus the pieces every Setup
// view shares (the destination gate, the read states, the phone back link). Tabs are route links with
// aria-current (Assumption A-7); badges show only the counts the API sends.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';

import type { RulesState } from './useSetupRules';

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

/** Loading and failed reads. 403 and 404 look the same, so nothing about a hidden rule shows (INV-ACCESS). */
export function RulesReadState({ state, retry }: { state: RulesState; retry: () => void }) {
  const pathname = usePathname() ?? '/setup/rules';
  const me = useMe();
  if (state.status === 'loading') return <LoadingState />;
  if (state.status !== 'error') return null;
  const { error } = state;
  if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
  if (error.kind === 'forbidden' || error.kind === 'not_found') return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  return <WorkErrorCard message="We couldn’t load the rules. Your work is safe; nothing was changed." error={error} onRetry={retry} />;
}

/** "← Setup" under the phone bar (D-08: the app frame owns the bar), with the board's mono label. */
export function PhoneBack({ label }: { label?: string }) {
  return (
    <div className="setup-back">
      <Link href="/setup/roles">
        <span aria-hidden="true">←</span> Setup
      </Link>
      {label && <span className="setup-back__label">{label}</span>}
    </div>
  );
}

export function RulesEmpty() {
  return (
    <div className="psl-empty">
      <h2>No rules to show.</h2>
      <p>Rules your role may read will appear here.</p>
    </div>
  );
}

/** Appends the next page; a failed page keeps the loaded rows and says so. */
export function ShowMore({ state, onMore }: { state: RulesState; onMore: () => void }) {
  if (state.status !== 'ready') return null;
  return (
    <>
      {state.more === 'failed' && (
        <div className="psl-callout psl-callout--warning" role="alert">
          <WarningIcon />
          <span>We couldn’t load more rules. Choose Show more to try again.</span>
        </div>
      )}
      {state.nextCursor && (
        <div className="psl-showmore setup-showmore">
          <span>{state.items.length} shown</span>
          <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" disabled={state.more === 'loading'} onClick={onMore}>
            Show more
          </button>
        </div>
      )}
    </>
  );
}
