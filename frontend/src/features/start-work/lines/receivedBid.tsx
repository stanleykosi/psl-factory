'use client';

// SCR-23 Log a received RFP (F-88, contract 1.26.0). The line has its own endpoint, so it owns its whole drawer (`ownsSubmit`): no project
// picker, no `POST /work`. The client comes from `GET /received-bids/organisations`; one `POST /received-bids` carries the
// fields and the file; the receipt is read back before "RFP logged." is said. `start_key` is made when the drawer opens and reused for
// every resend of the same input ("Check again" never makes a second RFP); it changes only after a failure that recorded nothing, once
// a field is changed. A 5xx, timeout or network failure is uncertain: the form locks until "Check again". Nothing is resent by itself.
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { refreshSession } from '@/api/client';
import { ApiError } from '@/api/errors';
import { Button, Callout, Checkbox, DateField, FileUpload, formatDateTime, formatSize, Icon, Loading, Segmented, Select, TextArea, TextField, ValidationSummary, type FileState } from '@/components';
import {
  DOCUMENT_MAX_BYTES,
  DOCUMENT_TYPES,
  fetchOrganisations,
  fetchReceipt,
  logReceivedBid,
  NAME_MAX,
  NOTE_MAX,
  type DeadlineStatus,
  type LoggedBid,
  type LogInput,
  type Organisation,
  type Receipt,
  type SubmissionMethod,
} from '@/features/rfp/receivedBids';
import { SignedOutState } from '@/shell/FrameStates';

import { DrawerFrame, useWide } from '../DrawerFrame';
import { newIdempotencyKey } from '../intake';
import { RECORD_UNAVAILABLE } from '../labels';
import { NOT_CONFIRMED, REFRESH_SESSION } from '../useStart';
import type { OwnLine } from './index';

export const RECEIVED_BID_KEY = 'received-bid';
export const NO_ORGANISATIONS = 'You can’t log a received RFP for any organisation yet.';
export const FORBIDDEN = 'You can’t log RFPs for this organisation.';
export const TOO_LARGE = 'The file is larger than 5 MB.';
export const WRONG_TYPE = 'Use a Word or PDF file.';
export const RATE_LIMITED = 'Too many tries. Wait a moment.';
export const RECEIPT_UNREAD = 'RFP logged. We couldn’t read the receipt back.';

const DEADLINES: { value: DeadlineStatus; label: string }[] = [
  { value: 'unknown', label: 'Not known' },
  { value: 'stated', label: 'A date is stated' },
  { value: 'not_stated', label: 'Not stated' },
];
const METHODS: { value: SubmissionMethod; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'portal', label: 'Portal' },
  { value: 'by_hand', label: 'By hand' },
  { value: 'not_stated', label: 'Not stated' },
];
/** The server's field names for this body, by the control that draws them; a name not here is drawn as a general message. */
const CONTROL: Record<string, string> = {
  authority: 'authority',
  reference: 'reference',
  received_at: 'received_at',
  deadline_status: 'deadline_status',
  deadline_at: 'deadline_at',
  note: 'note',
  prospect_name: 'prospect_name',
  submission_method: 'submission_method',
  submission_target: 'submission_target',
  context_attested: 'context_attested',
  document: 'document',
};
const fieldId = (name: string) => `rb-field-${name}`;

export type Draft = {
  authority: string;
  reference: string;
  receivedAt: string;
  deadlineStatus: DeadlineStatus | undefined;
  deadlineAt: string;
  note: string;
  prospectName: string;
  submissionMethod: SubmissionMethod | undefined;
  submissionTarget: string;
  attested: boolean;
  document: File | null;
};
const EMPTY: Draft = { authority: '', reference: '', receivedAt: '', deadlineStatus: undefined, deadlineAt: '', note: '', prospectName: '', submissionMethod: undefined, submissionTarget: '', attested: false, document: null };

/** A local date and time from the date field, as the offset date-time the server wants; null when it is not one. */
function offsetTime(local: string): string | null {
  const at = new Date(local);
  return local && !Number.isNaN(at.getTime()) ? at.toISOString() : null;
}

/** The file's refusal in plain words, or null. The server stays the final rule (413 and 415 say the same). */
export function refuseDocument(file: Pick<File, 'name' | 'size'>): string | null {
  const lower = file.name.toLowerCase();
  if (!DOCUMENT_TYPES.some((type) => lower.endsWith(type))) return WRONG_TYPE;
  if (file.size > DOCUMENT_MAX_BYTES) return TOO_LARGE;
  return null;
}

