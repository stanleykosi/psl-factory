// Month-end no-access view (INV-ACCESS): 403 and 404 look the same and show nothing about the checklist.
import Link from 'next/link';

export function MonthEndNoAccess() {
  return (
    <section className="psl-panel monthend-noaccess" aria-labelledby="monthend-noaccess-title">
      <div className="psl-panel__body">
        <span className="psl-tag psl-tag--neutral monthend-noaccess__tag">NO ACCESS</span>
        <h1 id="monthend-noaccess-title" className="shell-title">
          You can&rsquo;t open this month-end checklist
        </h1>
        <p className="monthend-plain">It is for people who work on Finance for this month. Nothing about it is shown here.</p>
        <p>
          <Link className="psl-btn psl-btn--dark psl-btn--lg" href="/my-work">
            Back to my queue
          </Link>
        </p>
      </div>
    </section>
  );
}
