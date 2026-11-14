import type { Metadata } from 'next';

import { ExceptionsPage } from '@/features/exceptions/ExceptionsPage';

export const metadata: Metadata = { title: 'All exceptions · PSL Factory' };

export default function Page() {
  return <ExceptionsPage />;
}
