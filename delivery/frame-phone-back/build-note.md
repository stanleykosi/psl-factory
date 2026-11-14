STATUS: READY
COMMIT: fb3a4d3faf8468f7afa1a408b7ce37a0b17fdef6
BUILDER: builder
LANE: frontend

## Summary
- The frame now has a typed phone back-link slot: `usePhoneBack({ label, href })` from `@/shell/AppShell`.
- When a page sets it, the phone bar shows only "← label" (white, 44px tall, 16px in) plus the sample tag slot, in place of Menu and PSL FACTORY. This matches SCR-10/07/22/06/13/04 mobile, which all hide Menu on sub-pages. Menu is one tap back on the destination page.
- Pages that don't set it are unchanged. No existing page adopts it yet; each page does that in its own follow-up.
- `.shell-title` desktop size goes from 36px to 40px, as on SCR-01-desktop and SCR-22-desktop. Phone stays at 26px, which matches the boards' top-level pages.

## Changes
- frontend/src/shell/AppShell.tsx: `PhoneBackContext` (setter), `usePhoneBack` hook (sets on mount or change, clears on unmount), and the state passed to PhoneBar as `back`.
- frontend/src/shell/PhoneBar.tsx: exported `PhoneBack` type, optional `back` prop (additive, defaults to null). When it is set: no Menu button or menu panel, and a `Link` "← label" with accessible name "Back to label" in place of the brand.
- frontend/src/styles/shell.css: `.shell-title` is 40px.
- frontend/src/app/frame-fixtures/phone-back/: a browser-run fixture page that uses the slot. It returns 404 unless the server sets FRAME_FIXTURES=1, so no real page content changed. frontend/playwright.config.ts sets FRAME_FIXTURES=1 for `next start`.
- frontend/tests/shell.test.tsx: 4 unit tests covering set, replace, unset, keyboard focus, accessible name, no Menu or brand, and axe.
- frontend/e2e/frame.spec.ts: a 390px test. The back link is in the bar, Menu and brand are absent, the link's look and position are checked, axe passes, Tab reaches it with the white focus ring, and Enter goes to /my-work where Menu is visible.

## Fixes
- TECH-1 | fb3a4d3 | `usePhoneBack` uses `useLayoutEffect`, so the back link is set and cleared before paint and no frame shows the previous page's link, Menu or brand. A new unit test swaps sub-page A ("← Queue") for a different component B ("← Projects") and checks synchronously after the commit that only "← Projects" shows. This test fails with the old `useEffect`.
- TECH-2 | fb3a4d3 | New tests/frame-fixtures.test.tsx checks that the fixture page calls `notFound()` unless FRAME_FIXTURES is exactly '1', and renders when it is.
- TECH-3 | not changed | This is a note for whoever merges F-05. The PhoneBar.tsx conflict should keep `back?` in Props. F-05's `canStart` should probably also require `back === null`, because the sub-page boards draw no "+ Start". That is for F-05's merge and the design engineer to decide.

## Acceptance criteria
1. [x] The bar renders as the boards draw it when the slot is set: e2e plus screenshot (the bar shows only "← Queue").
2. [x] The bar is unchanged when the slot is not set: all existing unit tests (323) and e2e tests (84) pass.
3. [x] Unit tests for set and unset, keyboard focus and accessible name: tests/shell.test.tsx "phone back link".
4. [x] e2e at 390: the back link is shown, and Menu is reachable by going back (the boards hide Menu on sub-pages).
5. [x] 40px desktop titles: the SCR-01-desktop visual score at 1440 went from 88.6 to 88.8. Coverage stayed at 82.1% before and after.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exits 0 (lint, typecheck, 326 vitest tests, build); round 1 had 323.
- `E2E_PORT=4501 MOCK_PORT=4502 npx playwright test`: 84 passed, both before and after the TECH fixes.
- Fidelity: frame-fid-before (88.6) and frame-fid (88.8) are in the session scratchpad.
- Deleted frontend/test-results. Stopped the servers on 4501 and 4502.

## Note for adopters
`usePhoneBack` sets state in a layout effect. On first load in jsdom, wait for the link with `findByRole` or `waitFor`, because the page mounts after the /me fetch.
