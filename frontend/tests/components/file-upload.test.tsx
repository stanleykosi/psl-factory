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
    expect(screen.getByText('PDF, PNG, JPG or EML · up to 10 MB')).toBeTruthy();
    const input = screen.getByLabelText(/Proof/, { selector: 'input' }) as HTMLInputElement;
    expect(input.type).toBe('file');
    expect(await violations()).toEqual([]);
    fireEvent.change(input, { target: { files: [file('site-photos.zip', 10)] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByText('ZIP files can’t be used as proof').closest('.psl-file')?.className).toBe('psl-file is-error');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(screen.getByLabelText(/Proof/, { selector: 'input' })).toBeTruthy();
  });

  it('a good file goes to onFile and shows as uploaded with Remove', async () => {
    const onFile = vi.fn();
    render(<Proof onFile={onFile} />);
    fireEvent.change(screen.getByLabelText(/Proof/, { selector: 'input' }), { target: { files: [file('client-signature.PDF', 430080)] } });
    expect(onFile).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Uploaded · 420 KB')).toBeTruthy();
    expect(await violations()).toEqual([]);
    fireEvent.click(screen.getByRole('button', { name: 'Remove client-signature.PDF' }));
    expect(screen.getByText(/Drop a file here or/)).toBeTruthy();
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
    expect(screen.getByRole('button', { name: 'Cancel upload of bank.pdf' })).toBeTruthy();
    expect(await violations()).toEqual([]);
    rerender(<FileUpload label="Proof" state={{ status: 'restricted', name: 'Payroll approval', note: 'Proof attached · HR only' }} onFile={() => {}} onRemove={() => {}} />);
    expect(screen.getByText('Payroll approval').closest('.psl-file')?.className).toBe('psl-file cmp-file--restricted');
    expect(screen.queryByRole('button')).toBeNull();
    rerender(<FileUpload label="Proof" state={{ status: 'empty' }} error="Proof is needed to record a signature." onFile={() => {}} onRemove={() => {}} />);
    expect(screen.getByText(/choose a file/).closest('.psl-drop')?.className).toContain('is-error');
    expect(screen.getByLabelText(/Proof/, { selector: 'input' }).getAttribute('aria-invalid')).toBe('true');
    rerender(<FileUpload label="Proof" state={{ status: 'empty' }} disabledReason="The record is verified." onFile={() => {}} onRemove={() => {}} />);
    expect(screen.getByText('Uploads are closed').closest('.psl-drop')?.className).toBe('psl-drop is-disabled');
    expect(await violations()).toEqual([]);
  });

  it('multi-file mode: rows with Remove per file, and the zone shrinks to one line', async () => {
    const onFile = vi.fn();
    const onRemove = vi.fn();
    const files = [
      { key: 1, status: 'uploaded' as const, name: 'client-email-17nov.eml', size: 48 * 1024 },
      { key: 2, status: 'uploaded' as const, name: 'award-letter-signed.pdf', size: 420 * 1024 },
    ];
    render(<FileUpload label="Proof" files={files} multiple onFile={onFile} onRemove={onRemove} />);
    expect(screen.getByText('Uploaded · 48 KB')).toBeTruthy();
    expect(screen.getByText('Add another file').closest('.psl-drop')?.className).toContain('psl-drop--compact');
    expect(screen.queryByText(/Drop a file here or/)).toBeNull();
    expect(screen.queryByText('PDF, PNG, JPG or EML · up to 10 MB')).toBeNull();
    expect(screen.getByLabelText(/Add another file/, { selector: 'input' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Remove award-letter-signed.pdf' }));
    expect(onRemove).toHaveBeenCalledWith(2);
    fireEvent.change(screen.getByLabelText(/Add another file/, { selector: 'input' }), { target: { files: [file('c.png', 5)] } });
    expect(onFile).toHaveBeenCalledTimes(1);
    expect(await violations()).toEqual([]);
  });

  it('one file allowed: the zone gives way to the row, and a row that cannot be sent again offers Remove', () => {
    const onRetry = vi.fn();
    const onRemove = vi.fn();
    const { rerender } = render(<FileUpload label="Proof" files={[{ key: 7, status: 'error', name: 'a.pdf', message: 'Couldn’t upload. Try again.' }]} onFile={() => {}} onRemove={onRemove} onRetry={onRetry} />);
    expect(screen.queryByText(/Drop a file here or/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalledWith(7);
    rerender(<FileUpload label="Proof" files={[{ key: 7, status: 'error', name: 'a.pdf', message: 'This item changed. Add the file again.', retry: false, remove: true }]} onFile={() => {}} onRemove={onRemove} onRetry={onRetry} />);
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Remove a.pdf' }));
    expect(onRemove).toHaveBeenCalledWith(7);
  });

  it('no accept list and no limit: any file goes to the consumer, and the chooser has no accept attribute', () => {
    const onFile = vi.fn();
    render(<FileUpload label="Proof" files={[]} accept={[]} maxBytes={null} hint="Proof for the project." onFile={onFile} onRemove={() => {}} />);
    const input = screen.getByLabelText(/Proof/, { selector: 'input' }) as HTMLInputElement;
    expect(input.hasAttribute('accept')).toBe(false);
    expect(input.hasAttribute('capture')).toBe(false);
    expect(input.getAttribute('aria-describedby')).toContain(screen.getByText('Proof for the project.').id);
    fireEvent.change(input, { target: { files: [file('a.zip', 50 * 1024 * 1024)] } });
    expect(onFile).toHaveBeenCalledTimes(1);
  });

  it('a phone is offered a photo or a file, with no capture', () => {
    const original = window.matchMedia;
    window.matchMedia = ((query: string) => ({ matches: true, media: query, addEventListener() {}, removeEventListener() {} })) as unknown as typeof window.matchMedia;
    try {
      render(<FileUpload label="Proof" state={{ status: 'empty' }} onFile={() => {}} onRemove={() => {}} />);
      expect(screen.getByText(/Take a photo or/)).toBeTruthy();
      expect(screen.queryByText(/Drop a file here or/)).toBeNull();
      expect((screen.getByLabelText(/Proof/, { selector: 'input' }) as HTMLInputElement).hasAttribute('capture')).toBe(false);
    } finally {
      window.matchMedia = original;
    }
  });

  it('the label can be for assistive technology only, and the chooser waits while an upload is pending', () => {
    render(<FileUpload label="Proof of the reply" hideLabel pending state={{ status: 'empty' }} onFile={() => {}} onRemove={() => {}} />);
    expect(screen.getByText('Proof of the reply').className).toContain('cmp-sr');
    expect((screen.getByLabelText(/Proof of the reply/, { selector: 'input' }) as HTMLInputElement).disabled).toBe(true);
  });

  it('formats sizes', () => {
    expect(formatSize(500)).toBe('500 B');
    expect(formatSize(20480)).toBe('20 KB');
    expect(formatSize(3565158)).toBe('3.4 MB');
  });
});
