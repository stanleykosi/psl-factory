'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { AlertSwitch } from './AlertSwitch';
import type { AlertEvent, AlertPrefs, SavedPrefs } from './types';
import { buildPrefsBody, draftFrom, quietLabel, selectsShown, type Draft } from './model';
import { useIsPhone } from './useIsPhone';
import './alerts.css';

const PATHNAME = '/settings/alerts';
const CHANNELS = [
  { key: 'whatsapp', name: 'WhatsApp' },
  { key: 'email', name: 'Email' },
] as const;

type PageState = { status: 'loading' } | { status: 'error'; code: string } | { status: 'ready'; prefs: AlertPrefs; draft: Draft };
type Notice =
  | { kind: 'saved' }
  | { kind: 'stale' }
  | { kind: 'invalid'; message: string }
  | { kind: 'problem'; message: string; code: string };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const readPrefs = () => call(api.GET('/api/v1/me/alert-preferences'));

/** A body without an events array is not a settings page: it gets the error card (Reference missing_events). */
function pageFrom(data: AlertPrefs | SavedPrefs): PageState {
  if (!Array.isArray(data.events)) return { status: 'error', code: 'missing_events' };
  const prefs = data as AlertPrefs;
  return { status: 'ready', prefs, draft: draftFrom(prefs) };
}

