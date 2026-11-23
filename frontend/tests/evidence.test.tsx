// @vitest-environment jsdom
// F-85: the shared evidence picker and upload (POST /cases/{case_id}/files), and the file-draft proposal.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { EvidencePicker } from '@/features/workspace/EvidencePicker';
import { fileToEvidence, refuseFile, uploadCaseFile, uploadErrorMessage, type EvidenceId, type UploadedFile, type UploadId } from '@/features/workspace/evidence';
import { ApiError, networkError } from '@/api/errors';

// @ts-expect-error plain ESM module without type declarations
import { workLive } from '../mock/work-live.mjs';

const CASE = 'case-1';
const pdf = (bytes = 'x') => new File([bytes], 'plan.pdf', { type: 'application/pdf' });

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let scenario: string | undefined;
let netDown = false;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const sessionReads = () => fetchStub.mock.calls.filter(([r]) => new URL(r.url).pathname === '/api/v1/session');

beforeEach(() => {
  scenario = undefined;
  netDown = false;
  setCsrfToken('tok');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/session') return new Response(JSON.stringify({ csrf_token: 'tok', signed_in: true, next_url: '/' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    if (netDown) throw new TypeError('network');
    const [status, body] = workLive({ method: request.method.toLowerCase(), url, scenario, csrfOk: true, persona: 'finance_lead', rawBytes: new Uint8Array(3) }) as [number, unknown];
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

describe('uploadCaseFile (AC22, AC23)', () => {
  it('posts multipart to the case and returns the upload id', async () => {
    const result = await uploadCaseFile(CASE, pdf('hello'));
    expect(result.upload_id).toBeGreaterThan(8000);
    expect(Object.keys(result).sort()).toEqual(['download_url', 'name', 'sha256', 'size', 'upload_id']);
    const [[request]] = posts();
    expect(new URL(request.url).pathname).toBe(`/api/v1/cases/${CASE}/files`);
    // the body is a FormData with the file under `file`; the browser (not this code) adds the multipart Content-Type
    expect(request.headers.get('content-type')).not.toMatch(/json/);
    expect(request.headers.get('x-csrftoken')).toBe('tok');
  });

  it('refuses the whole family of unaccepted files before any request', async () => {
    const tooBig = new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'big.pdf');
    for (const file of [new File(['x'], 'run.exe'), new File(['x'], 'RUN.EXE'), new File(['x'], 'plan.pdf.exe'), new File(['x'], 'noext'), new File(['x'], 'a.txt'), tooBig]) {
      expect(refuseFile(file)).toBeTruthy();
      await expect(uploadCaseFile(CASE, file)).rejects.toBeInstanceOf(ApiError);
    }
    expect(fetchStub).not.toHaveBeenCalled();
    expect(refuseFile(new File(['x'], 'Plan.PDF'))).toBeNull();
  });
});

describe('upload errors (AC24, AC25)', () => {
  it.each([
    ['413', 'That file is too large.'],
    ['415', 'That file type isn’t accepted.'],
    ['422', 'The file is empty.'],
    ['429', 'Try again shortly.'],
    ['404', 'This record is unavailable.'],
  ])('%s says its own words and is sent once', async (code, words) => {
    scenario = code;
    const error = await uploadCaseFile(CASE, pdf()).catch((e) => e);
    expect(uploadErrorMessage(error)).toBe(words);
    expect(posts()).toHaveLength(1);
  });

  it('a dropped network says nothing was uploaded', async () => {
    netDown = true;
    const error = await uploadCaseFile(CASE, pdf()).catch((e) => e);
    expect(uploadErrorMessage(error)).toBe('We couldn’t reach the server. Nothing was uploaded.');
    expect(uploadErrorMessage(networkError())).toContain('Nothing was uploaded');
  });

  it('403 csrf_failed refreshes the session once and says Press upload again; no second upload', async () => {
    scenario = 'csrf_failed';
    const error = await uploadCaseFile(CASE, pdf()).catch((e) => e);
    expect(uploadErrorMessage(error)).toBe('Press upload again.');
    expect(posts()).toHaveLength(1);
    expect(sessionReads()).toHaveLength(1);
  });
});

describe('the picker (AC22, AC23, AC29)', () => {
  const choose = (file: File) => {
    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
  };

  it('uploads into its own case only and hands back the upload id', async () => {
    const onChange = vi.fn();
    render(<EvidencePicker caseId={CASE} value={null} onChange={onChange} />);
    choose(pdf());
    await waitFor(() => expect(onChange).toHaveBeenCalledTimes(1));
    expect((onChange.mock.calls[0][0] as UploadedFile).upload_id).toBeGreaterThan(8000);
    expect(new URL(posts()[0][0].url).pathname).toBe(`/api/v1/cases/${CASE}/files`);
    expect(document.querySelector('input:not([type=file])')).toBeNull();
  });

  it('shows the failure in the row, never retries by itself, and Try again sends it once more', async () => {
    scenario = '429';
    const onChange = vi.fn();
    render(<EvidencePicker caseId={CASE} value={null} onChange={onChange} />);
    choose(pdf());
    expect(await screen.findByText('Try again shortly.')).toBeTruthy();
    expect(posts()).toHaveLength(1);
    scenario = undefined;
    fireEvent.click(screen.getByRole('button', { name: /Try again/ }));
    await waitFor(() => expect(onChange).toHaveBeenCalledTimes(1));
    expect(posts()).toHaveLength(2);
  });

  it('refuses a .exe before any request and offers Try again', async () => {
    render(<EvidencePicker caseId={CASE} value={null} onChange={vi.fn()} />);
    choose(new File(['x'], 'run.exe'));
    expect(await screen.findByRole('button', { name: /Try again/ })).toBeTruthy();
    expect(fetchStub).not.toHaveBeenCalled();
  });
});

describe('ids stay apart (AC26) and the proposal (AC27)', () => {
  it('an UploadId is not an EvidenceId', () => {
    const upload = 1 as UploadId;
    // @ts-expect-error an upload id is not an evidence id
    const evidence: EvidenceId = upload;
    expect(evidence).toBe(1);
  });

  // PROPOSAL, backend question 1 (unconfirmed): the file-draft review is the only route that gives an evidence id.
  it('proposal, backend question 1: drafts then review, returns reviewed_evidence_id', async () => {
    const id = await fileToEvidence(CASE, 8001 as UploadId, 'A01', async ({ draft }) => ({ draft: JSON.stringify(draft), summary: 's', gaps: [], note: 'n' }));
    expect(id).toBe(5001);
    expect(posts().map(([r]) => new URL(r.url).pathname)).toEqual([`/api/v1/cases/${CASE}/files/8001/drafts`, `/api/v1/cases/${CASE}/file-drafts/6001/review`]);
  });

  it('a null reviewed_evidence_id stays null', async () => {
    fetchStub.mockImplementation(async (request) => {
      const reviewing = new URL(request.url).pathname.endsWith('/review');
      const body = { job_id: 6001, upload_id: 1, role: 'A01', status: reviewing ? 'reviewed' : 'draft', label: 'x', attempt: 1, draft: null, recovery_pin: null, reviewed_evidence_id: null, workflow_record_id: null };
      return new Response(JSON.stringify(body), { status: reviewing ? 200 : 202, headers: { 'Content-Type': 'application/json' } });
    });
    expect(await fileToEvidence(CASE, 1 as UploadId, 'A01', async () => ({ draft: '', summary: '', gaps: [], note: '' }))).toBeNull();
  });
});
