import type { Metadata } from 'next';

import { DeliveryPageView } from '@/features/setup/DeliveryRulesView';

export const metadata: Metadata = { title: 'Delivery rules · Setup · PSL Factory' };

export default function Page() {
  return <DeliveryPageView />;
}
