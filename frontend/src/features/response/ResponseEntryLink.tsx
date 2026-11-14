// SCR-02 waiting: the link into SCR-16 for a response task you can act on, in place of "Open the decision".
// Variants this page doesn't record (team input, go-live, handover) get no link.
import Link from 'next/link';

import type { ResponseTask } from './contract';
import { RESPONSE_LABELS } from './labels';

export function ResponseEntryLink({ id, task }: { id: string; task: ResponseTask }) {
  const label = task.response && RESPONSE_LABELS.entry[task.response.variant];
  if (!label) return null;
  return (
    <Link className="psl-btn" href={`/work/${encodeURIComponent(id)}/respond?task=${encodeURIComponent(task.id)}`}>
      {label}
    </Link>
  );
}
