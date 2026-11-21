'use client';

// "@ Mention a project or record": a search popover over E-MENTION-OPTIONS. No request until the person has typed at
// least one character and paused; only returned items can be chosen. A mention is a pointer the backend re-checks.
import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';

import { Button, Loading, SampleLabel, SearchField, SEARCH_PAUSE_MS, useIsPhone, useKeepInView } from '@/components';

import { fetchMentions } from './api';
import { MENTION_FAILED, NOTHING_TO_MENTION } from './labels';
import type { MentionOption } from './types';

type Found = { status: 'idle' } | { status: 'loading' } | { status: 'ready'; items: MentionOption[] } | { status: 'error' };

export function MentionPicker({ onPick }: { onPick: (option: MentionOption) => void }) {
  const phone = useIsPhone();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [found, setFound] = useState<Found>({ status: 'idle' });
  const button = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  useKeepInView(pop, open);
  const popId = useId();
  const query = q.trim();

  useEffect(() => {
    if (!open || query === '') return undefined;
    const abort = new AbortController();
    const timer = setTimeout(() => {
      setFound({ status: 'loading' });
      fetchMentions(query, abort.signal)
        .then((page) => setFound({ status: 'ready', items: page.items }))
        .catch(() => {
          if (!abort.signal.aborted) setFound({ status: 'error' });
        });
    }, SEARCH_PAUSE_MS);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [open, query]);

  // Focus goes to the search box on opening; Esc closes and returns focus to the button.
  useEffect(() => {
    if (!open) return undefined;
    pop.current?.querySelector('input')?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      setOpen(false);
      setQ('');
      setFound({ status: 'idle' });
      button.current?.focus();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const close = () => {
    setOpen(false);
    setQ('');
    setFound({ status: 'idle' });
    button.current?.focus();
  };
  // Up and Down move between the search box and the options, Enter on the box picks the first (the Menu pattern).
  function keys(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (!['ArrowDown', 'ArrowUp', 'Enter'].includes(event.key)) return;
    const box = pop.current?.querySelector('input');
    const items = Array.from(pop.current?.querySelectorAll<HTMLElement>('.as-mention__item') ?? []);
    if (!box || items.length === 0) return;
    const at = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === 'Enter') {
      if (at >= 0 || document.activeElement !== box) return;
      items[0].click();
    } else if (event.key === 'ArrowDown') (items[at + 1] ?? items[0]).focus();
    else if (at <= 0) box.focus();
    else items[at - 1].focus();
    event.preventDefault();
  }
  const shown = query === '' ? { status: 'idle' as const } : found;

  return (
    <span className="cmp-anchor as-mention">
      <Button ref={button} kind="bare" className="as-tool" aria-expanded={open} aria-controls={open ? popId : undefined} onClick={() => (open ? close() : setOpen(true))}>
        {phone ? '@ Mention' : '@ Mention a project or record'}
      </Button>
      {open && (
        // Keys are handled once for the popover; each option is focusable.
        // eslint-disable-next-line jsx-a11y/no-static-element-interactions
        <div ref={pop} id={popId} className="psl-pop cmp-pop cmp-pop--up as-mention__pop" onKeyDown={keys}>
          <SearchField label="Search projects and records" placeholder="Search projects and records" value={q} onChange={setQ} />
          <div aria-live="polite">
            {shown.status === 'loading' && <Loading>Loading…</Loading>}
            {shown.status === 'error' && <p className="psl-hint as-mention__note">{MENTION_FAILED}</p>}
            {shown.status === 'ready' && shown.items.length === 0 && <p className="psl-hint as-mention__note">{NOTHING_TO_MENTION}</p>}
            {shown.status === 'ready' && shown.items.length > 0 && (
              <ul className="as-mention__list">
                {shown.items.map((item) => (
                  <li key={`${item.kind}:${item.id}`}>
                    <Button
                      kind="bare"
                      className="psl-menuitem as-mention__item"
                      onClick={() => {
                        onPick(item);
                        close();
                      }}
                    >
                      <strong>{item.label}</strong>
                      {(item.hint || item.sample) && (
                        <small>
                          {item.hint} {item.sample && <SampleLabel />}
                        </small>
                      )}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </span>
  );
}
