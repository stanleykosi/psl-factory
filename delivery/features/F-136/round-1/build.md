STATUS: READY
COMMIT: c4c6f27f86d1716f4c72432dc1fb12c24e2beb40
BUILDER: builder
LANE: full

## Summary
- The live work item's `commercial-response` panel (GET /projects/{case_id}/commercial-response, the panel key the live backend names on `commercial/v1` items) now draws where signing stands: what is to be signed, what the client was sent, the recorded response, proof files, signatures and signed baseline, and who may record.
- Three writes on POST /projects/{case_id}/commercial-response: `witness` (the client's response, incl. signed), `signatures` (SOW and PRD signatures), `adopt` (the signed baseline). Each uses the shared write lock, sends only from a press, is never retried, and is told "done" from the re-read.
- Proofs are chosen from the served lists (`owned_files`, `signature_proofs`, `requirements`); signers from `parties`; nothing is uploaded or invented.
- Registered with one import line in `workspace/lines/index.ts`; no shared API changed.

## Changes
- `frontend/src/features/response/commercialModel.ts`: sections and the three command descriptors (case_revision token only, as the endpoint takes no expected_revision), disabled reasons from the read.
- `frontend/src/features/response/commercialAdapter.ts`: the adapter (self-registers).
- `frontend/src/features/response/CommercialActions.tsx`: the three forms (Actions slot).
- `frontend/src/features/workspace/lines/index.ts`: one import line.
- `frontend/mock/commercial-live.mjs` and `mock/server.mjs`: live-shaped fixtures and routes, ids 4660 to 4666, matches the UUID and P-nnnn project path forms; `node --check` passes on both.
- `frontend/tests/commercial-response.test.tsx`, `tests/next-config.test.ts` (allow-list entry), `e2e/work-item-commercial-response.spec.ts`.

## Fixes
(round 1, none)

## Acceptance criteria
1. [x] Reads: SOW and version, proofs on file, signed or not, who may record, baseline state: tests "reads (SCR-16)" (6 cases) and the e2e read test; what the real demo database returns (Kora: a current version, no delivery, `can_record` true; Lagoon: signed response, packet, current adoption) is the shape the fixtures copy.
2. [x] Write the exact body with `case_revision` and key: bodies are validated against the contract's oneOf in tests; the mock refuses extra or missing keys and the old code paths a body with `expected_revision` would hit.
3. [x] Proof chosen from the served list, never uploaded: the response form lists `owned_files` as checkboxes; the signature proof is a select over `signature_proofs`.
4. [x] Re-read before saying done, shared locks: the toast and the "This item is now" line come from `useWorkCommand`'s re-read; test "a write whose answer is lost" shows a lost answer locks the button and posts once.
5. [x] Hold writes whose rule is unclear, with the reason: see Held.

## Held and why
- Uploading proof (`/commercial-response/files`): brief says choose from served lists.
- A "finding that holds it": the desk read carries none; the page's own blocker line is unchanged.
- "Who may sign": not served as a flag. Signing is drawn only when the server serves a signed response plus `requirements` and `signature_proofs` (it serves those only to people with baseline.sign); `parties` is the server's own signer list. The method words are free text (the signature contract's method list is not served), so the server decides on adoption.
- Asking the agent for revisions after "changes requested" (`review_changes`, `save_revision`, `prepare_revision`), `reaffirm`, `internal_exemption`, `signature_policy`: not part of recording a signature.
- Client testing sign-off and team inputs (other SCR-16 families): not this feature.
- A client response is recorded through the same `witness` action, so the response and SOW signature share this panel. `received_via` is sent (the contract has it) as an optional select.
- The old v7 screens `src/features/response/*` are unchanged and still serve the v7 mock.
- Real backend check (psl_demo5, GET only): Kemi gets 404 on all three commercial desks (not a visible project to her); Tunde (Kora, Lagoon) and Chinedu (Delta) get 200.

## Validation
- `tsc --noEmit`: clean. `eslint . --max-warnings 0`: clean.
- vitest: next-config, demo-mock, mock-contract, line-adapter, live-work-item, engagement-live, bid-submission and the new commercial-response: 8 files, 451 tests passed (16 new).
- Playwright on ports 4960/4961 (desktop 1440 and phone 390): 9 passed, 1 skipped (phone-only check on desktop). Servers stopped by playwright; ports free.
- `checks.sh` runs in CI mode (waits for GitHub on the pushed head); not run by me.
- Worktree clean, pushed.

## Shared code
None changed. Note for the coordinator: `useWorkCommand`'s uncertain-effect lock is keyed by the work item's revision, so it lifts as soon as a re-read shows a newer revision; correct for this line.
