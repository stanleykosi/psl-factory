import type { Metadata } from 'next';

import { WorkItemOverviewPane } from '@/features/work-item/WorkItemView';

// The title never names the item: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Work item · PSL Factory' };

export default function WorkItemPage() {
  return <WorkItemOverviewPane />;
}
