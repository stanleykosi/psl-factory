'use client';

// SCR-12 Money tab: each item of GET /projects/{case_id}/money in the order sent (a table on desktop, cards on phones)
// and, for a pressed amount, where that figure comes from (`?figure=<key>`: an aside on desktop, a bottom sheet on
// phones). `?figure=<key>` names the figure so it can be linked and reloaded. Reads only: nothing here totals, rounds,
// infers or decides; the backend decides access (INV-ACCESS).
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState, type ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import { BottomSheet, Callout, EmptyState, ErrorState, Link, Loading, Panel, Table, useIsPhone, When, type Column } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { InvoiceCell, PaidCell, Value } from './MoneyCells';
import { amountText, stageLabel, type MoneyItem, type MoneySource } from './moneyModel';
import { useMoney, type FigureState } from './useMoney';

import './money.css';

const PROMPT = 'Choose an amount to see where it comes from.';
const NO_SOURCE = 'No source recorded';
const refused = (error: ApiError) => error.kind === 'forbidden' || error.kind === 'not_found';

type Pick = {
  base: string;
  selectedKey: string | undefined;
  onPress: () => void;
  amountRef: (key: string) => (el: HTMLAnchorElement | null) => void;
};

/** The amount, a link to its figure when it is known or has sources; the backend's reason under an Unknown one. */
function AmountCell({ item, pick }: { item: MoneyItem; pick: Pick }) {
  const text = amountText(item.amount, item.currency);
  const amount =
    text !== undefined || item.sources.length > 0 ? (
      <Link
        ref={pick.amountRef(item.key)}
        href={`${pick.base}/money?figure=${encodeURIComponent(item.key)}`}
        replace
        scroll={false}
        aria-current={pick.selectedKey === item.key ? 'true' : undefined}
        className="money__amountlink"
        onClick={pick.onPress}
      >
        <Value text={text} />
      </Link>
    ) : (
      <span className="money__amount">
        <Value text={text} />
      </span>
    );
  return (
    <>
      {amount}
      {text === undefined && item.missing_reason && <span className="money__note">{item.missing_reason}</span>}
    </>
  );
}

function SourceItem({ source }: { source: MoneySource }) {
  return (
    <li>
      {source.label}
      {source.reference && <> <span className="money__ref">{source.reference}</span></>}
      {source.kind && <> · {source.kind}</>}
      {source.at && (
        <>
          {' · '}
          <When value={source.at} show="daytime" />
        </>
      )}
    </li>
  );
}

/** The figure's sources in the order sent; else "No source recorded". */
function Sources({ item }: { item: MoneyItem }) {
  if (item.sources.length === 0) return <p className="money__plain">{NO_SOURCE}</p>;
  return (
    <ol className="money__sources">
      {item.sources.map((s, i) => (
        <SourceItem key={`${s.label}-${i}`} source={s} />
      ))}
    </ol>
  );
}

/** The drill-down's head: the chosen item's label, the prompt when none is chosen. */
function headOf(figure: FigureState, selectedKey: string | undefined, items: MoneyItem[]): string {
  if (selectedKey === undefined) return PROMPT;
  if (figure.status === 'ready') return figure.item.label;
  return items.find((i) => i.key === selectedKey)?.label ?? 'Where this figure comes from';
}

/** The drill-down body, the same in the aside and the sheet. */
function Explanation({ figure, onRetry }: { figure: FigureState; onRetry: () => void }) {
  if (figure.status === 'idle') return null;
  if (figure.status === 'loading') return <Loading>Loading sources…</Loading>;
  if (figure.status === 'missing') return <p className="money__plain">That figure isn&rsquo;t available.</p>;
  if (figure.status === 'error') {
    if (refused(figure.error)) return <p className="money__plain">You can&rsquo;t see where this figure comes from.</p>;
    return (
      <ErrorState title="We couldn’t load where this figure comes from." retryLabel="Try again" onRetry={onRetry}>
        Your work is safe; nothing was changed.
      </ErrorState>
    );
  }
  return <Sources item={figure.item} />;
}

function Drilldown({ figure, head, onRetry }: { figure: FigureState; head: string; onRetry: () => void }) {
  return (
    <Panel as="aside" kind="agent" head={head} className="money__aside" headClassName="money__asidehead" bodyClassName="money__asidebody">
      <div className="money__explain">
        <Explanation figure={figure} onRetry={onRetry} />
      </div>
    </Panel>
  );
}

