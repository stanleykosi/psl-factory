import type { Metadata } from 'next';

import { DestinationPage } from '@/shell/DestinationPage';

export const metadata: Metadata = { title: 'Setup · PSL Factory' };

export default function SetupPage() {
  return <DestinationPage destination="setup" />;
}
