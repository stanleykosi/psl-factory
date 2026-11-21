import type { ReactNode } from 'react';

import { WorkItemLayoutFrame } from '@/features/work-item/WorkItemView';

/** One frame and one item read for Overview and History; the pages draw only the tab's content. */
export default async function WorkItemLayout({ children, params }: { children: ReactNode; params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WorkItemLayoutFrame id={id}>{children}</WorkItemLayoutFrame>;
}
