'use client';

import { usePhoneBack } from '@/shell/AppShell';

export function PhoneBackFixture() {
  usePhoneBack({ label: 'Queue', href: '/my-work' });
  return <h1 className="shell-title">Exceptions</h1>;
}
