import type { Metadata } from 'next';

import { DestinationPage } from '@/shell/DestinationPage';

export const metadata: Metadata = { title: 'My work · PSL Factory' };

export default function MyWorkPage() {
  return <DestinationPage destination="my_work" />;
}
