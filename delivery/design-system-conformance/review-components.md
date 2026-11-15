VERDICT: PASS
COMMIT: c144c91c5e0efe44abd04b94a8b796eaafcf358a
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

Run: `npx vitest run tests/components` in the worktree: 22 files, 75 tests pass. Read in full: Button, Callout, Tag/StateTag, Panel, TextField/Field, Select, Segmented, Tabs, Menu, Drawer, Dialog, FileUpload, ShowMore, Toast, Values, format, internal, components.css; the tokens.json and gen-styles diff. I did not compare every class against the bundle by script. Classes spot-checked match the spec folders and the build note's recorded deviations (all 12 spec gaps are reasonable).

Confirmed good: all 22 test files run axe (`violations()` from a11y.ts, WCAG 2.x A/AA, contrast off as in the project setup); tests assert keyboard, focus return, class names and states, not snapshots. The tokens.json additions (spacing px, z-index, motion) are generated and covered by the existing drift test (fresh generation equals committed tokens.css). The `--text-*` additions derive from tokens.json, so drift stays meaningful. Every `var(--x)` in components.css is defined. The only literals in components.css are the marked 719.98px, 18px, 26px and 1px sr-only; no hex or rgb (the existing grep test covers src/**/*.css). The inline styles are data widths only (progress, skeleton). Callout roles follow D-92 (alert and status only when `announce`). Drawer/Dialog trap focus, close on Esc and return focus to the opener, and Esc inside a Dialog opened from a Drawer does not close the drawer (portal events bubble through the React tree and `stopPropagation` is used). Menu, Tabs, Segmented and Select follow their APG patterns (roving tabindex, Home/End, wrap, typeahead, activedescendant).

## Findings
- DSC-1 | non-blocking | low | builder | `formatTime` / `formatDateTime` / `When show="time"` on a date-only string ("2026-11-17") parse it as UTC midnight and print "01:00 WAT". `formatDate` handles the date-only case but the time path does not. Return Unknown (or the date alone) for a date-only value in time and datetime modes. Migration lanes must pass timestamps, not calendar dates, to `show="time"` or `"datetime"`.
- DSC-2 | non-blocking | low | builder | `Toast` renders its `role="status"` / `role="alert"` element together with its content. Many screen readers do not announce a live region that mounts already filled. Keep a persistent empty live region in the toast host, or add the content a tick after mount. Whichever lane builds the toast host should do this once rather than each screen working around it.
- DSC-3 | non-blocking | low | builder | `formatAmount` accepts JS numbers. Beyond 2^53, or after arithmetic like 0.1+0.2, `String(n)` gives an inexact or exponent form (exponent forms print "Unknown", which is safe). Money must be passed as a decimal string. Do not pass a `number` computed in the browser; state this in the README so lanes do not.
- DSC-4 | non-blocking | low | builder | Menu: a link item (`href`) is a `menuitem` anchor, so Space does not activate it (native links activate on Enter only). Also `Tabs` has no disabled tab handling, unlike `Segmented`. Neither is needed by current callers; add them before a lane needs it.
- DSC-5 | non-blocking | low | builder | The build note says `Select` has no search box for lists over about 15 options (spec gap 11). Lanes must not replace long pickers (people, projects, records) with `Select`; keep RecordPicker for those.

## Do not copy (for the three migration lanes)
- Do not copy `Tabs` as a div-with-role-tablist model for in-page navigation where tabs are links; it is correct, but only keep `role="tab"` on link tabs when each has its own panel and address, as ProjectTabs does.
- Do not wrap the Callout `announce` default blindly: pass `announce={false}` for any problem or success callout that is part of the loaded page, or the page will announce on load.
- Do not pass `disabled` to `Button` while submitting; use `busy`.
- Do not use `getByLabelText` with `Select`, `DateField` or `FileUpload` in tests; use `getByRole('combobox', { name })`.
- Do not pass numbers or 0 for unknown amounts to `Money` or `MoneyField`; use null.
- Do not hand-roll a modal trap; use `Drawer`, `BottomSheet` or `Dialog` (`useModal` is internal and unexported).
