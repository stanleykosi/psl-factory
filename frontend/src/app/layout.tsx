import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';

import '@/styles/fonts.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import '@/styles/tokens.css';
import '@/styles/psl-bundle.css';
import '@/styles/shell.css';

import { AppShell } from '@/shell/AppShell';

export const metadata: Metadata = { title: 'PSL Factory' };
export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="psl">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
