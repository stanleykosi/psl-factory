'use client';

// The bell's drawer (F-15): concept 3 inside concept 1's drawer (design/concepts/alerts-bell-concepts.html), with
// SCR-15's rows, in the shared 500px Drawer (a full-height sheet below 720px, with the two groups as tabs). The
// Drawer holds focus, closes on Esc and the scrim and gives focus back to the bell that opened it. The page lists
// what the server returned for this person only; which group an alert sits in comes from `needs_you` (PROPOSAL),
// never from its text.
import NextLink from 'next/link';
import { useState, type MouseEvent } from 'react';

import { buttonClass, Drawer, Link, Tabs, VisuallyHidden } from '@/components';
import { ForbiddenState, LoadingState, SignedOutState } from '@/shell/FrameStates';

import { AlertAvatar, AlertBody, AlertsLoadError, useOpenAlert, type OpenAlert } from './AlertParts';
import type { AlertWithNeed } from './types';
import type { AlertsFeed } from './useAlertsFeed';
import { needsYou, needsYouKnown, workHref } from './model';
import './alerts.css';

type Tab = 'need' | 'info';

type Props = { feed: AlertsFeed; phone: boolean; pathname: string; onClose: () => void; onLeave: (href: string) => void };

const plainClick = (event: MouseEvent) => event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;

export function AlertsDrawer({ feed, phone, pathname, onClose, onLeave }: Props) {
  const [chosen, setChosen] = useState<Tab>();
  const { data, error, refresh, markRead } = feed;
  const openAlert = useOpenAlert((alert) => markRead(alert.id), feed.stop);

  const open: OpenAlert = (event, alert) => {
    void openAlert(event, alert);
    if (plainClick(event)) onLeave(workHref(alert));
  };
  const follow = (event: MouseEvent<HTMLAnchorElement>) => {
    if (plainClick(event)) onLeave(event.currentTarget.getAttribute('href') ?? '');
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
        <div role="tabpanel" id="alerts-panel" aria-label={tab === 'need' ? 'Needs you' : 'For your information'}>
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

  const showTabs = phone && known && items.length > 0 && !stateBody;

  return (
    <Drawer
      title="Alerts"
      onClose={onClose}
      className="alerts-drawer"
      footer={
        <>
          <Link href="/notifications" onClick={follow}>
            See all alerts
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
            { key: 'info', label: 'For your information' },
          ]}
        />
      )}
      <div className={stateBody ? 'alerts-dstate' : undefined}>{body}</div>
    </Drawer>
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
          <VisuallyHidden>, </VisuallyHidden>
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
          <NextLink
            href={workHref(alert)}
            className={buttonClass(primary ? 'primary' : 'secondary', 'sm')}
            aria-label={`Open: ${alert.text}`}
            onClick={(event) => onOpen(event, alert)}
          >
            Open
          </NextLink>
        </li>
      ))}
    </ul>
  );
}
