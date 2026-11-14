'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';

import { api, call } from '@/api/client';

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
  anchor: RefObject<HTMLElement | null>;
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
export function FilterPanel({ phone, lines, applied, anchor, preview, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<Filters>(applied);
  const [allLines, setAllLines] = useState(false);
  const [count, setCount] = useState<Preview>();
  const projects = useProjects();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panel.current?.querySelector<HTMLElement>('input, select, button')?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    const onPointer = (event: MouseEvent) => {
      const target = event.target as Node;
      if (panel.current?.contains(target) || anchor.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onPointer);
    };
  }, [anchor, onClose]);

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
          <label key={line.key} className="psl-check my-work__check">
            <input type="checkbox" checked={draft.line === line.key} onChange={(e) => setDraft({ ...draft, line: e.target.checked ? line.key : undefined })} />
            <span>{line.title}</span>
          </label>
        ))}
        {shownLines.length < lines.length && (
          <button type="button" className="psl-link my-work__linkbutton" onClick={() => setAllLines(true)}>
            {phone ? `All ${lines.length} lines` : `Show all ${lines.length} lines`}
          </button>
        )}
      </fieldset>
      <div className="my-work__field">
        <span className="my-work__label" id="my-work-project-label">
          Project
        </span>
        <select
          aria-labelledby="my-work-project-label"
          className="psl-input my-work__select"
          value={draft.project ?? ''}
          onChange={(e) => setDraft({ ...draft, project: e.target.value || undefined })}
        >
          <option value="">Any project</option>
          {[...appliedProject, ...projects].map((p) => (
            <option key={p.case_id} value={p.case_id}>
              {p.title}
            </option>
          ))}
        </select>
      </div>
      <div className="my-work__field">
        <span className="my-work__label" id="my-work-state-label">
          State
        </span>
        <select
          id="my-work-state"
          aria-labelledby="my-work-state-label"
          className="psl-input my-work__select"
          value={draft.state ?? ''}
          onChange={(e) => setDraft({ ...draft, state: (e.target.value || undefined) as WorkState | undefined })}
        >
          <option value="">Any state</option>
          {STATE_KEYS.map((key) => (
            <option key={key} value={key}>
              {STATES[key].words}
            </option>
          ))}
        </select>
      </div>
      <div className="my-work__field">
        <span className="my-work__label" id="my-work-waiting-label">
          Waiting on
        </span>
        <select
          aria-labelledby="my-work-waiting-label"
          className="psl-input my-work__select"
          value={draft.waiting ?? ''}
          onChange={(e) => setDraft({ ...draft, waiting: (e.target.value || undefined) as WaitingOn | undefined })}
        >
          <option value="">Anyone</option>
          {WAITING_KEYS.map((key) => (
            <option key={key} value={key}>
              {WAITING_ON[key]}
            </option>
          ))}
        </select>
      </div>
    </>
  );

  const clear = () => setDraft({});
  const apply = () => onApply(draft);
  const showLabel = count ? `Show ${count.count}${count.more ? '+' : ''} ${count.count === 1 && !count.more ? 'item' : 'items'}` : 'Show results';

  if (phone) {
    return (
      <div className="psl-scrim my-work__scrim">
        <div ref={panel} className="psl-sheet my-work__sheet" role="dialog" aria-label="Filter">
          <div className="psl-sheet__head">
            <strong className="my-work__sheettitle">Filter</strong>
            <button type="button" className="psl-link my-work__linkbutton" onClick={clear}>
              Clear
            </button>
          </div>
          <div className="psl-sheet__body my-work__sheetbody">{fields}</div>
          <div className="psl-sheet__foot">
            <button type="button" className="psl-btn psl-btn--dark psl-btn--xl psl-btn--block" onClick={apply}>
              {showLabel}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={panel} className="psl-pop my-work__pop" role="dialog" aria-label="Filter">
      <div className="my-work__pophead">Filter</div>
      <div className="my-work__popbody">{fields}</div>
      <div className="my-work__popfoot">
        <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block" onClick={clear}>
          Clear
        </button>
        <button type="button" className="psl-btn psl-btn--dark psl-btn--lg psl-btn--block" onClick={apply}>
          {showLabel}
        </button>
      </div>
    </div>
  );
}
