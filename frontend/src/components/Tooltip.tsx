'use client';

// Tooltip (design/system/project/components/Tooltip): a small dark label for an icon button or an abbreviation,
// shown above it on hover and on keyboard focus after 300ms; Esc hides it. One short sentence, never the only
// place important information lives, never actions or links, never on touch-only controls. The trigger is
// described by it (aria-describedby).
import { cloneElement, useEffect, useId, useState, type ReactElement } from 'react';

export const TOOLTIP_DELAY_MS = 300;

type TriggerProps = { 'aria-describedby'?: string };

export function Tooltip({ text, children }: { text: string; children: ReactElement<TriggerProps> }) {
  const id = useId();
  const [want, setWant] = useState(false);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (!want) return undefined;
    const timer = setTimeout(() => setShown(true), TOOLTIP_DELAY_MS);
    return () => clearTimeout(timer);
  }, [want]);

  const hide = () => {
    setWant(false);
    setShown(false);
  };

  return (
    // Hover and focus only show a description; the trigger inside is the interactive element.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <span
      className="cmp-anchor cmp-anchor--inline"
      onMouseEnter={() => setWant(true)}
      onMouseLeave={hide}
      onFocus={() => setWant(true)}
      onBlur={hide}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && shown) hide();
      }}
    >
      {cloneElement(children, { 'aria-describedby': [children.props['aria-describedby'], id].filter(Boolean).join(' ') })}
      <span id={id} role="tooltip" className="psl-tip cmp-tip" hidden={!shown}>
        {text}
      </span>
    </span>
  );
}
