'use client';

// SCR-12 Money tab: each contract stage's amount, invoice and paid state exactly as E-PROJECT-TAB sends them (a table
// on desktop, cards on phones) and, for a pressed amount, where that figure comes from in E-REPORT (an aside on
// desktop, a bottom sheet on phones). `?figure=<id>` names the figure so it can be linked and reloaded. Reads only:
// nothing here totals, rounds, infers or decides; the backend decides access (INV-ACCESS).
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState, type ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import { AgentAvatar, AGENTS, BottomSheet, Callout, EmptyState, ErrorState, Link, Loading, Panel, Table, Unknown, useIsPhone, VisuallyHidden, When, type Column } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { amountText, figureOf, figureTitle, invoiceText, paidWords, valuesDiffer, type Figure, type MoneyRow, type MoneyValue, type Paid, type Report, type SourceDetail } from './moneyModel';
import { ProjectNoAccess } from './ProjectStates';
import { useMoney, type ReportState } from './useMoney';

import './money.css';

const PROMPT = 'Choose an amount to see where it comes from.';
const NO_SOURCE = 'No source recorded';

/** A value as text, or the amber Unknown when the backend does not know it (never 0, never blank). */
function Value({ value }: { value: MoneyValue }) {
  const text = amountText(value);
  return text ? <>{text}</> : <Unknown />;
}

/** "Paid", "Part paid · ₦1,250,000.00 owed", "Not paid · owed Unknown"; `not_due` is a dash read as "Not due".
 *  No paid object reads Unknown. Never worked out from the invoice (INV-FACTS). */
function PaidText({ paid }: { paid: Paid | undefined }) {
  if (!paid) return <Unknown />;
  const words =
    paid.status === 'unknown' ? (
      <Unknown />
    ) : paid.status === 'not_due' ? (
      <>
        <span aria-hidden="true">—</span>
        <VisuallyHidden>Not due</VisuallyHidden>
      </>
    ) : (
      paidWords(paid.status)
    );
  if (!paid.owed) return <>{words}</>;
  const owed = amountText(paid.owed);
  return (
    <>
      {words} · {owed ? `${owed} owed` : <>owed <Unknown /></>}
    </>
  );
}

/** The backend's composed invoice status (else its reference), linked to the invoice's work item when it has one. */
function InvoiceText({ row }: { row: MoneyRow }) {
  const text = invoiceText(row);
  if (!text) {
    return (
      <>
        <span aria-hidden="true">—</span>
        <VisuallyHidden>No invoice</VisuallyHidden>
      </>
    );
  }
  const reference = row.invoice?.reference;
  const hidden = row.invoice_status && reference ? <VisuallyHidden>, {reference}</VisuallyHidden> : null;
  if (!row.invoice?.work_id) return <>{text}</>;
  return (
    <Link href={`/work/${encodeURIComponent(row.invoice.work_id)}`}>
      {text}
      {hidden}
    </Link>
  );
}

type Pick = {
  base: string;
  report: Report | undefined;
  selectedId: string | undefined;
  onPress: () => void;
  amountRef: (id: string) => (el: HTMLAnchorElement | null) => void;
};

/** The amount, a link to its figure only when the loaded report has that figure; then the backend's note under it. */
function AmountCell({ row, pick }: { row: MoneyRow; pick: Pick }) {
  const figure = figureOf(pick.report, row.figure_id);
  const text = amountText(row.amount);
  const amount =
    figure && text ? (
      <Link
        ref={pick.amountRef(figure.id!)}
        href={`${pick.base}/money?figure=${encodeURIComponent(figure.id!)}`}
        replace
        scroll={false}
        aria-current={pick.selectedId === figure.id ? 'true' : undefined}
        className="money__amountlink"
        onClick={pick.onPress}
      >
        {text}
      </Link>
    ) : (
      <span className="money__amount">
        <Value value={row.amount} />
      </span>
    );
  return (
    <>
      {amount}
      {row.amount_note && <span className="money__note">{row.amount_note}</span>}
    </>
  );
}

function SourceItem({ source }: { source: SourceDetail }) {
  // Only a work item has a page; a document has no route yet, and a rule or record without an id is text.
  const label = source.work_id ? <Link href={`/work/${encodeURIComponent(source.work_id)}`}>{source.label}</Link> : source.label;
  return (
    <li>
      {label} <span className="money__ref">{source.reference}</span>
    </li>
  );
}

