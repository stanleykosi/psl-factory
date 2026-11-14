import type { Metadata } from 'next';

import { DecideView } from '@/features/decide/DecideView';

// The title never names the item: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Decision · PSL Factory' };

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ task?: string | string[] }> };

export default async function DecidePage({ params, searchParams }: Props) {
  const { id } = await params;
  const { task } = await searchParams;
  return <DecideView id={id} taskId={Array.isArray(task) ? task[0] : task} />;
}
