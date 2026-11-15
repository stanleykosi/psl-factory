'use client';

// The upload panel under one template (inline, not a modal). It holds the chosen file and note; the view sends them
// and closes the panel on every outcome except a 422, which keeps the entries and marks the named fields.
import { useId, useState, type KeyboardEvent } from 'react';

import { WarningIcon } from '@/shell/icons';

import type { FieldProblem } from './api';
import { formatSize } from './format';

export const NOTE_LIMIT = 2000;
export type Invalid = { message: string; fields: FieldProblem[] };

type Props = {
  name: string;
  busy: boolean;
  /** The list could not be re-read after an unconfirmed upload, so nothing more is sent until it has been. */
  locked: boolean;
  onSend: (file: File, note: string) => Promise<Invalid | null>;
  onCancel: () => void;
};

const noteLength = (note: string) => Array.from(note).length;

export function TemplateUploadPanel({ name, busy, locked, onSend, onCancel }: Props) {
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState('');
  const [invalid, setInvalid] = useState<Invalid | null>(null);

  const problem = (...names: string[]) => invalid?.fields.find((f) => names.includes(f.name));
  const fileProblem = problem('filename', 'content_base64');
  const noteProblem = problem('note');
  const empty = file !== null && file.size === 0;
  const over = noteLength(note) > NOTE_LIMIT;
  const fileError = empty ? 'That file is empty. Choose another file.' : fileProblem?.message;
  const noteError = over ? `The note can be up to ${NOTE_LIMIT} characters.` : noteProblem?.message;

  const send = async () => {
    if (!file || empty || over || busy || locked) return;
    setInvalid(await onSend(file, note));
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && !busy) onCancel();
  };

  return (
    // Escape closes the panel from any control inside it.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <section className="setup-upload" aria-labelledby={`${id}-head`} onKeyDown={onKeyDown}>
      <h2 className="setup-upload__head" id={`${id}-head`}>
        Upload a version of {name}
      </h2>
      {invalid && (
        <div className="psl-callout psl-callout--problem" role="alert">
          <WarningIcon />
          <span>{invalid.message}</span>
        </div>
      )}
      <div className="psl-field">
        <label className="psl-label" htmlFor={`${id}-file`}>
          File
        </label>
        <input
          id={`${id}-file`}
          type="file"
          className={`psl-input setup-fileinput${fileError ? ' is-error' : ''}`}
          disabled={busy}
          aria-invalid={fileError ? true : undefined}
          aria-describedby={fileError ? `${id}-file-msg` : file ? `${id}-file-info` : undefined}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setInvalid(null);
          }}
        />
        {file && !fileError && (
          <p className="setup-help" id={`${id}-file-info`}>
            {file.name} · {formatSize(file.size)}
          </p>
        )}
        {fileError && (
          <p className="setup-help setup-help--error" id={`${id}-file-msg`}>
            {fileError}
          </p>
        )}
      </div>
      <div className="psl-field">
        <label className="psl-label" htmlFor={`${id}-note`}>
          Note (optional)
        </label>
        <textarea
          id={`${id}-note`}
          className={`psl-input psl-input--area${noteError ? ' is-error' : ''}`}
          value={note}
          disabled={busy}
          aria-invalid={noteError ? true : undefined}
          aria-describedby={`${id}-count${noteError ? ` ${id}-note-msg` : ''}`}
          onChange={(e) => {
            setNote(e.target.value);
            setInvalid((i) => (i ? { ...i, fields: i.fields.filter((f) => f.name !== 'note') } : i));
          }}
        />
        <span className={`psl-count${over ? ' is-over' : ''}`} id={`${id}-count`}>
          {noteLength(note)} / {NOTE_LIMIT}
        </span>
        {noteError && (
          <p className="setup-help setup-help--error" id={`${id}-note-msg`}>
            {noteError}
          </p>
        )}
      </div>
      <div className="setup-upload__actions">
        <button type="button" className="psl-btn" disabled={busy || locked || !file || empty || over} onClick={() => void send()}>
          {busy ? 'Uploading…' : 'Upload version'}
        </button>
        <button type="button" className="psl-btn psl-btn--secondary" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </section>
  );
}
