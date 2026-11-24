'use client';

// SCR-24 "Assign accountable PM" (F-88, contract 1.26.0): the shared Drawer over the Unassigned list. It reads
// `GET /received-bids/{case_id}/assignment` and draws only what that read carries: its nominees, roles, proofs and next steps,
// with nothing chosen ahead and nothing filtered here. Proof and a reason are required (LC-Q7). "PM assigned" waits for the
// assignment and the list to be read again; a failed or uncertain write never says it and is never repeated by itself
// (useReceivedBidAssign). Nothing here calls the v7 assignment or the base64 evidence upload.
import { useEffect, useMemo, useRef, useState } from 'react';

import { Button, Callout, Drawer, ErrorState, Icon, Loading, Segmented, Select, TextArea, Checkbox, formatDateTime, useIsPhone, ValidationSummary } from '@/components';
import { EvidencePicker } from '@/features/workspace/EvidencePicker';
import type { UploadedFile } from '@/features/workspace/evidence';
import { SignedOutState } from '@/shell/FrameStates';

import { REASON_MAX, type AssignmentRead } from './receivedBids';
import { FORBIDDEN, GONE, useReceivedBidAssign, type AssignInput } from './useReceivedBidAssign';

import '@/features/response/response.css';
import '@/features/workspace/workspace.css';
import './rfp.css';

/** Frontend copy, not business rules. */
export const ASSIGN_PM_TEXT = {
  title: 'Assign accountable PM',
  submit: 'Assign PM',
  owner: 'Accountable PM',
  choose: 'Choose a PM',
  roleLabel: 'You are assigning as',
  chooseRole: 'Choose a role',
  proof: 'Proof',
  listedProof: 'Use a recorded proof',
  uploadProof: 'Upload a file',
  chooseProof: 'Choose a proof',
  checked: 'I checked this file is the right proof.',
  reason: 'Reason for choosing this PM',
  nextHead: 'What happens next:',
  setup: 'Nobody is set up to assign yet. Ask a PSL admin to finish setup.',
  noNominees: 'No one can be chosen for this RFP yet.',
  loadFailed: 'We couldn’t load this RFP. Nothing was changed.',
  stale: 'This changed while you were working.',
  unconfirmedHead: 'Not confirmed',
  unconfirmed: 'We couldn’t confirm the PM was assigned. Check before trying again.',
  confirmedAfter: 'Not confirmed at first; confirmed after reading it again.',
  checkAgain: 'Check again',
  listRefresh: 'We couldn’t refresh the list.',
  cancel: 'Cancel',
  close: 'Close',
} as const;

/** The messages without the one for a control the person just changed. */
const without = (messages: Record<string, string>, control: string) => Object.fromEntries(Object.entries(messages).filter(([name]) => name !== control));

const FORM_ID = 'assign-pm-form';
const ids = { candidate: 'ap-candidate', role: 'ap-role', proof: 'ap-proof', reason: 'ap-reason', checked: 'ap-checked' } as const;

type Route = 'listed' | 'upload';
type Draft = { candidate: string | undefined; role: string | undefined; route: Route | undefined; evidence: string | undefined; upload: UploadedFile | null; checked: boolean; reason: string };
const EMPTY: Draft = { candidate: undefined, role: undefined, route: undefined, evidence: undefined, upload: null, checked: false, reason: '' };

/** The role to send: the only one served, or the one the person chose. */
const roleOf = (data: AssignmentRead, draft: Draft) => (data.roles.length === 1 ? data.roles[0] : draft.role);

/** What is missing, by control, in the order drawn: PM, role, proof, reason. */
export function assignProblems(data: AssignmentRead, draft: Draft): Record<string, string> {
  const out: Record<string, string> = {};
  if (!draft.candidate) out.candidate = 'Choose a PM to continue.';
  if (!roleOf(data, draft)) out.role = 'Choose a role to continue.';
  const route = data.proofs.length === 0 ? 'upload' : draft.route;
  if (route === 'listed' ? !draft.evidence : route === 'upload' ? !draft.upload : true) out.proof = 'Add proof to continue.';
  else if (route === 'upload' && !draft.checked) out.proof = 'Confirm you checked the file.';
  if (!draft.reason.trim()) out.reason = 'Give a reason to continue.';
  else if (draft.reason.length > REASON_MAX) out.reason = `Use ${REASON_MAX} characters or fewer.`;
  return out;
}

function NextSteps({ steps }: { steps: AssignmentRead['next_steps'] }) {
  if (steps.length === 0) return null;
  return (
    <div className="rfp-assign__next">
      <strong>{ASSIGN_PM_TEXT.nextHead}</strong>
      <ul>
        {steps.map((step) => (
          <li key={step.key}>{step.label}</li>
        ))}
      </ul>
    </div>
  );
}

type Props = {
  caseId: string;
  /** The list behind the drawer, read again after a write: whether the RFP is still listed, or null when it could not be read. */
  reloadList: () => Promise<boolean | null>;
  onClose: () => void;
  /** Where a signed-out person returns. */
  pathname: string;
};

