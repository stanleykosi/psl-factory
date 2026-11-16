// Assistant types, derived from the contract (E-CONVERSATIONS, E-CONVERSATION, E-CONVERSATION-NEW, E-MESSAGE, E-MENTION-OPTIONS).
import type { paths } from '@/api/schema';

type Json<T> = T extends { content: { 'application/json': infer B } } ? B : never;

export type ConversationList = Json<paths['/api/v1/assistant/conversations']['get']['responses'][200]>;
export type ConversationRow = ConversationList['items'][number];
export type Conversation = Json<paths['/api/v1/assistant/conversations/{conversation_id}']['get']['responses'][200]>;
export type Message = Conversation['messages'][number];
export type Draft = NonNullable<Message['draft']>;
export type NewConversation = Json<paths['/api/v1/assistant/conversations']['post']['responses'][200]>;
export type MessageBody = paths['/api/v1/assistant/conversations/{conversation_id}/messages']['post']['requestBody']['content']['application/json'];
export type MessageResult = Json<paths['/api/v1/assistant/conversations/{conversation_id}/messages']['post']['responses'][200]>;
export type MentionOptions = Json<paths['/api/v1/assistant/mentions']['get']['responses'][200]>;
export type MentionOption = MentionOptions['items'][number];
export type AgentName = NonNullable<ConversationRow['agent']>;
