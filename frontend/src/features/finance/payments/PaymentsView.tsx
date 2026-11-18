'use client';

// SCR-20 Payments and follow-up: the invoices E-INVOICES returns for this person, in returned order. Invoiced, received
// and still owed are three separate backend amounts; the state, overdue days, totals and count are the backend's. The
// page adds, filters and counts nothing itself (INV-UNKNOWN, D-94), reads no /me and decides nothing about access.
// Recording a payment received and the short-payment decision are not on this page (FE-PAYMENTS-RECEIPT, held).
import NextLink from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  AgentAvatar,
  Button,
  buttonClass,
  Callout,
  EmptyState,
  FilterPanel,
  ListToolbar,
  PageTitle,
  RadioGroup,
  ShowMore,
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
import { SampleLabel } from '@/shell/SampleLabel';

import {
  amountText,
  bankDataText,
  cardOverdue,
  filterLabel,
  monthName,
  overdueText,
  parseQuery,
  PAYMENTS_PATH,
  querySearch,
  resultText,
  stripText,
  stripValue,
  UNKNOWN,
  workHref,
  workText,
  type StripValue,
} from './model';
import { agentNote, coverage, period, RECORD_ID, type Amount, type InvoiceList, type InvoiceQuery, type InvoiceRow } from './proposal';
import { usePayments } from './usePayments';

import './payments.css';

const ANY = '';

/** A row amount as sent, or the amber Unknown with "amount not known" spoken; never 0 for a missing value. */
function AmountValue({ amount }: { amount: Amount | undefined }) {
  const text = amountText(amount);
  if (text === undefined) {
    return (
      <>
        <Unknown />
        <VisuallyHidden> amount not known</VisuallyHidden>
      </>
    );
  }
  return <span className="psl-mono">{text}</span>;
}

function StateTag({ row }: { row: InvoiceRow }) {
  if (!row.status) return <Unknown />;
  return (
    <Tag tone={tagTone(row.status.tone)} className="payments__tag">
      {row.status.label}
    </Tag>
  );
}

function Overdue({ row }: { row: InvoiceRow }) {
  const text = overdueText(row);
  return text === UNKNOWN ? <Unknown /> : <>{text}</>;
}

/** The reference: a link to its work item when the backend names one, else plain text. It takes focus after Show more. */
function Reference({ row }: { row: InvoiceRow }) {
  if (row.work_id && RECORD_ID.test(row.work_id)) {
    return (
      <NextLink href={workHref(row.work_id)} className="psl-mono" data-invoice-row="">
        {row.reference}
      </NextLink>
    );
  }
  return (
    <span className="psl-mono payments__ref" tabIndex={-1} data-invoice-row="">
      {row.reference}
    </span>
  );
}

const COLUMNS: Column<InvoiceRow>[] = [
  {
    key: 'invoice',
    header: 'INVOICE',
    cell: (row) => (
      <span className="payments__refcell">
        <Reference row={row} />
        <SampleLabel show={row.sample} />
      </span>
    ),
  },
  { key: 'work', header: 'WORK', cell: workText },
  { key: 'invoiced', header: 'INVOICED', cell: (row) => <AmountValue amount={row.invoiced} /> },
  { key: 'received', header: 'RECEIVED', cell: (row) => <AmountValue amount={row.received} /> },
  {
    key: 'owed',
    header: 'STILL OWED',
    cell: (row) => (
      <strong>
        <AmountValue amount={row.owed} />
      </strong>
    ),
  },
  { key: 'state', header: 'STATE', cell: (row) => <StateTag row={row} /> },
  { key: 'overdue', header: 'OVERDUE BY', cell: (row) => <Overdue row={row} /> },
];

function InvoiceTable({ items }: { items: InvoiceRow[] }) {
  return <Table className="payments__table" caption="Invoices" columns={COLUMNS} rows={items} rowKey={(row) => row.invoice_id} empty="No invoices to show yet." />;
}

function InvoiceCards({ items }: { items: InvoiceRow[] }) {
  return (
    <ul className="payments__cards" aria-label="Invoices">
      {items.map((row) => {
        const overdue = cardOverdue(row);
        return (
          <li key={row.invoice_id} className="payments__card">
            <span className="payments__cardhead">
              <strong>{workText(row)}</strong>
              <StateTag row={row} />
            </span>
            <span>
              Still owed{' '}
              <strong>
                <AmountValue amount={row.owed} />
              </strong>
            </span>
            <span className="payments__cardref">
              <Reference row={row} />
              {overdue === 'unknown' ? (
                <>
                  {' · overdue '}
                  <Unknown />
                </>
              ) : overdue !== 'none' ? (
                ` · overdue ${overdue}`
              ) : null}
            </span>
            <SampleLabel show={row.sample} />
          </li>
        );
      })}
    </ul>
  );
}

function StripCell({ label, value, tone, spoken }: { label: string; value: StripValue | string; tone: string; spoken?: string }) {
  const text = typeof value === 'string' ? value : stripText(value);
  const known = text !== UNKNOWN;
  // a cell with no known part is drawn neutral: the amber Unknown never sits on a coloured fill
  return (
    <div className={`payments__cell${known ? ` payments__cell--${tone}` : ''}`}>
      <span className="payments__celllabel">
        {label}
        {spoken && <VisuallyHidden> {spoken}</VisuallyHidden>}
      </span>
      <span className="payments__cellvalue">{known ? text : <Unknown />}</span>
    </div>
  );
}

