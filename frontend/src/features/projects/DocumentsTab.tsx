'use client';

// The Documents tab on the live sectioned project tab: the project's recorded documents (title, version, status, date). A row
// opens its review (SCR-08) only when its own api_url is this project's document-review path; any other row is plain text (B-7:
// no live link from a tab row to a version id). No filter, search or upload.
import Link from 'next/link';
import { useRef } from 'react';

import { Table, When, useIsPhone, type Column } from '@/components';
import { reviewHrefOf } from '@/features/documents/documentModel';

import { MoreFooter } from './MoreFooter';
import { DOCUMENTS_SECTION_KEY, type SectionItem } from './sectionsModel';
import { AsOf, TabEmpty, TabNoAccess, tabStateView } from './TabParts';
import { useFocusAfterMore } from './useFocusAfterMore';
import { useProjectSections } from './useProjectSections';

const rowKey = (row: SectionItem) => `${row.api_url ?? ''}|${row.record_id}`;

function Title({ caseId, row }: { caseId: string; row: SectionItem }) {
  const href = reviewHrefOf(caseId, row.api_url);
  return href ? <Link href={href}>{row.title}</Link> : <>{row.title}</>;
}

const Updated = ({ row }: { row: SectionItem }) => <When value={row.at} show="date" />;

function DocumentCards({ caseId, rows }: { caseId: string; rows: SectionItem[] }) {
  return (
    <div role="list" className="ptabs__cards">
      {rows.map((row) => (
        <div key={rowKey(row)} role="listitem" className="ptabs__card">
          <span className="ptabs__cardhead">
            <strong>
              <Title caseId={caseId} row={row} />
            </strong>
          </span>
          <span className="ptabs__cardhint">{[row.state, row.detail].filter(Boolean).join(' · ')}</span>
          <span className="ptabs__cardhint">
            Updated <Updated row={row} />
          </span>
        </div>
      ))}
    </div>
  );
}

export function DocumentsTab({ caseId }: { caseId: string }) {
  const phone = useIsPhone();
  const { state, more, showMore, retry } = useProjectSections(caseId, 'documents', undefined);
  const rowsRef = useRef<HTMLDivElement>(null);
  const ready = state.status === 'ready' ? state : undefined;
  const section = ready?.sections.find((s) => s.key === DOCUMENTS_SECTION_KEY);
  const rows = section?.items ?? [];
  useFocusAfterMore(rowsRef, rows.length);

  const columns: Column<SectionItem>[] = [
    { key: 'document', header: 'DOCUMENT', cell: (row) => <Title caseId={caseId} row={row} /> },
    { key: 'version', header: 'VERSION', cell: (row) => row.state },
    { key: 'status', header: 'STATUS', cell: (row) => row.detail ?? '—' },
    { key: 'updated', header: 'UPDATED', cell: (row) => <Updated row={row} /> },
  ];

  let body = tabStateView(state, { retry, signInPath: `/projects/${encodeURIComponent(caseId)}/documents` });
  if (ready) {
    if (!section) body = <TabNoAccess />;
    else if (rows.length === 0) body = <TabEmpty>No documents on this project yet.</TabEmpty>;
    else
      body = (
        <>
          <div ref={rowsRef} className="ptabs__rows">
            {phone ? <DocumentCards caseId={caseId} rows={rows} /> : <Table className="ptabs__table" caption="Documents" columns={columns} rows={rows} rowKey={rowKey} empty="" />}
          </div>
          <MoreFooter hasMore={section.has_more} busy={more === 'loading'} failed={more === 'error'} onMore={showMore} />
          <AsOf value={ready.asOf} />
        </>
      );
  }
  return <>{body}</>;
}