export function AssignPmDrawer({ caseId, reloadList, onClose, pathname }: Props) {
  const phone = useIsPhone();
  const flow = useReceivedBidAssign(caseId, reloadList);
  const { view, notice, errors, busy } = flow;
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [local, setLocal] = useState<Record<string, string>>({});
  const [attempt, setAttempt] = useState(0);
  const alertRef = useRef<HTMLDivElement>(null);
  const doneRef = useRef<HTMLDivElement>(null);
  const shown = useMemo(() => ({ ...local, ...errors }), [local, errors]);

  useEffect(() => {
    if (notice) alertRef.current?.focus();
  }, [notice]);
  useEffect(() => {
    if (view.kind === 'done') doneRef.current?.focus();
  }, [view.kind]);

  const set = <K extends keyof Draft>(patch: Pick<Draft, K>, control: string) => {
    setDraft((d) => ({ ...d, ...patch }));
    setLocal((e) => without(e, control));
    flow.setErrors((e) => without(e, control));
  };
  const problems = useMemo(() => Object.entries(shown).map(([name, message]) => ({ fieldId: ids[name as keyof typeof ids] ?? name, message })), [shown]);
  const unconfirmed = notice?.kind === 'unconfirmed';

  const send = (data: AssignmentRead) => {
    if (unconfirmed) return void flow.checkAgain();
    const found = assignProblems(data, draft);
    if (Object.keys(found).length > 0) {
      setLocal(found);
      flow.setErrors({});
      setAttempt((n) => n + 1);
      return;
    }
    setLocal({});
    const route = data.proofs.length === 0 ? 'upload' : draft.route;
    const proof: AssignInput['proof'] = route === 'listed' ? { evidence: Number.parseInt(draft.evidence ?? '', 10) } : { uploadId: draft.upload?.upload_id ?? 0 };
    void flow.submit(data, {
      candidate: Number.parseInt(draft.candidate ?? '', 10),
      candidateLabel: data.nominees.find((n) => String(n.id) === draft.candidate)?.label ?? '',
      role: roleOf(data, draft) ?? '',
      reason: draft.reason.trim(),
      proof,
    });
  };

  let body;
  let footer;
  const close = () => onClose();
  const closeButton = (
    <Button kind="secondary" onClick={close}>
      {ASSIGN_PM_TEXT.close}
    </Button>
  );
  const bid = view.kind === 'ready' || view.kind === 'done' ? view.data.bid : undefined;

  if (view.kind === 'lost' && view.why === 'unauthenticated') {
    body = <SignedOutState pathname={pathname} />;
  } else if (view.kind === 'lost') {
    body = (
      <>
        <Callout kind="problem" announce={false}>{view.why === 'forbidden' ? FORBIDDEN : GONE}</Callout>
        {closeButton}
      </>
    );
  } else if (view.kind === 'error') {
    body = <ErrorState title={ASSIGN_PM_TEXT.loadFailed} onRetry={() => void flow.load()} />;
  } else if (view.kind === 'loading') {
    body = <Loading>Loading…</Loading>;
  } else if (view.kind === 'done') {
    body = (
      <div ref={doneRef} tabIndex={-1} role="status" className="rfp-assign__body">
        <p className="rfp-assign__done">
          <strong>PM assigned: {view.label}.</strong>
        </p>
        {view.listed === null && <p className="psl-hint">{ASSIGN_PM_TEXT.listRefresh}</p>}
        <NextSteps steps={view.data.next_steps} />
        {closeButton}
      </div>
    );
  } else {
    const data = view.data;
    const who = data.assignment ? (data.nominees.find((n) => n.id === data.assignment?.person_id)?.label ?? null) : null;
    if (data.assignment) {
      body = (
        <>
          {notice?.kind === 'confirmed' && <p className="psl-hint">{ASSIGN_PM_TEXT.confirmedAfter}</p>}
          <p role="status">{who ? `Already assigned: ${who}` : 'Assigned to another person'}</p>
          <NextSteps steps={data.next_steps} />
          {closeButton}
        </>
      );
    } else if (data.setup_required) {
      body = (
        <>
          <p>{ASSIGN_PM_TEXT.setup}</p>
          {closeButton}
        </>
      );
    } else if (data.nominees.length === 0) {
      body = (
        <>
          <p>{ASSIGN_PM_TEXT.noNominees}</p>
          {closeButton}
        </>
      );
    } else {
      const route: Route | undefined = data.proofs.length === 0 ? 'upload' : draft.route;
      const locked = busy || unconfirmed;
      body = (
        <form
          id={FORM_ID}
          className="rfp-assign__body"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            send(data);
          }}
        >
          <ValidationSummary attempt={attempt + flow.attempt} problems={problems} />
          <div ref={alertRef} tabIndex={-1}>
            {notice?.kind === 'stale' && (
              <div role="alert">
                <Callout kind="warning">{ASSIGN_PM_TEXT.stale}</Callout>
              </div>
            )}
            {notice?.kind === 'problem' && <Callout kind="problem">{notice.message}</Callout>}
            {notice?.kind === 'invalid' && notice.general.length > 0 && (
              <Callout kind="problem">
                <span className="sw-stack">
                  {notice.general.map((message) => (
                    <span key={message}>{message}</span>
                  ))}
                </span>
              </Callout>
            )}
            {unconfirmed && (
              <div role="alert">
                <Callout kind="warning">
                  <strong>{ASSIGN_PM_TEXT.unconfirmedHead}</strong> <span>{ASSIGN_PM_TEXT.unconfirmed}</span>
                </Callout>
              </div>
            )}
          </div>
          <div className="resp-field">
            <Select
              id={ids.candidate}
              label={ASSIGN_PM_TEXT.owner}
              options={data.nominees.map((n) => ({ value: String(n.id), label: n.label }))}
              value={draft.candidate}
              placeholder={ASSIGN_PM_TEXT.choose}
              disabled={locked}
              error={shown.candidate}
              onChange={(candidate) => set({ candidate }, 'candidate')}
            />
          </div>
          {data.roles.length === 1 ? (
            <div className="resp-field">
              <span className="resp-label">{ASSIGN_PM_TEXT.roleLabel}</span>
              <span className="resp-static">{data.roles[0]}</span>
            </div>
          ) : (
            <div className="resp-field">
              <Select
                id={ids.role}
                label={ASSIGN_PM_TEXT.roleLabel}
                options={data.roles.map((r) => ({ value: r, label: r }))}
                value={draft.role}
                placeholder={ASSIGN_PM_TEXT.chooseRole}
                disabled={locked}
                error={shown.role}
                onChange={(role) => set({ role }, 'role')}
              />
            </div>
          )}
          <div className="resp-field" id={ids.proof} tabIndex={-1}>
            <span className="resp-label" id="ap-proof-label">
              {ASSIGN_PM_TEXT.proof}
            </span>
            {data.proofs.length > 0 && (
              <Segmented
                phone={phone}
                labelledBy="ap-proof-label"
                options={[
                  { value: 'listed' as Route, label: ASSIGN_PM_TEXT.listedProof, disabled: locked },
                  { value: 'upload' as Route, label: ASSIGN_PM_TEXT.uploadProof, disabled: locked },
                ]}
                value={draft.route}
                onChange={(next) => !locked && set({ route: next, evidence: undefined, upload: null, checked: false }, 'proof')}
              />
            )}
            {route === 'listed' && (
              <Select
                label={ASSIGN_PM_TEXT.listedProof}
                hideLabel
                options={data.proofs.map((p) => ({ value: String(p.id), label: p.label }))}
                value={draft.evidence}
                placeholder={ASSIGN_PM_TEXT.chooseProof}
                disabled={locked}
                onChange={(evidence) => set({ evidence }, 'proof')}
              />
            )}
            {route === 'upload' && (
              <>
                <EvidencePicker caseId={caseId} value={draft.upload} onChange={(upload) => set({ upload, checked: false }, 'proof')} disabledReason={locked ? 'The form is locked while it is checked.' : undefined} />
                {draft.upload && <Checkbox id={ids.checked} label={ASSIGN_PM_TEXT.checked} checked={draft.checked} disabled={locked} onChange={(event) => set({ checked: event.target.checked }, 'proof')} />}
              </>
            )}
            {shown.proof && (
              <span className="psl-error">
                <Icon name="warn" />
                <span>{shown.proof}</span>
              </span>
            )}
          </div>
          <div className="resp-field">
            <TextArea id={ids.reason} label={ASSIGN_PM_TEXT.reason} limit={REASON_MAX} value={draft.reason} readOnly={locked} error={shown.reason} onChange={(event) => set({ reason: event.target.value }, 'reason')} />
          </div>
          <NextSteps steps={data.next_steps} />
        </form>
      );
      footer = (
        <>
          {!phone && (
            <Button kind="secondary" onClick={close}>
              {ASSIGN_PM_TEXT.cancel}
            </Button>
          )}
          <Button type="submit" form={FORM_ID} kind="start" size={phone ? 'lg' : 'md'} block={phone} busy={busy} busyLabel="Assigning…">
            {unconfirmed ? ASSIGN_PM_TEXT.checkAgain : ASSIGN_PM_TEXT.submit}
          </Button>
        </>
      );
    }
  }

  const heading = bid ? `${bid.reference} · received ${formatDateTime(bid.received_at)}` : undefined;
  return (
    <Drawer className="rfp-assign" keepTop title={ASSIGN_PM_TEXT.title} eyebrow={phone ? undefined : heading} subline={phone ? heading : undefined} onClose={close} footer={footer}>
      <div className="rfp-assign__body">{body}</div>
    </Drawer>
  );
}
