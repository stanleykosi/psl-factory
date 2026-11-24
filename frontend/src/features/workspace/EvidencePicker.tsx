'use client';

// F-85: the shared evidence picker, on FileUpload (D-171). It uploads into the given case only and hands back the `upload_id`.
// Not used by any page yet (F-87 wires it); a failed upload is never retried by itself, only by Try again.
import { useState } from 'react';

import { FileUpload, type FileState } from '@/components';

import { uploadCaseFile, uploadErrorMessage, type UploadedFile } from './evidence';

type Props = { caseId: string; value: UploadedFile | null; onChange(file: UploadedFile | null): void; disabledReason?: string };

export function EvidencePicker({ caseId, value, onChange, disabledReason }: Props) {
  const [busy, setBusy] = useState<{ file: File } | null>(null);
  const [failed, setFailed] = useState<{ file: File; message: string } | null>(null);

  async function send(file: File) {
    setFailed(null);
    setBusy({ file });
    try {
      onChange(await uploadCaseFile(caseId, file));
    } catch (error) {
      setFailed({ file, message: uploadErrorMessage(error) });
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
      label="Evidence file"
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
