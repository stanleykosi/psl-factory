'use client';

// SCR-17 set-up from an invitation. The link's fragment holds the token: it is read once, kept in memory, removed from
// the address bar, and sent only in the body of the two requests. The page never says why an invitation can't be used.
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';

import { call, csrfHeader, liveApi, refreshSession } from '@/api/client';
import { ApiError } from '@/api/errors';
import { Button, buttonClass, Callout, Loading, Skeleton, TextField, useIsPhone } from '@/components';
import { safeNext } from '@/shell/signInNext';

import { BrandColumn } from '../sign-in/BrandColumn';
import '../sign-in/sign-in.css';
import { NewPasswordFields, newPasswordProblems, type NewPasswordProblems } from '../sign-in/NewPasswordFields';
import { NotAdmittedBody, useAfterSignIn } from '../sign-in/useAfterSignIn';
import './join.css';
import { signInTarget } from './signInTarget';
import { lagosWhen, welcomeSentences, type Workspace } from './welcome';

type Phase = 'loading' | 'cannot-open' | 'unavailable' | 'form' | 'done' | 'not-admitted';
type Preview = { name: string; email: string; expires_at: string; workspaces: Workspace[] };
type Problem = { text: string; trySigningIn: boolean; n: number };

const TOKEN = /^[A-Za-z0-9_-]{43}$/;
const PREVIEW = '/api/v1/accounts/invitations/preview' as const;
const ACCEPT = '/api/v1/accounts/invitations/accept' as const;

/** The fixed wording for a failed accept; a 422 shows the server's own message instead. */
function acceptProblem(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Set-up isn’t working right now. Try again in a moment. Nothing was changed.';
  if (error.kind === 'invalid') return error.message;
  if (error.kind === 'csrf') return 'Your session was refreshed. Press Finish setup again. Nothing was changed.';
  if (error.kind === 'rate_limited') return 'Too many tries. Try again later.';
  if (error.kind === 'network') return 'We could not reach PSL Factory. Check your connection and try again.';
  return 'Set-up isn’t working right now. Try again in a moment. Nothing was changed.';
}

const isUnavailable = (error: unknown) => error instanceof ApiError && error.kind === 'invalid' && error.code === 'invitation_unavailable';

