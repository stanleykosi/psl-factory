import type { Metadata } from 'next';

import { ClientDetailPage } from '@/features/clients';
import { routeCaseId } from '@/features/projects/model';

// The title never names the client: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Client · PSL Factory' };

export default async function Page({ params }: { params: Promise<{ clientId: string }> }) {
  const { clientId } = await params;
  return <ClientDetailPage clientId={routeCaseId(clientId)} />;
}
