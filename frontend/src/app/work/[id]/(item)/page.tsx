import type { Metadata } from 'next';

import { isLiveWorkId } from '@/features/work-item/live/model';
import { WorkItemOverviewPane } from '@/features/work-item/WorkItemView';

// The title never names the item: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Work item · PSL Factory' };

// A live (integer) id is drawn whole by the layout's frame.
export default async function WorkItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return isLiveWorkId(id) ? null : <WorkItemOverviewPane />;
}
