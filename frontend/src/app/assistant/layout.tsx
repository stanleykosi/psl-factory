import type { ReactNode } from 'react';

import { AssistantFrame } from '@/features/assistant/AssistantFrame';

export default function AssistantLayout({ children }: { children: ReactNode }) {
  return <AssistantFrame>{children}</AssistantFrame>;
}
