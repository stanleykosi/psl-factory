import type { Metadata } from 'next';

import { DelegationPageView } from '@/features/setup/DelegationView';

export const metadata: Metadata = { title: 'Delegation · Setup · PSL Factory' };

export default function Page() {
  return <DelegationPageView />;
}