function StageTable({ items, pick }: { items: MoneyItem[]; pick: Pick }) {
  const columns: Column<MoneyItem>[] = [
    { key: 'stage', header: 'STAGE', cell: (item) => (item.contract_stage ? stageLabel(item) : item.label) },
    { key: 'amount', header: 'AMOUNT', cell: (item) => <AmountCell item={item} pick={pick} /> },
    { key: 'invoice', header: 'INVOICE', cell: (item) => <InvoiceCell item={item} /> },
    { key: 'paid', header: 'PAID', cell: (item) => <PaidCell item={item} /> },
  ];
  return <Table caption="Billing by contract stage" columns={columns} rows={items} rowKey={(item) => item.key} empty="No contract stages yet" className="money__table" />;
}

function StageCards({ items, pick }: { items: MoneyItem[]; pick: Pick }) {
  return (
    <ol className="money__cards" aria-label="Billing by contract stage">
      {items.map((item) => (
        <li key={item.key} className="money__card">
          <span className="money__stage">{item.contract_stage ? stageLabel(item) : item.label}</span>
          <AmountCell item={item} pick={pick} />
          <span className="money__line">
            <InvoiceCell item={item} />
          </span>
          <span className="money__line">
            <PaidCell item={item} />
          </span>
        </li>
      ))}
    </ol>
  );
}

/** A 403 or 404 on the money read (Conflicts 14, Option B): the project's name stays in the header above, so the
 *  line says only that its money is not shown. No stage, amount, report title or server message appears. */
function MoneyNoAccess() {
  return (
    <section className="psl-panel money__noaccess" aria-label="No access">
      <div className="psl-panel__body">
        <p className="money__plain">You can&rsquo;t see this project&rsquo;s money.</p>
      </div>
    </section>
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
  const params = useSearchParams();
  const selectedKey = params.get('figure') ?? undefined;
  const { money, figure, retryMoney, retryFigure } = useMoney(caseId, selectedKey);
  const phone = useIsPhone();
  const router = useRouter();
  const [pressed, setPressed] = useState(false);
  const amounts = useRef(new Map<string, HTMLAnchorElement>());
  const returnFocus = useRef<HTMLAnchorElement | null>(null);

  useEffect(() => {
    // Kept after the sheet closes, so focus can go back to the amount that opened it.
    if (selectedKey !== undefined && amounts.current.has(selectedKey)) returnFocus.current = amounts.current.get(selectedKey) ?? null;
  });

  if (money.status === 'loading') return <LoadingState />;
  if ((money.status === 'error' && money.error.kind === 'unauthenticated') || (figure.status === 'error' && figure.error.kind === 'unauthenticated')) {
    return <SignedOutState pathname={`${base}/money`} />;
  }
  if (money.status === 'error') {
    if (refused(money.error)) return <MoneyNoAccess />;
    return <WorkErrorCard message="We couldn’t load this project’s money. Your work is safe; nothing was changed." error={money.error} onRetry={() => void retryMoney()} />;
  }

  const { items, limited, as_of: asOf } = money.money;
  if (items.length === 0) {
    return (
      <EmptyState level={2} title="No contract stages yet" className="money__empty">
        Stages appear here once the SOW is signed.
      </EmptyState>
    );
  }

  const pick: Pick = {
    base,
    selectedKey,
    onPress: () => setPressed(true),
    amountRef: (key) => (el) => {
      if (el) amounts.current.set(key, el);
      else amounts.current.delete(key);
    },
  };
  const head = headOf(figure, selectedKey, items);
  const incomplete = limited && <Callout kind="warning">Some figures may be incomplete.</Callout>;
  const explanation: ReactNode = <Explanation figure={figure} onRetry={retryFigure} />;

  if (phone) {
    return (
      <>
        {incomplete}
        <StageCards items={items} pick={pick} />
        <p className="money__hint">Tap an amount to see where it comes from</p>
        <AsOf value={asOf} />
        {selectedKey !== undefined && (
          <BottomSheet title={head} returnFocus={returnFocus} onClose={() => router.replace(`${base}/money`, { scroll: false })}>
            <div className="money__explain">{explanation}</div>
          </BottomSheet>
        )}
      </>
    );
  }

  return (
    <>
      <div className="money__intro">
        <p className="money__lead">Every figure links to the record it came from. Unknown amounts are shown as Unknown, never as 0.</p>
      </div>
      {incomplete}
      <div className="money__body">
        <div className="money__main">
          <StageTable items={items} pick={pick} />
          <AsOf value={asOf} />
        </div>
        <Drilldown figure={figure} head={head} onRetry={retryFigure} />
      </div>
      <p className="cmp-sr" aria-live="polite">
        {pressed && figure.status === 'ready' ? `Showing where ${figure.item.label} comes from` : ''}
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
