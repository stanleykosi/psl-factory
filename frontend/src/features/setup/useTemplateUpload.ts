'use client';

// One E-TEMPLATE-VERSION at a time. Nothing resends: every outcome except a 422 re-reads the list once and hands the
// result to the panel, which decides what the person sees. A network or server error is an uncertain effect: the list
// is read once to see whether the upload went through.
import { useCallback, useRef, useState } from 'react';

import { ApiError } from '@/api/errors';

import { uploadTemplateVersion, type FieldProblem, type TemplateUploadBody, type TemplateUploadResult, type TemplatesPage, type UploadError } from './api';
import { fileToBase64 } from './format';
import { asApiError } from './useSetupRules';

export type UploadOutcome =
  | { kind: 'uploaded'; result: TemplateUploadResult; page: TemplatesPage | ApiError }
  /** 409, 403 or 404: the message, and the list as re-read. */
  | { kind: 'rejected'; error: ApiError; page: TemplatesPage | ApiError }
  | { kind: 'invalid'; message: string; fields: FieldProblem[] }
  | { kind: 'signed_out'; error: ApiError }
  /** Uncertain effect, list re-read. */
  | { kind: 'unconfirmed'; page: TemplatesPage }
  /** Uncertain effect and the re-read failed too. */
  | { kind: 'unchecked' };

export type UploadInput = { revision: number; file: File; note: string };

export function useTemplateUpload(refresh: () => Promise<TemplatesPage | ApiError>) {
  // Checked synchronously so a double click cannot send two uploads.
  const writing = useRef(false);
  const [busy, setBusy] = useState(false);

  const upload = useCallback(
    async (templateId: string, input: UploadInput, onChecking: () => void): Promise<UploadOutcome | null> => {
      if (writing.current) return null;
      writing.current = true;
      setBusy(true);
      try {
        let content: string;
        try {
          content = await fileToBase64(input.file);
        } catch {
          const message = 'We couldn’t read that file. Choose it again.';
          return { kind: 'invalid', message, fields: [{ name: 'filename', message }] };
        }
        // expected_revision goes as read (0 included); a blank note is left out.
        const body: TemplateUploadBody = { expected_revision: input.revision, filename: input.file.name, content_base64: content };
        if (input.note.trim() !== '') body.note = input.note.trim();
        const result = await uploadTemplateVersion(templateId, body);
        return { kind: 'uploaded', result, page: await refresh() };
      } catch (error) {
        const apiError = asApiError(error);
        if (apiError.kind === 'unauthenticated') return { kind: 'signed_out', error: apiError };
        if (apiError.kind === 'invalid') return { kind: 'invalid', message: apiError.message, fields: (apiError as UploadError).fields ?? [] };
        if (apiError.kind === 'stale' || apiError.kind === 'forbidden' || apiError.kind === 'not_found') {
          return { kind: 'rejected', error: apiError, page: await refresh() };
        }
        onChecking();
        const page = await refresh();
        return page instanceof ApiError ? { kind: 'unchecked' } : { kind: 'unconfirmed', page };
      } finally {
        writing.current = false;
        setBusy(false);
      }
    },
    [refresh],
  );

  return { busy, upload };
}
