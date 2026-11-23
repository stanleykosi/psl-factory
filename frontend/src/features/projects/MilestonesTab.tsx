'use client';

// SCR-38 Milestones: the contract stages of /money (amount, completion, invoice and paid as separate facts), then the
// recorded completions of /milestones as their own list. A change sits beside the stage it changes; its amount is shown
// next to the contract amount and never added to it. A stage is tied to a completion only through `milestone_id`.
import { Button, Callout, Table, Tag, useIsPhone, VisuallyHidden, When, type Column } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { InvoiceCell, PaidCell, Value } from './MoneyCells';
import { changeText, completedText, completionFor, completionText, contractAmount, contractStages, dueText, hasChanges, recordedByText, type CompletionRow } from './milestonesModel';
import { stageLabel, type MoneyItem } from './moneyModel';
import { AsOf, NONE, TabEmpty } from './TabParts';
import { useMilestones, type ProofState } from './useMilestones';

const NO_FINANCE = 'Contract amounts, invoices and payments aren’t available to your role.';

type Proofs = { proofs: Record<string, ProofState>; press: (slot: string, id: number) => void };

/** "Proof" for one recorded completion; pressing it reads that completion once and shows the answer under the button. */
function Proof({ slot, id, label, proofs }: { slot: string; id: number; label: string; proofs: Proofs }) {
  const phone = useIsPhone();
  const state = proofs.proofs[slot];
  return (
    <span className="ptabs__proof">
      <Button kind="secondary" size={phone ? 'md' : 'sm'} busy={state?.status === 'loading'} busyLabel="Loading…" onClick={() => proofs.press(slot, id)}>
        Proof<VisuallyHidden> for {label}</VisuallyHidden>
      </Button>
      {state?.status === 'ready' && (
        <span className="ptabs__proofbody" role="status">
          <strong>{state.completion.name}</strong>
          <span>{completedText(state.completion)}</span>
          <span>Proof version {state.completion.proof_version}</span>
        </span>
      )}
      {state?.status === 'refused' && (
        <span className="ptabs__proofbody" role="status">
          Proof isn&rsquo;t available to your role.
        </span>
      )}
      {state?.status === 'error' && (
        <span className="ptabs__proofbody" role="alert">
          We couldn&rsquo;t load the proof.
          <Button kind="link" onClick={() => proofs.press(slot, id)}>
            Try again
          </Button>
        </span>
      )}
    </span>
  );
}

/** "NGN 4,250,000.00 + the change · change amount Unknown": both values as sent, never a sum. */
function AmountCell({ item }: { item: MoneyItem }) {
  return (
    <>
      <Value text={contractAmount(item)} />
      {item.changes.map((change) => (
        <span key={change.link_id}>
          {' + the change · change amount '}
          <Value text={undefined} />
        </span>
      ))}
    </>
  );
}

/** Done or not, the due date, who recorded it (only through `milestone_id`), and Proof where a completion is linked. */
function CompletionCell({ item, rows, proofs }: { item: MoneyItem; rows: CompletionRow[]; proofs: Proofs }) {
  const match = completionFor(item, rows);
  const by = match ? recordedByText(match) : undefined;
  const due = dueText(item);
  return (
    <>
      <span className="ptabs__block">{completionText(item)}</span>
      {due && <span className="ptabs__block ptabs__hint">{due}</span>}
      {by && <span className="ptabs__block ptabs__hint">{by}</span>}
      {item.completed_at !== null && item.milestone_id !== null && <Proof slot={`stage-${item.key}`} id={item.milestone_id} label={item.label} proofs={proofs} />}
    </>
  );
}

function ChangesCell({ item }: { item: MoneyItem }) {
  if (item.changes.length === 0) return NONE;
  return (
    <>
      {item.changes.map((change) => (
        <span key={change.link_id} className="ptabs__block">
          {changeText(change)}
        </span>
      ))}
    </>
  );
}

function columns(items: MoneyItem[], rows: CompletionRow[], proofs: Proofs): Column<MoneyItem>[] {
  const base: Column<MoneyItem>[] = [
    { key: 'name', header: 'MILESTONE', cell: (item) => stageLabel(item) },
    { key: 'amount', header: 'CONTRACT AMOUNT', cell: (item) => <AmountCell item={item} /> },
    { key: 'completion', header: 'COMPLETION', cell: (item) => <CompletionCell item={item} rows={rows} proofs={proofs} /> },
    { key: 'invoice', header: 'INVOICE', cell: (item) => <InvoiceCell item={item} /> },
    { key: 'paid', header: 'PAID', cell: (item) => <PaidCell item={item} /> },
  ];
  return hasChanges(items) ? [...base, { key: 'changes', header: 'CHANGES', cell: (item) => <ChangesCell item={item} /> }] : base;
}