/** The four figures the backend composed; a missing one reads Unknown. Nothing here is added up from the rows. */
function Strip({ body }: { body: InvoiceList }) {
  const month = monthName(period(body));
  return (
    <section aria-label="Facts earned" className="payments__strip">
      <StripCell label="OWED TO PSL" value={stripValue(body, 'owed')} tone="owed" />
      <StripCell label="OVERDUE" value={stripValue(body, 'overdue')} tone="overdue" />
      <StripCell label="RECEIVED THIS MONTH" value={stripValue(body, 'received_this_month')} tone="received" spoken={month ? `(${month})` : undefined} />
      <StripCell label="BANK DATA TO" value={bankDataText(body)} tone="bank" />
    </section>
  );
}

function Note({ body }: { body: InvoiceList }) {
  const note = agentNote(body);
  if (!note) return null;
  return (
    <aside className="payments__note" aria-label="Chidi · Finance agent">
      <div className="payments__notehead">
        <AgentAvatar agent="chidi" />
        <span>
          <strong>Chidi</strong> <span className="payments__noterole">· Finance agent</span>
        </span>
      </div>
      <div className="payments__notebody">
        {note.lines.map((line, i) => (
          <p key={i}>{note.strong.has(i) ? <strong>{line}</strong> : line}</p>
        ))}
        {note.workId && (
          <p>
            <NextLink href={workHref(note.workId)}>Open the reminder draft</NextLink>
          </p>
        )}
      </div>
    </aside>
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

function StateFilter({ filters, applied, onApply, onClose }: { filters: NonNullable<InvoiceList['filters']>; applied?: string; onApply: (value: string | undefined) => void; onClose: () => void }) {
  const [draft, setDraft] = useState<string>(applied ?? ANY);
  return (
    <FilterPanel applyLabel="Show results" onApply={() => onApply(draft === ANY ? undefined : draft)} onClear={() => setDraft(ANY)} onClose={onClose}>
      <RadioGroup legend="State" name="payments-state" value={draft} onChange={setDraft} options={[{ value: ANY, label: 'Any state' }, ...filters.map((f) => ({ value: f.value, label: f.label }))]} />
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

  useEffect(() => {
    if (focusRow.current !== null && state.status === 'ready') {
      rows.current?.querySelectorAll<HTMLElement>('[data-invoice-row]')[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [state]);

  const press = async () => {
    const before = await showMore();
    if (before !== undefined) focusRow.current = before;
  };

  if (state.status === 'error' && state.error.kind === 'unauthenticated') return <SignedOutState pathname={`${PAYMENTS_PATH}${querySearch(query)}`} />;
  if (state.status === 'error' && (state.error.kind === 'forbidden' || state.error.kind === 'not_found')) return <PaymentsNoAccess />;

  const body = state.status === 'ready' ? state.body : undefined;
  const filters = body?.filters ?? [];
  const closeFilter = () => setFilterOpen(false);
  const narrowed = query.q !== undefined || query.status !== undefined;

  let list;
  if (state.status === 'loading') {
    list = <LoadingState />;
  } else if (state.status === 'error') {
    list = <WorkErrorCard message="We couldn’t load the payments. Nothing was changed." error={state.error} onRetry={() => void retry()} />;
  } else if (state.body.items.length === 0 && !state.body.next_cursor) {
    list = narrowed ? (
      <EmptyState
        title="No invoices match"
        action={
          <button type="button" className="psl-link cmp-linkbutton" onClick={() => navigate({ q: undefined, status: undefined })}>
            Clear filters
          </button>
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
        <div ref={rows}>{phone ? <InvoiceCards items={state.body.items} /> : <InvoiceTable items={state.body.items} />}</div>
        {state.body.next_cursor && (
          <div className="payments__more">
            <ShowMore shown={state.body.items.length} hasMore busy={more === 'loading'} onMore={() => void press()} />
            {more === 'error' && (
              <Callout kind="problem">
                We couldn’t load more invoices. Nothing was changed.{' '}
                <Button kind="secondary" size="sm" onClick={() => void press()}>
                  Try again
                </Button>
              </Callout>
            )}
          </div>
        )}
      </>
    );
  }

  const sentence = body ? coverage(body) : undefined;
  return (
    <div className="payments">
      <p className="payments__eyebrow">FINANCE / PAYMENTS</p>
      <PageTitle size={36} phoneSize={26} className="payments__title">
        {phone ? 'Payments' : 'Payments and follow-up'}
      </PageTitle>
      {body && <Strip body={body} />}
      {sentence && <p className="payments__coverage">{sentence}</p>}
      <div className="payments__row">
        <div className="payments__main">
          <form
            role="search"
            className="payments__toolbar"
            onSubmit={(event) => {
              event.preventDefault();
              applySearch(text);
            }}
          >
            <ListToolbar
              search={{ label: 'Search', placeholder: phone ? 'Search invoices' : 'Search invoice, client or reference', value: text, onChange: setText, onSearch: applySearch }}
              filterCount={query.status ? 1 : 0}
              filterOpen={filterOpen}
              onFilterToggle={filters.length > 0 ? () => setFilterOpen(!filterOpen) : undefined}
              filterPanel={
                <StateFilter
                  filters={filters}
                  applied={query.status}
                  onApply={(status) => {
                    closeFilter();
                    navigate({ status });
                  }}
                  onClose={closeFilter}
                />
              }
              resultText={body ? resultText(body) : ''}
              chips={query.status ? [{ key: 'status', name: 'State', value: filterLabel(body?.filters, query.status), onRemove: () => navigate({ status: undefined }) }] : []}
              onClearAll={() => navigate({ status: undefined })}
            />
          </form>
          {list}
        </div>
        {body && <Note body={body} />}
      </div>
    </div>
  );
}
