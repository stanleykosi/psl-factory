import type { Metadata } from 'next';

import { DestinationPage } from '@/shell/DestinationPage';

export const metadata: Metadata = { title: 'Overview · PSL Factory' };

export default function OverviewPage() {
  return <DestinationPage destination="overview" />;
}