/** SCR-38 phone: one card per stage in the order returned. */
function MilestoneCards({ items, rows, proofs }: { items: MoneyItem[]; rows: CompletionRow[]; proofs: Proofs }) {
  return (
    <div role="list" className="ptabs__cards">
      {items.map((item) => (
        <div key={item.key} role="listitem" className="ptabs__card">
          <strong>{stageLabel(item)}</strong>
          <span className="ptabs__cardmain">
            <AmountCell item={item} />
          </span>
          <span className="ptabs__cardmain">
            <CompletionCell item={item} rows={rows} proofs={proofs} />
          </span>
          <span className="ptabs__cardnote">
            <InvoiceCell item={item} />
          </span>
          <span className="ptabs__cardnote">
            <PaidCell item={item} />
          </span>
          {item.changes.map((change) => (
            <Tag key={change.link_id} tone="waiting" className="ptabs__changed">
              CHANGED · {change.reference}
            </Tag>
          ))}
        </div>
      ))}
    </div>
  );
}

/** One recorded completion: what was completed, its state, when, and who recorded it. */
function CompletionItem({ row, proofs }: { row: CompletionRow; proofs: Proofs }) {
  return (
    <li className="ptabs__completion">
      <strong>{row.title}</strong>
      <span>{row.state}</span>
      {row.at && <When value={row.at} show="daytime" />}
      <span className="ptabs__hint">{recordedByText(row) ?? 'Recorded by: not shown'}</span>
      <Proof slot={`done-${row.record_id}`} id={row.record_id} label={row.title} proofs={proofs} />
    </li>
  );
}

export function MilestonesTab({ caseId, pathname }: { caseId: string; pathname: string }) {
  const phone = useIsPhone();
  const { money, completions, more, proofs, retryMoney, retryCompletions, showMore, readProof } = useMilestones(caseId);
  const proof: Proofs = { proofs, press: (slot, id) => void readProof(slot, id) };

  if (money.status === 'loading' || completions.status === 'loading') return <LoadingState />;
  const signedOut = (money.status === 'error' && money.error.kind === 'unauthenticated') || (completions.status === 'error' && completions.error.kind === 'unauthenticated');
  if (signedOut) return <SignedOutState pathname={pathname} />;

  const refusedMoney = money.status === 'error' && (money.error.kind === 'forbidden' || money.error.kind === 'not_found');
  const refusedCompletions = completions.status === 'error' && (completions.error.kind === 'forbidden' || completions.error.kind === 'not_found');
  const rows = completions.status === 'ready' ? completions.rows : [];
  const stages = money.status === 'ready' ? contractStages(money.money.items) : [];
  const asOf = money.status === 'ready' ? money.money.as_of : completions.status === 'ready' ? completions.asOf : undefined;

  return (
    <>
      {money.status === 'ready' && money.money.limited && <Callout kind="warning">Some figures may be incomplete.</Callout>}
      <div className="ptabs__rows">
        {money.status === 'ready' &&
          (stages.length === 0 ? (
            <TabEmpty>No milestones on this project yet.</TabEmpty>
          ) : phone ? (
            <MilestoneCards items={stages} rows={rows} proofs={proof} />
          ) : (
            <Table className="ptabs__table" tableClassName={hasChanges(stages) ? 'ptabs__ms ptabs__ms--6' : 'ptabs__ms ptabs__ms--5'} caption="Milestones" columns={columns(stages, rows, proof)} rows={stages} rowKey={(item) => item.key} empty="No milestones on this project yet." />
          ))}
        {refusedMoney && <p className="ptabs__note">{NO_FINANCE}</p>}
        {money.status === 'error' && !refusedMoney && <WorkErrorCard message="We couldn’t load this project’s milestones. Your work is safe; nothing was changed." error={money.error} onRetry={() => void retryMoney()} />}
      </div>
      {completions.status === 'ready' && (
        <section className="ptabs__completions" aria-labelledby="ptabs-completions">
          <h2 id="ptabs-completions" className="ptabs__subhead">
            Recorded completions
          </h2>
          {rows.length === 0 ? (
            <p className="ptabs__note">No completions recorded yet.</p>
          ) : (
            <ul className="ptabs__completionlist">
              {rows.map((row) => (
                <CompletionItem key={row.record_id} row={row} proofs={proof} />
              ))}
            </ul>
          )}
          {more === 'error' && (
            <p className="ptabs__note" role="alert">
              We couldn&rsquo;t load more. Choose Show more to try again.
            </p>
          )}
          {completions.hasMore && (
            <Button kind="secondary" size="sm" busy={more === 'loading'} busyLabel="Loading…" onClick={() => void showMore()}>
              Show more
            </Button>
          )}
        </section>
      )}
      {completions.status === 'error' && !refusedCompletions && <WorkErrorCard message="We couldn’t load the recorded completions. Your work is safe; nothing was changed." error={completions.error} onRetry={() => void retryCompletions()} />}
      {asOf !== undefined && <AsOf value={asOf} />}
      {money.status === 'ready' && (
        <p className="ptabs__note">
          Milestones and amounts come from the signed SOW. Completing a milestone is the PM&rsquo;s fact; invoicing and payment are Finance&rsquo;s, and each is shown separately.
        </p>
      )}
    </>
  );
}
