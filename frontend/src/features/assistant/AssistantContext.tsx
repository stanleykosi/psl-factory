'use client';

import { createContext, useContext } from 'react';

import type { Me } from '@/api/types';

import type { useConversationList } from './useConversationList';
import type { AgentName } from './types';

export type AssistantContextValue = {
  me: Me;
  /** E-ME `assistant_agents`, in the order returned; nothing else decides who may be talked to. */
  agents: AgentName[];
  list: ReturnType<typeof useConversationList>;
  /** Opens the list as a sheet (phones). */
  showList: () => void;
};

export const AssistantContext = createContext<AssistantContextValue | null>(null);

export function useAssistant(): AssistantContextValue {
  const value = useContext(AssistantContext);
  if (!value) throw new Error('useAssistant is only available inside AssistantFrame');
  return value;
}
