'use client';

// The upload panel under one template (inline, not a modal). It holds the chosen file and note; the view sends them
// and closes the panel on every outcome except a 422, which keeps the entries and marks the named fields.
import { useId, useState, type KeyboardEvent } from 'react';

import { Button, Callout, FileUpload, formatSize, TextArea } from '@/components';

import type { FieldProblem } from './api';

export const NOTE_LIMIT = 2000;
export type Invalid = { message: string; fields: FieldProblem[] };

/** What a template can be uploaded as; the server still checks the file. */
const TEMPLATE_TYPES = ['.docx', '.xlsx', '.pdf'];

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
      {invalid && <Callout kind="problem">{invalid.message}</Callout>}
      <FileUpload
        label="File"
        prompt="Drop the template here or"
        accept={TEMPLATE_TYPES}
        state={{ status: 'empty' }}
        error={fileError}
        onFile={(chosen) => {
          setFile(chosen);
          setInvalid(null);
        }}
        onRemove={() => {
          setFile(null);
          setInvalid(null);
        }}
      />
      {file && !fileError && <p className="setup-help">{file.name} · {formatSize(file.size)}</p>}
      <TextArea
        label="Note"
        optional
        value={note}
        disabled={busy}
        error={noteError}
        hint={`${noteLength(note)} / ${NOTE_LIMIT}`}
        onChange={(e) => {
          setNote(e.target.value);
          setInvalid((i) => (i ? { ...i, fields: i.fields.filter((f) => f.name !== 'note') } : i));
        }}
      />
      <div className="setup-upload__actions">
        <Button busy={busy} busyLabel="Uploading…" disabled={locked || !file || empty || over} onClick={() => void send()}>
          Upload version
        </Button>
        <Button kind="secondary" disabled={busy} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </section>
  );
}
