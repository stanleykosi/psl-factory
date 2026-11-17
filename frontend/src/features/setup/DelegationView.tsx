'use client';

// /setup/delegation (SCR-13-desktop-delegation, SCR-13-mobile-delegation): E-DELEGATIONS, and E-DELEGATION when the
// read says can_add and gives a revision. Every row is drawn from what was returned (from → to, dates, reason,
// status); nothing is worked out from dates, roles or the persona, and nothing claims an effect beyond the status.
// Add outcomes: 200 re-reads and focuses the new row; 409 re-reads and keeps the entries; 422 marks the named fields;
// a network or server error re-reads once and never resends: an unchanged revision means not added, a moved one holds
// Add until Start again, and a failed re-read holds it until Try again reads the list.
import { useEffect, useReducer, useRef, useState } from 'react';

import { ApiError } from '@/api/errors';
import { Button, Drawer, EmptyState, PageTitle, Panel, Table, Tag, Unknown, VisuallyHidden } from '@/components';

import type { DelegationBody, DelegationRow, DelegationsPage } from './contract-proposal';
import { CHANGED, DelegationForm, type Blocked, type FormFrame, type SendResult, type Summary } from './DelegationForm';
import { boardDate, dateRange } from './format';
import { OutcomeNotice, type Notice } from './SetRulePanel';
import { RulesReadState, SetupFrame, SetupGate, ShowMore, useSetupPhoneBack } from './SetupFrame';
import { useDelegationAdd } from './useDelegationAdd';
import { useDelegations } from './useDelegations';

const STATUS: Record<DelegationRow['status'], string> = { scheduled: 'Upcoming', active: 'Active', ended: 'Ended' };
const CHECKING = 'We couldn’t confirm the delegation. Checking the list…';
const NOT_ADDED = 'It was not added. You can add it again.';
const UNCHECKED = 'We couldn’t check whether the delegation was added. Try again to read the list before adding again.';
const STALE = 'This changed while you were working. The list has been reloaded; check it and add again.';
const STALE_UNREAD = 'This changed while you were working, and we couldn’t reload the list. Reload the page before adding again.';
const NOT_REFRESHED = 'The delegation was added. We couldn’t refresh the list.';

type Focus = { kind: 'row'; id: string } | { kind: 'head' };

const person = (p: { name: string; role?: string }) => (p.role ? `${p.name} · ${p.role}` : p.name);

/** "18–25 Nov 2026"; a missing end is Unknown, never blank or open-ended. */
function Dates({ row }: { row: DelegationRow }) {
  if (row.ends) return <>{dateRange(row.starts, row.ends)}</>;
  return (
    <>
      {boardDate(row.starts)} – <Unknown />
    </>
  );
}

const authorityText = (row: DelegationRow, page: DelegationsPage) =>
  row.authority === undefined ? null : `Authority: ${page.authorities?.find((a) => a.value === row.authority)?.label ?? row.authority}`;

const canAdd = (page: DelegationsPage): page is DelegationsPage & { revision: number } => page.can_add === true && typeof page.revision === 'number';

export function DelegationPageView() {
  return (
    <SetupGate>
      <DelegationView />
    </SetupGate>
  );
}

