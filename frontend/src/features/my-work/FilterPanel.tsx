'use client';

import { useEffect, useState } from 'react';

import { api, call } from '@/api/client';
import { Checkbox, FilterPanel as Panel, Select } from '@/components';

import { STATE_KEYS, STATES, WAITING_KEYS, WAITING_ON, type LineOption, type WaitingOn, type WorkState } from './model';

export type Filters = { line?: string; project?: string; state?: WorkState; waiting?: WaitingOn };
export type Preview = { count: number; more: boolean };
export type Project = { case_id: string; title: string };

const LINES_SHOWN = 4;
const PREVIEW_DEBOUNCE_MS = 250;

type Props = {
  phone: boolean;
  lines: LineOption[];
  applied: Filters;
  preview: (filters: Filters) => Promise<Preview>;
  onApply: (filters: Filters) => void;
  onClose: () => void;
};

/** Projects for the Project filter (E-PROJECTS). Until they load, or if they cannot, only "Any project" is offered. */
function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  useEffect(() => {
    let live = true;
    call(api.GET('/api/v1/projects', { params: { query: { limit: 50 } } })).then(
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
 * CMP-22 filter panel (SCR-01-*-filter): a popover under the Filter button on desktop, a bottom sheet on
 * phones. Line, Project, State and Waiting on edit a draft; "Show N items" applies it, where N comes from the
 * same list request with the draft. Esc or a click outside discards it.
 */
export function MyWorkFilter({ phone, lines, applied, preview, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<Filters>(applied);
  const [allLines, setAllLines] = useState(false);
  const [count, setCount] = useState<Preview>();
  const projects = useProjects();

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
        <legend className="psl-label">Line</legend>
        {shownLines.map((line) => (
          <Checkbox
            key={line.key}
            label={line.title}
            checked={draft.line === line.key}
            onChange={(e) => setDraft({ ...draft, line: e.target.checked ? line.key : undefined })}
          />
        ))}
        {shownLines.length < lines.length && (
          <button type="button" className="psl-link cmp-linkbutton cmp-linkbutton--small" onClick={() => setAllLines(true)}>
            {phone ? `All ${lines.length} lines` : `Show all ${lines.length} lines`}
          </button>
        )}
      </fieldset>
      {/* A project list is a record picker: Select has no search box yet (review-components.md), so the native list stays. */}
      <div className="psl-field">
        <label className="psl-label" htmlFor="my-work-project">
          Project
        </label>
        <select id="my-work-project" className="psl-input my-work__select" value={draft.project ?? ''} onChange={(e) => setDraft({ ...draft, project: e.target.value || undefined })}>
          <option value="">Any project</option>
          {[...appliedProject, ...projects].map((p) => (
            <option key={p.case_id} value={p.case_id}>
              {p.title}
            </option>
          ))}
        </select>
      </div>
      <Select
        label="State"
        placeholder="Any state"
        value={draft.state ?? ''}
        onChange={(value) => setDraft({ ...draft, state: (value || undefined) as WorkState | undefined })}
        options={[{ value: '', label: 'Any state' }, ...STATE_KEYS.map((key) => ({ value: key, label: STATES[key].words }))]}
      />
      <Select
        label="Waiting on"
        placeholder="Anyone"
        value={draft.waiting ?? ''}
        onChange={(value) => setDraft({ ...draft, waiting: (value || undefined) as WaitingOn | undefined })}
        options={[{ value: '', label: 'Anyone' }, ...WAITING_KEYS.map((key) => ({ value: key, label: WAITING_ON[key] }))]}
      />
    </>
  );

  const showLabel = count ? `Show ${count.count}${count.more ? '+' : ''} ${count.count === 1 && !count.more ? 'item' : 'items'}` : 'Show results';

  return (
    <Panel applyLabel={showLabel} onApply={() => onApply(draft)} onClear={() => setDraft({})} onClose={onClose}>
      {fields}
    </Panel>
  );
}
