'use client';

// Proof for one rule edit (setup-local until FE-M2A-PROOF or FE-M2B-RESPONSE builds the shared uploader).
// Enabled only when the row carries proof_case; the upload itself lives in SetRulePanel so it belongs to one edit.
import type { ChangeEvent } from 'react';

import { formatSize } from './format';
import { PaperclipIcon } from './icons';

export type ProofState =
  | { status: 'empty' }
  | { status: 'uploading'; filename: string }
  | { status: 'uploaded'; filename: string; size: number; evidenceId: string }
  | { status: 'failed'; message: string };

type Props = { id: string; enabled: boolean; state: ProofState; invalid: boolean; onPick: (file: File) => void };

export function ProofField({ id, enabled, state, invalid, onPick }: Props) {
  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) onPick(file);
  };
  const failed = state.status === 'failed';

  return (
    <div className="psl-field">
      <span className="psl-label" id={`${id}-label`}>
        Proof
      </span>
      {!enabled ? (
        <div className="psl-drop is-disabled setup-drop" aria-disabled="true">
          Proof can’t be attached here yet.
        </div>
      ) : (
        <label className={`psl-drop setup-drop${state.status === 'uploaded' ? ' setup-drop--file' : ''}${invalid ? ' is-error' : ''}`}>
          <input
            type="file"
            className="setup-sr"
            aria-labelledby={`${id}-label ${id}-text`}
            aria-invalid={invalid || undefined}
            aria-describedby={failed ? `${id}-error` : undefined}
            onChange={onChange}
          />
          <PaperclipIcon />
          {state.status === 'uploaded' ? (
            <span id={`${id}-text`}>
              <strong>{state.filename}</strong>
              <br />
              <span className="setup-drop__size">Uploaded · {formatSize(state.size)}</span>
            </span>
          ) : (
            <span id={`${id}-text`}>Choose a file</span>
          )}
        </label>
      )}
      {state.status === 'uploading' && (
        <p className="setup-help" role="status">
          Uploading {state.filename}…
        </p>
      )}
      {failed && (
        <p className="setup-help setup-help--error" id={`${id}-error`}>
          {state.message}
        </p>
      )}
    </div>
  );
}
