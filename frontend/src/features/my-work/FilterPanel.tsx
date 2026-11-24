'use client';

import { useEffect, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { Button, Checkbox, FilterPanel, Select, useIsPhone } from '@/components';

import type { LineKey, WorkLine, WorkState } from '@/features/work-list';

import { STATE_KEYS, stateWords } from './model';

export type Filters = { line?: LineKey; project?: string; state?: WorkState };
/** The server's exact count for the draft, or none when it could not give one. */
export type Preview = { count: number } | undefined;
export type Project = { case_id: string; title: string };

const LINES_SHOWN = 4;
const PREVIEW_DEBOUNCE_MS = 250;

type Props = {
  lines: WorkLine[];
  projects: Project[];
  applied: Filters;
  preview: (filters: Filters) => Promise<Preview>;
  onApply: (filters: Filters) => void;
  onClose: () => void;
};

/** Projects for the Project filter (GET /api/v1/projects, first page). Until they load, or if they cannot, only "Any project" is offered. */
export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  useEffect(() => {
    let live = true;
    call(liveApi.GET('/api/v1/projects', { params: { query: {} } })).then(
      (data) => live && setProjects(data.items.map(({ case_id, title }) => ({ case_id, title }))),
      () => {},
    );
    return () => {
      live = false;
    };
  }, []);
  return projects;
}

/**
 * CMP-22 filter panel (SCR-01-*-filter), the shared FilterPanel: a popover under the Filter button on desktop, a
 * bottom sheet on phones. Line, Project and State edit a draft; "Show N items" applies it, where N comes from a
 * one-page preview of the same list with the draft, and only when the server marks that count complete. Esc or a click outside discards it.
 */
export function MyWorkFilter({ lines, projects, applied, preview, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<Filters>(applied);
  const [allLines, setAllLines] = useState(false);
  const [count, setCount] = useState<Preview>();
  const phone = useIsPhone();

  // "Show N items": counts the draft with one list request, a moment after the last change.
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      preview(draft).then(
        (result) => live && setCount(result),
        () => live && setCount(undefined),
      );
    }, PREVIEW_DEBOUNCE_MS);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [draft, preview]);

  // The contract takes one line key, so checking a line replaces the one checked before.
  const shownLines = allLines || lines.length <= LINES_SHOWN ? lines : lines.slice(0, LINES_SHOWN);
  const appliedProject = applied.project && !projects.some((p) => p.case_id === applied.project) ? [{ case_id: applied.project, title: applied.project }] : [];

  const fields = (
    <>
      <fieldset className="my-work__fieldset">
        <legend className="my-work__label">Line</legend>
        {shownLines.map((line) => (
          <Checkbox key={line.key} className="my-work__check" label={line.title} checked={draft.line === line.key} onChange={(e) => setDraft({ ...draft, line: e.target.checked ? (line.key as LineKey) : undefined })} />
        ))}
        {shownLines.length < lines.length && (
          <Button kind="link" className="my-work__linkbutton cmp-target" onClick={() => setAllLines(true)}>
            {phone ? `All ${lines.length} lines` : `Show all ${lines.length} lines`}
          </Button>
        )}
      </fieldset>
      <Select
        label="Project"
        fieldClassName="my-work__field"
        placeholder="Any project"
        value={draft.project ?? ''}
        onChange={(value) => setDraft({ ...draft, project: value || undefined })}
        options={[{ value: '', label: 'Any project' }, ...[...appliedProject, ...projects].map((p) => ({ value: p.case_id, label: p.title }))]}
      />
      <Select
        label="State"
        fieldClassName="my-work__field"
        placeholder="Any state"
        value={draft.state ?? ''}
        onChange={(value) => setDraft({ ...draft, state: (value || undefined) as WorkState | undefined })}
        options={[{ value: '', label: 'Any state' }, ...STATE_KEYS.map((key) => ({ value: key, label: stateWords(key) }))]}
      />
    </>
  );

  const clear = () => setDraft({});
  const apply = () => onApply(draft);
  const showLabel = count ? `Show ${count.count} ${count.count === 1 ? 'item' : 'items'}` : 'Show results';

  return (
    <FilterPanel applyLabel={showLabel} onApply={apply} onClear={clear} onClose={onClose}>
      {fields}
    </FilterPanel>
  );
}
