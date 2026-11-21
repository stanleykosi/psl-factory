'use client';

// /setup/templates (SCR-34-desktop, SCR-34-mobile): E-TEMPLATES, and E-TEMPLATE-VERSION for the rows the API marks
// can_upload. Every element comes from a returned field. test_template is read, never set or guessed: no badge and no
// claim on a row that says false, and the banner only when the whole set is known to be test templates.
// Upload outcomes: 200 re-reads the list and moves focus to the row; 409 shows the message and clears the entries;
// 422 keeps them and marks the named fields; a network or server error re-reads once and never resends.
import { useEffect, useReducer, useRef, useState } from 'react';

import { ApiError } from '@/api/errors';
import { Button, Callout, EmptyState, PageTitle, SampleLabel, SearchField, Table, VisuallyHidden, ShowMore, useToast } from '@/components';

import type { TemplateRow } from './api';
import { boardDay, boardStamp } from './format';
import { OutcomeNotice, type Notice } from './SetRulePanel';
import { RulesReadState, SetupFrame, SetupGate, PagingNotes, useSetupPaging, useSetupPhoneBack } from './SetupFrame';
import { TemplateUploadPanel, type Invalid } from './TemplateUploadPanel';
import { useTemplateUpload } from './useTemplateUpload';
import { useTemplates } from './useTemplates';

type UploadRow = TemplateRow & { template_id: string; revision: number };
type Shown = Record<string, { version: string; test_template: boolean }>;
type Focus = { kind: 'name' | 'upload'; id: string };

const CHECKING = 'We couldn’t confirm the upload. Checking the list…';
const NOT_REFRESHED = 'Uploaded. We couldn’t refresh the list.';

// A value that is not a boolean reads as a test template: the safe wording on malformed data.
const isTest = (row: TemplateRow) => (typeof row.test_template === 'boolean' ? row.test_template : true);
const canUpload = (row: TemplateRow): row is UploadRow =>
  typeof row.template_id === 'string' && row.template_id !== '' && row.can_upload === true && typeof row.revision === 'number';
const uploadLabel = (row: TemplateRow) => (isTest(row) ? "Upload PSL's version" : 'Upload a new version');

/** Muted text after the name: "Version 3 · DOCX", then "3 versions · Changed by Ada Okafor, 12 Nov"; each part only when the API returned it. */
function metaParts(row: TemplateRow): { first: string; second: string } {
  const day = row.updated_at ? boardDay(row.updated_at) : null;
  const by = row.updated_by ? `by ${row.updated_by}` : null;
  const when = [by, day].filter(Boolean);
  return {
    first: [`Version ${row.version}`, row.kind].filter(Boolean).join(' · '),
    second: [
      typeof row.versions === 'number' ? `${row.versions} ${row.versions === 1 ? 'version' : 'versions'}` : null,
      when.length > 0 ? `Changed ${when.join(', ')}` : null,
    ]
      .filter(Boolean)
      .join(' · '),
  };
}

export function TemplatesPageView() {
  return (
    <SetupGate>
      <TemplatesView />
    </SetupGate>
  );
}

