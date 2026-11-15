'use client';

// ValidationSummary (design/system/project/components/ValidationSummary): at the top of a form when the person
// tries to submit with problems. Says how many things to fix and lists each as a link that moves focus to its
// field; the fields keep their own errors. It takes focus each time a submit fails (`attempt` changes) and
// disappears once everything is fixed.
import { useEffect, useRef } from 'react';

export type FieldProblem = { fieldId: string; message: string };

export function ValidationSummary({ problems, attempt }: { problems: FieldProblem[]; /** Increments on each failed submit. */ attempt: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const count = problems.length;
  useEffect(() => {
    if (attempt > 0) ref.current?.focus();
  }, [attempt]);
  if (count === 0) return null;
  return (
    <div ref={ref} className="psl-summary" role="alert" tabIndex={-1}>
      <strong>
        {count} {count === 1 ? 'thing' : 'things'} to fix
      </strong>
      <ul>
        {problems.map((p) => (
          <li key={p.fieldId}>
            <a
              href={`#${p.fieldId}`}
              onClick={(event) => {
                const field = document.getElementById(p.fieldId);
                if (!field) return;
                event.preventDefault();
                field.focus();
                field.scrollIntoView?.({ block: 'center' });
              }}
            >
              {p.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
