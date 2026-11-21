'use client';

// Composer (design/system/project/components/ChatMessage, "Composer"): a text box with Send, the focus ring on the
// whole box. Enter sends and Shift+Enter adds a line. Picked mentions show as chips with a remove button above the
// text. The paperclip ("Attach images", D-161) opens the image chooser; each chosen image is a thumbnail with a remove
// button, a busy state while it uploads and its own error line (the caller uploads; this only draws and reports). The "Speak your request" button is drawn on wide
// screens as held (aria-disabled, "Not available yet", no handler): D-SPEECH-INPUT is open, so nothing here listens to
// a microphone. `toolbar` is the start of the tool row (the "@ Mention" control).
import { useId, useRef, type ReactNode } from 'react';

import { Icon } from './Icon';
import { cx, usePhone } from './internal';
import { Tooltip } from './Tooltip';
import { VisuallyHidden } from './VisuallyHidden';

export type ComposerChip = { id: string; label: string };
export type ComposerImage = { id: string; name: string; /** What the thumbnail shows (a local preview). */ src: string; state: 'uploading' | 'ready' | 'error'; /** The server's words, for `error`. */ error?: string };

export function Composer({ agentName, value, onChange, onSend, canSend, busy = false, placeholder, error, chips = [], onRemoveChip, toolbar, heldMic = false, images, onAttach, onRemoveImage, className }: {
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
  /** The chosen images, in order. */
  images?: ComposerImage[];
  /** Draws the paperclip; called with the files the person chose (images only, several allowed). */
  onAttach?: (files: File[]) => void;
  onRemoveImage?: (id: string) => void;
  className?: string;
}) {
  const phone = usePhone();
  const errorId = useId();
  const inputId = useId();
  const picker = useRef<HTMLInputElement>(null);
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
        {images && images.length > 0 && (
          <ul className="cmp-composer__images" aria-label="Images">
            {images.map((image) => (
              <li key={image.id} className={cx('cmp-composer__image', `cmp-composer__image--${image.state}`)} aria-busy={image.state === 'uploading' || undefined}>
                <span className="cmp-composer__thumb">
                  {/* eslint-disable-next-line @next/next/no-img-element -- a local preview of the chosen file (blob: URL) */}
                  <img src={image.src} alt={image.name} />
                  {image.state === 'uploading' && (
                    <span className="psl-busy cmp-composer__uploading" role="status" aria-label={`Uploading ${image.name}`}>
                      <i />
                      <i />
                      <i />
                    </span>
                  )}
                  <button type="button" className="cmp-composer__remove" aria-label={`Remove ${image.name}`} onClick={() => onRemoveImage?.(image.id)}>
                    <span aria-hidden="true">×</span>
                  </button>
                </span>
                {image.state === 'error' && (
                  <span className="psl-error cmp-composer__imgerr" role="alert">
                    {image.error}
                  </span>
                )}
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
            {onAttach && (
              <>
                <button type="button" className="psl-iconbtn cmp-composer__attach" aria-label="Attach images" onClick={() => picker.current?.click()}>
                  <svg className="psl-icon" aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                    <path d="M16 9l-6.5 6.5a3.5 3.5 0 0 1-5-5L11 4a2.3 2.3 0 0 1 3.3 3.3L7.8 13.8a1.2 1.2 0 0 1-1.7-1.7L12 6.2" />
                  </svg>
                </button>
                {/* accept="image/*" lets phones offer the camera as well as the photo library */}
                <input
                  ref={picker}
                  type="file"
                  accept="image/*"
                  multiple
                  hidden
                  tabIndex={-1}
                  data-cmp-attach=""
                  onChange={(event) => {
                    const files = Array.from(event.target.files ?? []);
                    event.target.value = '';
                    if (files.length > 0) onAttach(files);
                  }}
                />
              </>
            )}
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
              ) : phone ? (
                <Icon name="send" />
              ) : (
                <svg className="psl-icon" aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square">
                  <path d="M10 16V4M4 10l6-6 6 6" />
                </svg>
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
