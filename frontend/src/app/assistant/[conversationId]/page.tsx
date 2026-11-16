import type { Metadata } from 'next';

import { ThreadPage } from '@/features/assistant/ThreadPage';

// The title never names the conversation: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Assistant · PSL Factory' };

export default async function ConversationPage({ params }: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await params;
  return <ThreadPage key={conversationId} id={conversationId} />;
}
