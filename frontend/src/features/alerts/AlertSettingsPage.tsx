'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { Button, Callout, ErrorState, Link, PageTitle, Select, Table, useIsPhone } from '@/components';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { AlertSwitch } from './AlertSwitch';
import type { AlertEvent, AlertPrefs, SavedPrefs } from './types';
import { buildPrefsBody, draftFrom, quietLabel, selectsShown, type Draft } from './model';
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
  const problem = useRef<HTMLDivElement>(null);

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
    // a failed save's message can sit under the phone's pinned Save bar; the callout's scroll-margin keeps it clear of the bar
    if (notice?.kind === 'problem') problem.current?.scrollIntoView?.({ block: 'nearest' });
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
      {notice.kind === 'saved' && <Callout kind="success">Your alert settings are saved.</Callout>}
      {notice.kind === 'stale' && (
        <Callout kind="warning" focusOnShow>
          Someone changed these settings since you opened them. This is the latest version; make your changes again.
        </Callout>
      )}
      {notice.kind === 'invalid' && (
        <Callout kind="problem" focusOnShow>
          We couldn&rsquo;t save your settings. {notice.message}
        </Callout>
      )}
      {notice.kind === 'problem' && (
        <div ref={problem} className="alerts-scroll">
          <Callout kind="problem">
            We couldn&rsquo;t save your settings. Nothing was changed. {notice.message} Reference {notice.code} for support.
          </Callout>
        </div>
      )}
    </>
  );
  const saveButton = (size: 'lg' | 'xl') => (
    <Button size={size} block busy={saving} busyLabel="Saving…" onClick={() => void save()}>
      Save settings
    </Button>
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
        <div className="alerts-footer">{saveButton('xl')}</div>
      </div>
    );
  }

  const shown = selectsShown(prefs);
  const number = prefs.whatsapp?.masked_number;
  return (
    <div className="alerts-page">
      {title}
      <Table
        caption="Alerts for each kind of work"
        className="alerts-table"
        columns={[
          {
            key: 'when',
            header: 'WHEN',
            cell: (event) => (
              <>
                {event.label}
                {locked(event)}
              </>
            ),
          },
          { key: 'whatsapp', header: 'WHATSAPP', cell: (event) => switches(event, false)[0] },
          { key: 'email', header: 'EMAIL', cell: (event) => switches(event, false)[1] },
          { key: 'timing', header: 'TIMING', cell: (event) => event.timing_label },
        ]}
        rows={prefs.events}
        rowKey={(event) => event.key}
        empty="No alert settings to show."
      />
      {(shown.digest || shown.quiet || number || prefs.note) && (
        <div className="alerts-cards">
          {(shown.digest || shown.quiet) && (
            <div className="alerts-card">
              {shown.digest && prefs.digest_at && (
                <Select
                  label="Daily digest at"
                  placeholder="Not set"
                  options={prefs.digest_at.options}
                  value={draft.digest || undefined}
                  onChange={(digest) => edit((d) => ({ ...d, digest }))}
                />
              )}
              {shown.quiet && prefs.quiet_hours && (
                <Select
                  label="Quiet hours"
                  placeholder="Not set"
                  options={prefs.quiet_hours.options}
                  value={draft.quiet || undefined}
                  onChange={(quiet) => edit((d) => ({ ...d, quiet }))}
                />
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
      <div className="alerts-save">{saveButton('lg')}</div>
    </div>
  );
}
