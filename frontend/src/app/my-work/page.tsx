import type { Metadata } from 'next';

import { MyWorkPage } from '@/features/my-work/MyWorkPage';

export const metadata: Metadata = { title: 'My work · PSL Factory' };

export default function Page() {
  return <MyWorkPage />;
}
