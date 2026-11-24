// SCR-08 document content: the numbered sections and the audience beside them. Every value is the response's own; text
// is rendered as React text, so markup in a section shows as characters.
import { Callout, Panel, Tag } from '@/components';

import { paragraphsOf, type LiveDocument } from './documentModel';

/** The document text: each preview item is a numbered section, its text split on blank lines. */
export function Sections({ doc }: { doc: LiveDocument }) {
  return (
    <article className="docrev__doc" aria-labelledby="docrev-doc-title">
      <h2 id="docrev-doc-title" className="cmp-sr">
        {doc.title}
      </h2>
      <div className="docrev__dochead">
        <strong>v{doc.version}</strong>
      </div>
      {doc.preview.length === 0 ? (
        <p className="docrev__sectionempty">This document has no sections yet.</p>
      ) : (
        doc.preview.map((section, i) => (
          <section key={i} className="docrev__section">
            <h3>
              {i + 1}. {section.field}
            </h3>
            {paragraphsOf(section.text).map((p, j) => (
              <p key={j} className="docrev__text">
                {p}
              </p>
            ))}
          </section>
        ))
      )}
    </article>
  );
}

/** The audience, the one fact the response gives about who the document is for. */
export function AudiencePanel({ audience }: { audience: string }) {
  return (
    <Panel head="Audience" headingLevel={2} className="docrev__checks" bodyClassName="docrev__checksbody">
      <ul className="docrev__checklist">
        <li className="docrev__check">
          <span className="docrev__checklabel">Audience</span>
          <Tag tone="neutral">{audience}</Tag>
        </li>
      </ul>
    </Panel>
  );
}

/** Why a decision is not open yet: the publication read's own sentences, listed as sent. */
export function Blockers({ findings }: { findings: string[] }) {
  return (
    <Callout kind="warning" announce={false}>
      <strong>Not ready to decide yet</strong>
      <ul className="docrev__blockers">
        {findings.map((finding, i) => (
          <li key={i}>{finding}</li>
        ))}
      </ul>
    </Callout>
  );
}