function DelegationView() {
  const { state, retry, refresh, loadMore, signOut } = useDelegations();
  const { busy, add } = useDelegationAdd(refresh);
  useSetupPhoneBack();
  const [sheet, setSheet] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [blocked, setBlocked] = useState<Blocked>(null);
  // The revision an unconfirmed write was sent against, kept until a read settles whether it went through.
  const sent = useRef<number | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const focus = useRef<Focus | null>(null);
  const sheetStart = useRef<HTMLDivElement>(null);
  const [, moveFocus] = useReducer((n: number) => n + 1, 0);

  // Runs after every render: a requested focus lands once the re-read rows are on the page.
  useEffect(() => {
    const target = focus.current;
    if (!target) return;
    focus.current = null;
    const selector = target.kind === 'row' ? '[data-row-for]' : '[data-list-head]';
    const found = Array.from(document.querySelectorAll<HTMLElement>(selector))
      .filter((el) => target.kind === 'head' || el.dataset.rowFor === target.id)
      // The table marks a row with an empty marker in its first cell; the row itself takes focus.
      .map((el) => (el.hidden ? el.closest('tr') : el))
      .filter((el): el is HTMLElement => el !== null);
    const into = found.find((el) => el.getClientRects().length > 0) ?? found[0];
    // A row is not focusable by default (its tabIndex reads -1 without the attribute), so the attribute is set.
    into?.setAttribute('tabindex', '-1');
    into?.focus();
  });

  if (state.status !== 'ready') {
    const closed = state.status === 'error' && (state.error.kind === 'forbidden' || state.error.kind === 'not_found');
    return (
      <>
        {closed && (
          <h1>
            <VisuallyHidden>Setup</VisuallyHidden>
          </h1>
        )}
        <RulesReadState state={state} retry={() => void retry()} what="delegations" />
      </>
    );
  }

  const { page, items } = state;
  const empty = items.length === 0;

  /** After an unconfirmed write: the same revision means nothing was written; a moved one may hold the new row. */
  const settle = (fresh: DelegationsPage, revision: number) => {
    sent.current = null;
    if (fresh.revision === revision) {
      setBlocked(null);
      setNotice({ tone: 'warning', text: NOT_ADDED });
    } else {
      setBlocked('changed');
      setNotice({ tone: 'warning', text: CHANGED });
      // On a phone the sheet covers the list the person now has to check, so it closes and the warning shows above the cards.
      setSheet(false);
    }
  };

  const send = async (body: DelegationBody, summary: Summary): Promise<SendResult> => {
    setNotice(null);
    const outcome = await add(body, () => setNotice({ tone: 'warning', text: CHECKING }));
    if (!outcome) return { kind: 'keep' };
    switch (outcome.kind) {
      case 'added': {
        const fresh = outcome.page instanceof ApiError ? undefined : outcome.page;
        const id = outcome.result.delegation_id;
        const row = id ? fresh?.items.find((r) => r.delegation_id === id) : undefined;
        const words = row
          ? `${row.from.name} to ${row.delegate.name}, ${row.ends ? dateRange(row.starts, row.ends) : summary.dates}`
          : `${summary.from ?? 'you'} to ${summary.to}, ${summary.dates}`;
        setAnnouncement(`Delegation added: ${words}.`);
        setNotice(fresh ? null : { tone: 'warning', text: NOT_REFRESHED });
        setSheet(false);
        focus.current = row ? { kind: 'row', id: row.delegation_id } : { kind: 'head' };
        moveFocus();
        return { kind: 'clear' };
      }
      case 'rejected':
        if (outcome.error.kind !== 'stale') setNotice({ tone: 'problem', text: outcome.error.message });
        else setNotice({ tone: 'problem', text: outcome.page instanceof ApiError ? STALE_UNREAD : STALE });
        return { kind: 'keep' };
      case 'invalid':
        return { kind: 'invalid', message: outcome.message, fields: outcome.fields };
      case 'signed_out':
        signOut(outcome.error);
        return { kind: 'keep' };
      case 'unconfirmed':
        settle(outcome.page, body.expected_revision);
        return { kind: 'keep' };
      case 'unchecked':
        sent.current = body.expected_revision;
        setBlocked('locked');
        setNotice({ tone: 'problem', text: UNCHECKED });
        return { kind: 'keep' };
    }
  };

  // Try again only reads; Add stays held until the read says whether the write went through.
  const tryAgain = async () => {
    const fresh = await refresh();
    if (!(fresh instanceof ApiError) && sent.current !== null) settle(fresh, sent.current);
  };

  const startAgain = () => {
    setBlocked(null);
    setNotice(null);
  };

  const form = (onCancel?: () => void, frame?: FormFrame) =>
    canAdd(page) ? (
      <DelegationForm
        page={page}
        busy={busy}
        blocked={blocked}
        notice={notice}
        onSend={send}
        onStartAgain={startAgain}
        onTryAgain={() => void tryAgain()}
        onCancel={onCancel}
        frame={frame}
      />
    ) : null;

  const emptyState = <EmptyState title="No delegations to show.">Delegations you may see will appear here.</EmptyState>;
  const status = (row: DelegationRow) => <Tag tone="neutral">{STATUS[row.status]}</Tag>;
  const from = (row: DelegationRow) => (
    <>
      {person(row.from)}
      <span hidden data-row-for={row.delegation_id} />
    </>
  );
  const head = (
    <h2 className="cmp-sr" tabIndex={-1} data-list-head="">
      Delegations
    </h2>
  );

  return (
    <>
      <div className="setup-page setup-desktop">
        <SetupFrame current="delegation" />
        <div className="setup-columns">
          <section className="setup-main" aria-label="Delegations">
            {head}
            {empty ? (
              emptyState
            ) : (
              <>
                <Table
                  caption="Delegations"
                  className="setup-table setup-table--deleg"
                  columns={[
                    { key: 'from', header: 'FROM', cell: from },
                    { key: 'to', header: 'TO', cell: (row) => person(row.delegate) },
                    { key: 'dates', header: 'DATES', cell: (row) => <Dates row={row} /> },
                    {
                      key: 'reason',
                      header: 'REASON',
                      cell: (row) => (
                        <>
                          {row.reason}
                          {row.authority !== undefined && <span className="setup-meta setup-deleg__line">{authorityText(row, page)}</span>}
                        </>
                      ),
                    },
                    { key: 'state', header: 'STATE', cell: status },
                  ]}
                  rows={items}
                  rowKey={(row) => row.delegation_id}
                  empty="No delegations to show."
                />
                <ShowMore state={state} onMore={() => void loadMore()} noun="delegations" />
              </>
            )}
          </section>
          {canAdd(page) && (
            <aside className="setup-aside" aria-label="Add a delegation">
              <Panel head={<h2>Add a delegation</h2>}>{form()}</Panel>
            </aside>
          )}
        </div>
      </div>

      <div className={canAdd(page) ? 'setup-page setup-phone setup-deleg--bar' : 'setup-page setup-phone'}>
        <PageTitle phoneSize={22}>Delegation</PageTitle>
        {head}
        {/* the sheet closed so the list can be checked (UX-1-2); reopening it shows the held form and Start again */}
        {!sheet && blocked === 'changed' && notice && <OutcomeNotice notice={notice} />}
        {empty ? (
          emptyState
        ) : (
          <>
            {/* ARIA list roles on divs: the same list semantics as ul/li, laid out as the board's cards */}
            <div role="list" className="setup-cards">
              {items.map((row) => (
                <div role="listitem" key={row.delegation_id} className="setup-card setup-name" tabIndex={-1} data-row-for={row.delegation_id}>
                  <strong>
                    {row.from.name} → {row.delegate.name}
                  </strong>
                  <span className="setup-card__line">
                    {row.from.role && <>{row.from.role} · </>}
                    <Dates row={row} />
                    {row.reason && <> · {row.reason}</>}
                    {row.authority !== undefined && <> · {authorityText(row, page)}</>}
                  </span>
                  {status(row)}
                </div>
              ))}
            </div>
            <ShowMore state={state} onMore={() => void loadMore()} noun="delegations" />
          </>
        )}
        {canAdd(page) && (
          <div className="psl-actionbar setup-deleg__bar">
            <Button size="lg" block aria-haspopup="dialog" onClick={() => setSheet(true)}>
              Add delegation
            </Button>
          </div>
        )}
        {sheet && canAdd(page) && (
          form(
            () => setSheet(false),
            ({ fields, actions, note }) => (
              // The sheet opens on its form, not on the first text field (Starts), so From and To come first; the buttons
              // sit in the sheet's footer, which stays while the fields scroll.
              <Drawer title="Add a delegation" initialFocus={sheetStart} onClose={() => setSheet(false)} footer={actions}>
                <div ref={sheetStart} tabIndex={-1} className="setup-name setup-deleg__form">
                  {fields}
                  {note}
                </div>
              </Drawer>
            ),
          )
        )}
      </div>

      <div role="status" aria-live="polite">
        <VisuallyHidden>{announcement}</VisuallyHidden>
      </div>
    </>
  );
}