/** What is missing or wrong before anything is sent, by control, in the order drawn. */
export function problemsOf(draft: Draft): Record<string, string> {
  const out: Record<string, string> = {};
  if (!draft.authority) out.authority = 'Client is required.';
  if (!draft.reference.trim()) out.reference = 'RFP reference is required.';
  else if (draft.reference.trim().length > NAME_MAX) out.reference = `Use ${NAME_MAX} characters or fewer.`;
  if (!draft.document) out.document = 'RFP document is required.';
  else {
    const refused = refuseDocument(draft.document);
    if (refused) out.document = refused;
  }
  if (!draft.receivedAt || offsetTime(draft.receivedAt) === null) out.received_at = 'Actually received is required.';
  if (!draft.deadlineStatus) out.deadline_status = 'Deadline is required.';
  else if (draft.deadlineStatus === 'stated' && offsetTime(draft.deadlineAt) === null) out.deadline_at = 'Choose the deadline date and time.';
  if (draft.note.length > NOTE_MAX) out.note = `Use ${NOTE_MAX} characters or fewer.`;
  if (draft.prospectName.trim().length > NAME_MAX) out.prospect_name = `Use ${NAME_MAX} characters or fewer.`;
  return out;
}

/** The body for a valid draft; the optional fields are present only when filled. */
export function inputOf(draft: Draft, startKey: string): LogInput {
  const target = draft.submissionTarget.trim();
  const name = draft.prospectName.trim();
  return {
    authority: Number.parseInt(draft.authority, 10),
    startKey,
    reference: draft.reference.trim(),
    receivedAt: offsetTime(draft.receivedAt) ?? '',
    deadlineStatus: draft.deadlineStatus ?? 'unknown',
    ...(draft.deadlineStatus === 'stated' ? { deadlineAt: offsetTime(draft.deadlineAt) ?? '' } : {}),
    ...(draft.note.trim() ? { note: draft.note } : {}),
    ...(name ? { prospectName: name } : {}),
    ...(draft.submissionMethod ? { submissionMethod: draft.submissionMethod } : {}),
    ...(target ? { submissionTarget: target } : {}),
    ...((name || draft.submissionMethod || target) && draft.attested ? { contextAttested: true } : {}),
    document: draft.document as File,
  };
}

type Notice = { kind: 'problem'; message: string } | { kind: 'invalid'; general: string[] } | { kind: 'uncertain' };
type Done = { logged: LoggedBid; receipt: Receipt | null };
type Orgs = { status: 'loading' } | { status: 'ready'; items: Organisation[] } | { status: 'error'; error: ApiError };

