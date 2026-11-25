'use client';

// SCR-20 Payments and follow-up: the invoices the live GET /payments returns for this person, in returned order. Billed,
// received and still owed are three separate amounts; the status, days overdue and totals are the backend's. The page adds,
// filters and counts nothing itself (INV-UNKNOWN, D-94), reads no /me and decides nothing about access. Recording a payment
// is not on this page: the action is a link to the returned address or its disabled form (FE-PAYMENTS-RECEIPT, held).
import NextLink from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  Button,
  buttonClass,
  EmptyState,
  FilterPanel,
  ListToolbar,
  PageTitle,
  RadioGroup,
  SEARCH_MIN_CHARS,
  Table,
  Tag,
  Unknown,
  useIsPhone,
  VisuallyHidden,
  type Column,
} from '@/components';
import { tagTone } from '@/features/workspace/labels';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import {
  coverageText,
  dataDate,
  figureText,
  filterLabel,
  linkOf,
  monthName,
  NOT_AVAILABLE,
  overdueText,
  overdueValues,
  owedValues,
  parseQuery,
  PAYMENTS_PATH,
  querySearch,
  receivedValues,
  STATES,
  STATUS_TONE,
  UNKNOWN,
  workText,
  type StripValue,
} from './model';
import type { InvoiceList, InvoiceQuery, InvoiceRow } from './types';
import { usePayments } from './usePayments';

import './payments.css';

const ANY = '';

/** A row amount with its currency and basis, or the amber Unknown with "amount not known" spoken; never 0 for a missing value. */
function AmountValue({ amount, row }: { amount: string | null; row: InvoiceRow }) {
  const text = figureText(amount, row.currency, row.basis);
  if (text === undefined) {
    return (
      <>
        <Unknown />
        <VisuallyHidden> amount not known</VisuallyHidden>
      </>
    );
  }
  return <>{text}</>;
}

/** The status chip with the backend's label; its reason, when there is one, is the helper text under it. */
function StateTag({ row }: { row: InvoiceRow }) {
  return (
    <>
      <Tag tone={tagTone(STATUS_TONE[row.status])} className="payments__tag">
        {row.label}
      </Tag>
      {row.reason && <span className="payments__reason">{row.reason}</span>}
    </>
  );
}

function Overdue({ row }: { row: InvoiceRow }) {
  const text = overdueText(row);
  return text === UNKNOWN ? <Unknown /> : <>{text}</>;
}

/** The reference: a link to the returned records address when it is a path, else plain text. It takes focus after Show more. */
function Reference({ row }: { row: InvoiceRow }) {
  const href = linkOf(row.records_url);
  if (href) {
    return (
      <a href={href} className="psl-mono" data-invoice-row="">
        {row.reference}
      </a>
    );
  }
  return (
    <span className="psl-mono payments__ref" tabIndex={-1} data-invoice-row="">
      {row.reference}
    </span>
  );
}

/** Open the reminder, Record a payment, Review the payment: a plain link to the returned address, or its disabled form with the reason. */
function Actions({ row }: { row: InvoiceRow }) {
  const reasonId = `payments-why-${row.invoice_id}`;
  const actions = [
    { key: 'reminder', label: 'Open the reminder', href: linkOf(row.reminder_url), extra: row.has_reminder_draft ? 'Draft ready' : undefined },
    { key: 'record', label: 'Record a payment', href: linkOf(row.record_payment_url) },
    { key: 'review', label: 'Review the payment', href: linkOf(row.review_payment_url) },
  ];
  return (
    <span className="payments__actions">
      {actions.map((action) =>
        action.href ? (
          <span key={action.key} className="payments__action">
            <a href={action.href}>{action.label}</a>
            {action.extra && <span className="payments__draft">{action.extra}</span>}
          </span>
        ) : (
          <span key={action.key} className="payments__action payments__action--off" aria-disabled="true" aria-describedby={reasonId}>
            {action.label}
          </span>
        ),
      )}
      {actions.some((action) => !action.href) && (
        <span id={reasonId} className="payments__why">
          {NOT_AVAILABLE}
        </span>
      )}
    </span>
  );
}

const COLUMNS: Column<InvoiceRow>[] = [
  { key: 'invoice', header: 'INVOICE', cell: (row) => <Reference row={row} /> },
  { key: 'work', header: 'WORK', cell: workText },
  { key: 'billed', header: 'BILLED', cell: (row) => <AmountValue amount={row.face} row={row} /> },
  { key: 'received', header: 'RECEIVED', cell: (row) => <AmountValue amount={row.paid} row={row} /> },
  {
    key: 'owed',
    header: 'STILL OWED',
    cell: (row) => (
      <strong>
        <AmountValue amount={row.owed} row={row} />
      </strong>
    ),
  },
  { key: 'state', header: 'STATE', cell: (row) => <StateTag row={row} /> },
  { key: 'overdue', header: 'OVERDUE BY', cell: (row) => <Overdue row={row} /> },
  { key: 'actions', header: '', cell: (row) => <Actions row={row} /> },
];

