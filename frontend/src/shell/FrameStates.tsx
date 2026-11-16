// Main-area states of the frame (STATES boards: loading, empty, error).
import Link from 'next/link';

import type { ApiError } from '@/api/errors';
import { Button, Callout, EmptyState, Loading, Skeleton } from '@/components';

import type { DestinationInfo } from './destinations';
import { SIGN_IN_URL } from './sample';

export function LoadingState() {
  return (
    <div className="shell-loading">
      <Skeleton widths={[90, 70, 80]} />
      <Loading>Loading…</Loading>
    </div>
  );
}

export function SignedOutState({ pathname }: { pathname: string }) {
  const href = `${SIGN_IN_URL}?next=${encodeURIComponent(pathname)}`;
  return (
    <Callout kind="warning">
      <strong>You&rsquo;re signed out.</strong> <a href={href}>Sign in</a>
    </Callout>
  );
}

export function ForbiddenState({ error }: { error: ApiError }) {
  return (
    <Callout kind="warning">
      <strong>Your account can&rsquo;t use PSL Factory.</strong> {error.message}
    </Callout>
  );
}

export function LoadErrorState({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div className="shell-errorcard" role="alert">
      <span className="shell-eyebrow">ERROR · COULDN&rsquo;T LOAD</span>
      <span>We couldn&rsquo;t load your account. Your work is safe; nothing was changed.</span>
      <span className="shell-reference">Reference {error.code} for support.</span>
      <div className="shell-errorcard__action">
        <Button kind="secondary" size="lg" block onClick={onRetry}>
          Try again
        </Button>
      </div>
    </div>
  );
}

export function NoSectionsState() {
  return (
    <EmptyState title="No sections are open to your role yet.">Ask a Lead or Admin to check your roles.</EmptyState>
  );
}

export function NotOpenState({ first }: { first: DestinationInfo | undefined }) {
  return (
    <EmptyState title="This section isn&rsquo;t open to your role.">
      {first && <Link href={first.href}>Go to {first.label}</Link>}
    </EmptyState>
  );
}
