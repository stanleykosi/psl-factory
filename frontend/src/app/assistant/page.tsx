import type { Metadata } from 'next';

import { DestinationPage } from '@/shell/DestinationPage';

export const metadata: Metadata = { title: 'Assistant · PSL Factory' };

export default function AssistantPage() {
  return <DestinationPage destination="assistant" />;
}