function MoreButton({ more, onMore }: { more: 'idle' | 'loading' | 'error'; onMore: () => void }) {
  return (
    <div className="payments__more">
      {more === 'error' && <p role="alert">We couldn’t load more invoices. The ones above are still here.</p>}
      <Button kind="secondary" disabled={more === 'loading'} onClick={onMore}>
        {more === 'error' ? 'Try again' : 'Show more'}
      </Button>
    </div>
  );
}

function InvoiceTable({ items }: { items: InvoiceRow[] }) {
  return <Table className="payments__table" caption="Invoices" columns={COLUMNS} rows={items} rowKey={(row) => String(row.invoice_id)} empty="No invoices to show yet." />;
}

function InvoiceCards({ items }: { items: InvoiceRow[] }) {
  return (
    <ul className="payments__cards" aria-label="Invoices">
      {items.map((row) => {
        const overdue = overdueText(row);
        return (
          <li key={row.invoice_id} className="payments__card">
            <span className="payments__cardhead">
              <strong>{workText(row)}</strong>
              <StateTag row={row} />
            </span>
            <span>
              Still owed{' '}
              <strong>
                <AmountValue amount={row.owed} row={row} />
              </strong>
            </span>
            <span>
              Billed <AmountValue amount={row.face} row={row} /> · Received <AmountValue amount={row.paid} row={row} />
            </span>
            <span className="payments__cardref">
              <Reference row={row} />
              {overdue === UNKNOWN ? (
                <>
                  {' · '}
                  <Unknown />
                </>
              ) : overdue !== '—' ? (
                ` · ${overdue}`
              ) : null}
            </span>
            <Actions row={row} />
          </li>
        );
      })}
    </ul>
  );
}

function StripCell({ label, values, tone, date, spoken }: { label: string; values?: StripValue[]; tone: string; date?: string; spoken?: string }) {
  const shown = values ?? [{ key: 'date', text: date ?? UNKNOWN, unknown: (date ?? UNKNOWN) === UNKNOWN }];
  const known = shown.every((value) => !value.unknown);
  // a cell with an Unknown part is drawn neutral: the amber Unknown never sits on a coloured fill
  return (
    <div className={`payments__cell${known ? ` payments__cell--${tone}` : ''}`}>
      <span className="payments__celllabel">
        {label}
        {spoken && <VisuallyHidden> {spoken}</VisuallyHidden>}
      </span>
      {shown.map((value) => (
        <span key={value.key} className="payments__cellvalue">
          {value.text === UNKNOWN ? <Unknown /> : value.text}
          {value.note && <span className="payments__cellnote">{value.note}</span>}
        </span>
      ))}
    </div>
  );
}

/** The figures the backend composed, one value per currency and basis; nothing here is added up from the rows. */
function Strip({ body }: { body: InvoiceList }) {
  const month = monthName(body.received_this_month.month);
  return (
    <section aria-label="Facts earned" className="payments__strip">
      <StripCell label="OWED TO PSL" values={owedValues(body.totals)} tone="owed" />
      <StripCell label="OVERDUE" values={overdueValues(body.totals)} tone="overdue" />
      <StripCell label="RECEIVED THIS MONTH" values={receivedValues(body.received_this_month)} tone="received" spoken={month ? `(${month})` : undefined} />
      <StripCell label="DATA DATE" date={dataDate(body.as_of)} tone="bank" />
    </section>
  );
}

function PaymentsNoAccess() {
  return (
    <section className="psl-panel payments__noaccess" aria-label="No access">
      <div className="psl-panel__body">
        <Tag tone="neutral" className="payments__noaccesstag">
          NO ACCESS
        </Tag>
        <PageTitle>You can&rsquo;t open this page</PageTitle>
        <p className="payments__plain">It is for people who work on Finance. Nothing about it is shown here.</p>
        <p className="payments__plain">
          <NextLink className={buttonClass('dark', 'lg')} href="/my-work">
            Back to my queue
          </NextLink>
        </p>
      </div>
    </section>
  );
}

function StateFilter({ applied, onApply, onClose }: { applied?: string; onApply: (value: string | undefined) => void; onClose: () => void }) {
  const [draft, setDraft] = useState<string>(applied ?? ANY);
  return (
    <FilterPanel applyLabel="Show results" onApply={() => onApply(draft === ANY ? undefined : draft)} onClear={() => setDraft(ANY)} onClose={onClose}>
      <RadioGroup legend="State" name="payments-state" value={draft} onChange={setDraft} options={[{ value: ANY, label: 'Any state' }, ...STATES.map((f) => ({ value: f.value, label: f.label }))]} />
    </FilterPanel>
  );
}

