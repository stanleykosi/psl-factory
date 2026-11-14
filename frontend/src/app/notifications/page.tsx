import type { Metadata } from 'next';

import { NotificationsPage } from '@/features/alerts/NotificationsPage';

export const metadata: Metadata = { title: 'Notifications · PSL Factory' };

export default function Page() {
  return <NotificationsPage />;
}
