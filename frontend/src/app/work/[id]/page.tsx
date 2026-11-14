import type { Metadata } from 'next';

import { WorkItemView } from '@/features/work-item/WorkItemView';

// The title never names the item: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Work item · PSL Factory' };

export default async function WorkItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WorkItemView id={id} tab="overview" />;
}
