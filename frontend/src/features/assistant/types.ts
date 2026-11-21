// Assistant types, derived from the contract (E-CONVERSATIONS, E-CONVERSATION, E-CONVERSATION-NEW, E-MESSAGE, E-MENTION-OPTIONS).
import type { paths } from '@/api/schema';

type Json<T> = T extends { content: { 'application/json': infer B } } ? B : never;

export type ConversationList = Json<paths['/api/v1/assistant/conversations']['get']['responses'][200]>;
export type ConversationRow = ConversationList['items'][number];
export type Conversation = Json<paths['/api/v1/assistant/conversations/{conversation_id}']['get']['responses'][200]>;
/** An image sent with a message (PROPOSAL D-161, G-SCR05-ATTACH: not in the v7 contract yet). */
export type Attachment = { file_id: string; name: string; size: number; content_type: string };
/** What the thread shows of a message that is not on the server yet (D-160): its chips, "Sending…", and local previews. */
export type LocalMessage = { chips: string[]; sending: boolean; images: { id: string; name: string; src: string }[] };
export type Message = Conversation['messages'][number] & { attachments?: Attachment[]; local?: LocalMessage };
export type ThreadConversation = Omit<Conversation, 'messages'> & { messages: Message[] };
export type Draft = NonNullable<Message['draft']>;
export type NewConversation = Json<paths['/api/v1/assistant/conversations']['post']['responses'][200]>;
type ContractMessageBody = paths['/api/v1/assistant/conversations/{conversation_id}/messages']['post']['requestBody']['content']['application/json'];
/** The contract's body, plus the proposed `attachments` (D-161); `text` may be empty when there are attachments. */
export type MessageBody = ContractMessageBody & { attachments?: { file_id: string }[] };
export type MessageResult = Json<paths['/api/v1/assistant/conversations/{conversation_id}/messages']['post']['responses'][200]>;
export type MentionOptions = Json<paths['/api/v1/assistant/mentions']['get']['responses'][200]>;
export type MentionOption = MentionOptions['items'][number];
export type AgentName = NonNullable<ConversationRow['agent']>;
