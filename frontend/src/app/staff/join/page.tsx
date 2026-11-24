import type { Metadata } from 'next';

import { JoinView } from '@/features/join/JoinView';

// The invitation token travels in the link's fragment; no referrer is sent from this page.
export const metadata: Metadata = { title: 'Set up your account', referrer: 'no-referrer' };

export default function Page() {
  return <JoinView />;
}
