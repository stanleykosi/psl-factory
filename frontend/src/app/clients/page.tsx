import type { Metadata } from 'next';

import { ClientsList } from '@/features/clients';

export const metadata: Metadata = { title: 'Clients · PSL Factory' };

export default function Page() {
  return <ClientsList />;
}
