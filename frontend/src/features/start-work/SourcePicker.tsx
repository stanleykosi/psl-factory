'use client';

// A line's source record, from `GET /projects/{case_id}/intake-sources`, on RecordPicker. Built for the lines after the
// weekly report (F-88): no weekly control renders it. `id` is the integer the line sends; `before` pages with
// `next_before`. `onRevision` gives the freshest case revision each answer carries.
import { useCallback, useId } from 'react';

import { RecordPicker, type OptionSource } from './RecordPicker';
import type { Field, LineOption } from './types';
import { fetchSources } from './useStartWork';

type Props = {
  caseId: string;
  lineKey: string;
  /** The source field's name as the line names it (`field` in the request); omitted when the line has one source. */
  field?: string;
  label: string;
  parentId?: number;
  value: { id: number; label: string } | undefined;
  onChange: (source: { id: number; label: string } | undefined) => void;
  onRevision?: (caseRevision: number) => void;
  disabled: boolean;
  error?: string;
};

export function SourcePicker({ caseId, lineKey, field, label, parentId, value, onChange, onRevision, disabled, error }: Props) {
  const labelId = `${useId()}-label`;
  const source = useCallback<OptionSource>(
    async (q, cursor) => {
      const page = await fetchSources(caseId, lineKey, { field, parentId, before: cursor ? Number.parseInt(cursor, 10) : undefined });
      onRevision?.(page.caseRevision);
      const needle = q.trim().toLowerCase();
      const items = page.items.filter((item) => item.label.toLowerCase().includes(needle)).map((item) => ({ value: String(item.id), label: item.label }));
      return { items, next_cursor: page.nextBefore === null ? undefined : String(page.nextBefore) };
    },
    [caseId, field, lineKey, onRevision, parentId],
  );
  const shape = { name: field ?? 'source', label, type: 'record', required: true } as Field;
  return (
    <div className="psl-field sw-field" data-field={shape.name}>
      <span className="psl-label" id={labelId}>
        {label}
      </span>
      <RecordPicker
        lineKey={lineKey}
        field={shape}
        parent={undefined}
        value={value ? ({ value: String(value.id), label: value.label } as LineOption) : undefined}
        onChange={(option) => {
          const one = option && !Array.isArray(option) && 'value' in option ? option : undefined;
          onChange(one ? { id: Number.parseInt(one.value, 10), label: one.label } : undefined);
        }}
        disabled={disabled}
        labelId={labelId}
        describedBy={undefined}
        invalid={error !== undefined}
        source={source}
      />
      {error && <span className="psl-error">{error}</span>}
    </div>
  );
}
