'use client';

// SCR-04 first field: the projects a line can start on, from `GET /lines/projects`. The list UI is RecordPicker's;
// only its data source is replaced. A "Sample" project carries the tag. The chosen row's case and revision are the
// start's. The search waits 250 ms and is sent only when it is not empty; the next page appends while `next_page` is set.
import { useCallback, useId, useRef } from 'react';

import { RecordPicker, type OptionSource } from './RecordPicker';
import type { Field, LineOption, Project } from './types';
import { fetchProjects } from './useStartWork';

export const NO_PROJECTS = 'No projects to start this on.';

const FIELD = { name: 'project', label: 'Project', type: 'record', required: true, placeholder: 'Choose a project' } as Field;

const toOption = (p: Project): LineOption => ({
  value: p.case_id,
  label: p.title,
  case_id: p.case_id,
  case_revision: p.case_revision,
  sample: p.sample,
  ...(p.sample ? { hint: 'Sample' } : {}),
});

type Props = { lineKey: string; value: Project | null; onChange: (project: Project) => void; disabled: boolean; error: string | undefined };

export function ProjectPicker({ lineKey, value, onChange, disabled, error }: Props) {
  const id = useId();
  const labelId = `${id}-label`;
  const errorId = `${id}-error`;
  // The projects last listed, so the chosen option maps back to the whole project (title and revision as read).
  const seen = useRef(new Map<string, Project>());
  const source = useCallback<OptionSource>(
    async (q, cursor) => {
      const page = await fetchProjects(lineKey, q, cursor ? Number.parseInt(cursor, 10) : undefined);
      for (const p of page.items) seen.current.set(p.case_id, p);
      return { items: page.items.map(toOption), next_cursor: page.next_page === null ? undefined : String(page.next_page) };
    },
    [lineKey],
  );
  return (
    <div className="psl-field sw-field" data-field="project" id="sw-field-project" tabIndex={-1}>
      <span className="psl-label" id={labelId}>
        Project
      </span>
      <RecordPicker
        lineKey={lineKey}
        field={FIELD}
        parent={undefined}
        value={value ? toOption(value) : undefined}
        onChange={(option) => {
          const chosen = option && !Array.isArray(option) && 'value' in option ? seen.current.get(option.value) : undefined;
          if (chosen) onChange(chosen);
        }}
        disabled={disabled}
        labelId={labelId}
        describedBy={error ? errorId : undefined}
        invalid={error !== undefined}
        source={source}
        emptyText={NO_PROJECTS}
      />
      {error && (
        <span className="psl-error" id={errorId}>
          {error}
        </span>
      )}
    </div>
  );
}