/** /finance/payments. q and status live in the address; a reload sends the same query. */
export function PaymentsView() {
  usePhoneBack({ label: 'Home', href: '/' });
  const params = useSearchParams();
  const router = useRouter();
  const query = parseQuery(new URLSearchParams(params?.toString() ?? ''));
  const phone = useIsPhone();
  const { state, more, retry, showMore } = usePayments(query);
  const [filterOpen, setFilterOpen] = useState(false);
  const rows = useRef<HTMLDivElement>(null);
  const focusRow = useRef<number | null>(null);
  const queryRef = useRef(query);
  useEffect(() => {
    queryRef.current = query;
  }, [query]);

  const navigate = useCallback((next: InvoiceQuery) => router.replace(`${PAYMENTS_PATH}${querySearch({ ...queryRef.current, ...next })}`, { scroll: false }), [router]);

  // The box keeps what the person typed; the address takes it once the search settles (2+ characters, or emptied).
  const [text, setText] = useState(query.q ?? '');
  const [syncedQ, setSyncedQ] = useState(query.q);
  if (query.q !== syncedQ) {
    setSyncedQ(query.q);
    if ((text.trim() || undefined) !== query.q) setText(query.q ?? '');
  }
  const applySearch = (value: string) => {
    const q = value.trim() || undefined;
    if (q !== queryRef.current.q) navigate({ q });
  };

  const items = state.status === 'ready' ? state.body.items : [];

  useEffect(() => {
    if (focusRow.current !== null && state.status === 'ready' && items.length > focusRow.current) {
      rows.current?.querySelectorAll<HTMLElement>('[data-invoice-row]')[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [state, items.length]);


  if (state.status === 'error' && state.error.kind === 'unauthenticated') return <SignedOutState pathname={`${PAYMENTS_PATH}${querySearch(query)}`} />;
  if (state.status === 'error' && (state.error.kind === 'forbidden' || state.error.kind === 'not_found')) return <PaymentsNoAccess />;

  const body = state.status === 'ready' ? state.body : undefined;
  const closeFilter = () => setFilterOpen(false);
  const narrowed = query.q !== undefined || query.status !== undefined;

  // Show more: the keyboard moves to the first row it added.
  const onMore = () => {
    if (more !== 'error') focusRow.current = items.length;
    void showMore();
  };

  let list;
  if (state.status === 'loading') {
    list = <LoadingState />;
  } else if (state.status === 'error') {
    list = <WorkErrorCard message="We couldn’t load the payments. Nothing was changed." error={state.error} onRetry={() => void retry()} />;
  } else if (state.body.items.length === 0 && !state.body.cursor) {
    list = narrowed ? (
      <EmptyState
        title="No invoices match"
        action={
          <Button kind="link" onClick={() => navigate({ q: undefined, status: undefined })}>
            Clear filters
          </Button>
        }
      >
        Nothing matches your search and filters.
      </EmptyState>
    ) : (
      <EmptyState title="No invoices">No invoices to show yet.</EmptyState>
    );
  } else {
    list = (
      <>
        {state.body.limited && (
          <p role="note" className="payments__partial">
            Partial result. The totals cover the rows returned, not every invoice. Use Show more for the rest.
          </p>
        )}
        <div ref={rows}>{phone ? <InvoiceCards items={items} /> : <InvoiceTable items={items} />}</div>
        {state.body.cursor && <MoreButton more={more} onMore={onMore} />}
      </>
    );
  }

  const sentence = body ? coverageText(body.received_this_month) : undefined;
  return (
    <div className="payments">
      <p className="payments__eyebrow">FINANCE / PAYMENTS</p>
      <div className="payments__head">
        <PageTitle size={36} phoneSize={26}>
          {phone ? 'Payments' : 'Payments and follow-up'}
        </PageTitle>
      </div>
      {body && <Strip body={body} />}
      {sentence && <p className="payments__coverage">{sentence}</p>}
      <div className="payments__row">
        <div className="payments__main">
          <form
            role="search"
            className="payments__toolbar"
            onSubmit={(event) => {
              event.preventDefault();
              // Enter follows the same rule as typing: 2+ characters, or an empty box (TECH-1-3)
              const typed = text.trim();
              if (typed.length === 0 || typed.length >= SEARCH_MIN_CHARS) applySearch(text);
            }}
          >
            <ListToolbar
              search={{ label: 'Search', placeholder: phone ? 'Search invoices' : 'Search invoice, client or reference', value: text, onChange: setText, onSearch: applySearch }}
              filterOpen={filterOpen}
              onFilterToggle={() => setFilterOpen(!filterOpen)}
              filterPanel={
                <StateFilter
                  applied={query.status}
                  onApply={(status) => {
                    closeFilter();
                    navigate({ status });
                  }}
                  onClose={closeFilter}
                />
              }
              resultText=""
              chips={query.status ? [{ key: 'status', name: 'State', value: filterLabel(query.status), onRemove: () => navigate({ status: undefined }) }] : []}
              onClearAll={() => navigate({ status: undefined })}
            />
          </form>
          {list}
        </div>
      </div>
    </div>
  );
}
