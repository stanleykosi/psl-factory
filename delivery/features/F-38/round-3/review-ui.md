VERDICT: PASS
REVIEWER: reviewer-ui
COMMIT: 4b70abcdc0d7a345e6f66a90324b6f92411878c3
AUTHORITY: delivery UI review

## Findings
- UI-2-1 | accepted for sign-off | unsigned waivers wait for the design engineer. This does not block the build.
- UI-1-4 | non-blocking | sign-off item | tab nav role/name exceptions and the dark Submission chip (shared F-18 frame).
- UI-1-5 | non-blocking | sign-off item | title is h2 under the frame h1.
- UI-1-6 | non-blocking | sign-off item | shared-code colour deviations. The SUBMITTED tag is now neutral, as F-18 draws it.
- UI-1-7 | non-blocking | sign-off item | remaining shared-code differences, honestly listed.
- UI-1-9 | non-blocking | sign-off item | top bar exceptions (no PMO Lead persona, /me never read). Add the persona or sign them as shell.

## Verified
- UI-1-8 | verified | live at 390 on W-3501. The .ws-decide bar holding Send for review and Edit cover letter has computed position fixed, bounding box x0 y699 w390 h145, so it ends at 844 (the viewport bottom). The box is identical at scroll 0 and at scroll 100000 (page height 1249). Edit cover letter sits inside it at y786. So it is a pinned bottom bar, as the board draws. My round-2 finding came from a full-page capture and was wrong. The builder's claim holds.
