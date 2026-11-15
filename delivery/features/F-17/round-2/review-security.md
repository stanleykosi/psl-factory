VERDICT: PASS
COMMIT: a5e803ab09ccd3122a4c252be8658a9138314be0
REVIEWER: reviewer-security
AUTHORITY: reviewer-security

## Summary
- Round-2 diff (1432023 to a5e803a) is layout, CSS and message-text work. The write path is unchanged: same shared client (CSRF), same single-flight guard, same key lifecycle, same lock after effect_uncertain.
- The 422 top alert now lists the response message plus messages for fields the form does not show. Each is a React text child (`<span>{m}</span>`). There is no innerHTML or dangerouslySetInnerHTML, and no markup or URL is built from the text.
- The new done and failed notice labels (step.label, result.message) are also text children. No new links. The only hrefs stay on the existing id-built Link components.
- Restricted rendering is unchanged. The new hasValue check only turns blank values into "Unknown". The side-column regrouping by section kind keeps restricted sections on the same SectionView path.
- usePageReload resets fresh/lost state when the id changes, so one item's data cannot carry over to another. No new dependency or secret.

## Findings
None.

## Notes
- The round-1 non-blocking notes still stand (resend lock lives in page state; backend must set `sends` and hold idempotency/reconcile server-side).
- Mobile CSS makes the decide panel sticky and hides its heading visually (still in the accessibility tree). This is not a security matter.
