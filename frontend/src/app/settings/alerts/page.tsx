import type { Metadata } from 'next';

import { AlertSettingsPage } from '@/features/alerts/AlertSettingsPage';

export const metadata: Metadata = { title: 'Alert settings · PSL Factory' };

export default function Page() {
  return <AlertSettingsPage />;
}
