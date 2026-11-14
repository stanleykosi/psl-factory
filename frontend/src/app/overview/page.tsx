import type { Metadata } from 'next';

import { OverviewPage } from '@/features/overview/OverviewPage';

export const metadata: Metadata = { title: 'Overview · PSL Factory' };

export default function Page() {
  return <OverviewPage />;
}
