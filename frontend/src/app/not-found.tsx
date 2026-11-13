import type { Metadata } from 'next';

import { UnknownPage } from '@/shell/DestinationPage';

export const metadata: Metadata = { title: 'Page not found · PSL Factory' };

export default function NotFound() {
  return <UnknownPage />;
}
