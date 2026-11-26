'use client';

// F-112 "Log a change": the shared Drawer over the Registers tab's Changes register, in the look of Record an issue. It reads
// `GET /projects/{case_id}/ordinary-changes` and offers only the proofs that read serves, none chosen ahead; the category is the contract's
// two words. Every field is required. "Logged" is said only from the list read again (useLogChange); a lost connection locks the form.
// No board draws this form (spec Questions 1 and 2): it is built from the Record an issue form and flagged for a board.
import { useEffect, useMemo, useRef, useState } from 'react';

import { Button, Callout, Drawer, ErrorState, Loading, Select, TextArea, TextField, useIsPhone, ValidationSummary } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { CATEGORIES, EMPTY_DRAFT, LIMITS, problemsOf, proofLabel, type Draft } from './logChange';
import { LOG_TEXT, useLogChange } from './useLogChange';

import '@/features/response/response.css';
import '@/features/start-work/start-work.css';

export const LOG_CHANGE_TEXT = {
  title: 'Log a change',
  submit: 'Log the change',
  checkAgain: 'Check the list',
  loadFailed: 'We couldn’t load the choices for this project. Nothing was changed.',
  noProofs: 'No proof file is recorded for this case yet',
  cancel: 'Cancel',
  close: 'Close',
} as const;

const FORM_ID = 'log-change-form';
const ids = { reference: 'lc-reference', category: 'lc-category', module: 'lc-module', description: 'lc-description', reason: 'lc-reason', evidence: 'lc-evidence' } as const;
const without = (messages: Record<string, string>, control: string) => Object.fromEntries(Object.entries(messages).filter(([name]) => name !== control));

type Props = { caseId: string; reloadList: () => Promise<void>; onClose: () => void; pathname: string };

export function LogChangeDrawer({ caseId, reloadList, onClose, pathname }: Props) {
  const phone = useIsPhone();
  const flow = useLogChange(caseId, reloadList);
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
      {LOG_CHANGE_TEXT.close}
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
    body = <ErrorState title={LOG_CHANGE_TEXT.loadFailed} onRetry={() => void flow.load()} />;
  } else if (view.kind === 'loading') {
    body = <Loading>Loading…</Loading>;
  } else if (view.kind === 'done') {
    const { change } = view;
    body = (
      <div ref={doneRef} tabIndex={-1} role="status" className="sw-stack">
        <p>
          <strong>
            Logged: {change.reference} · {change.module}.
          </strong>
        </p>
        <p>
          {change.category} change. {change.description}
        </p>
        {closeButton}
      </div>
    );
  } else {
    const data = view.data;
    const locked = busy || uncertain;
    body = (
      <form
        id={FORM_ID}
        className="sw-stack"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (uncertain) return void flow.check();
          const found = problemsOf(draft, data);
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
              <Callout kind="warning">{LOG_TEXT.uncertain}</Callout>
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
        <TextField id={ids.reference} label="Reference" phone={phone} value={draft.reference} readOnly={locked} error={shown.reference} onChange={(e) => set({ reference: e.target.value }, 'reference')} hint={`${draft.reference.length} / ${LIMITS.reference}`} />
        <Select id={ids.category} label="Category" options={CATEGORIES.map((c) => ({ value: c, label: c }))} value={draft.category} placeholder="Choose the category" disabled={locked} error={shown.category} onChange={(category) => set({ category }, 'category')} />
        <TextField id={ids.module} label="Module" phone={phone} value={draft.module} readOnly={locked} error={shown.module} onChange={(e) => set({ module: e.target.value }, 'module')} hint={`${draft.module.length} / ${LIMITS.module}`} />
        <TextArea id={ids.description} label="Description" limit={LIMITS.description} value={draft.description} readOnly={locked} error={shown.description} onChange={(e) => set({ description: e.target.value }, 'description')} />
        <TextArea id={ids.reason} label="Reason" limit={LIMITS.reason} value={draft.reason} readOnly={locked} error={shown.reason} onChange={(e) => set({ reason: e.target.value }, 'reason')} />
        {data.evidence.length === 0 ? (
          <p>{LOG_CHANGE_TEXT.noProofs}</p>
        ) : (
          <Select id={ids.evidence} label="Proof" options={data.evidence.map((p) => ({ value: String(p.id), label: proofLabel(p) }))} value={draft.evidence} placeholder="Choose the proof" disabled={locked} error={shown.evidence} onChange={(evidence) => set({ evidence }, 'evidence')} />
        )}
      </form>
    );
    footer = (
      <>
        {!phone && (
          <Button kind="secondary" onClick={onClose}>
            {LOG_CHANGE_TEXT.cancel}
          </Button>
        )}
        <Button type="submit" form={FORM_ID} kind="start" size={phone ? 'lg' : 'md'} block={phone} busy={busy} busyLabel={uncertain ? 'Checking…' : 'Logging…'} disabled={data.evidence.length === 0} reason={data.evidence.length === 0 ? LOG_CHANGE_TEXT.noProofs : null}>
          {uncertain ? LOG_CHANGE_TEXT.checkAgain : LOG_CHANGE_TEXT.submit}
        </Button>
      </>
    );
  }
  return (
    <Drawer keepTop title={LOG_CHANGE_TEXT.title} onClose={onClose} footer={footer}>
      <div className="sw-body">{body}</div>
    </Drawer>
  );
}
