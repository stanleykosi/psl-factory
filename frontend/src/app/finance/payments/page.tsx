import type { Metadata } from 'next';
import { Suspense } from 'react';

import { PaymentsView } from '@/features/finance/payments/PaymentsView';

export const metadata: Metadata = { title: 'Payments · PSL Factory' };

/** q and status come from the address (useSearchParams needs a Suspense boundary so `next build` can prerender the route). */
export default function PaymentsPage() {
  return (
    <Suspense fallback={null}>
      <PaymentsView />
    </Suspense>
  );
}
