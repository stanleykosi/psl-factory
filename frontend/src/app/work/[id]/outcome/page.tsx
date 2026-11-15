import type { Metadata } from 'next';

import { OutcomeView } from '@/features/rfp/OutcomeView';

// The title never names the item: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Record the outcome · PSL Factory' };

type Props = { params: Promise<{ id: string }> };

export default async function OutcomePage({ params }: Props) {
  const { id } = await params;
  return <OutcomeView id={id} />;
}
