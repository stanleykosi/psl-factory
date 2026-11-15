'use client';

// What the Alerts page (SCR-15) and the bell's drawer share: the row's avatar and text over meta, opening an alert,
// and the error card.
import { useRouter } from 'next/navigation';
import { useCallback, useRef, type MouseEvent } from 'react';

import { api, call } from '@/api/client';
import { ApiError } from '@/api/errors';
import { formatClock } from '@/features/decide/format';

import type { Alert } from './types';
import { agentImage, metaLine, workHref } from './model';

export function AlertAvatar({ agent }: { agent: string }) {
  const image = agentImage(agent);
  return (
    <span className={image ? `psl-avatar psl-avatar--40 psl-avatar--${agent}` : 'psl-avatar psl-avatar--40'}>
      {/* Decorative: the agent's name is in the meta line. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {image && <img src={image} alt="" width={40} height={40} />}
    </span>
  );
}

/** The alert's sentence over its meta line ("Chidi · WhatsApp · 09:42"). */
export function AlertBody({ alert, now }: { alert: Alert; now: number }) {
  return (
    <span className="alerts-body">
      <span className="alerts-text">{alert.text}</span>
      <span className="alerts-sr">, </span>
      <span className="alerts-meta">{metaLine(alert, now)}</span>
    </span>
  );
}

export type OpenAlert = (event: MouseEvent<HTMLAnchorElement>, alert: Alert) => void;

/**
 * An unread alert is marked read first (one POST); the work opens whether or not that worked, and nothing retries.
 * A read alert, or a click with a modifier key or another button, is left to the link. `onRead` hears a mark-read
 * the server accepted; `onError` hears one that failed.
 */
export function useOpenAlert(onRead?: (alert: Alert) => void, onError?: (error: ApiError) => void): OpenAlert {
  const router = useRouter();
  const opening = useRef(false);
  return useCallback(
    async (event: MouseEvent<HTMLAnchorElement>, alert: Alert) => {
      if (alert.read || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (opening.current) return;
      opening.current = true;
      try {
        await call(api.POST('/api/v1/notifications/{notification_id}/read', { params: { path: { notification_id: alert.id } } }));
        onRead?.(alert);
      } catch (caught) {
        // The row stays unread: the list is re-read later and shows what the server holds.
        if (caught instanceof ApiError) onError?.(caught);
      }
      opening.current = false;
      router.push(workHref(alert));
    },
    [router, onRead, onError],
  );
}

/** STATES error card for the alerts list: when it was last loaded, the reference, and one Try again. */
export function AlertsLoadError({ error, asOf, onRetry }: { error: ApiError; asOf?: string; onRetry: () => void }) {
  return (
    <div className="shell-errorcard" role="alert">
      <span className="shell-eyebrow">ERROR · COULDN&rsquo;T LOAD</span>
      <span>We couldn&rsquo;t load your alerts. Your work is safe; nothing was changed.</span>
      <span className="shell-reference">
        {asOf && `Last loaded ${formatClock(asOf)}. `}Reference {error.code} for support.
      </span>
      <div className="shell-errorcard__action">
        <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block" onClick={onRetry}>
          Try again
        </button>
      </div>
    </div>
  );
}
