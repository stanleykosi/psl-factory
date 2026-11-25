'use client';

// F-137 "Record an issue": the shared Drawer over the Registers tab, in the look of the Assign PM drawer. It reads
// `GET /projects/{case_id}/issues` and offers only the owners and proofs that read serves, none chosen ahead. Severity is the contract's
// four words or none. "Recorded" is said only from the register read again (useRecordIssue); a lost connection locks the form.
import { useEffect, useMemo, useRef, useState } from 'react';

import { Button, Callout, Drawer, ErrorState, Loading, Select, TextArea, TextField, useIsPhone, ValidationSummary } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { EMPTY_DRAFT, LIMITS, problemsOf, proofLabel, SEVERITIES, type Draft } from './recordIssue';
import { RECORD_TEXT, useRecordIssue } from './useRecordIssue';

import '@/features/response/response.css';
import '@/features/start-work/start-work.css';

export const RECORD_ISSUE_TEXT = {
  title: 'Record an issue',
  submit: 'Record issue',
  reference: 'Reference',
  titleLabel: 'Title',
  kind: 'Kind',
  owner: 'Responsible owner',
  chooseOwner: 'Choose an owner',
  nextAction: 'Next action',
  evidence: 'Evidence',
  chooseEvidence: 'Choose the evidence',
  note: 'Note',
  severity: 'Severity',
  chooseSeverity: 'Not set',
  loadFailed: 'We couldn’t load the choices for this project. Nothing was changed.',
  noOwners: 'No one can be chosen as owner yet.',
  noProofs: 'No evidence is recorded for this project, so an issue can’t be recorded yet.',
  checkAgain: 'Check the register',
  cancel: 'Cancel',
  close: 'Close',
} as const;

const FORM_ID = 'record-issue-form';
const ids = { reference: 'ri-reference', title: 'ri-title', kind: 'ri-kind', owner: 'ri-owner', next_action: 'ri-next', evidence: 'ri-evidence', note: 'ri-note', severity: 'ri-severity' } as const;
const without = (messages: Record<string, string>, control: string) => Object.fromEntries(Object.entries(messages).filter(([name]) => name !== control));

type Props = { caseId: string; reloadList: () => Promise<void>; onClose: () => void; pathname: string };

