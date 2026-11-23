import type { Metadata } from 'next';

import { isLiveWorkId } from '@/features/work-item/live/model';
import { WorkItemHistoryPane } from '@/features/work-item/WorkItemView';

export const metadata: Metadata = { title: 'Work item · PSL Factory' };

export default async function WorkItemHistoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return isLiveWorkId(id) ? null : <WorkItemHistoryPane />;
}
