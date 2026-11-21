import type { ReactNode } from 'react';

import { SetupLayoutFrame } from '@/features/setup/SetupFrame';

/** One frame for the seven Setup tabs (the delivery and finance rule pages outside this group draw their own header). */
export default function SetupTabsLayout({ children }: { children: ReactNode }) {
  return <SetupLayoutFrame>{children}</SetupLayoutFrame>;
}
