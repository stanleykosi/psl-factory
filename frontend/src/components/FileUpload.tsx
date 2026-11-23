'use client';

// FileUpload (design/system/project/components/FileUpload): the one file field across the platform (signed SOW,
// client email, bank statement, templates). Drop or choose a file; the consumer uploads it at once and passes the
// state back. The zone says what is accepted; a file of the wrong type or over the size limit is refused here, with
// Try again, before any upload (no `accept` list or `maxBytes: null`: the consumer's service is the only rule).
// One file (`state`), or a list of rows (`files`) with the zone shrinking to one line once a file is in, where
// `multiple`. Row states: uploading (progress, Cancel), uploaded (Remove), error (orange edge, Try again),
// restricted (the proof exists but this person cannot open it). On a phone the zone offers a photo or a file (the
// input has no `capture`). `error` marks the zone; `disabledReason` closes it.
import { useId, useRef, useState, type ChangeEvent, type DragEvent, type ReactNode } from 'react';

import { Button } from './Button';
import { FieldLabel } from './Field';
import { Icon } from './Icon';
import { cx, usePhone } from './internal';

export const PROOF_TYPES = ['.pdf', '.png', '.jpg', '.jpeg', '.eml'];
export const PROOF_MAX_BYTES = 10 * 1024 * 1024;

export type FileState =
  | { status: 'empty' }
  | { status: 'uploading'; name: string; loaded?: number; total?: number }
  | { status: 'uploaded'; name: string; size: number }
  /** `retry: false`: the file cannot be sent again as it is, so no Try again. `remove`: the row offers Remove too, for a file that must go before another can be added. */
  | { status: 'error'; name: string; message: string; retry?: boolean; remove?: boolean }
  | { status: 'restricted'; name: string; note: string };

export type FileRowState = Exclude<FileState, { status: 'empty' }> & { key?: string | number };

/** "420 KB", "3.4 MB"; a size that is not known is said so, never 0. */
export function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes)) return 'Size unknown';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** "1.2 of 3.4 MB": both figures in the total's unit. */
function progressText(loaded: number, total: number): string {
  const [unit, size] = total < 1024 * 1024 ? ['KB', 1024] : ['MB', 1024 * 1024];
  const show = (n: number) => (unit === 'MB' ? (n / size).toFixed(1) : String(Math.round(n / size)));
  return `${show(loaded)} of ${show(total)} ${unit}`;
}

/** "10 MB": the limit as the zone says it. */
function limitText(bytes: number): string {
  return `up to ${formatSize(bytes).replace('.0 ', ' ')}`;
}

function typeLabel(types: string[]): string {
  const names = [...new Set(types.map((t) => (t === '.jpeg' ? 'JPG' : t.replace('.', '').toUpperCase())))];
  return names.length > 1 ? `${names.slice(0, -1).join(', ')} or ${names[names.length - 1]}` : names[0];
}

type Props = {
  label: ReactNode;
  /** The label is for assistive technology only (the screen's own layout already names the field). */
  hideLabel?: boolean;
  /** One file: its state. */
  state?: FileState;
  /** Several files: a row each. Wins over `state`. */
  files?: FileRowState[];
  /** More than one file is allowed: the zone shrinks to "Add another file or drop it here" once a file is in. */
  multiple?: boolean;
  /** The consumer is busy with an upload: the chooser waits. */
  pending?: boolean;
  /** A file that passed the type and size checks: start the upload. */
  onFile: (file: File) => void;
  onRemove: (key?: string | number) => void;
  onCancel?: (key?: string | number) => void;
  /** Send the same file again; without it, Try again clears the row and opens the chooser. */
  onRetry?: (key?: string | number) => void;
  /** Accepted extensions; none: anything (the consumer's service refuses what it cannot use). */
  accept?: string[];
  /** None: no limit here. */
  maxBytes?: number | null;
  /** The first words of the zone ("Drop a file here or"); the link that follows is "choose a file". */
  prompt?: string;
  /** What the zone says it accepts, where `accept` is not listed ("Proof can’t be uploaded for this item."). */
  hint?: ReactNode;
  /** The zone's error ("Proof is needed to record a signature."). */
  error?: ReactNode;
  /** Uploads are closed, and why ("The record is verified."). */
  disabledReason?: string;
  className?: string;
};

