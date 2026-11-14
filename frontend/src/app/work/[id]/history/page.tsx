import type { Metadata } from 'next';

import { WorkItemView } from '@/features/work-item/WorkItemView';

export const metadata: Metadata = { title: 'Work item · PSL Factory' };

export default async function WorkItemHistoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WorkItemView id={id} tab="history" />;
}
