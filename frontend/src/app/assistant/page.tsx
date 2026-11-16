import type { Metadata } from 'next';

import { AssistantHome } from '@/features/assistant/AssistantHome';

export const metadata: Metadata = { title: 'Assistant · PSL Factory' };

export default function AssistantPage() {
  return <AssistantHome />;
}
