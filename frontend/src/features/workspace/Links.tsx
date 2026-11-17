'use client';

// PROPOSAL (D-LINE-WORKSPACE, X-LINKS, contract mock only): the links a workspace supplies (proposals.ts). "assistant"
// is a link to the assistant page; "project_tab" (F-28) a link to one of the project's tabs; "document" reads E-DOCUMENT once, on press, and shows the version in a panel. The
// frame adds no words about the template: "Test template" is drawn only when the document says test_template.
import { useId, useState } from 'react';

import { api } from '@/api/client';
import { ApiError, errorFromResponse, networkError } from '@/api/errors';
import type { paths } from '@/api/schema';
import { Button, Callout, Link, Loading, Panel, Tag } from '@/components';
import { isAppPath } from '@/features/work-item/presentation';

import type { WorkspacePage } from './usePageReload';
import type { WorkspaceLink } from './proposals';

type Document = paths['/api/v1/documents/{document_id}/versions/{version}']['get']['responses'][200]['content']['application/json'];
type Reading = { key: string; status: 'loading' } | { key: string; status: 'ready'; document: Document } | { key: string; status: 'gone' | 'failed' };

// Frontend-owned neutral sentences (spec Assumptions); none of them is a business rule.
const LINK_TEXT = {
  loading: 'Opening the minutes…',
  gone: 'You can’t open this document.',
  failed: 'We couldn’t open the minutes. Try again.',
  retry: 'Try again',
  close: 'Close',
  testTemplate: 'Test template',
  status: 'Status',
  template: 'Template',
  version: 'Version',
  body: 'Open the file',
} as const;

async function readDocument(documentId: string, version: string): Promise<Document> {
  const result = await api.GET('/api/v1/documents/{document_id}/versions/{version}', { params: { path: { document_id: documentId, version } } }).catch((error: unknown) => {
    throw error instanceof ApiError ? error : networkError();
  });
  if (result.response.ok && result.data) return result.data;
  throw errorFromResponse(result.response.status, result.error);
}

function DocumentPanel({ document }: { document: Document }) {
  return (
    <Panel kind="readonly" head={document.title} headingLevel={3} className="ws-doc">
      <dl className="ws-facts">
        <div className="ws-fact">
          <dt>{LINK_TEXT.version}</dt>
          <dd>{document.version}</dd>
        </div>
        <div className="ws-fact">
          <dt>{LINK_TEXT.status}</dt>
          <dd>{document.status}</dd>
        </div>
        <div className="ws-fact">
          <dt>{LINK_TEXT.template}</dt>
          <dd>
            {document.template}
            {document.test_template && (
              <>
                {' '}
                <Tag tone="neutral">{LINK_TEXT.testTemplate}</Tag>
              </>
            )}
          </dd>
        </div>
      </dl>
      {document.body_url && (isAppPath(document.body_url) ? <Link href={document.body_url}>{LINK_TEXT.body}</Link> : <p className="ws-detail">{document.body_url}</p>)}
    </Panel>
  );
}

export function WorkspaceLinks({ links, page }: { links: WorkspaceLink[]; page?: WorkspacePage }) {
  const [reading, setReading] = useState<Reading | null>(null);
  const noteId = useId();
  if (links.length === 0) return null;

  const open = async (link: Extract<WorkspaceLink, { kind: 'document' }>) => {
    if (reading?.key === link.key && reading.status === 'ready') return setReading(null);
    if (reading?.status === 'loading') return;
    setReading({ key: link.key, status: 'loading' });
    try {
      setReading({ key: link.key, status: 'ready', document: await readDocument(link.documentId, link.version) });
    } catch (error) {
      const failure = error instanceof ApiError ? error : networkError();
      if (failure.kind === 'unauthenticated') page?.onAccessLost(failure);
      setReading({ key: link.key, status: failure.kind === 'forbidden' || failure.kind === 'not_found' ? 'gone' : 'failed' });
    }
  };

  return (
    <div className="ws-links">
      <div className="ws-links__row">
        {links.map((link) =>
          link.kind === 'assistant' ? (
            <Link key={link.key} href="/assistant">
              {link.label}
            </Link>
          ) : link.kind === 'project_tab' ? (
            <Link key={link.key} className="psl-btn psl-btn--secondary" href={link.href}>
              {link.label}
            </Link>
          ) : (
            <Button key={link.key} kind="secondary" aria-expanded={reading?.key === link.key && reading.status === 'ready'} aria-describedby={reading?.key === link.key ? noteId : undefined} onClick={() => void open(link)}>
              {link.label}
            </Button>
          ),
        )}
      </div>
      <div id={noteId} role="status" aria-live="polite">
        {reading?.status === 'loading' && <Loading>{LINK_TEXT.loading}</Loading>}
        {reading?.status === 'gone' && <Callout kind="warning" announce={false}>{LINK_TEXT.gone}</Callout>}
        {reading?.status === 'failed' && (
          <Callout kind="problem" announce={false}>
            <span>{LINK_TEXT.failed}</span>
            <Button
              kind="secondary"
              onClick={() => {
                const link = links.find((l) => l.key === reading.key);
                if (link?.kind === 'document') void open(link);
              }}
            >
              {LINK_TEXT.retry}
            </Button>
          </Callout>
        )}
      </div>
      {reading?.status === 'ready' && <DocumentPanel document={reading.document} />}
    </div>
  );
}
