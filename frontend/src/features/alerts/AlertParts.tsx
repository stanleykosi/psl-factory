'use client';

// What the Alerts page (SCR-15) and the bell's drawer share: the row's avatar and text over meta, opening an alert,
// and the error card.
import { useRouter } from 'next/navigation';
import { useCallback, useRef, type MouseEvent } from 'react';

import { api, call } from '@/api/client';
import { ApiError } from '@/api/errors';
import { AgentAvatar, agentKey, ErrorState, formatDateTime, VisuallyHidden } from '@/components';

import type { Alert } from './types';
import { metaLine, workHref } from './model';

export function AlertAvatar({ agent }: { agent: string }) {
  // Decorative: the agent's name is in the meta line. An agent we do not know gets a plain circle.
  const key = agentKey(agent);
  return key ? <AgentAvatar agent={key} size={40} /> : <span className="psl-avatar psl-avatar--40" aria-hidden="true" />;
}

/** The alert's sentence over its meta line ("Chidi · WhatsApp · 09:42 WAT"). */
export function AlertBody({ alert, now }: { alert: Alert; now: number }) {
  return (
    <span className="alerts-body">
      <span className="alerts-text">{alert.text}</span>
      <VisuallyHidden>, </VisuallyHidden>
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

/** STATES error: when it was last loaded, the reference, and one Try again. */
export function AlertsLoadError({ error, asOf, onRetry }: { error: ApiError; asOf?: string; onRetry: () => void }) {
  return (
    <ErrorState title="We couldn’t load your alerts." retryLabel="Try again" onRetry={onRetry}>
      Your work is safe; nothing was changed. {asOf && `Last loaded ${formatDateTime(asOf)}. `}Reference {error.code} for support.
    </ErrorState>
  );
}