/** The figure's own sources in the order sent; the plain `sources` strings when no details; else "No source recorded". */
function Sources({ figure }: { figure: Figure | undefined }) {
  if (figure?.source_details && figure.source_details.length > 0) {
    return (
      <ol className="money__sources">
        {figure.source_details.map((s, i) => (
          <SourceItem key={`${s.reference}-${i}`} source={s} />
        ))}
      </ol>
    );
  }
  if (figure && figure.sources.length > 0) {
    return (
      <ol className="money__sources">
        {figure.sources.map((s, i) => (
          <li key={`${s}-${i}`}>{s}</li>
        ))}
      </ol>
    );
  }
  return <p className="money__plain">{NO_SOURCE}</p>;
}

/** Chidi's card when the report names an agent and /me lists the Assistant; the link carries no figure (G-SCR12-2). */
function AgentCard({ report }: { report: Report | undefined }) {
  const me = useMe();
  if (!report?.agent) return null;
  const { name, role } = AGENTS[report.agent];
  return (
    <div className="money__agent">
      <AgentAvatar agent={report.agent} size={40} />
      <span>
        <strong>{name}</strong> · {role}
        {me.destinations.includes('assistant') && (
          <>
            <br />
            <Link href={`/assistant?agent=${report.agent}`}>Ask me</Link> about any figure here.
          </>
        )}
      </span>
    </div>
  );
}

const reportOf = (state: ReportState) => (state.status === 'ready' ? state.report : undefined);
const refused = (error: ApiError) => error.kind === 'forbidden' || error.kind === 'not_found';

/** The drill-down's head: the figure's own value when one is chosen, the prompt when the report can be pressed. */
function headOf(state: ReportState, selectedId: string | undefined): string {
  if (selectedId !== undefined) return figureTitle(figureOf(reportOf(state), selectedId));
  return state.status === 'ready' ? PROMPT : 'Where these figures come from';
}

/** The drill-down body, the same in the aside and the sheet. */
function Explanation({ state, rows, selectedId, onRetry, label = false }: { state: ReportState; rows: MoneyRow[]; selectedId: string | undefined; onRetry: () => void; label?: boolean }) {
  if (state.status === 'loading') return <Loading>Loading sources…</Loading>;
  if (state.status === 'error') {
    if (refused(state.error)) return <p className="money__plain">You can&rsquo;t see where these figures come from.</p>;
    return (
      <ErrorState title="We couldn’t load where these figures come from." retryLabel="Try again" onRetry={onRetry}>
        Your work is safe; nothing was changed.
      </ErrorState>
    );
  }
  const report = reportOf(state);
  if (selectedId === undefined) return report ? null : <p className="money__plain">{NO_SOURCE}</p>;
  const figure = figureOf(report, selectedId);
  const row = rows.find((r) => r.figure_id === selectedId);
  return (
    <>
      {label && figure && <VisuallyHidden>{figure.label}</VisuallyHidden>}
      {figure && !amountText(figure.value) && (
        <p className="money__plain">
          Amount: <Unknown />
        </p>
      )}
      {figure && row && valuesDiffer(row.amount, figure.value) && (
        <Callout kind="warning">
          These figures differ: the table shows <Value value={row.amount} />; the report shows <Value value={figure.value} />.
        </Callout>
      )}
      <Sources figure={figure} />
    </>
  );
}

function Drilldown({ state, rows, selectedId, onRetry }: { state: ReportState; rows: MoneyRow[]; selectedId: string | undefined; onRetry: () => void }) {
  // Two stages can share an amount, so the figure's label is part of the aside's name.
  const label = selectedId !== undefined ? figureOf(reportOf(state), selectedId)?.label : undefined;
  const head = (
    <>
      {headOf(state, selectedId)}
      {label && <VisuallyHidden>, {label}</VisuallyHidden>}
    </>
  );
  return (
    <Panel as="aside" kind="agent" head={head} className="money__aside" headClassName="money__asidehead" bodyClassName="money__asidebody">
      <div className="money__explain">
        <Explanation state={state} rows={rows} selectedId={selectedId} onRetry={onRetry} />
      </div>
      <AgentCard report={reportOf(state)} />
    </Panel>
  );
}

function StageTable({ rows, pick }: { rows: MoneyRow[]; pick: Pick }) {
  const columns: Column<MoneyRow>[] = [
    { key: 'stage', header: 'STAGE', cell: (row) => row.stage },
    { key: 'amount', header: 'AMOUNT', cell: (row) => <AmountCell row={row} pick={pick} /> },
    { key: 'invoice', header: 'INVOICE', cell: (row) => <InvoiceText row={row} /> },
    { key: 'paid', header: 'PAID', cell: (row) => <PaidText paid={row.paid} /> },
  ];
  return <Table caption="Billing by contract stage" columns={columns} rows={rows} rowKey={(row) => `${row.position}-${row.stage}`} empty="No contract stages yet" className="money__table" />;
}

