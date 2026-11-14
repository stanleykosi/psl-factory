VERDICT: CHANGES (1 must-fix: TECH-1; TECH-2 and TECH-3 are minor/notes)

Review of branch fe-frame-phone-back, head e8e99658275de990dd7d3c4c9dddf7fb50789f98, against origin/dlv-00-delivery-setup (one commit, 8 files, +181/-11). Goal: decision D-23.

## What I checked

- Read the full diff, AppShell.tsx, PhoneBar.tsx, the fixture page, the unit and e2e additions, and BUILD-NOTE.md.
- Boards: SCR-10-mobile shows only "← Queue" then the heading. SCR-22-mobile shows only "← Home". SCR-01-mobile (top level) shows PSL FACTORY and Start. So hiding Menu and the brand on sub-pages matches the boards.
- Ran `npx vitest run tests/shell.test.tsx`: 24 passed.
- Ran `git merge-tree` against fe-m2a-start-work-pick-a-line-fill-its-intake-i to check the merge with F-05.

## What holds

- **The slot is simple.** One setter context, one `useState` in AppShell, and an optional `back` prop on PhoneBar that defaults to null. The provider wraps only the loaded children. `usePhoneBack` can only run once /me is ready, and if /me reloads the children unmount and the link clears. The hook throws outside AppShell, which is right.
- **Unmount clears the link.** The effect cleanup sets it back to null. Navigating from a sub-page to a top-level page ends with no link, and changing the label or href replaces it. Unit and e2e tests cover both.
- **Pages that set no link are unchanged.** `hasMenu` only changes when `back` is set. The brand span and menu panel are the same as before. TopNav is not touched. The phone title stays 26px through the existing media query at shell.css:43. Only the desktop `.shell-title` changes, from 36px to 40px, which D-23 asks for.
- **Accessibility.** The link's accessible name is "Back to Queue". It contains the visible word "Queue", so WCAG 2.5.3 (label in name) holds. It is a real `Link`, reachable by keyboard with the existing white focus ring (e2e: Tab, focus style, Enter), and axe is clean in jsdom and the browser. The skip link is still first.
  - Menu is gone on sub-pages, so the main navigation is one step away through the back link. That is how SCR-10/22-mobile draw it, and the decision sits under D-08/D-23 with the design engineer. On desktop the TopNav is unaffected.
- **The fixture gate.** The page reads `process.env.FRAME_FIXTURES` at request time (`force-dynamic`, server component, not a `NEXT_PUBLIC_` variable, so the build does not inline it). It calls `notFound()` unless the value is exactly '1'. The only place that sets it is the Playwright `next start` environment, and nothing in frontend/ or delivery/ sets it for a real deployment. The client component ships in the bundle, but it cannot render anything without the gate.

## Findings

### TECH-1 (must fix): the back link is set and cleared after paint, so a stale or missing link can show for a frame during navigation

AppShell.tsx `usePhoneBack` uses `useEffect`. PhoneBar re-mounts on the new pathname in the same commit that swaps the page, but `phoneBack` is still the old page's value until passive effects run. Next's Link navigation is a transition, so passive effects run after paint. The results:

- Sub-page A ("← Queue") to a top-level page: the top-level page paints once with "← Queue" and no Menu, then Menu appears.
- Sub-page A to sub-page B ("← Projects"): B paints once with A's "← Queue".
- First load of a sub-page: the bar paints once with Menu and PSL FACTORY, then swaps to "← label".

This is the "stale link across navigation" case the task asks about. The fix is one word: use `useLayoutEffect` in `usePhoneBack`. The cleanup and the set then both run before paint. It is safe here because the children only render on the client after /me loads, so there is no server-render warning, and React 19 does not warn anyway.

Please also add a unit test that renders sub-page component A and then a different component B with another label (a remount, not a prop change on the same instance). It should assert that B's label shows and A's never comes back. The current "follows the page" test only rerenders the same `SubPage` instance.

### TECH-2 (minor): the 404 gate has no automated check

Nothing tests that `/frame-fixtures/phone-back` returns 404 without `FRAME_FIXTURES=1`. The code is clearly correct. A small vitest that calls the page function with the variable unset and expects `notFound` (mock `next/navigation`) would stop a later edit from silently opening the page. Optional.

### TECH-3 (note for whoever merges F-05): there is a textual conflict in PhoneBar.tsx, and one behaviour needs deciding

`git merge-tree` reports a content conflict in frontend/src/shell/PhoneBar.tsx. Both branches rewrite the `Props` line and the doc comment. It is easy to resolve: keep this branch's `Props` with `back?`, and F-05's import, `canStart`, header class and `sw-phoneslot` block. shell.test.tsx merges cleanly, and TopNav and AppShell do not overlap.

Behaviour after the merge: SCR-10-mobile and SCR-22-mobile draw only "← label" on sub-pages, with no "+ Start". So the merged `canStart` should probably also require `back === null` (and drop the `sw-phonebar` class when it is false). That belongs to F-05's merge and the design engineer, not to this branch.

## Scope

Everything is inside the frame lane: shell, shell CSS, a gated fixture, tests, and the Playwright env. No page adopts the slot yet, as D-23 intends.

## Round 2 (fb3a4d3)

Ran `npx vitest run tests/shell.test.tsx tests/frame-fixtures.test.tsx`: 27 passed. Then reverted `useLayoutEffect` to `useEffect` in a scratch edit of AppShell.tsx (restored afterwards; the worktree has no tracked changes) and re-ran shell.test.tsx: 25 passed.

### TECH-1: REOPENED (code fixed, test does not guard it)
- Code: `usePhoneBack` now uses `useLayoutEffect`. Correct.
- Test: the new "swapping to a different sub-page" test passes on the old `useEffect` code. RTL's `rerender` runs inside `act`, which flushes passive effects before it returns, so the "synchronously after the commit" assertion cannot see the pre-paint state. The comment in the test claims something it does not check. A later revert to `useEffect` would go unnoticed.
- Needed: make the test discriminate, or drop the false claim. Options: capture the DOM at commit time (a layout effect or ref callback in a probe sibling that records `phoneBar()` link text during the commit and asserts it is already `['← Projects']`; passive-effect code would record `← Queue`). Or render with `react-dom/client` `createRoot` and `flushSync`, with no `act`, then assert before passive effects flush. Verify it fails with `useEffect` before accepting it.

### TECH-2: VERIFIED
`tests/frame-fixtures.test.tsx` mocks `notFound`, asserts a 404 for an empty value and for 'true' (only '1' opens), and asserts the page renders with '1'. Passes.

### TECH-3: n/a (note for the F-05 merge).

VERDICT: CHANGES

## Round 3 (be6b60e)

### TECH-1: VERIFIED
With `useLayoutEffect` changed to `useEffect` in AppShell.tsx (scratch edit), shell.test.tsx fails: "swapping to a different sub-page never commits the old link for the new page" (1 failed, 24 passed). After `git checkout src/shell/AppShell.tsx`, `tests/shell.test.tsx` and `tests/frame-fixtures.test.tsx` pass (27 tests). The worktree has no tracked changes.

VERDICT: PASS
