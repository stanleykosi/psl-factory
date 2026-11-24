'use client';

// F-85: the shared evidence picker, on FileUpload (D-171). It uploads into the given case only and hands back the `upload_id`.
// Not used by any page yet (F-87 wires it); a failed upload is never retried by itself, only by Try again.
import { useState } from 'react';

import { FileUpload, type FileState } from '@/components';

import { uploadCaseFile, uploadErrorMessage, type UploadedFile } from './evidence';

type Props = {
  caseId: string;
  value: UploadedFile | null;
  onChange(file: UploadedFile | null): void;
  disabledReason?: string;
  /** F-78: a narrower list of accepted extensions than the default proof types (the zone refuses the rest before any request). */
  accept?: string[];
  /** F-78: the zone's label; default "Evidence file". */
  label?: string;
  /** F-78: the words for a failed upload; default `uploadErrorMessage`. */
  describeError?: (error: unknown) => string;
};

export function EvidencePicker({ caseId, value, onChange, disabledReason, accept, label = 'Evidence file', describeError = uploadErrorMessage }: Props) {
  const [busy, setBusy] = useState<{ file: File } | null>(null);
  const [failed, setFailed] = useState<{ file: File; message: string } | null>(null);

  async function send(file: File) {
    setFailed(null);
    setBusy({ file });
    try {
      onChange(await uploadCaseFile(caseId, file));
    } catch (error) {
      setFailed({ file, message: describeError(error) });
    } finally {
      setBusy(null);
    }
  }

  const state: FileState = busy
    ? { status: 'uploading', name: busy.file.name }
    : failed
      ? { status: 'error', name: failed.file.name, message: failed.message }
      : value
        ? { status: 'uploaded', name: value.name, size: value.size }
        : { status: 'empty' };

  return (
    <FileUpload
      label={label}
      accept={accept}
      state={state}
      pending={busy !== null}
      disabledReason={disabledReason}
      onFile={(file) => void send(file)}
      onRetry={() => failed && void send(failed.file)}
      onRemove={() => {
        setFailed(null);
        onChange(null);
      }}
    />
  );
}
