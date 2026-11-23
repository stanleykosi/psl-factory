DECISION: READY
RISK: high
SURFACES: ui, api, security, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Re-points the app frame (src/shell) and API client (src/api) at API 1.24.0 under D-185 and the backend answers A-1 to A-5, A-55 and A-56. It is FE-CONNECT-1 and one outcome: the frame stops using v7 workarounds.
- Dependencies F-56, F-57 and F-58 are DONE and merged. No client decision is open, because D-185 says the lanes follow the backend answers without new questions.
- Rated high because the CSRF retry sits in the shared write path. Every later feature's writes inherit it, including money and sign-in writes.
- Product acceptance is required. Visible wording changes: the "Your session was refreshed. Press the action again" line goes away, and a signed-out download shows the frame's signed-out state. Only presentation goes to the design engineer's batch, since D-185 settles the behaviour.
- The architecture and design approvals were not rechecked for this feature, because it adds no screen or board. F-67 draws no new board and reuses F-57 and F-58 components.

## Scope
Outcome: the frame and client use the 1.24.0 data and rules below. Task: FE-CONNECT-1. Only src/shell and src/api (lane A). No new endpoints are added. It consumes GET /me, GET /role-dashboard (optional), POST/GET /session and the six download routes.

In:
1. Role words (A-1). Read each position's name, mode and workspace from `/me` positions. There is no `roles[]`. Remove the F-57 fallback that D-172 recorded.
2. Menu (A-2, A-4). Build the five-link menu from `destinations[].key`, `url` and `available`: hide entries with `available: false`, link to `url`, and never read `django_url` or `work_desk_url`. This replaces the D-174 unfiltered menu, so Setup stops showing for everyone. Every destination `url` must be same-origin or a relative Next.js path, and the client must not follow an arbitrary absolute URL from the response.
3. CSRF retry (A-3). Replaces D-174's never-repeat rule. On a 403 whose code is exactly `csrf_failed`, call `GET /session` once, then repeat the same request with the same idempotency key, exactly once. Retry nothing else: not other 403s, not 401s and not 5xx. If the retry fails, surface its error. A second `csrf_failed` shows the existing "can't get ready" or error spot, with no loop. The retry must not rebuild the body or mint a new key. A write that has no idempotency key is not retried, and the spec must say how that is detected.
4. Limit errors (A-5). Show the JSON `code` and `message` for 429 `rate_limited` and 503 `read_limited`. Do not assume `Retry-After`; use it only if present.
5. Downloads (A-55). A JSON 401 from a download route shows the frame's own signed-out state ("You're signed out. Sign in"). The client no longer expects a 302.
6. A-56. The admin role loads without `invite_minutes`. Drop any workaround and keep the frame tolerant of the field being absent.

Out: any screen's own writes or copy, alerts, Setup screens, new boards, backend changes, and the types regeneration beyond what 1.24.0 already generates. Remove the F-57 csrf wording only where this feature replaces the behaviour.

The spec writer must list, for acceptance, the changed frame texts: the csrf line, the signed-out download state, and the menu now varying by account. The mock path (v7) keeps working unless the spec says otherwise.

Tests the spec must require: a retry-once test with the same key against the real client; a second csrf_failed with no third attempt; a non-csrf 403 with no retry; a duplicate-effect check that a retried write executes once; the menu hiding `available: false`; a 401 download.

## Risk
High, because the retry lives in src/api and applies to every write in the product, including sign-in (F-58) and the money and payment features coming in later waves. A retry that mints a new key, loops, or repeats a non-csrf failure could double-execute an effect that is hard to undo. Auth and security apply because the change touches session refresh, CSRF and the signed-out state. Contract-change applies because it moves the client from v7 to 1.24.0 fields. Merge goes through the security review and a technical reviewer on the high-risk route (Opus per D-123). Per D-184, sign-in and security surfaces still come to the design engineer.

## Questions
None.
