import type { Metadata } from 'next';

import { TemplatesPageView } from '@/features/setup/TemplatesView';

export const metadata: Metadata = { title: 'Templates · Setup · PSL Factory' };

export default function Page() {
  return <TemplatesPageView />;
}
