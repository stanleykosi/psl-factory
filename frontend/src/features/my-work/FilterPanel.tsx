'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';

import { CloseIcon } from './icons';
import { STATE_KEYS, STATES, type WorkState } from './model';

export type Filters = { line?: string; state?: WorkState };

type Props = {
  phone: boolean;
  lines: string[];
  applied: Filters;
  anchor: RefObject<HTMLElement | null>;
  onApply: (filters: Filters) => void;
  onClose: () => void;
};

/**
 * CMP-22 filter panel: a popover under the Filter button on desktop, a bottom sheet on phones.
 * It edits a draft; only "Show results" applies it. Esc, close or a click outside discards it.
 */
export function FilterPanel({ phone, lines, applied, anchor, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<Filters>(applied);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const first = panel.current?.querySelector<HTMLElement>('input:checked') ?? panel.current?.querySelector<HTMLElement>('input, select, button');
    first?.focus();
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

  const fields = (
    <>
      <fieldset className="my-work__fieldset">
        <legend className="psl-label">Line</legend>
        {[undefined, ...lines].map((line) => (
          <label key={line ?? ''} className="psl-radio">
            <input type="radio" name="my-work-line" checked={draft.line === line} onChange={() => setDraft({ ...draft, line })} />
            <span>{line ?? 'Any line'}</span>
          </label>
        ))}
      </fieldset>
      <div className="psl-field">
        <label className="psl-label" htmlFor="my-work-state">
          State
        </label>
        <select
          id="my-work-state"
          className="psl-input"
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
    </>
  );

  const clear = () => setDraft({});
  const apply = () => onApply(draft);

  if (phone) {
    return (
      <div className="psl-scrim my-work__scrim">
        <div ref={panel} className="psl-sheet my-work__sheet" role="dialog" aria-label="Filter">
          <div className="psl-sheet__grab" aria-hidden="true" />
          <div className="psl-sheet__head">
            <strong>Filter</strong>
            <button type="button" className="psl-iconbtn psl-iconbtn--bare" aria-label="Close" onClick={onClose}>
              <CloseIcon />
            </button>
          </div>
          <div className="psl-sheet__body">{fields}</div>
          <div className="psl-sheet__foot">
            <button type="button" className="psl-btn psl-btn--dark psl-btn--xl psl-btn--block" onClick={apply}>
              Show results
            </button>
            <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block" onClick={clear}>
              Clear
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
          Show results
        </button>
      </div>
    </div>
  );
}
