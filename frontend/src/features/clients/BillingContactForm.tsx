'use client';

// The billing contact of one client. The form is shown only when the detail says can_change; nothing is read from /me.
// One PUT per press (a ref blocks a second press at once), never resent. After a 200, a 409, a 403 or an unclear
// failure the client is read once, and the reloaded revision and can_change decide what happens next.
import { useEffect, useRef, useState, type FormEvent } from 'react';

import type { ApiError } from '@/api/errors';

import { saveBillingContact, type ClientDetail, type FieldMessage } from './api';
import type { RefreshResult } from './useClient';

type Notice =
  | { kind: 'saved' }
  | { kind: 'saved_unread' }
  | { kind: 'stale'; unread?: boolean }
  | { kind: 'forbidden'; message: string }
  | { kind: 'uncertain' }
  | { kind: 'invalid'; message: string; fields?: FieldMessage[] };

const HELP_ID = 'client-name-help';
const FIELDS = ['name', 'email'] as const;

type Props = {
  client: ClientDetail;
  refresh: () => Promise<RefreshResult>;
  onSignedOut: () => void;
  onNoAccess: () => void;
};

function ReadOnlyValue({ id, label, value, set }: { id: string; label: string; value?: string; set: boolean }) {
  return (
    <div className="psl-field">
      <span className="psl-label" id={id}>
        {label}
      </span>
      <span className="clients__value" aria-labelledby={id}>
        {value ?? (set ? 'Not given' : 'Not set')}
      </span>
    </div>
  );
}

