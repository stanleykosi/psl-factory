# Technical review: frame phone-bar note (cc8ab63)

VERDICT: PASS

- Identical to F-11 604e1b0 for AppShell.tsx, PhoneBar.tsx and the shell.test.tsx note test (compared hunk by hunk). The only differences are the CSS fix (margin-left:auto plus a longer comment) and one extra test for it. F-11's setup-specific files are not touched, so F-11 merges cleanly; its shell.css line will conflict trivially (same line, different text), so take this branch's version.
- Pages without a note are unchanged: note is optional, the span renders only when `back?.note` is truthy, and the effect dependency just adds `note` (undefined stays stable).
- Note is rendered as a React text child, not as HTML.
- With `.psl-phonebar` using space-between, the auto margin pushes the note to the right so it sits next to the SAMPLE DATA tag (tag at the far right) instead of floating mid-bar. Without the tag it is at the far right.
- New test: DOM order and class are asserted. The CSS part is a regex on the stylesheet source, which is weak (it does not check layout) but acceptable in jsdom, which has no layout engine.
- `npx vitest run tests/shell.test.tsx`: 27 passed.
