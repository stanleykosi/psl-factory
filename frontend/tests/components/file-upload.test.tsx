// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { FileUpload, formatSize, type FileState } from '@/components';

import { violations } from './a11y';

const file = (name: string, size: number) => new File([new Uint8Array(size)], name);

function Proof({ onFile, error }: { onFile: (f: File) => void; error?: string }) {
  const [state, setState] = useState<FileState>({ status: 'empty' });
  return (
    <FileUpload
      label="Proof"
      state={state}
      error={error}
      onFile={(f) => {
        onFile(f);
        setState({ status: 'uploaded', name: f.name, size: f.size });
      }}
      onRemove={() => setState({ status: 'empty' })}
    />
  );
}

describe('FileUpload', () => {
  it('the zone says what is accepted; a wrong type or a file over 10 MB is refused before upload, with Try again', async () => {
    const onFile = vi.fn();
    render(<Proof onFile={onFile} />);
    expect(screen.getByText('PDF, PNG, JPG or EML · up to 10.0 MB')).toBeTruthy();
    const input = screen.getByLabelText(/Proof/) as HTMLInputElement;
    expect(input.type).toBe('file');
    expect(await violations()).toEqual([]);
    fireEvent.change(input, { target: { files: [file('site-photos.zip', 10)] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByText('ZIP files can’t be used as proof').closest('.psl-file')?.className).toBe('psl-file is-error');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(screen.getByLabelText(/Proof/)).toBeTruthy();
  });

  it('a good file goes to onFile and shows as uploaded with Remove', async () => {
    const onFile = vi.fn();
    render(<Proof onFile={onFile} />);
    fireEvent.change(screen.getByLabelText(/Proof/), { target: { files: [file('client-signature.PDF', 430080)] } });
    expect(onFile).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Uploaded · 420 KB')).toBeTruthy();
    expect(await violations()).toEqual([]);
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    expect(screen.getByText(/choose a file/)).toBeTruthy();
  });

  it('drag over turns the zone blue; drop takes the file', () => {
    const onFile = vi.fn();
    render(<Proof onFile={onFile} />);
    const zone = screen.getByText(/choose a file/).closest('.psl-drop') as HTMLElement;
    fireEvent.dragOver(zone);
    expect(zone.className).toContain('is-over');
    expect(screen.getByText('Drop to upload')).toBeTruthy();
    fireEvent.drop(zone, { dataTransfer: { files: [file('a.eml', 5)] } });
    expect(onFile).toHaveBeenCalled();
  });

  it('uploading, restricted, error zone and disabled states', async () => {
    const { rerender } = render(<FileUpload label="Proof" state={{ status: 'uploading', name: 'bank.pdf', loaded: 1.2 * 1048576, total: 3.4 * 1048576 }} onFile={() => {}} onRemove={() => {}} onCancel={() => {}} />);
    expect(screen.getByText('Uploading · 1.2 of 3.4 MB')).toBeTruthy();
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('35');
    expect(screen.getByRole('button', { name: 'Cancel upload' })).toBeTruthy();
    expect(await violations()).toEqual([]);
    rerender(<FileUpload label="Proof" state={{ status: 'restricted', name: 'Payroll approval', note: 'Proof attached · HR only' }} onFile={() => {}} onRemove={() => {}} />);
    expect(screen.getByText('Payroll approval').closest('.psl-file')?.className).toBe('psl-file cmp-file--restricted');
    expect(screen.queryByRole('button')).toBeNull();
    rerender(<FileUpload label="Proof" state={{ status: 'empty' }} error="Proof is needed to record a signature." onFile={() => {}} onRemove={() => {}} />);
    expect(screen.getByText(/choose a file/).closest('.psl-drop')?.className).toContain('is-error');
    expect(screen.getByLabelText(/Proof/).getAttribute('aria-invalid')).toBe('true');
    rerender(<FileUpload label="Proof" state={{ status: 'empty' }} disabledReason="The record is verified." onFile={() => {}} onRemove={() => {}} />);
    expect(screen.getByText('Uploads are closed').closest('.psl-drop')?.className).toBe('psl-drop is-disabled');
    expect(await violations()).toEqual([]);
  });

  it('formats sizes', () => {
    expect(formatSize(500)).toBe('500 B');
    expect(formatSize(20480)).toBe('20 KB');
    expect(formatSize(3565158)).toBe('3.4 MB');
  });
});
