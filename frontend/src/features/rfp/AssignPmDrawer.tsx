'use client';

// SCR-24 "Assign the accountable PM" (F-36, PROPOSAL D-RFP-INTAKE, contract mock only): the shared Drawer over My work's Unassigned
// list. It reads the work item and draws only what the response carries: `assign.candidates` are the only people to choose from,
// nothing is chosen ahead, nothing comes from /me, and an item with no `assign` has no control (the page goes on to /work/<id>).
// F-30's AssignForm and useWorkspaceAssign send the one E-WORK-ASSIGN; the proposed keys (assign.roles, evidence_kind, next and the
// request's acting_role, evidence_id, case_revision) are read through ./proposals and sent only when the response offers them.
// The success words wait for the item and the list to be read again; a failed, timed-out or uncertain write never says "assigned".
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Button, Callout, Drawer, ErrorState, Icon, Loading, Select, Unknown, UNKNOWN, useIsPhone } from '@/components';
import { ProofField } from '@/features/response/ProofField';
import { useEvidenceUpload } from '@/features/response/useEvidenceUpload';
import { AssignForm, type AssignWords } from '@/features/workspace/AssignForm';
import { useWorkspacePage } from '@/features/workspace/usePageReload';
import { ASSIGN_TEXT, useWorkspaceAssign, type AssignRequest } from '@/features/workspace/useWorkspaceAssign';
import type { SubmitResult } from '@/features/workspace/useWorkspaceStep';
import { SignedOutState } from '@/shell/FrameStates';

import { assignEvidenceKind, assignNext, assignRoles } from './proposals';

import '@/features/response/response.css';
import '@/features/workspace/workspace.css';
import './rfp.css';

/** Frontend copy, not business rules. */
export const ASSIGN_PM_TEXT = {
  title: 'Assign accountable PM',
  submit: 'Assign PM',
  intro: 'Only people allowed to prepare RFPs for this workspace are listed. Who may assign is set by PSL in Setup.',
  count: (n: number) => `${n} ${n === 1 ? 'person' : 'people'} can prepare RFPs here`,
  roleLabel: 'You are assigning as',
  roleHelp: 'One of the roles PSL allows to assign RFPs',
  chooseRole: 'Choose a role to continue.',
  proof: 'Proof (optional)',
  proofChoose: 'Choose a file',
  proofBlocked: 'Remove the file that didn’t upload, or try it again.',
  nextHead: 'What happens next:',
  next: 'The PM you choose is alerted and sees it in Needs me. They start the RFP response.',
  empty: 'No one can prepare RFPs here yet.',
  notOpen: 'You can’t open this item.',
  loadFailed: 'We couldn’t load this item. Nothing was changed.',
  unconfirmedHead: 'Not confirmed',
  unconfirmed: 'We couldn’t confirm the PM was assigned. Check before trying again.',
  checkAgain: 'Check again',
  gone: 'That person can no longer be chosen.',
  // the page's own words for a 422 on a field, whatever wording the backend sends
  fieldMessage: { person_id: 'Choose a PM from the list to continue.', note: 'Check the note and try again.', acting_role: 'Choose a role you may assign as.', evidence_id: 'Remove the file, or add it again.' } as Record<string, string>,
  confirmedAfter: 'Not confirmed at first; confirmed after reading it again.',
  cancel: 'Cancel',
  close: 'Close',
} as const;

const WORDS: AssignWords = { owner: 'Accountable PM', choose: 'Choose a PM', submit: ASSIGN_PM_TEXT.submit, chooseOwner: 'Choose a PM to continue.', gone: ASSIGN_PM_TEXT.gone };
const FORM_ID = 'assign-pm-form';
const ROLE_ID = 'assign-pm-role';

export type Assigned = { reference: string; assignedTo: string; reread: boolean };

type Props = {
  workId: string;
  /** `wrote`: the Drawer ended on an assignment that was written, so the list behind it needs a re-read. */
  onClose: (wrote: boolean) => void;
  /** 200 and the item re-read: the page re-reads the list, then closes this Drawer and says so. */
  onAssigned: (done: Assigned) => Promise<void>;
};

