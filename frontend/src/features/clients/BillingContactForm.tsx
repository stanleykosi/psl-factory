'use client';

// The billing contact of one client. The form is shown only when the detail says can_change; nothing is read from /me.
// One PUT per press (a ref blocks a second press at once), never resent. After a 200, a 409, a 403 or an unclear
// failure the client is read once, and the reloaded revision and can_change decide what happens next.
import { useEffect, useRef, useState, type FormEvent } from 'react';

import type { ApiError } from '@/api/errors';
import { Button, Callout, Panel, TextField } from '@/components';

import { saveBillingContact, type ClientDetail, type FieldMessage } from './api';
import type { RefreshResult } from './useClient';

type Notice =
  | { kind: 'saved' }
  | { kind: 'saved_unread' }
  | { kind: 'stale'; unread?: boolean }
  | { kind: 'forbidden'; message: string }
  | { kind: 'uncertain' }
  | { kind: 'invalid'; message: string; fields?: FieldMessage[] };

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
  const noticeBox = useRef<HTMLDivElement>(null);

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

  const showsNotice = notice !== null && notice.kind !== 'invalid' && notice.kind !== 'saved';
  useEffect(() => {
    // A failure notice is announced and takes focus once per press; its scroll-margin keeps it clear of the phone's Save bar.
    if (showsNotice) noticeBox.current?.focus();
  }, [notice, showsNotice]);

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
    <Panel head="Billing contact" className="clients__panel clients__formpanel" bodyClassName="clients__panelbody clients__formbody">
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
            <Callout kind="problem" focusOnShow={!firstInvalid}>
              {notice.fields ? 'Check the highlighted details.' : notice.message || 'Check the highlighted details.'}
              {summary.map((m, i) => (
                <span key={i} className="clients__block">
                  {m}
                </span>
              ))}
            </Callout>
          )}
          <div className="clients__fieldgroup">
            <TextField
              id="client-name"
              ref={nameInput}
              label="Billing contact name"
              className={needed ? 'clients__needed' : undefined}
              value={name}
              readOnly={unread}
              autoComplete="off"
              hint="Needed before any invoice can start"
              error={fieldMessages.get('name')}
              onChange={(e) => setName(e.target.value)}
            />
            {current?.name && <span className="clients__current">Current: {[current.name, current.email].filter(Boolean).join(' · ')}</span>}
          </div>
          <TextField
            id="client-email"
            ref={emailInput}
            label="Billing email"
            className={needed ? 'clients__needed' : undefined}
            type="email"
            value={email}
            readOnly={unread}
            autoComplete="off"
            error={fieldMessages.get('email')}
            onChange={(e) => setEmail(e.target.value)}
          />
          {!unread && (
            <div className="clients__bar">
              <Button type="submit" size="lg" className="clients__save" busy={busy} busyLabel="Saving…">
                Save billing contact
              </Button>
            </div>
          )}
        </form>
      )}
      {notice && showsNotice && (
        <div ref={noticeBox} tabIndex={-1} role="alert" className="clients__notice">
          <Callout kind="warning">
            {notice.kind === 'saved_unread' && <span className="clients__block">Saved. We couldn’t refresh the page; reload to see the latest.</span>}
            {notice.kind === 'stale' && <span className="clients__block">This client changed while you were editing. Check the details and save again.</span>}
            {notice.kind === 'stale' && notice.unread && <span className="clients__block">We couldn’t refresh the page, so nothing can be saved yet.</span>}
            {notice.kind === 'forbidden' && <span className="clients__block">{notice.message || 'Your role does not allow this.'}</span>}
            {notice.kind === 'uncertain' && <span className="clients__block">We couldn’t confirm the change was saved.</span>}
          </Callout>
        </div>
      )}
      {notice?.kind === 'saved' && <Callout kind="success">Billing contact saved.</Callout>}
      {unread && (
        <Button kind="secondary" className="clients__retry" busy={busy} busyLabel="Trying again…" onClick={() => void tryAgain()}>
          Try again
        </Button>
      )}
    </Panel>
  );
}
