import type { Metadata } from 'next';

import { DocumentReviewPage } from '@/features/documents/DocumentReview';

// The title never names the document or project: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Document · PSL Factory' };

export default async function DocumentPage({ params }: { params: Promise<{ caseId: string; documentId: string }> }) {
  const { caseId, documentId } = await params;
  return <DocumentReviewPage caseId={caseId} documentId={documentId} />;
}
