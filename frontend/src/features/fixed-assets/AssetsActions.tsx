'use client';

// F-102: the links the section renderer cannot draw (it links app paths only): the date-proof PDFs and the accounting note. No write
// control is drawn here (F-102B adds them). A proof link is drawn only for a fact id the read lists; the PDF is served only to a
// person with access. The accounting note link is the returned URL as sent, and nothing at all when it is null.
import { Link, Panel } from '@/components';
import type { LineActionsProps } from '@/features/workspace/adapter';

import type { AssetsReadback } from './assetsAdapter';
import { proofLinks } from './labels';

export function AssetsActions({ readback, ctx }: LineActionsProps<AssetsReadback>) {
  if (readback.error) {
    return readback.error.signIn ? (
      <p>
        <Link href={`/sign-in?next=${encodeURIComponent(`/work/${ctx.workId}`)}`}>Sign in</Link>
      </p>
    ) : null;
  }
  const a = readback.assets;
  const proofs = proofLinks(a);
  const note = typeof a.accounting_note_url === 'string' && a.accounting_note_url !== '' ? a.accounting_note_url : null;
  if (proofs.length === 0 && note === null) return null;
  return (
    <Panel kind="readonly" head="Proof and notes" headingLevel={2}>
      {proofs.length > 0 && (
        <ul>
          {proofs.map((p) => (
            <li key={p.factId}>
              <a className="psl-link" href={`/api/v1/work/${ctx.workId}/assets/date-proofs/${p.factId}`} target="_blank" rel="noopener noreferrer">
                Open proof
              </a>{' '}
              <span className="ws-detail">{p.assetId ? `Date proof for ${p.assetId}` : `Other proof ${p.factId}`}</span>
            </li>
          ))}
        </ul>
      )}
      {note !== null && (
        <p>
          <a className="psl-link" href={note} target="_blank" rel="noopener noreferrer">
            Open accounting note
          </a>
        </p>
      )}
    </Panel>
  );
}
