# Decisions, 23 November 2026: sign-in, reset and invitation set-up approved as built

Relayed by the coordinator from the design engineer (hunchoweb), at the start of wave 1 (task FE-SIGNIN, SCR-17).

## Context

D-SIGNIN r1 was left open for the backend developer: sign-in through new session endpoints or styled Django pages, and how reset and invite set-up work. API 1.22.0 (main, 22 Nov 2026) built new session, recovery and invitation endpoints, and Django is now API-only. `handoffs/nextjs/README.md` sets the browser destinations.

## Question and answer

Asked: "Decision D-SIGNIN (how sign-in, password reset and invitation set-up work) is still 'not decided', and it blocks the sign-in screen. The backend built it this way: the Next.js app draws its own sign-in, reset and set-up pages and talks to /api/v1/session, /api/v1/accounts/recovery/* and /api/v1/accounts/invitations/*. Reset and invitation links arrive at /accounts/recovery/link/ and /staff/join/, with the token in the link. Approve D-SIGNIN as built?"

Answer (design engineer, 23 Nov 2026): **"Approve as built"**.

## What is approved (D-SIGNIN r2)

- The Next.js app draws sign-in, error, reset and account set-up (SCR-17) itself. Django pages are not styled for it.
- Sign-in and sign-out use `GET` and `POST /api/v1/session` and `POST /api/v1/session/logout`. The CSRF token rotates on each (D-AUTH r3).
- Reset uses `POST /api/v1/accounts/recovery/request`, then `POST /api/v1/accounts/recovery/link`, which redeems the token from the link, then `GET` and `POST /api/v1/accounts/recovery/password`. The emailed link opens `/accounts/recovery/link/`, with the token in the URL fragment.
- Invitation set-up uses `POST /api/v1/accounts/invitations/preview` and `POST /api/v1/accounts/invitations/accept`. The invitation link opens `/staff/join/`, with the token in the URL fragment.
- Who may sign in is the backend's admission and role model (`guide/11-FULL-PRODUCT.md`, six roles). The frontend never decides it.
