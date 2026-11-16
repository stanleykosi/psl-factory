'use client';

// Composer (design/system/project/components/ChatMessage, "Composer"): a text box with Send, the focus ring on the
// whole box. Enter sends and Shift+Enter adds a line. It sends text and mentions only: no attach button. Picked
// mentions show as chips with a remove button above the text. The "Speak your request" button is drawn on wide
// screens as held (aria-disabled, "Not available yet", no handler): D-SPEECH-INPUT is open, so nothing here listens to
// a microphone. `toolbar` is the start of the tool row (the "@ Mention" control).
import { useId, type ReactNode } from 'react';

import { Icon } from './Icon';
import { cx, usePhone } from './internal';
import { Tooltip } from './Tooltip';
import { VisuallyHidden } from './VisuallyHidden';

export type ComposerChip = { id: string; label: string };

export function Composer({ agentName, value, onChange, onSend, canSend, busy = false, placeholder, error, chips = [], onRemoveChip, toolbar, heldMic = false, className }: {
  /** Names the box for screen readers: "Message Tola". */
  agentName: string;
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  /** False while the text is blank or too long; Enter and Send then do nothing. */
  canSend: boolean;
  /** A send is in flight: the button shows the busy squares and presses are ignored. */
  busy?: boolean;
  placeholder?: string;
  /** Shown under the box in a role="alert" (a 422, the length limit). */
  error?: ReactNode;
  chips?: ComposerChip[];
  onRemoveChip?: (id: string) => void;
  toolbar?: ReactNode;
  /** Draw the held microphone (wide screens only). */
  heldMic?: boolean;
  className?: string;
}) {
  const phone = usePhone();
  const errorId = useId();
  const inputId = useId();
  const send = () => {
    if (canSend && !busy) onSend();
  };
  return (
    <form
      className={cx('cmp-composer', className)}
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <div className="cmp-composer__box">
        {chips.length > 0 && (
          <ul className="cmp-composer__chips" aria-label="Mentions">
            {chips.map((chip) => (
              <li key={chip.id} className="cmp-composer__chip">
                {chip.label}
                <button type="button" className="cmp-composer__remove" aria-label={`Remove ${chip.label}`} onClick={() => onRemoveChip?.(chip.id)}>
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <VisuallyHidden>
          <label htmlFor={inputId}>Message {agentName}</label>
        </VisuallyHidden>
        <textarea
          id={inputId}
          className="cmp-composer__input"
          rows={2}
          value={value}
          placeholder={placeholder}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
            event.preventDefault();
            send();
          }}
        />
        <div className="cmp-composer__tools">
          {toolbar}
          <span className="cmp-composer__end">
            {heldMic && !phone && (
              <Tooltip text="Not available yet">
                <button type="button" className="psl-iconbtn cmp-composer__mic" aria-label="Speak your request" aria-disabled="true">
                  <svg className="psl-icon" aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                    <rect x="7" y="2" width="6" height="10" />
                    <path d="M4 9v1a6 6 0 0 0 12 0V9M10 16v3" />
                  </svg>
                </button>
              </Tooltip>
            )}
            <button type="submit" className="cmp-composer__send" aria-label="Send" aria-disabled={!canSend || busy || undefined} aria-busy={busy || undefined}>
              {busy ? (
                <span className="psl-busy" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
              ) : (
                <Icon name="send" />
              )}
            </button>
          </span>
        </div>
      </div>
      {error && (
        <p className="psl-error" id={errorId} role="alert">
          <Icon name="warn" />
          <span>{error}</span>
        </p>
      )}
    </form>
  );
}