export function JoinView() {
  const phone = useIsPhone();
  const [phase, setPhase] = useState<Phase>('loading');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [errors, setErrors] = useState<NewPasswordProblems>({});
  const [announceUnavailable, setAnnounceUnavailable] = useState(false);
  const token = useRef<string | null>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);
  const doneRef = useRef<HTMLHeadingElement>(null);
  const [target, setTarget] = useState('/sign-in');
  const sending = useRef(false);

  const notAdmitted = useCallback(() => setPhase('not-admitted'), []);
  const afterSignIn = useAfterSignIn(notAdmitted);

  const open = useCallback(async () => {
    const held = token.current;
    if (!held) return setPhase('unavailable');
    setPhase('loading');
    try {
      await refreshSession();
      const found = await call(liveApi.POST(PREVIEW, { params: csrfHeader, body: { token: held } }));
      setPreview(found);
      setPhase('form');
    } catch (error) {
      const retryable = error instanceof ApiError && ['network', 'server', 'rate_limited', 'csrf', 'read_limited'].includes(error.kind);
      setPhase(retryable || !(error instanceof ApiError) ? 'cannot-open' : 'unavailable');
    }
  }, []);

  useEffect(() => {
    // The fragment is read once and removed; a second run of this effect keeps the value already held.
    if (token.current === null) {
      const value = window.location.hash.replace(/^#/, '');
      token.current = TOKEN.test(value) ? value : '';
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
    void open();
  }, [open]);

  useEffect(() => {
    if (phase === 'done') doneRef.current?.focus();
  }, [phase]);

  // A failed accept may have left the invitation unusable (replaced, or the sign-in name taken): the preview says which.
  async function recheck() {
    try {
      await call(liveApi.POST(PREVIEW, { params: csrfHeader, body: { token: token.current ?? '' } }));
    } catch (error) {
      if (isUnavailable(error)) {
        setAnnounceUnavailable(true);
        setPhase('unavailable');
      }
    }
  }

  const send = () => call(liveApi.POST(ACCEPT, { params: csrfHeader, body: { token: token.current ?? '', password, confirm } }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending.current) return;
    const found = newPasswordProblems(password, confirm);
    setErrors(found ?? {});
    if (found) {
      (found.password ? passwordRef : confirmRef).current?.focus();
      return;
    }
    sending.current = true;
    setBusy(true);
    setProblem(null);
    try {
      let accepted;
      try {
        accepted = await send();
      } catch (error) {
        // A refused token means the request never reached the handler (A-3): the session has been re-read, so send it once more.
        if (!(error instanceof ApiError) || error.kind !== 'csrf') throw error;
        accepted = await send();
      }
      token.current = '';
      setPassword('');
      setConfirm('');
      setTarget(signInTarget(accepted.next_url));
      const session = await refreshSession();
      if (session.signed_in) {
        await afterSignIn(safeNext(accepted.next_url));
        return;
      }
      setPhase('done');
    } catch (error) {
      setPassword('');
      setConfirm('');
      if (isUnavailable(error)) {
        setAnnounceUnavailable(true);
        return setPhase('unavailable');
      }
      const fields = error instanceof ApiError && error.kind === 'invalid' && error.code === 'invalid_input' ? error.fields : [];
      const known: NewPasswordProblems = {};
      const other: string[] = [];
      for (const field of fields) {
        if (field.name === 'password') known.password = field.message;
        else if (field.name === 'confirm') known.confirm = field.message;
        else other.push(field.message);
      }
      setErrors(known);
      if (fields.length > 0 && other.length === 0) {
        (known.password ? passwordRef : confirmRef).current?.focus();
        return;
      }
      const text = other.length > 0 ? other.join(' ') : acceptProblem(error);
      const trySigningIn = error instanceof ApiError && (error.kind === 'network' || error.status >= 500);
      setProblem((previous) => ({ text, trySigningIn, n: (previous?.n ?? 0) + 1 }));
      if (error instanceof ApiError && error.kind === 'invalid' && error.code !== 'invalid_input') await recheck();
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  let body;
  if (phase === 'loading') {
    body = (
      <div className="signin-form">
        <h1 className="signin-title">Set up your account</h1>
        <Skeleton widths={[60, 90, 90]} />
        <Loading>Opening your invitation…</Loading>
      </div>
    );
  } else if (phase === 'cannot-open') {
    body = (
      <div className="signin-form">
        <h1 className="signin-title">Set up your account</h1>
        <Callout kind="problem" announce={false}>
          We couldn’t open your invitation. Nothing was changed.
        </Callout>
        <Button kind="secondary" size="lg" onClick={() => void open()}>
          Try again
        </Button>
      </div>
    );
  } else if (phase === 'unavailable') {
    body = (
      <div className="signin-form">
        <Callout kind="problem" announce={announceUnavailable} focusOnShow={announceUnavailable} plain>
          <div>
            <h1 className="signin-title">This invitation can’t be used</h1>
            <p className="join-note">It may have expired or already been used. Ask the person who invited you to send a new one.</p>
          </div>
        </Callout>
        <Link className="psl-link join-link" href="/sign-in">
          Already set up? Sign in
        </Link>
      </div>
    );
  } else if (phase === 'done') {
    body = (
      <div className="signin-form">
        <h1 ref={doneRef} tabIndex={-1} className="signin-title join-done-title">
          Your account is ready.
        </h1>
        <p className="join-note">Sign in with {preview?.email}.</p>
        <Link className={`${buttonClass('primary', 'lg', phone)} join-link`} href={target}>
          Sign in
        </Link>
      </div>
    );
  } else if (phase === 'not-admitted') {
    body = <NotAdmittedBody />;
  } else {
    const expires = preview ? lagosWhen(preview.expires_at) : null;
    body = (
      <form className="signin-form join-form" method="post" noValidate onSubmit={(event) => void submit(event)}>
        <h1 className="signin-title">Set up your account</h1>
        {problem && (
          <Callout key={problem.n} kind="problem" focusOnShow>
            {problem.text}
            {problem.trySigningIn && (
              <>
                {' '}
                If this keeps happening, try signing in; your account may already be set up. <Link className="psl-link" href="/sign-in">Sign in</Link>
              </>
            )}
          </Callout>
        )}
        <p className="join-welcome">
          Welcome, {preview?.name}.{' '}
          {welcomeSentences(preview?.workspaces ?? []).map((sentence, i) => (
            <span key={i}>
              {i > 0 && ' '}
              {sentence.lead} <strong>{sentence.access}</strong> for {sentence.names}.
            </span>
          ))}
        </p>
        {expires && <p className="join-valid">This invitation works until {expires}.</p>}
        <TextField label="Work email" name="username" type="text" autoComplete="username" readOnly phone={phone} value={preview?.email ?? ''} />
        <NewPasswordFields
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
          errors={errors}
          hint="At least 12 characters"
          passwordRef={passwordRef}
          confirmRef={confirmRef}
        />
        <Button type="submit" size="lg" block={phone} busy={busy} busyLabel="Setting up…">
          Finish setup
        </Button>
        <p className="join-note">Wrong roles? Ask the person who invited you; you can’t change your own roles.</p>
      </form>
    );
  }

  return (
    <main className="signin">
      <BrandColumn />
      {body}
    </main>
  );
}
