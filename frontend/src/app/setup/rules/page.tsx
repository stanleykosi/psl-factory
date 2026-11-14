import type { Metadata } from 'next';

import { RulesPageView } from '@/features/setup/RulesView';

export const metadata: Metadata = { title: 'Rules · Setup · PSL Factory' };

export default function Page() {
  return <RulesPageView />;
}