export function RecordIssueDrawer({ caseId, reloadList, onClose, pathname }: Props) {
  const phone = useIsPhone();
  const flow = useRecordIssue(caseId, reloadList);
  const { view, notice, errors, busy } = flow;
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [local, setLocal] = useState<Record<string, string>>({});
  const [attempt, setAttempt] = useState(0);
  const alertRef = useRef<HTMLDivElement>(null);
  const doneRef = useRef<HTMLDivElement>(null);
  const shown = useMemo(() => ({ ...local, ...errors }), [local, errors]);
  const uncertain = notice?.kind === 'uncertain';

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

  const closeButton = (
    <Button kind="secondary" onClick={onClose}>
      {RECORD_ISSUE_TEXT.close}
    </Button>
  );
  let body;
  let footer;
  if (view.kind === 'lost' && view.why === 'unauthenticated') {
    body = <SignedOutState pathname={pathname} />;
  } else if (view.kind === 'lost') {
    body = (
      <>
        <Callout kind="problem" announce={false}>{view.message}</Callout>
        {closeButton}
      </>
    );
  } else if (view.kind === 'error') {
    body = <ErrorState title={RECORD_ISSUE_TEXT.loadFailed} onRetry={() => void flow.load()} />;
  } else if (view.kind === 'loading') {
    body = <Loading>Loading…</Loading>;
  } else if (view.kind === 'done') {
    const { issue, data } = view;
    const owner = data.owners.find((o) => o.id === issue.owner_id)?.name;
    body = (
      <div ref={doneRef} tabIndex={-1} role="status" className="sw-stack">
        <p>
          <strong>
            Recorded: {issue.reference} · {issue.title}.
          </strong>
        </p>
        <p>
          It is now {issue.status}
          {issue.severity ? `, severity ${issue.severity}` : ''}
          {owner ? `, with ${owner}` : ''}. Next action: {issue.next_action}
        </p>
        {closeButton}
      </div>
    );
  } else {
    const data = view.data;
    if (data.owners.length === 0 || data.proofs.length === 0) {
      body = (
        <>
          <p>{data.owners.length === 0 ? RECORD_ISSUE_TEXT.noOwners : RECORD_ISSUE_TEXT.noProofs}</p>
          {closeButton}
        </>
      );
    } else {
      const locked = busy || uncertain;
      body = (
        <form
          id={FORM_ID}
          className="sw-stack"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (uncertain) return void flow.check();
            const found = problemsOf(draft);
            if (Object.keys(found).length > 0) {
              setLocal(found);
              flow.setErrors({});
              setAttempt((n) => n + 1);
              return;
            }
            setLocal({});
            void flow.submit(data, draft);
          }}
        >
          <ValidationSummary attempt={attempt + flow.attempt} problems={problems} />
          <div ref={alertRef} tabIndex={-1}>
            {uncertain && (
              <div role="alert">
                <Callout kind="warning">{RECORD_TEXT.uncertain}</Callout>
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
          </div>
          <TextField id={ids.reference} label={RECORD_ISSUE_TEXT.reference} phone={phone} value={draft.reference} readOnly={locked} error={shown.reference} onChange={(e) => set({ reference: e.target.value }, 'reference')} hint={`${draft.reference.length} / ${LIMITS.reference}`} />
          <TextField id={ids.title} label={RECORD_ISSUE_TEXT.titleLabel} phone={phone} value={draft.title} readOnly={locked} error={shown.title} hint={`${draft.title.length} / ${LIMITS.title}`} onChange={(e) => set({ title: e.target.value }, 'title')} />
          <TextField id={ids.kind} label={RECORD_ISSUE_TEXT.kind} phone={phone} value={draft.kind} readOnly={locked} error={shown.kind} onChange={(e) => set({ kind: e.target.value }, 'kind')} hint={`${draft.kind.length} / ${LIMITS.kind}`} />
          <Select
            id={ids.owner}
            label={RECORD_ISSUE_TEXT.owner}
            options={data.owners.map((o) => ({ value: String(o.id), label: o.name }))}
            value={draft.owner}
            placeholder={RECORD_ISSUE_TEXT.chooseOwner}
            disabled={locked}
            error={shown.owner}
            onChange={(owner) => set({ owner }, 'owner')}
          />
          <TextArea id={ids.next_action} label={RECORD_ISSUE_TEXT.nextAction} limit={LIMITS.next_action} value={draft.next_action} readOnly={locked} error={shown.next_action} onChange={(e) => set({ next_action: e.target.value }, 'next_action')} />
          <Select
            id={ids.evidence}
            label={RECORD_ISSUE_TEXT.evidence}
            options={data.proofs.map((p) => ({ value: String(p.id), label: proofLabel(p) }))}
            value={draft.evidence}
            placeholder={RECORD_ISSUE_TEXT.chooseEvidence}
            disabled={locked}
            error={shown.evidence}
            onChange={(evidence) => set({ evidence }, 'evidence')}
          />
          <TextArea id={ids.note} label={RECORD_ISSUE_TEXT.note} limit={LIMITS.note} value={draft.note} readOnly={locked} error={shown.note} onChange={(e) => set({ note: e.target.value }, 'note')} />
          <Select
            id={ids.severity}
            label={RECORD_ISSUE_TEXT.severity}
            optional
            options={SEVERITIES.map((s) => ({ value: s, label: s }))}
            value={draft.severity}
            placeholder={RECORD_ISSUE_TEXT.chooseSeverity}
            disabled={locked}
            error={shown.severity}
            onChange={(severity) => set({ severity }, 'severity')}
          />
        </form>
      );
      footer = (
        <>
          {!phone && (
            <Button kind="secondary" onClick={onClose}>
              {RECORD_ISSUE_TEXT.cancel}
            </Button>
          )}
          <Button type="submit" form={FORM_ID} kind="start" size={phone ? 'lg' : 'md'} block={phone} busy={busy} busyLabel={uncertain ? 'Checking…' : 'Recording…'}>
            {uncertain ? RECORD_ISSUE_TEXT.checkAgain : RECORD_ISSUE_TEXT.submit}
          </Button>
        </>
      );
    }
  }
  return (
    <Drawer keepTop title={RECORD_ISSUE_TEXT.title} onClose={onClose} footer={footer}>
      <div className="sw-body">{body}</div>
    </Drawer>
  );
}
