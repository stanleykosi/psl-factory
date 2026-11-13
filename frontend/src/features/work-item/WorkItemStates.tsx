// Work-item states from the SCR-02 and STATES boards: the error card and the no-access board.
import Link from 'next/link';

import type { ApiError } from '@/api/errors';

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

/** 403 and 404 look the same (INV-ACCESS): nothing about the item is shown, not even its id. */
export function NoAccessState() {
  return (
    <section className="psl-panel work-noaccess" aria-labelledby="work-noaccess-title">
      <div className="psl-panel__body">
        <span className="psl-tag psl-tag--neutral work-noaccess__tag">NO ACCESS</span>
        <h1 id="work-noaccess-title" className="shell-title">
          You can&rsquo;t open this work item
        </h1>
        <p className="work-plain">
          It belongs to a project or line you don&rsquo;t have access to. Nothing about it is shown here, not even its
          name or amount.
        </p>
        <p className="work-plain">
          If your work needs it, ask the PMO Lead for access to the project. If someone sent you this link, ask them
          what they need from you.
        </p>
        <p>
          <Link className="psl-btn psl-btn--dark psl-btn--lg" href="/my-work">
            Back to my queue
          </Link>
        </p>
      </div>
    </section>
  );
}
