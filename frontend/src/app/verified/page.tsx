import type { Metadata } from 'next';

import { VerifiedPage } from '@/features/verified/VerifiedPage';

export const metadata: Metadata = { title: 'Verified outputs · PSL Factory' };

export default function Page() {
  return <VerifiedPage />;
}
