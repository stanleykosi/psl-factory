'use client';

// The bell's drawer (F-15, F-61): concept 3 inside concept 1's drawer (design/concepts/alerts-bell-concepts.html), with
// SCR-15's rows, in the shared 500px Drawer (a full-height sheet below 720px, with the two groups as tabs). The
// Drawer holds focus, closes on Esc and the scrim and gives focus back to the bell that opened it. The page lists
// what the server returned for this person only (page 1); which group an alert sits in comes from its `group`,
// never from its text.
import NextLink from 'next/link';
import { useState, type MouseEvent } from 'react';

import { buttonClass, Drawer, formatTime, Link, Tabs, VisuallyHidden } from '@/components';
import { ForbiddenState, LoadingState, SignedOutState } from '@/shell/FrameStates';

import { AlertAvatar, AlertBody, AlertsLoadError, RowTail, useAlertActions, type OpenAlert, type RowNotice } from './AlertParts';
import type { Alert } from './types';
import type { AlertsFeed } from './useAlertsFeed';
import { alertHref, needsYou, summaryLine } from './model';
import './alerts.css';

type Tab = 'need' | 'info';

type Props = { feed: AlertsFeed; phone: boolean; pathname: string; onClose: () => void; onLeave: (href: string) => void };

const plainClick = (event: MouseEvent) => event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;

export function AlertsDrawer({ feed, phone, pathname, onClose, onLeave }: Props) {
  const [chosen, setChosen] = useState<Tab>();
  const { data, error, refresh } = feed;
  const actions = useAlertActions({ onGone: () => void refresh(), onSignedOut: feed.stop });

  // A read alert is left to its link; an unread one is marked read first. The drawer stays open until the work opens; after a
  // failed mark-read it is closed by the route change itself, so its row keeps the notice until then.
  const open: OpenAlert = async (event, alert) => {
    const result = await actions.open(event, alert);
    const href = alertHref(alert);
    if (href && plainClick(event) && (alert.read || result === 'read')) onLeave(href);
    return result;
  };
  const follow = (event: MouseEvent<HTMLAnchorElement>) => {
    if (plainClick(event)) onLeave(event.currentTarget.getAttribute('href') ?? '');
  };

  const items = data?.items ?? [];
  const need = items.filter(needsYou);
  const info = items.filter((alert) => !needsYou(alert));
  const tab: Tab = chosen ?? (need.length > 0 ? 'need' : 'info');
  const now = data?.now ?? 0;
  const rows = { now, onOpen: open, onMark: (alert: Alert) => void actions.markRead(alert), notices: actions.notices };

  let body;
  if (error?.kind === 'unauthenticated') body = <SignedOutState pathname={pathname} />;
  else if (error?.kind === 'forbidden') body = <ForbiddenState error={error} />;
  else if (!data && !error) body = <LoadingState />;
  else {
    const failed = error && <AlertsLoadError error={error} asOf={data?.asOf} onRetry={() => void refresh()} />;
    const summary = summaryLine(data?.summary);
    let list;
    if (!data) list = null;
    else if (items.length === 0) list = <p className="alerts-none">No alerts</p>;
    else if (phone) {
      const shown = tab === 'need' ? need : info;
      list = (
        <div role="tabpanel" id="alerts-panel" aria-label={tab === 'need' ? 'Needs you' : 'For information'}>
          <Rows items={shown} {...rows} primary={tab === 'need'} empty={tab === 'need' ? 'Nothing needs you right now.' : 'No other alerts.'} />
        </div>
      );
    } else {
      list = (
        <>
          <Group id="need" title="Needs you" items={need} {...rows} empty="Nothing needs you right now." />
          <Group id="info" title="For information" items={info} {...rows} empty="No other alerts." />
        </>
      );
    }
    body = (
      <>
        {failed && <div className="alerts-dstate">{failed}</div>}
        {summary && <p className="alerts-summary">{summary}</p>}
        {list}
        {data && <p className="alerts-asof">As of {formatTime(data.asOf)}</p>}
      </>
    );
  }
  const stateBody = error?.kind === 'unauthenticated' || error?.kind === 'forbidden' || (!data && !error);

  const showTabs = phone && items.length > 0 && !stateBody;
  const unread = data && !error ? data.unread : undefined;

  return (
    <Drawer
      title="Alerts"
      onClose={onClose}
      className="alerts-drawer"
      footer={
        <>
          <Link href="/notifications" onClick={follow}>
            See all alerts{unread !== undefined && ` (${unread} unread)`}
          </Link>
          <Link href="/settings/alerts" onClick={follow}>
            Alert settings
          </Link>
        </>
      }
    >
      {showTabs && (
        <Tabs
          label="Alerts"
          panelId="alerts-panel"
          selected={tab}
          onSelect={setChosen}
          tabs={[
            { key: 'need', label: 'Needs you', count: need.length > 0 ? need.length : undefined },
            { key: 'info', label: 'For information' },
          ]}
        />
      )}
      <div className={stateBody ? 'alerts-dstate' : undefined}>{body}</div>
    </Drawer>
  );
}

type RowsProps = { items: Alert[]; now: number; onOpen: OpenAlert; onMark: (alert: Alert) => void; notices: Record<string, RowNotice> };
type GroupProps = RowsProps & { id: Tab; title: string; empty: string };

/** A group header (mono, with the count of its loaded alerts) and its rows. */
function Group({ id, title, items, empty, ...rows }: GroupProps) {
  return (
    <section aria-labelledby={`alerts-grp-${id}`}>
      <h3 id={`alerts-grp-${id}`} className={`alerts-grp${id === 'need' ? ' alerts-grp--need' : ''}`}>
        <span>{title}</span>
        <span>
          <VisuallyHidden>, </VisuallyHidden>
          {items.length}
        </span>
      </h3>
      <Rows items={items} {...rows} primary={id === 'need'} empty={empty} />
    </section>
  );
}

/** SCR-15 rows with Open as the only action: filled in Needs you, outlined in For information; a row with no link has Mark as read. */
function Rows({ items, now, primary, onOpen, onMark, notices, empty }: RowsProps & { primary: boolean; empty: string }) {
  if (items.length === 0) return <p className="alerts-none">{empty}</p>;
  return (
    <ul className="alerts-dlist">
      {items.map((alert) => {
        const href = alertHref(alert);
        return (
          <li key={alert.id} className={alert.read === false ? 'alerts-row alerts-row--unread alerts-drow' : 'alerts-row alerts-drow'}>
            <AlertAvatar agent={alert.agent} />
            <span className="alerts-rowmain">
              <AlertBody alert={alert} now={now} />
              <RowTail alert={alert} notice={notices[alert.id]} onMark={onMark} />
            </span>
            {href && (
              <NextLink
                href={href}
                className={`${buttonClass(primary ? 'primary' : 'secondary', 'sm')} cmp-btn-sm`}
                aria-label={`Open: ${alert.title}`}
                onClick={(event) => void onOpen(event, alert)}
              >
                Open
              </NextLink>
            )}
          </li>
        );
      })}
    </ul>
  );
}