export function AssignPmDrawer({ workId, onClose, onAssigned }: Props) {
  const router = useRouter();
  const phone = useIsPhone();
  const { fresh, lost, page } = useWorkspacePage(workId);
  const { reload } = page;
  const item = fresh?.item;
  const assign = item?.assign;
  const rfp = item?.rfp;
  // set once the person presses Assign: an item without `assign` after that is the result of a write (read-only), not a page to leave
  const [submitted, setSubmitted] = useState(false);
  // the item as it was while the item and list are read again after a 200
  const [holding, setHolding] = useState<typeof item>(undefined);
  const [rolePick, setRolePick] = useState<string>();
  const [roleError, setRoleError] = useState<string>();
  const [proofError, setProofError] = useState<string>();
  const [fieldError, setFieldError] = useState<{ evidence?: string }>({});

  useEffect(() => {
    void reload();
  }, [reload]);

  // No `assign` on the first read: this is not an item to assign here, so the page goes on to the item itself.
  const leave = item !== undefined && !assign && !submitted;
  useEffect(() => {
    if (leave) router.replace(`/work/${workId}`);
  }, [leave, router, workId]);

  const flow = useWorkspaceAssign({ id: workId, revision: item?.revision, page });
  const proofKind = assign ? assignEvidenceKind(assign) : undefined;
  const proof = useEvidenceUpload({
    caseId: item?.case_id,
    caseRevision: item?.case_revision,
    kind: proofKind,
    reloadCaseRevision: async () => (await reload())?.case_revision,
    onAccessError: page.onAccessLost,
  });

  // Held while the item and list are read again after a 200, so the form does not flip to the result before the page says so.
  const shown = holding ?? item;
  const shownAssign = shown?.assign;
  const roles = shownAssign ? assignRoles(shownAssign) : undefined;
  const picked = roles?.some((r) => r.role === rolePick) ? rolePick : undefined;
  const actingRole = roles && roles.length === 1 ? roles[0].role : (picked ?? roles?.find((r) => r.role === shownAssign?.role)?.role);

  const submit = async (request: { person_id: string; note?: string }): Promise<SubmitResult> => {
    if (!shownAssign || proof.uploading) return { kind: 'kept' };
    setSubmitted(true);
    setRoleError(undefined);
    setProofError(undefined);
    setFieldError({});
    if (roles && actingRole === undefined) {
      setRoleError(ASSIGN_PM_TEXT.chooseRole);
      requestAnimationFrame(() => document.getElementById(ROLE_ID)?.focus());
      return { kind: 'invalid', fields: { acting_role: ASSIGN_PM_TEXT.chooseRole } };
    }
    if (proof.files.some((f) => f.status !== 'uploaded')) {
      setProofError(ASSIGN_PM_TEXT.proofBlocked);
      return { kind: 'kept' };
    }
    const file = proof.files.length === 1 ? proof.files[0] : undefined;
    const body: AssignRequest = {
      ...request,
      ...(roles && actingRole !== undefined ? { acting_role: actingRole } : {}),
      ...(file?.evidenceId ? { evidence_id: file.evidenceId, case_revision: proof.caseRevision() } : {}),
    };
    setHolding(item);
    const result = await flow.submit(body);
    if (result.kind === 'done' && 'assignedTo' in result) {
      await onAssigned({ reference: shown?.reference ?? item?.reference ?? workId, assignedTo: result.assignedTo, reread: result.reread });
      return { kind: 'done' };
    }
    setHolding(undefined);
    if (result.kind === 'invalid') {
      const fields = Object.fromEntries(Object.keys(result.fields).map((name) => [name, ASSIGN_PM_TEXT.fieldMessage[name] ?? result.fields[name]]));
      if (fields.acting_role) setRoleError(fields.acting_role);
      if (fields.evidence_id) setFieldError({ evidence: fields.evidence_id });
      return { ...result, fields };
    }
    return result as SubmitResult;
  };

  const rfpWords = shown?.rfp !== undefined;
  const clientPart = rfp ? (rfp.client ?? UNKNOWN) : (item?.title ?? UNKNOWN);
  const heading = item && !lost ? `${clientPart} · ${rfp?.reference ?? item.reference}` : undefined;
  const title = rfpWords || !item ? ASSIGN_PM_TEXT.title : ASSIGN_TEXT.open;
  const busy = flow.pending || holding !== undefined;
  const wrote = item !== undefined && !assign && submitted;
  const close = () => onClose(wrote);

  let body;
  let footer;
  if (lost?.kind === 'unauthenticated') {
    body = <SignedOutState pathname={`/my-work?queue=unassigned&assign=${workId}`} />;
  } else if (lost) {
    body = (
      <>
        <p>{ASSIGN_PM_TEXT.notOpen}</p>
        <Button kind="secondary" onClick={close}>
          {ASSIGN_PM_TEXT.close}
        </Button>
      </>
    );
  } else if (!item && page.refreshFailed) {
    body = (
      <ErrorState title={ASSIGN_PM_TEXT.loadFailed} onRetry={() => void reload()}>
        Nothing was changed.
      </ErrorState>
    );
  } else if (!item || leave) {
    body = <Loading>Loading…</Loading>;
  } else if (!shownAssign) {
    // the re-read shows the assignment was written (ours, a lost reply, or someone else's)
    const name = rfp?.pm?.name;
    body = (
      <>
        <p role="status">
          Assigned to {name ?? <Unknown />}
        </p>
        {flow.notice?.kind === 'unconfirmed' && <p className="psl-hint">{ASSIGN_PM_TEXT.confirmedAfter}</p>}
        <Button kind="secondary" onClick={close}>
          {ASSIGN_PM_TEXT.close}
        </Button>
      </>
    );
  } else if (shownAssign.candidates.length === 0) {
    body = (
      <>
        <p>{ASSIGN_PM_TEXT.empty}</p>
        <Button kind="secondary" onClick={close}>
          {ASSIGN_PM_TEXT.close}
        </Button>
      </>
    );
  } else {
    const staticRole = roles ? (roles.length === 1 ? roles[0].label : undefined) : shownAssign.role;
    const next = assignNext(shownAssign);
    const unconfirmed = flow.notice?.kind === 'unconfirmed';
    const words = rfpWords ? WORDS : undefined;
    body = (
      <>
        {page.refreshFailed && (
          <Callout kind="warning">
            <span>We couldn’t refresh this item, so Assign PM stays off.</span>{' '}
            <Button kind="secondary" size="sm" onClick={() => void reload()}>
              {ASSIGN_PM_TEXT.checkAgain}
            </Button>
          </Callout>
        )}
        {flow.notice?.kind === 'stale' && <Callout kind="warning">{ASSIGN_TEXT.stale(flow.notice.revision)}</Callout>}
        {unconfirmed && (
          <Callout kind="warning">
            <strong>{ASSIGN_PM_TEXT.unconfirmedHead}</strong> <span>{ASSIGN_PM_TEXT.unconfirmed}</span>
          </Callout>
        )}
        <AssignForm
          assign={shownAssign}
          pending={busy || proof.uploading}
          words={words}
          hint={rfpWords ? ASSIGN_PM_TEXT.count(shownAssign.candidates.length) : undefined}
          formId={FORM_ID}
          actions={false}
          lead={rfpWords ? <Callout kind="info">{ASSIGN_PM_TEXT.intro}</Callout> : undefined}
          middle={
            <>
              {roles && roles.length > 1 ? (
                <div className="resp-field">
                  <Select
                    id={ROLE_ID}
                    label={ASSIGN_PM_TEXT.roleLabel}
                    hint={ASSIGN_PM_TEXT.roleHelp}
                    options={roles.map((r) => ({ value: r.role, label: r.label }))}
                    value={actingRole}
                    onChange={setRolePick}
                    placeholder="Choose a role"
                    error={roleError}
                  />
                </div>
              ) : staticRole ? (
                <div className="resp-field">
                  <span className="resp-label">{ASSIGN_PM_TEXT.roleLabel}</span>
                  <span className="resp-static">{staticRole}</span>
                  <span className="psl-hint">{ASSIGN_PM_TEXT.roleHelp}</span>
                </div>
              ) : null}
              {proofKind && (
                <div className="resp-field">
                  <ProofField proof={proof} layout="card" label={ASSIGN_PM_TEXT.proof} choose={ASSIGN_PM_TEXT.proofChoose} />
                  {(proofError ?? fieldError.evidence) && (
                    <span className="psl-error" role="alert">
                      <Icon name="warn" />
                      <span>{proofError ?? fieldError.evidence}</span>
                    </span>
                  )}
                </div>
              )}
            </>
          }
          tail={
            rfpWords ? (
              <p className="rfp-assign__next">
                <strong>{ASSIGN_PM_TEXT.nextHead}</strong> {next ? [next.summary, next.agent].filter(Boolean).join(' ') : ASSIGN_PM_TEXT.next}
              </p>
            ) : undefined
          }
          onSubmit={submit}
        />
      </>
    );
    const label = unconfirmed ? ASSIGN_TEXT.tryAgain : (words?.submit ?? ASSIGN_TEXT.submit);
    const off = busy || proof.uploading || page.refreshFailed;
    footer = (
      <>
        {!phone && (
          <Button kind="secondary" onClick={close}>
            {ASSIGN_PM_TEXT.cancel}
          </Button>
        )}
        <Button type="submit" form={FORM_ID} kind="start" size={phone ? 'lg' : 'md'} block={phone} busy={busy} busyLabel="Assigning…" aria-disabled={off || undefined}>
          {label}
        </Button>
      </>
    );
  }

  return (
    <Drawer className="rfp-assign" keepTop title={title} eyebrow={phone ? undefined : heading} subline={phone ? heading : undefined} onClose={close} footer={footer}>
      <div className="rfp-assign__body">{body}</div>
    </Drawer>
  );
}
