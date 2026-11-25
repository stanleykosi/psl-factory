import type { Metadata } from 'next';
import { Suspense } from 'react';

import { ClientsList } from '@/features/clients';

export const metadata: Metadata = { title: 'Clients · PSL Factory' };

/** q and billing come from the address (useSearchParams needs a Suspense boundary so `next build` can prerender the route). */
export default function Page() {
  return (
    <Suspense fallback={null}>
      <ClientsList />
    </Suspense>
  );
}
