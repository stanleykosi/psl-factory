import type { Metadata } from 'next';

import { ResponseView } from '@/features/response/ResponseView';

// The title never names the item: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Record a response · PSL Factory' };

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ task?: string | string[] }> };

export default async function RespondPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { task } = await searchParams;
  return <ResponseView id={id} taskId={Array.isArray(task) ? task[0] : task} />;
}
