import type { Metadata } from 'next';

import { WorkItemHistoryPane } from '@/features/work-item/WorkItemView';

export const metadata: Metadata = { title: 'Work item · PSL Factory' };

export default function WorkItemHistoryPage() {
  return <WorkItemHistoryPane />;
}
