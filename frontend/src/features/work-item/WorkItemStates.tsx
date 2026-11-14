'use client';

// Work-item states from the SCR-02 and STATES boards: the error card and the no-access board.
import Link from 'next/link';

import type { ApiError } from '@/api/errors';

import { useIsPhone } from './usePhone';

/** STATES error card (the frame's classes) with this page's message and a Try again that re-reads. */
export function WorkErrorCard({ message, error, onRetry }: { message: string; error: ApiError; onRetry: () => void }) {
  return (
    <div className="shell-errorcard" role="alert">
      <span className="shell-eyebrow">ERROR · COULDN&rsquo;T LOAD</span>
      <span>{message}</span>
      <span className="shell-reference">Reference {error.code} for support.</span>
      <div className="shell-errorcard__action">
        <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block" onClick={onRetry}>
          Try again
        </button>
      </div>
    </div>
  );
}

/** 403 and 404 look the same (INV-ACCESS): nothing about the item is shown, not even its id. Each viewport uses its
 *  board's wording; on phones the way back sits in the bottom bar. */
export function NoAccessState() {
  const phone = useIsPhone();
  const back = (
    <Link className="psl-btn psl-btn--dark psl-btn--lg" href="/my-work">
      Back to my queue
    </Link>
  );
  return (
    <section className="psl-panel work-noaccess" aria-labelledby="work-noaccess-title">
      <div className="psl-panel__body">
        <span className="psl-tag psl-tag--neutral work-noaccess__tag">NO ACCESS</span>
        <h1 id="work-noaccess-title" className="shell-title">
          You can&rsquo;t open this work item
        </h1>
        {phone ? (
          <>
            <p className="work-plain">It belongs to a project or line you don&rsquo;t have access to. Nothing about it is shown.</p>
            <p className="work-plain">If your work needs it, ask the PMO Lead for access.</p>
            <div className="work-phonebar">{back}</div>
          </>
        ) : (
          <>
            <p className="work-plain">
              It belongs to a project or line you don&rsquo;t have access to. Nothing about it is shown here, not even its
              name or amount.
            </p>
            <ul className="work-noaccess__list">
              <li>If your work needs it, ask the PMO Lead for access to the project.</li>
              <li>If someone sent you this link, ask them what they need from you.</li>
            </ul>
            <p>{back}</p>
          </>
        )}
      </div>
    </section>
  );
}