export function FileUpload({ label, hideLabel, state, files, multiple, pending, onFile, onRemove, onCancel, onRetry, accept = PROOF_TYPES, maxBytes = PROOF_MAX_BYTES, prompt = 'Drop a file here or', hint, error, disabledReason, className }: Props) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const phone = usePhone();
  const [over, setOver] = useState(false);
  const [refused, setRefused] = useState<{ name: string; message: string } | null>(null);
  const kinds = accept.length > 0 ? typeLabel(accept) : undefined;
  const limit = maxBytes ? limitText(maxBytes) : undefined;
  const accepts = [kinds, limit].filter(Boolean).join(' · ');

  function take(file: File | undefined) {
    if (!file) return;
    const lower = file.name.toLowerCase();
    if (accept.length > 0 && !accept.some((t) => lower.endsWith(t))) {
      setRefused({ name: file.name, message: `${file.name.split('.').pop()?.toUpperCase() ?? 'This'} files can’t be used as proof` });
      return;
    }
    if (maxBytes && file.size > maxBytes) {
      setRefused({ name: file.name, message: `Too large: ${formatSize(file.size)}, ${limit}` });
      return;
    }
    setRefused(null);
    onFile(file);
  }

  const given: FileRowState[] = files ?? (state && state.status !== 'empty' ? [state] : []);
  const rows: FileRowState[] = refused ? [...(multiple ? given : []), { status: 'error', key: 'refused', ...refused }] : given;
  const showZone = multiple || rows.length === 0;
  const compact = multiple && rows.length > 0;
  const hintId = `${id}-hint`;
  const describedBy = [accepts && !compact ? `${id}-kinds` : '', hint ? hintId : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined;
  const chooser = (
    <input
      ref={input}
      type="file"
      className="cmp-sr"
      accept={accept.length > 0 ? accept.join(',') : undefined}
      disabled={pending}
      aria-labelledby={showZone ? `${id}-label ${id}-zone` : undefined}
      aria-label={showZone ? undefined : 'Choose a file'}
      aria-hidden={showZone ? undefined : true}
      tabIndex={showZone ? undefined : -1}
      aria-describedby={showZone ? describedBy : undefined}
      aria-invalid={showZone && error ? true : undefined}
      onChange={(event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        take(file);
      }}
    />
  );
  const retry = (key?: string | number) => {
    if (key === 'refused') setRefused(null);
    else if (onRetry) onRetry(key);
    else onRemove(key);
    if (key === 'refused' || !onRetry) input.current?.click();
  };
  const remove = (key?: string | number) => {
    if (key === 'refused') setRefused(null);
    else onRemove(key);
  };

  const zone = disabledReason ? (
    <div className="psl-drop is-disabled" aria-disabled="true">
      <Icon name="upload" />
      <strong>Uploads are closed</strong>
      <small>{disabledReason}</small>
    </div>
  ) : (
    <label
      className={cx('psl-drop cmp-drop', compact && 'psl-drop--compact', over && 'is-over', error && 'is-error')}
      onDragOver={(event: DragEvent) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event: DragEvent) => {
        event.preventDefault();
        setOver(false);
        if (!pending) take(event.dataTransfer.files[0]);
      }}
    >
      {chooser}
      <Icon name={phone && !compact ? 'camera' : 'upload'} />
      <strong id={`${id}-zone`}>
        {over ? (
          'Drop to upload'
        ) : compact ? (
          <>
            <span className="psl-link">Add another file</span> or drop it here
          </>
        ) : (
          <>
            {phone ? 'Take a photo or' : prompt} <span className="psl-link">choose a file</span>
          </>
        )}
      </strong>
      {error ? (
        <small id={`${id}-error`} className="cmp-drop__error">
          {error}
        </small>
      ) : null}
      {accepts && !compact && <small id={`${id}-kinds`}>{accepts}</small>}
    </label>
  );

  return (
    <div className={cx('psl-field', className)} role="group" aria-labelledby={`${id}-label`}>
      <FieldLabel id={`${id}-label`} label={label} hidden={hideLabel} />
      {rows.length > 0 && (
        <div className="psl-files">
          {rows.map((row, i) => (
            <FileRow key={row.key ?? i} state={row} onRemove={() => remove(row.key)} onCancel={onCancel && (() => onCancel(row.key))} onRetry={() => retry(row.key)} />
          ))}
        </div>
      )}
      {showZone ? zone : !disabledReason && chooser}
      {hint && (
        <span id={hintId} className="psl-hint">
          {hint}
        </span>
      )}
    </div>
  );
}

function FileRow({ state, onRemove, onCancel, onRetry }: { state: FileRowState; onRemove: () => void; onCancel?: () => void; onRetry: () => void }) {
  if (state.status === 'restricted') {
    return (
      <div className="psl-file cmp-file--restricted">
        <Icon name="lock" />
        <span className="psl-file__name">
          <strong>{state.name}</strong>
          <small>{state.note}</small>
        </span>
      </div>
    );
  }
  const progress =
    state.status === 'uploading' && state.total ? Math.round(((state.loaded ?? 0) / state.total) * 100) : undefined;
  return (
    <div className={cx('psl-file', state.status === 'error' && 'is-error')}>
      <Icon name={state.status === 'error' ? 'warn' : 'clip'} />
      <span className="psl-file__name">
        <strong>{state.name}</strong>
        <small role="status">
          {state.status === 'uploading' &&
            (state.total ? `Uploading · ${progressText(state.loaded ?? 0, state.total)}` : 'Uploading…')}
          {state.status === 'uploaded' && `Uploaded · ${formatSize(state.size)}`}
          {state.status === 'error' && state.message}
        </small>
        {progress !== undefined && (
          <span className="psl-progress cmp-progress" role="progressbar" aria-label={`Uploading ${state.name}`} aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <i style={{ width: `${progress}%` }} />
          </span>
        )}
      </span>
      {state.status === 'uploading' && onCancel && (
        <Button kind="text" aria-label={`Cancel upload of ${state.name}`} onClick={onCancel}>
          Cancel
        </Button>
      )}
      {(state.status === 'uploaded' || (state.status === 'error' && state.remove)) && (
        <Button kind="text" aria-label={`Remove ${state.name}`} onClick={onRemove}>
          Remove
        </Button>
      )}
      {state.status === 'error' && state.retry !== false && (
        <Button kind="text" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
