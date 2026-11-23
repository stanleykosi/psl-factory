import type { Metadata } from 'next';

import { SignInView } from '@/features/sign-in/SignInView';

export const metadata: Metadata = { title: 'Sign in' };

export default function Page() {
  return <SignInView />;
}
