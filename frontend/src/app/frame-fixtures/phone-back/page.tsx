import { notFound } from 'next/navigation';

import { PhoneBackFixture } from './PhoneBackFixture';

// Browser-run fixture for the frame's phone back-link slot; a 404 unless the server sets FRAME_FIXTURES=1.
export const dynamic = 'force-dynamic';

export default function PhoneBackFixturePage() {
  if (process.env.FRAME_FIXTURES !== '1') notFound();
  return <PhoneBackFixture />;
}
