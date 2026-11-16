'use client';

import { useState } from 'react';

import { Checkbox, FilterPanel, RadioGroup } from '@/components';

import type { AlertAgent } from './types';
import { AGENTS, agentName } from './model';

export type AlertFilters = { agent?: AlertAgent; unread?: true };

type Props = {
  applied: AlertFilters;
  unreadCount: number | undefined;
  onApply: (filters: AlertFilters) => void;
  onClose: () => void;
};

/**
 * CMP-22 filter panel for alerts: the v7 facets only (agent, unread). It edits a draft; only "Show results"
 * applies it. Esc, close or a click outside discards it.
 */
export function AlertsFilterPanel({ applied, unreadCount, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<AlertFilters>(applied);
  return (
    <FilterPanel applyLabel="Show results" onApply={() => onApply(draft)} onClear={() => setDraft({})} onClose={onClose}>
      <RadioGroup
        legend="Agent"
        name="alerts-agent"
        options={['', ...AGENTS].map((agent) => ({ value: agent, label: agent ? agentName(agent) : 'Any agent' }))}
        value={draft.agent ?? ''}
        onChange={(agent) => setDraft({ ...draft, agent: (agent || undefined) as AlertAgent | undefined })}
      />
      <Checkbox
        label="Unread only"
        detail={unreadCount !== undefined ? `${unreadCount} unread` : undefined}
        checked={Boolean(draft.unread)}
        onChange={(e) => setDraft({ ...draft, unread: e.target.checked ? true : undefined })}
      />
    </FilterPanel>
  );
}
