VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: cc694876c715f0c927f3879491eb9ede706c4f31

Scope: diff 521bbf18..cc694876.

- Links.tsx: project_tab href still comes only from link.href (data); only a className was added. The assistant link stays the fixed "/assistant". Both use the internal Link component. No new href source, no dangerouslySetInnerHTML.
- Sections.tsx: data-label={c.label} and a static class toggle are rendered as React text/attributes (escaped). No injection path.
- CSS and tests: no security impact.

No findings.
