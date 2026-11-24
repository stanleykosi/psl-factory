'use client';

// The Documents tab: the project's documents (title, version, status, TEST TEMPLATE) from E-PROJECT-TAB. A row opens its
// review (SCR-08) only when its own api_url is this project's document-review path; any other row is plain text (B-7:
// no live link from a tab row to a version id). No filter, search or upload.
import Link from 'next/link';

import { ShowMore, Table, Tag, Unknown, useIsPhone, type Column } from '@/components';
import { reviewHrefOf } from '@/features/documents/documentModel';

import { AsOf, useTabPaging, TabEmpty, tabStateView } from './TabParts';
import { textOf } from './model';
import type { DocumentRow } from './tabsModel';
import { useFocusAfterMore } from './useFocusAfterMore';
import { useProjectTab } from './useProjectTab';
import { useRef } from 'react';

// useProjectTab needs a view; Documents has no search or filter, so this carries nothing the query sends.
const VIEW = {};

function Title({ caseId, row }: { caseId: string; row: DocumentRow }) {
  const href = reviewHrefOf(caseId, (row as { api_url?: unknown }).api_url);
  return href ? <Link href={href}>{row.title}</Link> : <>{row.title}</>;
}

const Status = ({ row }: { row: DocumentRow }) => textOf(row.status) ?? <Unknown />;
const Template = ({ row }: { row: DocumentRow }) => (row.test_template === true ? <Tag tone="waiting">TEST TEMPLATE</Tag> : null);

function DocumentCards({ caseId, rows }: { caseId: string; rows: DocumentRow[] }) {
  return (
    <div role="list" className="ptabs__cards">
      {rows.map((row) => (
        <div key={`${row.document_id}-${row.version}`} role="listitem" className="ptabs__card">
          <span className="ptabs__cardhead">
            <strong>
              <Title caseId={caseId} row={row} />
            </strong>
            <Template row={row} />
          </span>
          <span className="ptabs__cardhint">
            v{row.version} · <Status row={row} />
          </span>
        </div>
      ))}
    </div>
  );
}

export function DocumentsTab({ caseId }: { caseId: string }) {
  const phone = useIsPhone();
  const { state, more, showMore, retry } = useProjectTab(caseId, 'documents', VIEW);
  const { rows: pagedRows, paging } = useTabPaging(state, more, showMore, '');
  const rowsRef = useRef<HTMLDivElement>(null);
  useFocusAfterMore(rowsRef, pagedRows.length);

  const columns: Column<DocumentRow>[] = [
    {
      key: 'document',
      header: 'DOCUMENT',
      cell: (row) => (
        <>
          <Title caseId={caseId} row={row} /> <Template row={row} />
        </>
      ),
    },
    { key: 'version', header: 'VERSION', cell: (row) => `v${row.version}` },
    { key: 'status', header: 'STATUS', cell: (row) => <Status row={row} /> },
  ];

  let body = tabStateView(state, { retry, signInPath: `/projects/${encodeURIComponent(caseId)}/documents` });
  if (state.status === 'ready') {
    const rows = pagedRows;
    body =
      rows.length === 0 ? (
        <TabEmpty>No documents on this project yet.</TabEmpty>
      ) : (
        <>
          <div ref={rowsRef} className="ptabs__rows">
            {phone ? (
              <>
                <DocumentCards caseId={caseId} rows={rows} />
                <ShowMore solo {...paging} />
              </>
            ) : <Table className="ptabs__table" caption="Documents" columns={columns} rows={rows} rowKey={(row) => `${row.document_id}-${row.version}`} empty="" paging={paging} />}
          </div>
          <AsOf value={state.asOf} />
        </>
      );
  }
  return <>{body}</>;
}
