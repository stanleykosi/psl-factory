import type { Metadata } from 'next';

import { ReservedTab } from '@/features/setup/ReservedTab';

export const metadata: Metadata = { title: 'Payroll visibility · Setup · PSL Factory' };

export default function Page() {
  return <ReservedTab tab="payroll-visibility" />;
}
