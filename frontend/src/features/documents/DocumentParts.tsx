// SCR-08 document content: the numbered sections with their agent notes, the Checks panel with the audience, the
// returned banner and the agent's panel. Every value is the response's own; text is rendered as React text, so
// markup in a section shows as characters.
import { AGENTS, AgentAvatar, agentKey, Button, Panel, Tag, Unknown, VisuallyHidden } from '@/components';
import { When } from '@/features/decide/DecisionContent';

import {
  agentName,
  checksOf,
  checkTag,
  checkTone,
  notesOf,
  paragraphsOf,
  returnedByText,
  textOf,
  type DocReturned,
  type DocSection,
  type DocumentView,
} from './documentModel';

function Notes({ section }: { section: DocSection }) {
  const notes = notesOf(section);
  if (notes.length === 0) return null;
  return (
    <>
      {notes.map((note, i) => (
        <p key={i} className="docrev__note">
          <strong>{agentName(note.agent)}</strong>
          <VisuallyHidden> (agent note)</VisuallyHidden>: {note.text}
          {Array.isArray(note.cites) &&
            note.cites.map((cite, j) => (
              <span key={j} className="docrev__cite">
                {' '}
                {cite.label} {cite.reference}
              </span>
            ))}
        </p>
      ))}
    </>
  );
}

/** The document text. `changed` marks sections the response flags as changed (a tint and a hidden sentence). */
export function Sections({ doc, sections, showNotes = true }: { doc: DocumentView; sections: DocSection[]; showNotes?: boolean }) {
  return (
    <article className="docrev__doc" aria-labelledby="docrev-doc-title">
      <h2 id="docrev-doc-title" className="cmp-sr">
        {doc.title}
      </h2>
      <div className="docrev__dochead">
        <strong>v{doc.version}</strong>
        {doc.test_template === true && <span className="docrev__testtemplate">TEST TEMPLATE</span>}
      </div>
      {sections.length === 0 ? (
        <p className="docrev__sectionempty">This document has no sections yet.</p>
      ) : (
        sections.map((section, i) => (
          <section key={section.key} className={section.changed_since === true ? 'docrev__section is-changed' : 'docrev__section'}>
            <h3>
              {i + 1}. {section.heading}
            </h3>
            {section.changed_since === true && <p className="cmp-sr">Changed since the last version.</p>}
            {paragraphsOf(section.text).map((p, j) => (
              <p key={j} className="docrev__text">
                {p}
              </p>
            ))}
            {showNotes && <Notes section={section} />}
          </section>
        ))
      )}
    </article>
  );
}

/** The document has no `sections` at all: only the link the response gave (never embedded or fetched). */
export function NoText({ doc }: { doc: DocumentView }) {
  return (
    <article className="docrev__doc docrev__notext" aria-label="Document text">
      <p className="docrev__text">The text isn&rsquo;t available here.</p>
      {textOf(doc.body_url) && (
        <p className="docrev__text">
          <a href={doc.body_url} rel="noopener noreferrer" download>
            Download
          </a>
        </p>
      )}
    </article>
  );
}

function CheckRow({ doc, check }: { doc: DocumentView; check: ReturnType<typeof checksOf>[number] }) {
  const tag = checkTag(check);
  // The board draws the test-template check in amber: it passes, and the template is still a test one.
  const tone = check.key === 'template' && doc.test_template === true && checkTone(check) === 'done' ? 'waiting' : checkTone(check);
  return (
    <li className="docrev__check">
      <span className="docrev__checklabel">{check.label}</span>
      <Tag tone={tone}>{tag.text}</Tag>
      {tag.reason && <span className="docrev__reason">{tag.reason}</span>}
      {textOf(check.cite) && <span className="docrev__cite">{check.cite}</span>}
    </li>
  );
}

/** Checks in the order sent, then the audience row. */
export function ChecksPanel({ doc }: { doc: DocumentView }) {
  const checks = checksOf(doc);
  const audience = textOf(doc.audience?.label);
  return (
    <Panel head="Checks" headingLevel={2} className="docrev__checks" bodyClassName="docrev__checksbody">
      <ul className="docrev__checklist">
        {checks.map((check) => (
          <CheckRow key={check.key} doc={doc} check={check} />
        ))}
        <li className="docrev__check">
          <span className="docrev__checklabel">Audience</span>
          {audience ? <Tag tone="neutral">{audience}</Tag> : <Unknown />}
        </li>
      </ul>
    </Panel>
  );
}

/** The returned banner; the quote only where the response sent the note (INV-ACCESS), never a made-up one. */
export function ReturnedBanner({ returned, version }: { returned: DocReturned; version: string }) {
  const note = textOf(returned.note);
  return (
    <div className="docrev__returned">
      <div className="docrev__returnedhead">
        {returnedByText(returned)}
        {returned.at && (
          <>
            {' · '}
            <When at={returned.at} />
          </>
        )}
      </div>
      <div className="docrev__returnedbody">
        {note ? <p className="docrev__quote">&ldquo;{note}&rdquo;</p> : <p className="docrev__quote">The note isn&rsquo;t shown to you.</p>}
        <p className="docrev__rule">
          v{version} is kept as returned. Your fix becomes v{Number(version) + 1} and goes back to the PMO Lead. Approval on v{version} is not carried over.
        </p>
      </div>
    </div>
  );
}

/** The agent's panel on the returned state: the agent's own words from the work item, then the two held buttons. */
export function AgentPanel({ agent, lines, next }: { agent: string; lines: string[]; next: number }) {
  const key = agentKey(agent);
  return (
    <Panel
      kind="agent"
      as="aside"
      aria-label={`${agentName(agent)}'s note`}
      className="docrev__agent"
      head={
        <span className="docrev__agenthead">
          {key && <AgentAvatar agent={key} size={32} />}
          <span>
            <strong>{agentName(agent)}</strong>
            {key && ` · ${AGENTS[key].role}`}
          </span>
        </span>
      }
    >
      <div className="docrev__agentbody">
        {lines.map((line, i) => (
          <p key={i}>{line}</p>
        ))}
        <p>
          <Button kind="text" disabled reason="Not available yet">
            Ask {agentName(agent)} to draft v{next}
          </Button>
        </p>
      </div>
    </Panel>
  );
}
