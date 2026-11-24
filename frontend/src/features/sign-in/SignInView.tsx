'use client';

// SCR-17 sign-in (default and error states). One sign-in, one wrong-details message: the page never says which part was wrong.
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';

import { call, csrfHeader, liveApi, refreshSession, setCsrfToken } from '@/api/client';
import { ApiError } from '@/api/errors';
import { Button, Callout, Checkbox, Loading, Skeleton, TextField, useIsPhone } from '@/components';
import { safeNext } from '@/shell/signInNext';

import { BrandColumn } from './BrandColumn';
import './sign-in.css';
import { NotAdmittedBody, useAfterSignIn } from './useAfterSignIn';

type Phase = 'loading' | 'unready' | 'ready' | 'not-admitted';

/** The fixed wording for a failed sign-in; the server's own message is never shown. */
export function signInProblem(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Sign-in isn’t working right now. Try again in a moment. Nothing was changed.';
  if (error.kind === 'invalid') return error.code === 'sign_in_failed' ? 'That email and password don’t match.' : 'We couldn’t read those details. Check them and try again.';
  if (error.kind === 'csrf') return 'Your session was refreshed. Press Sign in again. Nothing was changed.';
  if (error.kind === 'rate_limited') return 'Too many sign-in tries. Try again later.';
  if (error.kind === 'network') return 'We could not reach PSL Factory. Check your connection and try again.';
  return 'Sign-in isn’t working right now. Try again in a moment. Nothing was changed.';
}

const queryNext = () => safeNext(new URLSearchParams(window.location.search).get('next'));

export function SignInView() {
  const phone = useIsPhone();
  const [phase, setPhase] = useState<Phase>('loading');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<{ text: string; n: number } | null>(null);
  const [missing, setMissing] = useState<{ username?: string; password?: string }>({});
  const usernameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const signingIn = useRef(false);

  const notAdmitted = useCallback(() => setPhase('not-admitted'), []);
  const afterSignIn = useAfterSignIn(notAdmitted);

  const prepare = useCallback(async () => {
    setPhase('loading');
    try {
      const session = await refreshSession();
      if (session.signed_in) void afterSignIn(queryNext() ?? safeNext(session.next_url));
      else setPhase('ready');
    } catch {
      setPhase('unready');
    }
  }, [afterSignIn]);

  useEffect(() => {
    // One session read per visit; the effect only starts the request.
    void prepare();
  }, [prepare]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (signingIn.current) return;
    const name = username.trim();
    const empty = { username: name === '' ? 'Enter your work email.' : undefined, password: password === '' ? 'Enter your password.' : undefined };
    setMissing(empty);
    if (empty.username || empty.password) {
      (empty.username ? usernameRef : passwordRef).current?.focus();
      return;
    }
    signingIn.current = true;
    setBusy(true);
    setProblem(null);
    const next = queryNext();
    try {
      const session = await call(liveApi.POST('/api/v1/session', { params: csrfHeader, body: { username: name, password, remember, ...(next ? { next_url: next } : {}) } }));
      setCsrfToken(session.csrf_token);
      setPassword('');
      await afterSignIn(safeNext(session.next_url));
    } catch (error) {
      setPassword('');
      setProblem((previous) => ({ text: signInProblem(error), n: (previous?.n ?? 0) + 1 }));
    } finally {
      signingIn.current = false;
      setBusy(false);
    }
  }

  let body;
  if (phase === 'loading') {
    body = (
      <div className="signin-form">
        <h1 className="signin-title">Sign in</h1>
        <Skeleton widths={[60, 90, 90]} />
        <Loading>Preparing sign-in…</Loading>
      </div>
    );
  } else if (phase === 'unready') {
    body = (
      <div className="signin-form">
        <h1 className="signin-title">Sign in</h1>
        <Callout kind="problem" announce={false}>
          We couldn’t get sign-in ready. Nothing was changed.
        </Callout>
        <Button kind="secondary" size="lg" onClick={() => void prepare()}>
          Try again
        </Button>
      </div>
    );
  } else if (phase === 'not-admitted') {
    body = <NotAdmittedBody onSignedOut={() => void prepare()} />;
  } else {
    body = (
      <form className="signin-form" method="post" noValidate onSubmit={(event) => void submit(event)}>
        <h1 className="signin-title">{phone ? 'Sign in to continue' : 'Sign in'}</h1>
        {problem && (
          <Callout key={problem.n} kind="problem" focusOnShow>
            {problem.text}
          </Callout>
        )}
        <TextField
          ref={usernameRef}
          label="Work email or sign-in name"
          name="username"
          type="text"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          phone={phone}
          value={username}
          error={missing.username}
          onChange={(event) => setUsername(event.target.value)}
        />
        <TextField
          ref={passwordRef}
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          phone={phone}
          value={password}
          error={missing.password}
          className={problem && !missing.password ? 'is-error' : undefined}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Checkbox label={phone ? 'Keep me signed in on this phone' : 'Keep me signed in'} checked={remember} onChange={(event) => setRemember(event.target.checked)} />
        <Button type="submit" size="lg" block busy={busy} busyLabel="Signing in…">
          Sign in
        </Button>
        <p className="signin-forgot">Forgot your password? Reset opens in a later release. Ask your administrator for help.</p>
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