function OwnDrawer({ onBack, onClose, pathname }: { onBack: () => void; onClose: () => void; pathname: string }) {
  const wide = useWide();
  const [orgs, setOrgs] = useState<Orgs>({ status: 'loading' });
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [key, setKey] = useState(newIdempotencyKey);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<Notice | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const [done, setDone] = useState<Done | null>(null);
  const [reading, setReading] = useState(false);
  const [fileState, setFileState] = useState<FileState>({ status: 'empty' });
  const writing = useRef(false);
  const sent = useRef<LogInput | null>(null);
  // A failure that said nothing was recorded: the next change of a field starts a new key.
  const recordedNothing = useRef(false);
  const alertRef = useRef<HTMLDivElement>(null);
  const doneRef = useRef<HTMLDivElement>(null);

  const loadOrganisations = useCallback(async () => {
    setOrgs({ status: 'loading' });
    try {
      setOrgs({ status: 'ready', items: await fetchOrganisations() });
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthenticated') setSignedOut(true);
      else setOrgs({ status: 'error', error: error instanceof ApiError ? error : new ApiError(0, 'network', 'network_error', '') });
    }
  }, []);
  useEffect(() => {
    // One read per opening; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadOrganisations();
  }, [loadOrganisations]);
  useEffect(() => {
    if (notice) alertRef.current?.focus();
  }, [notice]);
  useEffect(() => {
    if (done) doneRef.current?.focus();
  }, [done]);

  const readOnly = busy || uncertain;
  const set = <K extends keyof Draft>(name: K, value: Draft[K], control: string) => {
    if (recordedNothing.current) {
      recordedNothing.current = false;
      setKey(newIdempotencyKey());
    }
    setDraft((d) => ({ ...d, [name]: value }));
    setErrors((e) => Object.fromEntries(Object.entries(e).filter(([name]) => name !== control)));
  };

  const readReceipt = useCallback(async (logged: LoggedBid) => {
    setReading(true);
    try {
      setDone({ logged, receipt: await fetchReceipt(logged.case_id, logged.receipt_id) });
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthenticated') setSignedOut(true);
      else setDone({ logged, receipt: null });
    } finally {
      setReading(false);
    }
  }, []);

  const submit = async () => {
    if (writing.current) return;
    let input = uncertain ? sent.current : null;
    if (!input) {
      const found = problemsOf(draft);
      if (Object.keys(found).length > 0) {
        setErrors(found);
        setNotice(null);
        setAttempt((n) => n + 1);
        return;
      }
      input = inputOf(draft, key);
    }
    writing.current = true;
    sent.current = input;
    setBusy(true);
    try {
      let logged: LoggedBid;
      try {
        logged = await logReceivedBid(input);
      } catch (thrown) {
        const error = thrown instanceof ApiError ? thrown : new ApiError(0, 'network', 'network_error', '');
        // Thrown before sending (no CSRF token) is signed out; a 5xx or no answer may have reached the server.
        if (error.kind === 'unauthenticated') return setSignedOut(true);
        if (error.kind === 'network' || error.kind === 'server' || error.kind === 'read_limited') {
          setUncertain(true);
          return setNotice({ kind: 'uncertain' });
        }
        setUncertain(false);
        sent.current = null;
        recordedNothing.current = true;
        setErrors({});
        switch (error.kind) {
          case 'csrf':
            await refreshSession().catch(() => undefined);
            return setNotice({ kind: 'problem', message: REFRESH_SESSION });
          case 'forbidden':
            return setNotice({ kind: 'problem', message: FORBIDDEN });
          case 'not_found':
            return setNotice({ kind: 'problem', message: RECORD_UNAVAILABLE });
          case 'too_large':
            setErrors({ document: TOO_LARGE });
            return setNotice({ kind: 'problem', message: TOO_LARGE });
          case 'unsupported':
            setErrors({ document: WRONG_TYPE });
            return setNotice({ kind: 'problem', message: WRONG_TYPE });
          case 'rate_limited':
            return setNotice({ kind: 'problem', message: RATE_LIMITED });
          case 'invalid': {
            const mapped: Record<string, string> = {};
            const general: string[] = [];
            for (const problem of error.fields) {
              const control = CONTROL[problem.name];
              if (control) mapped[control] = mapped[control] ? `${mapped[control]} ${problem.message}` : problem.message;
              else general.push(problem.message);
            }
            if (error.fields.length === 0) general.push(error.message);
            setErrors(mapped);
            setAttempt((n) => n + 1);
            return setNotice({ kind: 'invalid', general });
          }
          default:
            return setNotice({ kind: 'problem', message: error.message });
        }
      }
      setNotice(null);
      await readReceipt(logged);
    } finally {
      writing.current = false;
      setBusy(false);
    }
  };

  const onFile = (file: File) => {
    const refused = refuseDocument(file);
    set('document', file, 'document');
    setFileState(refused ? { status: 'error', name: file.name, message: refused } : { status: 'uploaded', name: file.name, size: file.size });
  };
  const problems = useMemo(() => Object.entries(errors).map(([name, message]) => ({ fieldId: fieldId(name), message })), [errors]);
  const subline = wide ? (
    <>
      Line chosen from the Start work menu ·{' '}
      <Button kind="text" size="sm" className="sw-change" onClick={onBack}>
        change line
      </Button>
    </>
  ) : (
    <>
      Step 2 of 2 ·{' '}
      <Button kind="text" size="sm" className="sw-change" onClick={onBack}>
        change line
      </Button>
    </>
  );
  const title = 'Log a received RFP';
  const cancel = (
    <Button kind="secondary" className="sw-secondary" onClick={onClose}>
      {done ? 'Close' : 'Cancel'}
    </Button>
  );

  if (signedOut) {
    return (
      <DrawerFrame eyebrow="START WORK" title={title} subline={subline} onClose={onClose} footer={cancel} focusKey="signed-out">
        <SignedOutState pathname={pathname} />
      </DrawerFrame>
    );
  }

  if (done) {
    const { receipt, logged } = done;
    return (
      <DrawerFrame eyebrow="START WORK" title={title} onClose={onClose} footer={cancel} focusKey="logged">
        <div ref={doneRef} tabIndex={-1} role="status" className="sw-stack">
          {receipt ? (
            <>
              <p className="sw-logged">
                <strong>RFP logged.</strong>
              </p>
              <dl className="sw-receipt">
                <dt>Reference</dt>
                <dd>{receipt.reference}</dd>
                <dt>Received</dt>
                <dd>{formatDateTime(receipt.received_at)}</dd>
                <dt>File</dt>
                <dd>
                  {receipt.original.filename} · {formatSize(receipt.original.bytes)}
                </dd>
                {receipt.note && (
                  <>
                    <dt>Note</dt>
                    <dd>{receipt.note}</dd>
                  </>
                )}
              </dl>
              <Link href="/my-work?queue=unassigned" className="psl-link" onClick={onClose}>
                Open Unassigned
              </Link>
            </>
          ) : (
            <>
              <Callout kind="warning">{RECEIPT_UNREAD}</Callout>
              <Button kind="secondary" busy={reading} busyLabel="Reading…" onClick={() => void readReceipt(logged)}>
                Read the receipt again
              </Button>
              <Link href="/my-work?queue=unassigned" className="psl-link" onClick={onClose}>
                Open Unassigned
              </Link>
            </>
          )}
        </div>
      </DrawerFrame>
    );
  }

  const organisations = orgs.status === 'ready' ? orgs.items : [];
  const none = orgs.status === 'ready' && organisations.length === 0;
  const off = orgs.status !== 'ready' || none;
  const offReason = orgs.status === 'loading' ? 'The client list is still loading.' : none ? NO_ORGANISATIONS : 'The client list could not be loaded.';
  const optionalFilled = draft.prospectName.trim() !== '' || draft.submissionMethod !== undefined || draft.submissionTarget.trim() !== '';
  const footer = (
    <>
      {uncertain && <span className="psl-hint sw-foothint">If it was logged, it will be in Unassigned.</span>}
      {off && (
        <span className="psl-hint sw-foothint" id="rb-off">
          {offReason}
        </span>
      )}
      {wide && cancel}
      <Button kind="start" className="sw-primary" busy={busy} busyLabel="Logging…" disabled={off} aria-describedby={off ? 'rb-off' : undefined} onClick={() => void submit()}>
        {uncertain ? 'Check again' : 'Log RFP'}
      </Button>
    </>
  );
  const fail = orgs.status === 'error' ? orgs.error : null;

  return (
    <DrawerFrame eyebrow="START WORK" title={title} subline={subline} onClose={onClose} footer={footer} focusKey={`rb-${orgs.status}`}>
      <ValidationSummary problems={problems} attempt={attempt} />
      <div ref={alertRef} tabIndex={-1}>
        {notice?.kind === 'invalid' && notice.general.length > 0 && (
          <Callout kind="problem">
            <span className="sw-stack">
              {notice.general.map((message) => (
                <span key={message}>{message}</span>
              ))}
            </span>
          </Callout>
        )}
        {notice?.kind === 'problem' && <Callout kind="problem">{notice.message}</Callout>}
        {notice?.kind === 'uncertain' && (
          <div role="alert">
            <Callout kind="warning">{NOT_CONFIRMED}</Callout>
          </div>
        )}
      </div>
      {orgs.status === 'loading' && <Loading>Loading…</Loading>}
      {fail && (
        <>
          <Callout kind="problem" announce={false}>{fail.kind === 'forbidden' ? FORBIDDEN : 'We couldn’t load your clients. Nothing was logged.'}</Callout>
          {fail.kind !== 'forbidden' && (
            <Button kind="secondary" className="sw-retry" onClick={() => void loadOrganisations()}>
              Try again
            </Button>
          )}
        </>
      )}
      {none && <Callout kind="info">{NO_ORGANISATIONS}</Callout>}
      {orgs.status === 'ready' && !none && (
        <>
          <div className="psl-field sw-field" data-field="authority">
            <Select
              id={fieldId('authority')}
              label="Client"
              options={organisations.map((o) => ({ value: String(o.id), label: o.organisation }))}
              value={draft.authority || undefined}
              placeholder="Choose a client"
              disabled={readOnly}
              error={errors.authority}
              onChange={(value) => set('authority', value, 'authority')}
            />
          </div>
          <div className="psl-field sw-field" data-field="reference">
            <TextField id={fieldId('reference')} label="RFP reference" aria-required value={draft.reference} readOnly={readOnly} error={errors.reference} onChange={(e) => set('reference', e.target.value, 'reference')} />
          </div>
          <div className="psl-field sw-field" data-field="document" id={fieldId('document')} tabIndex={-1}>
            <FileUpload
              label="RFP document"
              state={fileState}
              accept={[]}
              maxBytes={null}
              hint="Word or PDF, up to 5 MB"
              error={errors.document}
              disabledReason={readOnly ? 'The form is locked while it is checked.' : undefined}
              onFile={onFile}
              onRemove={() => {
                setFileState({ status: 'empty' });
                set('document', null, 'document');
              }}
            />
          </div>
          <div className="psl-field sw-field" data-field="received_at">
            <DateField time id={fieldId('received_at')} label="Actually received" value={draft.receivedAt} disabled={readOnly} error={errors.received_at} onChange={(when) => set('receivedAt', when, 'received_at')} />
          </div>
          <div className="psl-field sw-field" data-field="deadline_status" id={fieldId('deadline_status')} tabIndex={-1}>
            <span className="psl-label" id="rb-deadline-label">
              Deadline
            </span>
            <div aria-invalid={errors.deadline_status ? true : undefined}>
              <Segmented
                phone={!wide}
                labelledBy="rb-deadline-label"
                className="sw-seg"
                options={DEADLINES.map((o) => ({ value: o.value, label: o.label, disabled: readOnly }))}
                value={draft.deadlineStatus}
                onChange={(next) => !readOnly && set('deadlineStatus', next, 'deadline_status')}
              />
            </div>
            {errors.deadline_status && (
              <span className="psl-error">
                <Icon name="warn" />
                <span>{errors.deadline_status}</span>
              </span>
            )}
          </div>
          {draft.deadlineStatus === 'stated' && (
            <div className="psl-field sw-field" data-field="deadline_at">
              <DateField time id={fieldId('deadline_at')} label="Deadline date and time" value={draft.deadlineAt} disabled={readOnly} error={errors.deadline_at} onChange={(when) => set('deadlineAt', when, 'deadline_at')} />
            </div>
          )}
          <div className="psl-field sw-field" data-field="submission_method">
            <Select
              id={fieldId('submission_method')}
              label="Submission method"
              optional
              options={METHODS.map((o) => ({ value: o.value, label: o.label }))}
              value={draft.submissionMethod}
              placeholder="Choose…"
              disabled={readOnly}
              error={errors.submission_method}
              onChange={(value) => set('submissionMethod', value as SubmissionMethod, 'submission_method')}
            />
          </div>
          <div className="psl-field sw-field" data-field="submission_target">
            <TextField id={fieldId('submission_target')} label="Where to submit" optional value={draft.submissionTarget} readOnly={readOnly} error={errors.submission_target} onChange={(e) => set('submissionTarget', e.target.value, 'submission_target')} />
          </div>
          <div className="psl-field sw-field" data-field="prospect_name">
            <TextField
              id={fieldId('prospect_name')}
              label="Client name as written in the RFP"
              optional
              hint="Recorded as written. It doesn’t create or match a client."
              value={draft.prospectName}
              readOnly={readOnly}
              error={errors.prospect_name}
              onChange={(e) => set('prospectName', e.target.value, 'prospect_name')}
            />
          </div>
          {optionalFilled && (
            <div className="psl-field sw-field" data-field="context_attested">
              <Checkbox
                id={fieldId('context_attested')}
                label="I confirm the client name and submission details above match the RFP."
                checked={draft.attested}
                disabled={readOnly}
                error={errors.context_attested}
                onChange={(e) => set('attested', e.target.checked, 'context_attested')}
              />
            </div>
          )}
          <div className="psl-field sw-field" data-field="note">
            <TextArea id={fieldId('note')} label="Note" optional oneLine limit={NOTE_MAX} value={draft.note} readOnly={readOnly} error={errors.note} onChange={(e) => set('note', e.target.value, 'note')} />
          </div>
        </>
      )}
    </DrawerFrame>
  );
}

export const receivedBid: OwnLine = {
  key: RECEIVED_BID_KEY,
  ownsSubmit: true,
  startLabel: 'Log RFP',
  drawerTitle: 'Log a received RFP',
  description: 'Record an RFP a client sent, with its file',
  Own: OwnDrawer,
};
