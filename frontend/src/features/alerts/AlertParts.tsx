'use client';

// What the Alerts page (SCR-15) and the bell's drawer share: the row's avatar and text, opening an alert, marking one
// read, and the error card.
import { useRouter } from 'next/navigation';
import { useCallback, useRef, useState, type MouseEvent } from 'react';

import { markAlertRead } from '@/api/alerts';
import { ApiError } from '@/api/errors';
import { AgentAvatar, agentKey, Button, ErrorState, formatClock, VisuallyHidden } from '@/components';

import type { Alert } from './types';
import { alertHref, metaLine, subjectLine } from './model';
import { ALERT_READ_EVENT } from './useAlertsFeed';

export function AlertAvatar({ agent }: { agent: string | null }) {
  // Decorative: the agent's name is in the meta line. No agent, or one we do not know, gets a plain circle.
  const key = agentKey(agent);
  return key ? <AgentAvatar agent={key} size={40} /> : <span className="psl-avatar psl-avatar--40" aria-hidden="true" />;
}

/** The alert's title over its subject and detail, and the agent and time when it has them ("Chidi · 09:42"). */
export function AlertBody({ alert, now }: { alert: Alert; now: number }) {
  const subject = subjectLine(alert);
  const meta = metaLine(alert, now);
  return (
    <span className="alerts-body">
      <span className="alerts-text">{alert.title}</span>
      {subject && (
        <>
          <VisuallyHidden>, </VisuallyHidden>
          <span className="alerts-sub">{subject}</span>
        </>
      )}
      {meta && (
        <>
          <VisuallyHidden>, </VisuallyHidden>
          <span className="alerts-meta">{meta}</span>
        </>
      )}
    </span>
  );
}

/** 'read': marked read, then opened; 'failed': opened although the mark-read failed; 'held': nothing opened from here (a link click left to the browser, or the alert is gone). */
export type OpenAlert = (event: MouseEvent<HTMLAnchorElement>, alert: Alert) => Promise<'read' | 'failed' | 'held'>;
/** A row's quiet notice after a mark-read that did not work. */
export type RowNotice = 'gone' | 'failed' | 'session';

export const NOTICE_WORDS: Record<RowNotice, string> = {
  gone: 'This alert is no longer available.',
  failed: 'Couldn’t mark as read. Try again.',
  session: 'Your session was refreshed. Try again. Nothing was changed.',
};

type Handlers = { onRead?: (alert: Alert) => void; onGone?: () => void; onSignedOut?: (error: ApiError) => void };

/**
 * Marking read and opening. POST /notifications/{id}/read with `{}`; only a 200 changes anything (`onRead`, and the
 * bell's count through ALERT_READ_EVENT). A 401 goes to `onSignedOut`; a 403 or 404 says the alert is gone and
 * `onGone` re-reads the list; the work still opens after a failure of the server or the network, never after a stale
 * session token. Nothing retries; a read alert is never posted again.
 */
export function useAlertActions({ onRead, onGone, onSignedOut }: Handlers) {
  const router = useRouter();
  const sent = useRef(new Set<string>());
  const opening = useRef(false);
  const [notices, setNotices] = useState<Record<string, RowNotice>>({});

  const setNotice = useCallback((id: string, notice?: RowNotice) => {
    setNotices((prev) => {
      if (prev[id] === notice) return prev;
      const next = { ...prev };
      if (notice) next[id] = notice;
      else delete next[id];
      return next;
    });
  }, []);

  /** Marks one alert read; gives the notice when it did not work, or 'signedout' after a 401. */
  const markRead = useCallback(
    async (alert: Alert): Promise<RowNotice | 'signedout' | undefined> => {
      if (alert.read || sent.current.has(alert.id)) return undefined;
      sent.current.add(alert.id);
      try {
        await markAlertRead(alert.id);
      } catch (caught) {
        sent.current.delete(alert.id);
        const e = caught instanceof ApiError ? caught : undefined;
        if (e?.kind === 'unauthenticated') {
          onSignedOut?.(e);
          return 'signedout';
        }
        const notice: RowNotice = e?.kind === 'forbidden' || e?.kind === 'not_found' ? 'gone' : e?.kind === 'csrf' ? 'session' : 'failed';
        setNotice(alert.id, notice);
        if (notice === 'gone') onGone?.();
        return notice;
      }
      setNotice(alert.id);
      onRead?.(alert);
      window.dispatchEvent(new CustomEvent(ALERT_READ_EVENT, { detail: alert.id }));
      return undefined;
    },
    [onRead, onGone, onSignedOut, setNotice],
  );

  /** The row's link: unread, mark read first, then go; read, or a click with a modifier key, is left to the link. */
  const open: OpenAlert = useCallback(
    async (event, alert) => {
      if (alert.read || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return 'held';
      event.preventDefault();
      if (opening.current) return 'held';
      opening.current = true;
      const href = alertHref(alert);
      const notice = await markRead(alert);
      opening.current = false;
      if (!href || notice === 'gone' || notice === 'session' || notice === 'signedout') return 'held';
      router.push(href);
      return notice ? 'failed' : 'read';
    },
    [markRead, router],
  );

  return { open, markRead, notices };
}

/** A row with no link: a Mark as read button (unread only) and the row's notice. */
export function RowTail({ alert, notice, onMark }: { alert: Alert; notice?: RowNotice; onMark: (alert: Alert) => void }) {
  return (
    <>
      {notice && (
        <span className="alerts-rownote" role="status">
          {NOTICE_WORDS[notice]}
        </span>
      )}
      {!alert.read && !alertHref(alert) && notice !== 'gone' && (
        <Button kind="bare" className="alerts-markread" onClick={() => onMark(alert)}>
          Mark as read<VisuallyHidden>: {alert.title}</VisuallyHidden>
        </Button>
      )}
    </>
  );
}

/** STATES error: when it was last loaded, the reference, and one Try again. */
export function AlertsLoadError({ error, asOf, onRetry }: { error: ApiError; asOf?: string; onRetry: () => void }) {
  return (
    <ErrorState title="We couldn’t load your alerts." retryLabel="Try again" onRetry={onRetry}>
      Your work is safe; nothing was changed. {asOf && `Last loaded ${formatClock(asOf)}. `}Reference {error.code} for support.
    </ErrorState>
  );
}
