// Main-area states of the frame (STATES boards: loading, empty, error).
import Link from 'next/link';

import type { ApiError } from '@/api/errors';

import type { DestinationInfo } from './destinations';
import { WarningIcon } from './icons';
import { SIGN_IN_URL } from './sample';

export function LoadingState() {
  return (
    <div className="psl-panel shell-loading">
      <div className="shell-skel" aria-hidden="true">
        <span className="psl-skel" style={{ width: '90%' }} />
        <span className="psl-skel" style={{ width: '70%' }} />
        <span className="psl-skel" style={{ width: '80%' }} />
      </div>
      <span className="psl-loading" role="status">
        <span className="psl-busy" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        Loading…
      </span>
    </div>
  );
}

export function SignedOutState({ pathname }: { pathname: string }) {
  const href = `${SIGN_IN_URL}?next=${encodeURIComponent(pathname)}`;
  return (
    <div className="psl-callout psl-callout--warning">
      <WarningIcon />
      <span>
        <strong>You&rsquo;re signed out.</strong> <a href={href}>Sign in</a>
      </span>
    </div>
  );
}

export function ForbiddenState({ error }: { error: ApiError }) {
  return (
    <div className="psl-callout psl-callout--warning">
      <WarningIcon />
      <span>
        <strong>Your account can&rsquo;t use PSL Factory.</strong> {error.message}
      </span>
    </div>
  );
}

export function LoadErrorState({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div className="shell-stack">
      <div className="psl-callout psl-callout--problem" role="alert">
        <WarningIcon />
        <span>
          <strong>We couldn&rsquo;t load your account.</strong> Your work is safe; nothing was changed.
        </span>
      </div>
      <p className="shell-reference">Reference {error.code} for support.</p>
      <div>
        <button type="button" className="psl-btn psl-btn--secondary" onClick={onRetry}>
          Try again
        </button>
      </div>
    </div>
  );
}

export function NoSectionsState() {
  return (
    <div className="psl-empty">
      <h3>No sections are open to your role yet.</h3>
      <p>Ask a Lead or Admin to check your roles.</p>
    </div>
  );
}

export function NotOpenState({ first }: { first: DestinationInfo | undefined }) {
  return (
    <div className="psl-empty">
      <h3>This section isn&rsquo;t open to your role.</h3>
      {first && (
        <p>
          <Link href={first.href}>Go to {first.label}</Link>
        </p>
      )}
    </div>
  );
}