export function BillingContactForm({ client, refresh, onSignedOut, onNoAccess }: Props) {
  const contact = client.billing_contact;
  const [name, setName] = useState(contact.name ?? '');
  const [email, setEmail] = useState(contact.email ?? '');
  const seeded = useRef({ name: contact.name ?? '', email: contact.email ?? '' });
  const [busy, setBusy] = useState(false);
  const pressed = useRef(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [current, setCurrent] = useState<ClientDetail['billing_contact'] | null>(null);
  // The page could not be read again: the revision on screen may be stale, so nothing can be saved until it is.
  const [unread, setUnread] = useState(false);
  const nameInput = useRef<HTMLInputElement>(null);
  const emailInput = useRef<HTMLInputElement>(null);

  const fieldMessages = new Map<string, string>();
  const summary: string[] = [];
  if (notice?.kind === 'invalid') {
    for (const f of notice.fields ?? []) {
      if (FIELDS.includes(f.name as (typeof FIELDS)[number]) && !fieldMessages.has(f.name)) fieldMessages.set(f.name, f.message);
      else summary.push(f.message);
    }
  }
  const firstInvalid = FIELDS.find((f) => fieldMessages.has(f));
  const invalidKey = notice?.kind === 'invalid' ? notice : null;
  useEffect(() => {
    if (invalidKey && firstInvalid) (firstInvalid === 'name' ? nameInput : emailInput).current?.focus();
    // Focus moves once per 422, to the first input that has a message.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invalidKey]);

  const seed = (to: ClientDetail['billing_contact']) => {
    seeded.current = { name: to.name ?? '', email: to.email ?? '' };
    setName(seeded.current.name);
    setEmail(seeded.current.email);
  };

  /** Shows the reloaded contact: in the fields when the person has not typed, else as "Current: …" under them. */
  const showReloaded = (fresh: ClientDetail) => {
    const typed = name !== seeded.current.name || email !== seeded.current.email;
    if (!typed) seed(fresh.billing_contact);
    else if (fresh.billing_contact.set) setCurrent(fresh.billing_contact);
  };

  /** A sign-out or a hidden record ends the page; true when it did. */
  const ended = (error: ApiError) => {
    if (error.kind === 'unauthenticated') onSignedOut();
    else if (error.kind === 'not_found') onNoAccess();
    else return false;
    return true;
  };

  async function reload(): Promise<ClientDetail | undefined> {
    const result = await refresh();
    if (result.error) {
      if (!ended(result.error)) setUnread(true);
      return undefined;
    }
    setUnread(false);
    return result.client;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pressed.current) return;
    // A blank input sends nothing: the message sits beside it and focus goes to the first one.
    const blank: FieldMessage[] = [];
    if (!name.trim()) blank.push({ name: 'name', message: 'Enter the billing contact name.' });
    if (!email.trim()) blank.push({ name: 'email', message: 'Enter the billing email.' });
    if (blank.length) return setNotice({ kind: 'invalid', message: '', fields: blank });
    pressed.current = true;
    setBusy(true);
    setNotice(null);
    setCurrent(null);
    try {
      const outcome = await saveBillingContact(client.client_id, { expected_revision: client.revision, name: name.trim(), email: email.trim() });
      if (outcome.kind === 'unauthenticated') return onSignedOut();
      if (outcome.kind === 'not_found') return onNoAccess();
      if (outcome.kind === 'invalid') return setNotice({ kind: 'invalid', message: outcome.message, fields: outcome.fields });
      const fresh = await reload();
      if (outcome.kind === 'saved') {
        if (fresh) seed(fresh.billing_contact);
        return setNotice({ kind: fresh ? 'saved' : 'saved_unread' });
      }
      if (fresh) showReloaded(fresh);
      if (outcome.kind === 'stale') setNotice({ kind: 'stale', unread: !fresh });
      else if (outcome.kind === 'forbidden') setNotice({ kind: 'forbidden', message: outcome.message });
      else setNotice({ kind: 'uncertain' });
    } finally {
      pressed.current = false;
      setBusy(false);
    }
  }

  async function tryAgain() {
    if (pressed.current) return;
    pressed.current = true;
    setBusy(true);
    try {
      const fresh = await reload();
      if (fresh) {
        showReloaded(fresh);
        setNotice(null);
      }
    } finally {
      pressed.current = false;
      setBusy(false);
    }
  }

  const editable = client.can_change === true;
  const needed = !contact.set;

  return (
    <section className="psl-panel clients__panel clients__formpanel" aria-labelledby="client-contact-title">
      <h2 id="client-contact-title" className="psl-panel__head clients__h2 clients__h2--panel">
        Billing contact
      </h2>
      <div className="clients__panelbody clients__formbody">
        {!editable ? (
          <>
            <ReadOnlyValue id="client-name-label" label="Billing contact name" value={contact.name} set={contact.set} />
            <p className="clients__help">Needed before any invoice can start</p>
            <ReadOnlyValue id="client-email-label" label="Billing email" value={contact.email} set={contact.set} />
            <p className="clients__plain">You can’t change this client’s details.</p>
          </>
        ) : (
          <form onSubmit={(e) => void submit(e)} noValidate className="clients__form">
            {notice?.kind === 'invalid' && (
              <div role="alert" className="psl-callout psl-callout--problem">
                <span>
                  {notice.fields ? 'Check the highlighted details.' : notice.message || 'Check the highlighted details.'}
                  {summary.map((m, i) => (
                    <span key={i} className="clients__block">
                      {m}
                    </span>
                  ))}
                </span>
              </div>
            )}
            <div className="psl-field">
              <label className="psl-label" htmlFor="client-name">
                Billing contact name
              </label>
              <input
                id="client-name"
                ref={nameInput}
                className={`psl-input${needed ? ' clients__needed' : ''}`}
                value={name}
                readOnly={unread}
                autoComplete="off"
                aria-invalid={fieldMessages.has('name') || undefined}
                aria-describedby={fieldMessages.has('name') ? `client-name-error ${HELP_ID}` : HELP_ID}
                onChange={(e) => setName(e.target.value)}
              />
              <span id={HELP_ID} className="clients__help">
                Needed before any invoice can start
              </span>
              {fieldMessages.has('name') && (
                <span id="client-name-error" className="psl-error">
                  {fieldMessages.get('name')}
                </span>
              )}
              {current?.name && <span className="clients__current">Current: {[current.name, current.email].filter(Boolean).join(' · ')}</span>}
            </div>
            <div className="psl-field">
              <label className="psl-label" htmlFor="client-email">
                Billing email
              </label>
              <input
                id="client-email"
                ref={emailInput}
                className={`psl-input${needed ? ' clients__needed' : ''}`}
                type="email"
                value={email}
                readOnly={unread}
                autoComplete="off"
                aria-invalid={fieldMessages.has('email') || undefined}
                aria-describedby={fieldMessages.has('email') ? 'client-email-error' : undefined}
                onChange={(e) => setEmail(e.target.value)}
              />
              {fieldMessages.has('email') && (
                <span id="client-email-error" className="psl-error">
                  {fieldMessages.get('email')}
                </span>
              )}
            </div>
            {!unread && (
              <div className="clients__bar">
                <button type="submit" className="psl-btn psl-btn--lg clients__save" disabled={busy} aria-busy={busy}>
                  {busy ? 'Saving…' : 'Save billing contact'}
                </button>
              </div>
            )}
          </form>
        )}
        {notice && notice.kind !== 'invalid' && (
          <div className="clients__notice">
            {notice.kind === 'saved_unread' && <p>Saved. We couldn’t refresh the page; reload to see the latest.</p>}
            {notice.kind === 'stale' && <p>This client changed while you were editing. Check the details and save again.</p>}
            {notice.kind === 'stale' && notice.unread && <p>We couldn’t refresh the page, so nothing can be saved yet.</p>}
            {notice.kind === 'forbidden' && <p>{notice.message || 'Your role does not allow this.'}</p>}
            {notice.kind === 'uncertain' && <p>We couldn’t confirm the change was saved.</p>}
          </div>
        )}
        <p role="status" className="clients__status">
          {notice?.kind === 'saved' ? 'Billing contact saved.' : ''}
        </p>
        {unread && (
          <button type="button" className="psl-btn psl-btn--secondary clients__retry" disabled={busy} onClick={() => void tryAgain()}>
            Try again
          </button>
        )}
      </div>
    </section>
  );
}
