Verified bounded checkpoint28 October2026. See BUILD-TESTS.md for actual RUN312 failure and final RUN313 success; operational owners remain unconfigured.

# Human duplicate and alias findings

This is the P03 human identity investigation path. It does not merge cases or transfer access, invoices, debt, PM assignments or other business records. A Case UUID and each source identifier remain stable history. Use a human finding when duplicate candidates or conflicting references need an explanation.

Capture both engagements before resolution. The source case's engagement workbench links to `/cases/<case-uuid>/identity-resolution/`. Select a second currently visible project case in the same tenant/classification, then supply both cases' public source evidence, a relation (unresolved, distinct or directional alias), current PMO source role, rationale and idempotency key. No additional registration approval is created.

Both cases need independently active D11.engagement_identity_resolution criteria, current D05 source-role authority and explicit engagement.resolve_identity grants for the human recording the finding. The UI supports criteria drafts; the normal policy workbench validates/activates/supersedes/revokes them. Missing criteria hold only the identity finding. Case creation, initial engagement capture and other configured paths remain available. Actual PMO role/principal values and graph bounds are operational inputs; the fixture is synthetic.

Tenant advisory locking precedes ordered case/principal/grant locks. Two simultaneous opposite aliases cannot create a cycle. Alias graph inspection is bounded by the smaller configured budget of the two scopes. Conflicting targets require an explicit successor finding retiring the prior alias. An inspection-budget hold affects alias recording; distinct/unresolved findings do not require traversing the graph. No background effect or financial worker is dispatched.

Findings append immutable history with source/target capture, policy and role bindings. Current acceptance re-evaluates original human authority and source lineage. A policy, grant, role or capture successor can make acceptance stale while preserving the historical finding. Readers require current access to both cases before seeing target references. If target access is revoked, the source history shows only an access-held marker for that decision. Alias status never grants visibility to the target.

The engagement A01/A04 investigation includes these findings as bounded evidence. It cannot merge records, copy grants, select owners or execute financial work. Source identifier uniqueness and the ordinary domain controls remain enforced. Native source identity mapping contracts and operational owner confirmation are separate evidence inputs.

Actual retained tests and failures are in BUILD-TESTS.md. RUN312's UI error came from a missing status key used by a template fallback; it did not pass the increment. Subsequent tests must prove the corrected UI alongside actual PostgreSQL cycle/concurrency/scope/source/policy/revocation/SQL history behavior before completion is recorded.
