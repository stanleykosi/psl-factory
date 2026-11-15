'use client';

import { useState } from 'react';

import { FilterPanel, RadioGroup } from '@/components';

import { KIND_TAGS, KINDS } from './labels';
import type { ExceptionKind } from './types';

const ANYTHING = '';

/**
 * CMP-22 filter panel for SCR-10, as on My work: the shared FilterPanel (a popover under Filter on desktop, a bottom
 * sheet on phones). One choice, what happened. It edits a draft; only "Show results" applies it. Esc, close or a
 * click outside discards it.
 */
export function ExceptionsFilter({ applied, onApply, onClose }: { applied?: ExceptionKind; onApply: (what: ExceptionKind | undefined) => void; onClose: () => void }) {
  const [draft, setDraft] = useState<ExceptionKind | undefined>(applied);
  return (
    <FilterPanel applyLabel="Show results" onApply={() => onApply(draft)} onClear={() => setDraft(undefined)} onClose={onClose}>
      <RadioGroup
        legend="What happened"
        name="exc-what"
        value={draft ?? ANYTHING}
        onChange={(value) => setDraft(value === ANYTHING ? undefined : (value as ExceptionKind))}
        options={[{ value: ANYTHING, label: 'Anything' }, ...KINDS.map((what) => ({ value: what, label: KIND_TAGS[what].words }))]}
      />
    </FilterPanel>
  );
}
