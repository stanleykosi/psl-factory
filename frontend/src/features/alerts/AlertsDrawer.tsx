'use client';

// The bell's drawer (F-15): concept 3 inside concept 1's drawer (design/concepts/alerts-bell-concepts.html), with
// SCR-15's rows. From 720px a 420px panel at the right under the top bar; below, a full-height sheet with the two
// groups as tabs. A modal dialog: focus moves to Close and stays inside, Esc, the scrim and Close shut it, and the
// shell gives focus back to the bell that opened it. The page lists what the server returned for this person only;
// which group an alert sits in comes from `needs_you` (PROPOSAL), never from its text.
import Link from 'next/link';
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react';

import { ForbiddenState, LoadingState, SignedOutState } from '@/shell/FrameStates';

import { AlertAvatar, AlertBody, AlertsLoadError, useOpenAlert, type OpenAlert } from './AlertParts';
import { ALERTS_DRAWER_ID } from './AlertsBell';
import type { AlertWithNeed } from './types';
import type { AlertsFeed } from './useAlertsFeed';
import { needsYou, needsYouKnown, workHref } from './model';
import './alerts.css';

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';
type Tab = 'need' | 'info';

type Props = { feed: AlertsFeed; phone: boolean; pathname: string; onClose: () => void; onLeave: () => void };

const plainClick = (event: MouseEvent) => event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;

export function AlertsDrawer({ feed, phone, pathname, onClose, onLeave }: Props) {
  const layerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [chosen, setChosen] = useState<Tab>();
  const { data, error, refresh, markRead } = feed;
  const openAlert = useOpenAlert((alert) => markRead(alert.id), feed.stop);

  // The drawer starts at the bar's bottom edge as it is on screen now (again when the viewport crosses 720px).
  useLayoutEffect(() => {
    const bar = document.querySelector('.shell-topbar')?.getBoundingClientRect();
    layerRef.current?.style.setProperty('--alerts-top', `${Math.max(0, bar?.bottom ?? 0)}px`);
  }, [phone]);

  // The page behind does not scroll.
  useLayoutEffect(() => {
    const root = document.documentElement;
    const overflow = root.style.overflow;
    root.style.overflow = 'hidden';
    return () => {
      root.style.overflow = overflow;
    };
  }, []);

  useEffect(() => closeRef.current?.focus(), []);

  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  function trapTab(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab' || !panelRef.current) return;
    const items = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === panelRef.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const open: OpenAlert = (event, alert) => {
    void openAlert(event, alert);
    if (plainClick(event)) onLeave();
  };
  const follow = (event: MouseEvent) => {
    if (plainClick(event)) onLeave();
  };

  const items = data?.items ?? [];
  const known = needsYouKnown(items);
  const need = known ? items.filter(needsYou) : [];
  const info = known ? items.filter((alert) => !needsYou(alert)) : items;
  const tab: Tab = chosen ?? (need.length > 0 ? 'need' : 'info');
  const now = data?.now ?? 0;

  let body;
  if (error?.kind === 'unauthenticated') body = <SignedOutState pathname={pathname} />;
  else if (error?.kind === 'forbidden') body = <ForbiddenState error={error} />;
  else if (!data && !error) body = <LoadingState />;
  else {
    const failed = error && <AlertsLoadError error={error} asOf={data?.asOf} onRetry={() => void refresh()} />;
    let list;
    if (!data) list = null;
    else if (items.length === 0) list = <p className="alerts-none">No alerts yet.</p>;
    else if (phone && known) {
      const shown = tab === 'need' ? need : info;
      list = (
        <div role="tabpanel" id="alerts-panel" aria-labelledby={`alerts-tab-${tab}`}>
          <Rows items={shown} now={now} primary={tab === 'need'} onOpen={open} empty={tab === 'need' ? 'Nothing needs you right now.' : 'No other alerts.'} />
        </div>
      );
    } else {
      list = (
        <>
          {known && <Group id="need" title="Needs you" items={need} now={now} onOpen={open} empty="Nothing needs you right now." />}
          <Group id="info" title="For your information" items={info} now={now} onOpen={open} empty="No other alerts." />
        </>
      );
    }
    body = (
      <>
        {failed && <div className="alerts-dstate">{failed}</div>}
        {list}
      </>
    );
  }
  const stateBody = error?.kind === 'unauthenticated' || error?.kind === 'forbidden' || (!data && !error);

  function onTabKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const next: Tab = tab === 'need' ? 'info' : 'need';
    setChosen(next);
    document.getElementById(`alerts-tab-${next}`)?.focus();
  }

  const showTabs = phone && known && items.length > 0 && !stateBody;

  return (
    <div ref={layerRef} className={`alerts-layer alerts-layer--${phone ? 'sheet' : 'drawer'}`}>
      {/* Pointer-only dismissal; Esc and Close are the keyboard equivalents. */}
      <div className="alerts-dscrim" aria-hidden="true" onClick={onClose} />
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <div
        ref={panelRef}
        id={ALERTS_DRAWER_ID}
        role="dialog"
        aria-modal="true"
        aria-labelledby="alerts-drawer-title"
        className="alerts-drawer"
        onKeyDown={trapTab}
      >
        {phone && <div className="alerts-grab" aria-hidden="true" />}
        <div className="alerts-dhead">
          <h2 id="alerts-drawer-title" className="alerts-dtitle">
            Alerts
          </h2>
          <button ref={closeRef} type="button" className="alerts-close" onClick={onClose}>
            Close
          </button>
        </div>
        {showTabs && (
          <div role="tablist" aria-label="Alerts" className="alerts-tabs">
            {(['need', 'info'] as const).map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                id={`alerts-tab-${key}`}
                aria-selected={tab === key}
                aria-controls="alerts-panel"
                tabIndex={tab === key ? 0 : -1}
                className="alerts-tab"
                onClick={() => setChosen(key)}
                onKeyDown={onTabKey}
              >
                {key === 'need' ? 'Needs you' : 'For your information'}
                {key === 'need' && need.length > 0 && <span className="alerts-tabcount">{need.length}</span>}
              </button>
            ))}
          </div>
        )}
        <div className={stateBody ? 'alerts-dbody alerts-dstate' : 'alerts-dbody'}>{body}</div>
        <div className="alerts-dfoot">
          <Link href="/notifications" onClick={follow}>
            See all alerts
          </Link>
          <Link href="/settings/alerts" onClick={follow}>
            Alert settings
          </Link>
        </div>
      </div>
    </div>
  );
}

