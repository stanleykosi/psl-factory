'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { readAlertPreferences, saveAlertPreferences } from '@/api/alerts';
import { ApiError, networkError } from '@/api/errors';
import { Button, Callout, ErrorState, Link, PageTitle, useIsPhone, formatDateTime } from '@/components';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { AlertSwitch } from './AlertSwitch';
import type { AlertPrefs } from './types';
import { buildPrefsBody, CHANNEL_WORDS, DELIVERY_STATE_WORDS, deliveryTime, draftFrom, prefsChanged, type Draft } from './model';
import './alerts.css';

const PATHNAME = '/settings/alerts';
const CHANNELS = [
  { key: 'email', name: 'Email' },
  { key: 'whatsapp', name: 'WhatsApp' },
] as const;
const NOT_READY = 'Not ready yet: you will not receive anything on this channel until it is set up';

type PageState = { status: 'loading' } | { status: 'error'; code: string } | { status: 'ready'; prefs: AlertPrefs; draft: Draft };
type Notice = { kind: 'stale' } | { kind: 'invalid'; message: string } | { kind: 'problem' };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/** A body without a revision, both switches and a receipts list is not a settings page: it gets the error card. */
function pageFrom(data: AlertPrefs): PageState {
  const ok = typeof data?.revision === 'number' && typeof data.email_requested === 'boolean' && typeof data.whatsapp_requested === 'boolean' && Array.isArray(data.recent_deliveries);
  return ok ? { status: 'ready', prefs: data, draft: draftFrom(data) } : { status: 'error', code: 'unexpected_response' };
}

