'use client';

// The shared upload for a line that takes a file: F-85's EvidencePicker (which sends with uploadCaseFile), into the chosen project's case only. It hands back
// the `upload_id` (not an evidence id). It is disabled until a project is chosen and starts empty again when the project
// changes (the picker is keyed by the case). No line registered today sets `takesUpload`, so the weekly form has none.
import { EvidencePicker } from '@/features/workspace/EvidencePicker';
import type { UploadedFile } from '@/features/workspace/evidence';

type Props = {
  caseId: string | null;
  value: UploadedFile | null;
  onChange: (uploadId: number | null, file: UploadedFile | null) => void;
  disabledReason?: string;
};

export const CHOOSE_PROJECT_FIRST = 'Choose a project first.';

export function StartUpload({ caseId, value, onChange, disabledReason }: Props) {
  return (
    <EvidencePicker
      key={caseId ?? 'none'}
      caseId={caseId ?? ''}
      value={caseId ? value : null}
      onChange={(file) => onChange(file ? file.upload_id : null, file)}
      disabledReason={caseId ? disabledReason : (disabledReason ?? CHOOSE_PROJECT_FIRST)}
    />
  );
}
