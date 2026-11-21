// The message the person just sent (D-160), kept in the frame so it survives the move from the home to the new thread.
// It is shown at once, under "Sending…", until the server's own copy is read; the send button stays busy until the
// agent has replied. Nothing here is sent: useSend writes, the thread page reads and clears it.
import { WORKING_STEP } from './labels';
import type { AgentName, Conversation, Message, ThreadConversation } from './types';
import type { SentImage } from './useSend';

export type Pending = {
  agent: AgentName;
  /** Known once the conversation exists (the thread at once; the home after E-CONVERSATION-NEW). */
  conversationId?: string;
  text: string;
  chips: string[];
  images: SentImage[];
  at: string;
  /** How many of the person's messages the thread showed before this one: the server has it when there are more. */
  base: number;
  /** `sending`: the write is not confirmed. `waiting`: it is, and the agent has not replied. */
  phase: 'sending' | 'waiting';
};

export const personMessages = (conversation: Pick<Conversation, 'messages'>) => conversation.messages.filter((m) => m.role === 'person').length;

/** True when the server's copy has the message and the agent is no longer working on it. */
export const replied = (pending: Pending, conversation: Conversation) => personMessages(conversation) > pending.base && conversation.status !== 'working';

/** The conversation as the person sees it: the server's, plus their message and a working step until the server has it. */
export function withPending(conversation: ThreadConversation, pending: Pending | undefined): ThreadConversation {
  if (!pending || personMessages(conversation) > pending.base) return conversation;
  const person: Message = {
    role: 'person', text: pending.text, steps: [], sources: [], at: pending.at,
    local: { chips: pending.chips, sending: pending.phase === 'sending', images: pending.images.map(({ id, name, src }) => ({ id, name, src })) },
  };
  const agent: Message = {
    role: 'agent', text: '', steps: [WORKING_STEP], sources: [], at: pending.at,
    step_details: [{ text: WORKING_STEP, state: 'now' }],
  };
  return { ...conversation, status: 'working', messages: [...conversation.messages, person, agent] };
}

/** A conversation that is not read yet: only what the person sent. */
export function startedConversation(id: string, pending: Pending): ThreadConversation {
  return withPending({ conversation_id: id, agent: pending.agent, title: pending.text.replace(/\s+/g, ' ').slice(0, 60) || 'New request', status: 'answered', messages: [] } as ThreadConversation, pending);
}

