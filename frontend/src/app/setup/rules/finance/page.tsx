import type { Metadata } from 'next';

import { FinancePageView } from '@/features/setup/FinanceRulesView';

export const metadata: Metadata = { title: 'Finance rules · Setup · PSL Factory' };

export default function Page() {
  return <FinancePageView />;
}