/** /settings/alerts (SCR-15 settings): the person's own alert preferences, saved with the read revision. */
export function AlertSettingsPage() {
  const phone = useIsPhone();
  const [page, setPage] = useState<PageState>({ status: 'loading' });
  const [notice, setNotice] = useState<Notice | null>(null);
  const [saving, setSaving] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const savingRef = useRef(false);
  const callout = useRef<HTMLDivElement>(null);

  const failed = useCallback((error: unknown) => {
    const e = asApiError(error);
    if (e.kind === 'unauthenticated') setSignedOut(true);
    else setPage({ status: 'error', code: e.code });
  }, []);

  const load = useCallback(async () => {
    setPage({ status: 'loading' });
    setNotice(null);
    try {
      setPage(pageFrom(await readPrefs()));
    } catch (error) {
      failed(error);
    }
  }, [failed]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  useEffect(() => {
    if (notice?.kind === 'stale' || notice?.kind === 'invalid') callout.current?.focus();
  }, [notice]);

  const edit = (change: (draft: Draft) => Draft) => {
    setPage((prev) => (prev.status === 'ready' ? { ...prev, draft: change(prev.draft) } : prev));
    setNotice((prev) => (prev?.kind === 'saved' ? null : prev));
  };
  const toggle = (key: string, channel: 'whatsapp' | 'email') =>
    edit((draft) => ({ ...draft, events: draft.events.map((e) => (e.key === key ? { ...e, [channel]: !e[channel] } : e)) }));

  /** One save at a time; no failure retries by itself. */
  const save = async () => {
    if (page.status !== 'ready' || savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setNotice(null);
    try {
      const data = await call(api.PUT('/api/v1/me/alert-preferences', { body: buildPrefsBody(page.prefs, page.draft, phone) }));
      setPage(pageFrom(data));
      setNotice({ kind: 'saved' });
    } catch (error) {
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') setSignedOut(true);
      else if (e.kind === 'stale') {
        // Someone else saved first: show their version and drop every edit.
        try {
          setPage(pageFrom(await readPrefs()));
          setNotice({ kind: 'stale' });
        } catch (reread) {
          failed(reread);
        }
      } else if (e.kind === 'invalid') setNotice({ kind: 'invalid', message: e.message });
      else setNotice({ kind: 'problem', message: e.message, code: e.code });
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  if (signedOut) return <SignedOutState pathname={PATHNAME} />;

  // Phone: "← Notifications" sits level with the heading until the frame's phone bar has a back-link slot (D-19, D-13).
  const title = phone ? (
    <div className="alerts-head">
      <h1 className="shell-title alerts-settitle">How you&rsquo;re alerted</h1>
      <Link href="/notifications" className="alerts-back">
        ← Notifications
      </Link>
    </div>
  ) : (
    <>
      <p className="alerts-eyebrow">SETTINGS / ALERTS</p>
      <h1 className="shell-title">How you&rsquo;re alerted</h1>
    </>
  );

  if (page.status === 'loading') return <LoadingState />;
  if (page.status === 'error') {
    return (
      <div className="alerts-page">
        {title}
        <div className="shell-errorcard" role="alert">
          <span className="shell-eyebrow">ERROR · COULDN&rsquo;T LOAD</span>
          <span>We couldn&rsquo;t load your alert settings. Your work is safe; nothing was changed.</span>
          <span className="shell-reference">Reference {page.code} for support.</span>
          <div className="shell-errorcard__action">
            <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block" onClick={() => void load()}>
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { prefs, draft } = page;
  const switches = (event: AlertEvent, withWords: boolean) => {
    const current = draft.events.find((e) => e.key === event.key) ?? event;
    return CHANNELS.map((ch) => (
      <span key={ch.key} className="alerts-switchwrap">
        <AlertSwitch name={`${ch.name}, ${event.label}`} on={current[ch.key]} locked={Boolean(event.locked_reason)} onToggle={() => toggle(event.key, ch.key)} />
        {withWords && <span aria-hidden="true">{ch.name}</span>}
      </span>
    ));
  };
  const locked = (event: AlertEvent) => event.locked_reason && <span className="alerts-locked">{event.locked_reason}</span>;

  const notices = notice && (
    <>
      {notice.kind === 'saved' && (
        <div className="psl-callout psl-callout--success" role="status">
          Your alert settings are saved.
        </div>
      )}
      {notice.kind === 'stale' && (
        <div ref={callout} tabIndex={-1} className="psl-callout psl-callout--warning" role="alert">
          Someone changed these settings since you opened them. This is the latest version; make your changes again.
        </div>
      )}
      {notice.kind === 'invalid' && (
        <div ref={callout} tabIndex={-1} className="psl-callout psl-callout--problem" role="alert">
          We couldn&rsquo;t save your settings. {notice.message}
        </div>
      )}
      {notice.kind === 'problem' && (
        <div className="psl-callout psl-callout--problem" role="alert">
          We couldn&rsquo;t save your settings. Nothing was changed. {notice.message} Reference {notice.code} for support.
        </div>
      )}
    </>
  );
  const saveButton = (className: string) => (
    <button type="button" className={className} aria-disabled={saving || undefined} onClick={() => void save()}>
      {saving ? 'Saving…' : 'Save settings'}
    </button>
  );

  if (phone) {
    const quiet = quietLabel(prefs);
    return (
      <div className="alerts-page">
        {title}
        {prefs.events.map((event) => (
          <div key={event.key} className="alerts-eventcard">
            <span className="alerts-eventlabel">{event.label}</span>
            {locked(event)}
            <span className="alerts-eventswitches">{switches(event, true)}</span>
            {event.timing_label && <span className="alerts-timing">{event.timing_label}</span>}
          </div>
        ))}
        {quiet && <p className="alerts-quiet">Quiet hours {quiet}</p>}
        {notices}
        <div className="alerts-footspace" aria-hidden="true" />
        <div className="alerts-footer">{saveButton('psl-btn psl-btn--xl psl-btn--block')}</div>
      </div>
    );
  }

  const shown = selectsShown(prefs);
  const number = prefs.whatsapp?.masked_number;
  return (
    <div className="alerts-page">
      {title}
      <div className="psl-tablewrap">
        <table className="psl-table alerts-table">
          <caption className="alerts-sr">Alerts for each kind of work</caption>
          <thead>
            <tr>
              <th scope="col">WHEN</th>
              <th scope="col">WHATSAPP</th>
              <th scope="col">EMAIL</th>
              <th scope="col">TIMING</th>
            </tr>
          </thead>
          <tbody>
            {prefs.events.map((event) => {
              const [whatsapp, email] = switches(event, false);
              return (
                <tr key={event.key}>
                  <td>
                    {event.label}
                    {locked(event)}
                  </td>
                  <td>{whatsapp}</td>
                  <td>{email}</td>
                  <td>{event.timing_label}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {(shown.digest || shown.quiet || number || prefs.note) && (
        <div className="alerts-cards">
          {(shown.digest || shown.quiet) && (
            <div className="alerts-card">
              {shown.digest && prefs.digest_at && (
                <>
                  <label htmlFor="alerts-digest" className="alerts-cardlabel">
                    Daily digest at
                  </label>
                  <select
                    id="alerts-digest"
                    className="psl-input alerts-select"
                    value={draft.digest}
                    onChange={(e) => edit((d) => ({ ...d, digest: e.target.value }))}
                  >
                    {prefs.digest_at.value === undefined && <option value="">Not set</option>}
                    {prefs.digest_at.options.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </>
              )}
              {shown.quiet && prefs.quiet_hours && (
                <>
                  <label htmlFor="alerts-quiet" className="alerts-cardlabel">
                    Quiet hours
                  </label>
                  <select
                    id="alerts-quiet"
                    className="psl-input alerts-select"
                    value={draft.quiet}
                    onChange={(e) => edit((d) => ({ ...d, quiet: e.target.value }))}
                  >
                    {prefs.quiet_hours.value === undefined && <option value="">Not set</option>}
                    {prefs.quiet_hours.options.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </>
              )}
            </div>
          )}
          {(number || prefs.note) && (
            <div className="alerts-card">
              {number && (
                <>
                  <span className="alerts-cardlabel">WhatsApp number</span>
                  <span className="alerts-number">
                    {number} · {prefs.whatsapp?.verified ? 'verified' : 'not verified'}
                  </span>
                </>
              )}
              {prefs.note && <span className="alerts-note">{prefs.note}</span>}
            </div>
          )}
        </div>
      )}
      {notices}
      <div className="alerts-save">{saveButton('psl-btn psl-btn--lg psl-btn--block')}</div>
    </div>
  );
}