/** /settings/alerts (SCR-15 settings): the person's own email and WhatsApp switches, saved with the read revision, and the recent receipts. */
export function AlertSettingsPage() {
  const phone = useIsPhone();
  const [page, setPage] = useState<PageState>({ status: 'loading' });
  const [notice, setNotice] = useState<Notice | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const savingRef = useRef(false);

  const failed = useCallback((error: unknown) => {
    const e = asApiError(error);
    if (e.kind === 'unauthenticated') setSignedOut(true);
    else setPage({ status: 'error', code: e.code });
  }, []);

  const load = useCallback(async () => {
    setPage({ status: 'loading' });
    setNotice(null);
    setSaved(false);
    try {
      setPage(pageFrom(await readAlertPreferences()));
    } catch (error) {
      failed(error);
    }
  }, [failed]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const toggle = (key: 'email' | 'whatsapp') => {
    setSaved(false);
    setPage((prev) => (prev.status === 'ready' ? { ...prev, draft: { ...prev.draft, [key]: !prev.draft[key] } } : prev));
  };

  /** One save at a time; no failure retries by itself. */
  const save = async () => {
    if (page.status !== 'ready' || savingRef.current || !prefsChanged(page.prefs, page.draft)) return;
    savingRef.current = true;
    setSaving(true);
    setNotice(null);
    setSaved(false);
    try {
      const data = await saveAlertPreferences(buildPrefsBody(page.prefs, page.draft));
      // The held revision, switches and readiness are the response's; the receipts stay unless it carries them.
      const next = pageFrom({ ...data, recent_deliveries: data.recent_deliveries ?? page.prefs.recent_deliveries });
      setPage(next);
      setSaved(next.status === 'ready');
    } catch (error) {
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') setSignedOut(true);
      else if (e.kind === 'stale') setNotice({ kind: 'stale' });
      else if (e.kind === 'invalid') setNotice({ kind: 'invalid', message: e.message });
      else setNotice({ kind: 'problem' });
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  if (signedOut) return <SignedOutState pathname={PATHNAME} />;

  // Phone: "← Notifications" sits level with the heading until the frame's phone bar has a back-link slot (D-19, D-13).
  const title = phone ? (
    <div className="alerts-head">
      <PageTitle phoneSize={24}>How you&rsquo;re alerted</PageTitle>
      <Link href="/notifications" className="alerts-back">
        ← Notifications
      </Link>
    </div>
  ) : (
    <>
      <p className="alerts-eyebrow">SETTINGS / ALERTS</p>
      <PageTitle size={36}>How you&rsquo;re alerted</PageTitle>
    </>
  );

  if (page.status === 'loading') return <LoadingState />;
  if (page.status === 'error') {
    return (
      <div className="alerts-page">
        {title}
        <ErrorState title="We couldn’t load your alert settings." retryLabel="Try again" onRetry={() => void load()}>
          Your work is safe; nothing was changed. Reference {page.code} for support.
        </ErrorState>
      </div>
    );
  }

  const { prefs, draft } = page;
  const changed = prefsChanged(prefs, draft);
  const notices = (
    <>
      {notice?.kind === 'stale' && (
        <Callout kind="warning" focusOnShow>
          These settings changed elsewhere. Reload to see the latest.{' '}
          <Button kind="secondary" size="sm" onClick={() => void load()}>
            Reload
          </Button>
        </Callout>
      )}
      {notice?.kind === 'invalid' && (
        <Callout kind="problem" focusOnShow>
          We couldn&rsquo;t save your settings. {notice.message}
        </Callout>
      )}
      {notice?.kind === 'problem' && <Callout kind="problem">We couldn&rsquo;t save your settings. Nothing was changed. Try again.</Callout>}
      {saved && (
        <p className="alerts-saved" role="status">
          Saved
        </p>
      )}
    </>
  );
  const saveButton = (size: 'lg' | 'xl') => (
    <>
      <Button size={size} block busy={saving} busyLabel="Saving…" disabled={!changed} aria-describedby={changed ? undefined : 'alerts-nochange'} onClick={() => void save()}>
        Save settings
      </Button>
      {!changed && (
        <span id="alerts-nochange" className="alerts-receiptmeta">
          Nothing to save: change a switch first.
        </span>
      )}
    </>
  );

  const channels = (
    <ul className="alerts-channels" aria-label="Channels">
      {CHANNELS.map(({ key, name }) => {
        const ready = prefs[`${key}_ready`];
        const state = ready ? 'Ready' : draft[key] ? NOT_READY : 'Not ready yet';
        return (
          <li key={key} className="alerts-channel">
            <span>
              <span className="alerts-channelname">{name}</span>
              <span id={`alerts-state-${key}`} className="alerts-channelstate">
                {state}
              </span>
            </span>
            <AlertSwitch name={name} on={draft[key]} describedBy={`alerts-state-${key}`} onToggle={() => toggle(key)} />
          </li>
        );
      })}
    </ul>
  );

  const receipts = (
    <section aria-labelledby="alerts-recent" className="cmp-stack">
      <h2 id="alerts-recent" className="alerts-h2">
        Recent deliveries
      </h2>
      {prefs.recent_deliveries.length === 0 ? (
        <p className="alerts-receiptmeta">Nothing has been sent to you yet.</p>
      ) : (
        <ul className="alerts-receipts">
          {prefs.recent_deliveries.map((delivery, index) => (
            <li key={`${delivery.channel}-${delivery.created_at}-${index}`} className="alerts-receipt">
              <span>{CHANNEL_WORDS[delivery.channel]}</span>
              <span className={`alerts-receiptstate alerts-receiptstate--${delivery.state}`}>{DELIVERY_STATE_WORDS[delivery.state]}</span>
              <span className="alerts-receiptmeta">{formatDateTime(deliveryTime(delivery))}</span>
              {delivery.receipt && <span className="alerts-receiptmeta">Receipt {delivery.receipt}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );

  if (phone) {
    return (
      <div className="alerts-page">
        {title}
        {channels}
        {notices}
        {receipts}
        <div className="alerts-footspace" aria-hidden="true" />
        <div className="alerts-footer">{saveButton('xl')}</div>
      </div>
    );
  }

  return (
    <div className="alerts-page">
      {title}
      {channels}
      {notices}
      <div className="alerts-save">{saveButton('lg')}</div>
      {receipts}
    </div>
  );
}
