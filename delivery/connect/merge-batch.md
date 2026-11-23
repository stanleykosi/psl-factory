# Risky merges waiting for the design engineer (D-180)

| Feature | PR | Summary | Evidence |
|---|---|---|---|
| ~~F-58 (lane A) · sign in and sign out (SCR-17)~~ MERGED 8f562602 (D-183) | https://github.com/stanleykosi/psl-factory/pull/100 | Sign-in page on the live session API, Sign out in the account menu, signed-out link to `/sign-in`. Sign-in surface, high risk; product acceptance required. F-59 and F-60 build on it. | Head `57ae81e8`: gate PASS (3824 tests); technical, security (Opus), UX, UI, QA (live sign-in, sign-out, bad details) and PMO all PASS; fidelity 100% coverage, visual waived by D-179. Non-blocking: SEC-1-1 (sign-out is an in-app move, not a fresh load), TECH-1-1 (mock 401 scenario). Main merged in and gate re-run right before merge. |
