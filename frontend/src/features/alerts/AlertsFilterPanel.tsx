'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';

import { CloseIcon } from '@/features/my-work/icons';

import type { AlertAgent } from './types';
import { AGENTS, agentName } from './model';

export type AlertFilters = { agent?: AlertAgent; unread?: true };

type Props = {
  phone: boolean;
  applied: AlertFilters;
  unreadCount: number | undefined;
  anchor: RefObject<HTMLElement | null>;
  onApply: (filters: AlertFilters) => void;
  onClose: () => void;
};

/**
 * CMP-22 filter panel for alerts: the v7 facets only (agent, unread). A popover under the Filter button on
 * desktop, a bottom sheet on phones. It edits a draft; only "Show results" applies it. Esc, close or a click
 * outside discards it.
 */
export function AlertsFilterPanel({ phone, applied, unreadCount, anchor, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<AlertFilters>(applied);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const first = panel.current?.querySelector<HTMLElement>('input:checked') ?? panel.current?.querySelector<HTMLElement>('input, button');
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
      <fieldset className="alerts-fieldset">
        <legend className="psl-label">Agent</legend>
        {[undefined, ...AGENTS].map((agent) => (
          <label key={agent ?? ''} className="psl-radio">
            <input type="radio" name="alerts-agent" checked={draft.agent === agent} onChange={() => setDraft({ ...draft, agent })} />
            <span>{agent ? agentName(agent) : 'Any agent'}</span>
          </label>
        ))}
      </fieldset>
      <label className="psl-check">
        <input
          type="checkbox"
          checked={Boolean(draft.unread)}
          onChange={(e) => setDraft({ ...draft, unread: e.target.checked ? true : undefined })}
        />
        <span>
          Unread only
          {unreadCount !== undefined && <span className="alerts-hint"> {unreadCount} unread</span>}
        </span>
      </label>
    </>
  );

  const clear = () => setDraft({});
  const apply = () => onApply(draft);

  if (phone) {
    return (
      <div className="psl-scrim alerts-scrim">
        <div ref={panel} className="psl-sheet alerts-sheet" role="dialog" aria-label="Filter">
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
    <div ref={panel} className="psl-pop alerts-pop" role="dialog" aria-label="Filter">
      <div className="alerts-pophead">Filter</div>
      <div className="alerts-popbody">{fields}</div>
      <div className="alerts-popfoot">
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
