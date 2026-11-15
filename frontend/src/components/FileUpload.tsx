'use client';

// FileUpload (design/system/project/components/FileUpload): the one proof and file field (signed SOW, client email,
// bank statement). Drop or choose a file; the consumer uploads it at once and passes the state back. The zone
// says what is accepted; a file of the wrong type or over the size limit is refused here, with Try again, before
// any upload. File row states: uploading (progress in mono, Cancel), uploaded (Remove), error (Try again),
// restricted (the proof exists but this person cannot open it). Proof is required where the factory needs it:
// the record button explains when it is missing; `error` marks the zone.
import { useId, useRef, useState, type ChangeEvent, type DragEvent, type ReactNode } from 'react';

import { Button } from './Button';
import { FieldLabel } from './Field';
import { Icon } from './Icon';
import { IconButton } from './IconButton';
import { cx } from './internal';

export const PROOF_TYPES = ['.pdf', '.png', '.jpg', '.jpeg', '.eml'];
export const PROOF_MAX_BYTES = 10 * 1024 * 1024;

export type FileState =
  | { status: 'empty' }
  | { status: 'uploading'; name: string; loaded?: number; total?: number }
  | { status: 'uploaded'; name: string; size: number }
  | { status: 'error'; name: string; message: string }
  | { status: 'restricted'; name: string; note: string };

/** "420 KB", "3.4 MB". */
export function formatSize(bytes: number): string {
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

function typeLabel(types: string[]): string {
  const names = [...new Set(types.map((t) => (t === '.jpeg' ? 'JPG' : t.replace('.', '').toUpperCase())))];
  return names.length > 1 ? `${names.slice(0, -1).join(', ')} or ${names[names.length - 1]}` : names[0];
}

export function FileUpload({ label, state, onFile, onRemove, onCancel, accept = PROOF_TYPES, maxBytes = PROOF_MAX_BYTES, prompt = 'Drop the proof here or', error, disabledReason, className }: {
  label: ReactNode;
  state: FileState;
  /** A file that passed the type and size checks: start the upload. */
  onFile: (file: File) => void;
  onRemove: () => void;
  onCancel?: () => void;
  accept?: string[];
  maxBytes?: number;
  prompt?: string;
  /** The zone's error ("Proof is needed to record a signature."). */
  error?: ReactNode;
  /** Uploads are closed, and why ("The record is verified."). */
  disabledReason?: string;
  className?: string;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [refused, setRefused] = useState<{ name: string; message: string } | null>(null);
  const kinds = typeLabel(accept);
  const limit = `up to ${formatSize(maxBytes)}`;

  function take(file: File | undefined) {
    if (!file) return;
    const lower = file.name.toLowerCase();
    if (!accept.some((t) => lower.endsWith(t))) {
      setRefused({ name: file.name, message: `${file.name.split('.').pop()?.toUpperCase() ?? 'This'} files can’t be used as proof` });
      return;
    }
    if (file.size > maxBytes) {
      setRefused({ name: file.name, message: `Too large: ${formatSize(file.size)}, ${limit}` });
      return;
    }
    setRefused(null);
    onFile(file);
  }

  const shownState: FileState = refused ? { status: 'error', ...refused } : state;
  const retry = () => {
    setRefused(null);
    if (state.status === 'error') onRemove();
    input.current?.click();
  };

  const zone = disabledReason ? (
    <div className="psl-drop is-disabled" aria-disabled="true">
      <Icon name="upload" />
      <strong>Uploads are closed</strong>
      <small>{disabledReason}</small>
    </div>
  ) : (
    <label
      className={cx('psl-drop cmp-drop', over && 'is-over', error && 'is-error')}
      onDragOver={(event: DragEvent) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event: DragEvent) => {
        event.preventDefault();
        setOver(false);
        take(event.dataTransfer.files[0]);
      }}
    >
      <input
        ref={input}
        type="file"
        className="cmp-sr"
        accept={accept.join(',')}
        aria-labelledby={`${id}-label ${id}-zone`}
        aria-describedby={`${id}-kinds${error ? ` ${id}-error` : ''}`}
        aria-invalid={error ? true : undefined}
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          const file = event.target.files?.[0];
          event.target.value = '';
          take(file);
        }}
      />
      <Icon name="upload" />
      <strong id={`${id}-zone`}>
        {over ? (
          'Drop to upload'
        ) : (
          <>
            {prompt} <span className="psl-link">choose a file</span>
          </>
        )}
      </strong>
      {error ? (
        <small id={`${id}-error`} className="cmp-drop__error">
          {error}
        </small>
      ) : null}
      <small id={`${id}-kinds`}>
        {kinds} · {limit}
      </small>
    </label>
  );

  return (
    <div className={cx('psl-field', className)}>
      <FieldLabel id={`${id}-label`} label={label} />
      {shownState.status === 'empty' ? zone : <FileRow state={shownState} onRemove={onRemove} onCancel={onCancel} onRetry={retry} />}
      {/* The chooser stays mounted for Try again while a row shows. */}
      {shownState.status !== 'empty' && !disabledReason && (
        <input
          ref={input}
          type="file"
          className="cmp-sr"
          tabIndex={-1}
          aria-hidden="true"
          accept={accept.join(',')}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            take(file);
          }}
        />
      )}
    </div>
  );
}

function FileRow({ state, onRemove, onCancel, onRetry }: { state: Exclude<FileState, { status: 'empty' }>; onRemove: () => void; onCancel?: () => void; onRetry: () => void }) {
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
      <Icon name="clip" />
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
      {state.status === 'uploading' && onCancel && <IconButton bare icon="close" label="Cancel upload" onClick={onCancel} />}
      {state.status === 'uploaded' && (
        <Button kind="text" onClick={onRemove}>
          Remove
        </Button>
      )}
      {state.status === 'error' && (
        <Button kind="text" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
