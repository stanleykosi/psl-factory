VERDICT: CHANGES
COMMIT: 230edd60f366ea64a1a138dc66f2084bd447ebd1
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-2-2 and TECH-2-4 are fixed and tested. The start button is checked as greyed after the 422 and enabled again after a change. Problem boxes are keyed by name plus index. A 422 for the disabled Proof box now gets its own box.
- TECH-2-1 is only partly fixed. All five values named in round 2 are now refused (tab, newline, `//`, backslash, another origin). But `safePath` returns the *normalised* pathname, and a same-origin URL can normalise to `//host`. So `"/.//evil.example"` still becomes the link `//evil.example`, which goes to another site.
- The fix is one line: return `resolved.href`, or refuse a pathname that starts with `//`. Add a test for `"/.//evil.example"`.
- The other changes are presentation only and look correct: the moved change-line hint keeps `aria-describedby`, the Tola image has `alt=""`, and "change line" is regular weight. The start logic, idempotency, CSRF and request body are unchanged from round 2.
- `tests/start-work.test.tsx` passes at head (55 tests). No existing assertion was weakened.

## Findings
- TECH-3-1 | blocking | medium | frontend | `safePath` (`frontend/src/features/start-work/LineForm.tsx:121-130`) still lets some values link to another site. The origin check runs on the resolved URL. But the function then returns `resolved.pathname + resolved.search + resolved.hash`, and the URL parser can normalise a same-origin URL's path into one that starts with `//`. Next's `Link` (`LineForm.tsx:146`) then renders that as a protocol-relative href to another host. I ran the exact function body in node with origin `http://localhost:3501`. `"/.//evil.example"`, `"/a/..//evil.example"` and `"http://localhost:3501//evil.example"` all return `"//evil.example"`, and `new URL("//evil.example", origin).href` is `http://evil.example/`. Expected: return `resolved.href`, which is absolute and same-origin, so it can't be read as protocol-relative. Or return `undefined` when `resolved.pathname.startsWith('//')`. Add `'/.//evil.example'` to the `safePath` refused list (`tests/start-work.test.tsx:680`), or assert that it maps to a same-origin href. This is the same risk as TECH-2-1 (a bad or compromised E-LINES value), so it keeps the same severity.

## Verified
- TECH-2-1 | reopen | Every value in the coordinator's list is refused at head: `"/\t/evil.example"`, `"/\n/evil.example"`, `"//evil"`, `"/\\evil"` and `"https://evil"` all return `undefined`. I checked this by replicating the function in node and with the new unit tests at `tests/start-work.test.tsx:678-687`, which pass. A same-origin path with query and hash, and an absolute same-origin URL, are kept. It still fails on dot-segment values that normalise to `//host` (see TECH-3-1).
- TECH-2-2 | verified | `tests/start-work.test.tsx:494-498` asserts `start.disabled === true` after the 422 and `false` after `pick('Completed milestone', 'Milestone 3')`. The existing check that the second POST uses a new `idempotency_key` is still there. It passes at head.
- TECH-2-4 | verified | `ProblemBox` is keyed by `${problem.name}-${at}` (`LineForm.tsx:299`). `useStartWork.ts:203` matches a problem inline only against `fillable` fields, and `intake.ts:33` excludes `evidence`, so a `proof` problem goes to `unmatched`. The new test (`tests/start-work.test.tsx:520-546`) gets 3 boxes in order: proof, billing_contact, billing_contact. It also checks that no error appears under the disabled `.sw-proof` control. It passes at head.
- TECH-2-3 (backend, non-blocking) is kept, with a handoff note in build.md. TECH-1-1 and TECH-1-4 are unchanged and stay non-blocking.

## Notes
- The control-character regex in `safePath` adds safety, but the origin comparison is what actually protects the link. With `resolved.href` returned, the regex could stay or go.
- `movedHelp` (`LineForm.tsx:183-188`) handles two proof fields in a row and an owner with no help: both return `undefined`. The owner keeps the help's id in `aria-describedby`, and the proof box does not add it to its own.
- `safePath` reads `window.location.origin` as a default parameter during render. That is safe only because the drawer renders on the client after a click. Keep it out of any server-rendered path.