function StageCards({ rows, pick }: { rows: MoneyRow[]; pick: Pick }) {
  return (
    <ol className="money__cards" aria-label="Billing by contract stage">
      {rows.map((row) => {
        const invoice = invoiceText(row);
        return (
          <li key={`${row.position}-${row.stage}`} className="money__card">
            <span className="money__stage">{row.stage}</span>
            <AmountCell row={row} pick={pick} />
            {invoice ? (
              <span className="money__line">
                <InvoiceText row={row} />
              </span>
            ) : (
              <VisuallyHidden>No invoice</VisuallyHidden>
            )}
            {row.paid?.status !== 'not_due' && (
              <span className="money__line">
                Paid · <PaidText paid={row.paid} />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function AsOf({ value }: { value: string | undefined }) {
  return (
    <p className="money__asof">
      As of <When value={value} show="daytime" />
    </p>
  );
}

function MoneyContent({ caseId, base }: { caseId: string; base: string }) {
  const { money, report, retryMoney, retryReport } = useMoney(caseId);
  const phone = useIsPhone();
  const router = useRouter();
  const params = useSearchParams();
  const selectedId = params.get('figure') ?? undefined;
  const [pressed, setPressed] = useState(false);
  const amounts = useRef(new Map<string, HTMLAnchorElement>());
  const returnFocus = useRef<HTMLAnchorElement | null>(null);

  useEffect(() => {
    // Kept after the sheet closes, so focus can go back to the amount that opened it.
    if (selectedId !== undefined && amounts.current.has(selectedId)) returnFocus.current = amounts.current.get(selectedId) ?? null;
  });

  if (money.status === 'loading') return <LoadingState />;
  const reportError = report.status === 'error' ? report.error : undefined;
  if ((money.status === 'error' && money.error.kind === 'unauthenticated') || reportError?.kind === 'unauthenticated') {
    return <SignedOutState pathname={`${base}/money`} />;
  }
  if (money.status === 'error') {
    if (refused(money.error)) return <ProjectNoAccess />;
    return <WorkErrorCard message="We couldn’t load this project’s money. Your work is safe; nothing was changed." error={money.error} onRetry={() => void retryMoney()} />;
  }

  const { rows, asOf } = money.view;
  if (rows.length === 0) {
    return (
      <EmptyState level={2} title="No contract stages yet" className="money__empty">
        Stages appear here once the SOW is signed.
      </EmptyState>
    );
  }

  const loaded = reportOf(report);
  const pick: Pick = {
    base,
    report: loaded,
    selectedId,
    onPress: () => setPressed(true),
    amountRef: (id) => (el) => {
      if (el) amounts.current.set(id, el);
      else amounts.current.delete(id);
    },
  };
  const anyLinked = rows.some((row) => figureOf(loaded, row.figure_id) !== undefined && amountText(row.amount) !== undefined);
  const title = loaded && <h2 className="money__title">{loaded.title}</h2>;
  const explanation: ReactNode = <Explanation state={report} rows={rows} selectedId={selectedId} onRetry={retryReport} label />;

  if (phone) {
    return (
      <>
        {title}
        <StageCards rows={rows} pick={pick} />
        {anyLinked && <p className="money__hint">Tap an amount to see where it comes from</p>}
        <AsOf value={asOf} />
        {selectedId !== undefined && (
          <BottomSheet title={headOf(report, selectedId)} returnFocus={returnFocus} onClose={() => router.replace(`${base}/money`, { scroll: false })}>
            <div className="money__explain">{explanation}</div>
            <AgentCard report={loaded} />
          </BottomSheet>
        )}
      </>
    );
  }

  const figure = figureOf(loaded, selectedId);
  return (
    <>
      <div className="money__intro">
        {title}
        <p className="money__lead">Every figure links to the record it came from. Unknown amounts are shown as Unknown, never as 0.</p>
      </div>
      <div className="money__body">
        <div className="money__main">
          <StageTable rows={rows} pick={pick} />
          <AsOf value={asOf} />
        </div>
        <Drilldown state={report} rows={rows} selectedId={selectedId} onRetry={retryReport} />
      </div>
      <p className="cmp-sr" aria-live="polite">
        {pressed && figure ? `Showing ${figureTitle(figure).replace(/^Where/, 'where')}` : ''}
      </p>
    </>
  );
}

/** /projects/<case_id>/money inside the project page's tab panel. */
export function MoneyTab({ caseId, base }: { caseId: string; base: string }) {
  // useSearchParams needs a Suspense boundary so `next build` can prerender the route.
  return (
    <Suspense fallback={<LoadingState />}>
      <MoneyContent caseId={caseId} base={base} />
    </Suspense>
  );
}
