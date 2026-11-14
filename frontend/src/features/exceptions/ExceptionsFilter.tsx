'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';

import { CloseIcon } from '@/features/my-work/icons';

import { KIND_TAGS, KINDS } from './labels';
import type { ExceptionKind } from './types';

type Props = {
  phone: boolean;
  applied?: ExceptionKind;
  anchor: RefObject<HTMLElement | null>;
  onApply: (what: ExceptionKind | undefined) => void;
  onClose: () => void;
};

/**
 * CMP-22 filter panel for SCR-10, as on My work: a popover under Filter on desktop, a bottom sheet on phones.
 * One choice, what happened. It edits a draft; only "Show results" applies it. Esc, close or a click outside discards it.
 */
export function ExceptionsFilter({ phone, applied, anchor, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<ExceptionKind | undefined>(applied);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panel.current?.querySelector<HTMLElement>('input:checked')?.focus();
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
    <fieldset className="exc-fieldset">
      <legend className="psl-label">What happened</legend>
      {[undefined, ...KINDS].map((what) => (
        <label key={what ?? ''} className="psl-radio">
          <input type="radio" name="exc-what" checked={draft === what} onChange={() => setDraft(what)} />
          <span>{what ? KIND_TAGS[what].words : 'Anything'}</span>
        </label>
      ))}
    </fieldset>
  );
  const clear = () => setDraft(undefined);
  const apply = () => onApply(draft);

  if (phone) {
    return (
      <div className="psl-scrim exc-scrim">
        <div ref={panel} className="psl-sheet exc-sheet" role="dialog" aria-label="Filter">
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
    <div ref={panel} className="psl-pop exc-pop" role="dialog" aria-label="Filter">
      <div className="exc-pophead">Filter</div>
      <div className="exc-popbody">{fields}</div>
      <div className="exc-popfoot">
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