function TemplatesView() {
  const { state, retry, refresh, loadMore, signOut } = useTemplates();
  const { items: pagedItems, paging, notes } = useSetupPaging(state, loadMore, 'templates');
  const { busy, upload } = useTemplateUpload(refresh);
  useSetupPhoneBack();
  const [open, setOpen] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const toast = useToast();
  // The list could not be re-read after an unconfirmed upload: nothing more is sent until a read works.
  const [locked, setLocked] = useState(false);
  // The 200 body's version and badge, shown only for a row while the re-read after it has failed.
  const [shown, setShown] = useState<Shown>({});
  const [query, setQuery] = useState('');
  const focus = useRef<Focus | null>(null);
  const [, moveFocus] = useReducer((n: number) => n + 1, 0);

  // Runs after every render: a requested focus lands once the re-read rows are on the page.
  useEffect(() => {
    const target = focus.current;
    if (!target) return;
    focus.current = null;
    const attribute = `data-${target.kind}-for`;
    const found = Array.from(document.querySelectorAll<HTMLElement>(`[${attribute}]`)).filter((el) => el.getAttribute(attribute) === target.id);
    (found.find((el) => el.getClientRects().length > 0) ?? found[0])?.focus();
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
        <RulesReadState state={state} retry={() => void retry()} what="templates" />
      </>
    );
  }

  const rows = pagedItems.map((row) => {
    const override = row.template_id ? shown[row.template_id] : undefined;
    return override ? { ...row, ...override } : row;
  });
  const empty = rows.length === 0;
  const testCount = rows.filter(isTest).length;
  const allTest = !empty && !state.nextCursor && testCount === rows.length;
  const needle = query.trim().toLowerCase();
  const matching = needle ? rows.filter((r) => r.name.toLowerCase().includes(needle) || r.line.toLowerCase().includes(needle)) : rows;
  const asOf = state.asOf ? boardStamp(state.asOf) : null;

  const close = (id: string, target: Focus['kind']) => {
    setOpen(null);
    focus.current = { kind: target, id };
    moveFocus();
  };

  const send = async (row: UploadRow, file: File, note: string): Promise<Invalid | null> => {
    const outcome = await upload(row.template_id, { revision: row.revision, file, note }, () => setNotice({ tone: 'warning', text: CHECKING }));
    if (!outcome) return null;
    switch (outcome.kind) {
      case 'uploaded': {
        const { result } = outcome;
        if (outcome.page instanceof ApiError) {
          setShown((s) => ({ ...s, [row.template_id]: { version: result.version, test_template: result.test_template } }));
          setNotice({ tone: 'warning', text: NOT_REFRESHED });
        } else {
          setShown({});
          setNotice(null);
        }
        toast.show(`Version ${result.version} uploaded for ${row.name}`);
        close(row.template_id, 'name');
        return null;
      }
      case 'rejected':
        setNotice({ tone: 'problem', text: outcome.error.message });
        close(row.template_id, 'upload');
        return null;
      case 'invalid':
        return { message: outcome.message, fields: outcome.fields };
      case 'signed_out':
        signOut(outcome.error);
        return null;
      case 'unconfirmed': {
        const fresh = outcome.page.items.find((r) => r.template_id === row.template_id);
        if (fresh && (fresh.version !== row.version || fresh.revision !== row.revision)) {
          setNotice(null);
          toast.show('The upload went through.');
          close(row.template_id, 'name');
        } else {
          setNotice({ tone: 'warning', text: 'We couldn’t confirm the upload. Nothing new is shown for this template, so you can upload again.' });
        }
        return null;
      }
      case 'unchecked':
        setLocked(true);
        setNotice({ tone: 'problem', text: 'We couldn’t check whether the upload went through. Try again to read the list before uploading again.' });
        return null;
    }
  };

  const tryAgain = async () => {
    if (!(await refresh() instanceof ApiError)) {
      setLocked(false);
      setNotice(null);
    }
  };

  const openPanel = (id: string) => {
    setNotice(null);
    setOpen(id);
  };

  const panelFor = (row: TemplateRow) =>
    open !== null && row.template_id === open && canUpload(row) ? (
      <TemplateUploadPanel
        key={row.template_id}
        name={row.name}
        busy={busy}
        locked={locked}
        onSend={(file, note) => send(row, file, note)}
        onCancel={() => close(row.template_id, 'upload')}
      />
    ) : null;

  const uploadButton = (row: TemplateRow, asLink: boolean) =>
    canUpload(row) && (
      <Button
        kind={asLink ? 'text' : 'secondary'}
        block={!asLink}
        data-upload-for={row.template_id}
        aria-expanded={open === row.template_id}
        onClick={() => openPanel(row.template_id)}
      >
        {uploadLabel(row)}
      </Button>
    );

  const notices = (
    <>
      {notice && <OutcomeNotice notice={notice} />}
      {locked && (
        <div>
          <Button kind="secondary" size="sm" onClick={() => void tryAgain()}>
            Try again
          </Button>
        </div>
      )}
    </>
  );
  const name = (row: TemplateRow) => (
    <strong className="setup-name" tabIndex={-1} data-name-for={row.template_id}>
      {row.name}
    </strong>
  );
  const badge = (row: TemplateRow) => isTest(row) && <SampleLabel kind="test" />;
  const meta = (row: TemplateRow) => {
    const { first, second } = metaParts(row);
    return (
      <>
        <span className="setup-meta">{first}</span>
        {second && <span className="setup-meta setup-meta--more">{second}</span>}
      </>
    );
  };

  return (
    <>
      <div className="setup-page setup-desktop">
        <SetupFrame current="templates" />
        {empty ? (
          <EmptyState title="No templates to show.">Document templates your role may read will appear here.</EmptyState>
        ) : (
          <>
            {allTest && (
              <Callout kind="warning">
                Every document currently uses a test template. When PSL supplies its real template, upload it here; documents already sent keep the template they were made with.
              </Callout>
            )}
            {notices}
            <div role="search" className="psl-toolbar">
              <SearchField label="Search" fieldClassName="setup-search" placeholder="Search templates" value={query} onChange={setQuery} />
              {state.nextCursor && needle && <span className="setup-more">Searching the {rows.length} shown</span>}
              <span className="setup-counts">
                <span className="setup-more">
                  {rows.length} {state.nextCursor ? 'SHOWN' : 'TEMPLATES'} · {testCount} TEST
                </span>
                {asOf && <span className="setup-more">AS OF {asOf.toUpperCase()}</span>}
              </span>
            </div>
            <Table
              caption="Document templates"
              className="setup-table setup-table--templates"
              columns={[
                {
                  key: 'document',
                  header: 'DOCUMENT',
                  cell: (row) => (
                    <div className="setup-docname">
                      {name(row)}
                      <span className="setup-meta">{metaParts(row).first}</span>
                      {metaParts(row).second && <span className="setup-meta setup-docname__history">{metaParts(row).second}</span>}
                    </div>
                  ),
                },
                { key: 'line', header: 'USED BY LINE', cell: (row) => <span className="setup-line">{row.line}</span> },
                { key: 'status', header: 'STATUS', cell: (row) => badge(row) },
                { key: 'action', header: 'Action', hideHeader: true, cell: (row) => <div className="setup-actioncell">{uploadButton(row, true)}</div> },
              ]}
              rows={matching}
              rowKey={(row) => row.template_id ?? `${row.name}-${matching.indexOf(row)}`}
              empty="No templates match your search."
              paging={paging}
              expanded={(row) => panelFor(row)}
            />
            <PagingNotes notes={notes} />
          </>
        )}
      </div>

      <div className="setup-page setup-phone">
        <PageTitle phoneSize={22}>Templates</PageTitle>
        {empty ? (
          <EmptyState title="No templates to show.">Document templates your role may read will appear here.</EmptyState>
        ) : (
          <>
            {allTest && (
              <Callout kind="warning">All {rows.length} are test templates until PSL supplies its own.</Callout>
            )}
            {asOf && <p className="setup-more">AS OF {asOf.toUpperCase()}</p>}
            {notices}
            <ul className="setup-cards">
              {rows.map((row, i) => (
                <li key={row.template_id ?? `${row.name}-${i}`} className="setup-card">
                  {name(row)}
                  {badge(row)}
                  <span className="setup-card__line">{row.line}</span>
                  {meta(row)}
                  {uploadButton(row, false)}
                  {panelFor(row)}
                </li>
              ))}
            </ul>
            <ShowMore solo {...paging} />
            <PagingNotes notes={notes} />
          </>
        )}
      </div>
    </>
  );
}
