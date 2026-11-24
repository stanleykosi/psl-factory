'use client';

// What went wrong with a write, above its button: words for a 422 no control carries, the sign-in link after a 401,
// and the plain sentence for the other failures. "We couldn't confirm it saved" has its own block in the form.
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

import { Callout } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { generalMessage, type Failure } from './failure';

export function FailureNotice({ failure, drawn, children }: { failure: Failure | null; /** The field keys this form draws a control for. */ drawn: readonly string[]; children?: ReactNode }) {
  const pathname = usePathname();
  if (!failure || failure.kind === 'unconfirmed') return null;
  if (failure.kind === 'signed_out') return <SignedOutState pathname={pathname} />;
  if (failure.kind === 'invalid') {
    const text = generalMessage(failure, drawn);
    return text ? <Callout kind="problem">{text}</Callout> : null;
  }
  return (
    <Callout kind={failure.kind === 'forbidden' || failure.kind === 'gone' ? 'problem' : 'warning'}>
      {failure.message}
      {children}
    </Callout>
  );
}
