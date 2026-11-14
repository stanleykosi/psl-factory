'use client';

import { ExceptionsList } from './ExceptionsList';

/** /exceptions (SCR-10): the header, then the full list. Search, Filter, the open total and the per-row reference
 *  are not drawn: E-EXCEPTIONS does not supply them (readiness PMO-0-1). */
export function ExceptionsPage() {
  return (
    <div className="exc-page">
      <header className="exc-header">
        <h1 className="shell-title">All exceptions</h1>
        <p className="exc-intro">
          Everyone&rsquo;s work that can&rsquo;t move on by itself, across every line you can see: an outcome we
          couldn&rsquo;t confirm, a missing owner or rule, or a check that failed.
        </p>
      </header>
      <ExceptionsList />
    </div>
  );
}
