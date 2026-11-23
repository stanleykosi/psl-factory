import type { ReactNode } from 'react';

import { isLiveWorkId } from '@/features/work-item/live/model';
import { LiveWorkItemLayoutFrame } from '@/features/work-item/live/LiveWorkItemView';
import { WorkItemLayoutFrame } from '@/features/work-item/WorkItemView';

/** One frame and one item read for Overview and History; the pages draw only the tab's content.
 *  An integer id is a live work item (F-85); any other id is a v7 item and keeps its frame until its line moves. */
export default async function WorkItemLayout({ children, params }: { children: ReactNode; params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (isLiveWorkId(id)) return <LiveWorkItemLayoutFrame id={id} />;
  return <WorkItemLayoutFrame id={id}>{children}</WorkItemLayoutFrame>;
}
