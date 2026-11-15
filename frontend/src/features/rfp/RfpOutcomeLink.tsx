// SCR-02: the quiet way into the RFP outcome, shown only when the item carries rfp_outcome (the backend's grant).
import Link from 'next/link';

import type { WorkItem } from '@/api/types';

export function RfpOutcomeLink({ id, item }: { id: string; item: Pick<WorkItem, 'rfp_outcome'> }) {
  if (!item.rfp_outcome) return null;
  return (
    <Link className="psl-btn psl-btn--secondary" href={`/work/${encodeURIComponent(id)}/outcome`}>
      Record the outcome
    </Link>
  );
}