type GroupProps = { id: Tab; title: string; items: AlertWithNeed[]; now: number; onOpen: OpenAlert; empty: string };

/** A group header (mono, with the count of its alerts) and its rows. */
function Group({ id, title, items, now, onOpen, empty }: GroupProps) {
  return (
    <section aria-labelledby={`alerts-grp-${id}`}>
      <h3 id={`alerts-grp-${id}`} className={`alerts-grp${id === 'need' ? ' alerts-grp--need' : ''}`}>
        <span>{title}</span>
        <span>
          <span className="alerts-sr">, </span>
          {items.length}
        </span>
      </h3>
      <Rows items={items} now={now} primary={id === 'need'} onOpen={onOpen} empty={empty} />
    </section>
  );
}

type RowsProps = { items: AlertWithNeed[]; now: number; primary: boolean; onOpen: OpenAlert; empty: string };

/** SCR-15 rows with Open as the only action: filled in Needs you, outlined in For your information; no NEW tag. */
function Rows({ items, now, primary, onOpen, empty }: RowsProps) {
  if (items.length === 0) return <p className="alerts-none">{empty}</p>;
  return (
    <ul className="alerts-dlist">
      {items.map((alert) => (
        <li key={alert.id} className={alert.read === false ? 'alerts-row alerts-row--unread alerts-drow' : 'alerts-row alerts-drow'}>
          <AlertAvatar agent={alert.agent} />
          <AlertBody alert={alert} now={now} />
          <Link
            href={workHref(alert)}
            className={primary ? 'alerts-open alerts-open--pri' : 'alerts-open'}
            aria-label={`Open: ${alert.text}`}
            onClick={(event) => onOpen(event, alert)}
          >
            Open
          </Link>
        </li>
      ))}
    </ul>
  );
}
