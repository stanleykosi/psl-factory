import type { Metadata } from 'next';

import { MilestoneCompleteRoute } from '@/features/projects/MilestoneCompleteRoute';

// The title never names the project or milestone: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Mark a milestone complete · PSL Factory' };

export default async function MilestoneCompletePage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return <MilestoneCompleteRoute caseId={caseId} />;
}
