# D05 role eligibility

The source-backed D05 requirement is to configure named role assignments, delegation/absence and dual-role eligibility without adding approval gates or replacing the known role matrix. Exact role bundles and explicit time windows below are the implemented engineering interface, not an owner decision about who qualifies.

The existing `D05.role_principal_assignments` component supports immutable references with two schemas:

- `schema:psl/role-assignment/v1`: exact `role` and `user_id` nomination. An operational person assigned multiple distinct roles remains held until explicit eligibility is configured. Single-role nominations and existing synthetic fixtures retain their behavior.
- `schema:psl/role-assignment/v2`: the same nomination plus `eligibility`, containing the exact `roles` bundle and timezone-aware `valid_from` / `valid_until`. Every assignment for that person must declare the same bundle and window. The window includes its start and excludes its end.

Use the policy workbench's role-assignment form to save a draft with actual owner-decision evidence and a configuration effective time. Invalid or incomplete declarations remain drafts. Review/validate/activate through the existing component lifecycle. Saving a draft, registering a reference, agent investigation or scope adoption does not activate authority or create action grants.

The runtime checks the exact requested role, fresh active principal, current component/origin and the person's eligibility window. Other single-role nominees remain usable when a different person's eligibility is absent or expired. Native services still enforce record/action grants, source versions and their independent human controls. Existing decisions pin D05; a successor or expired eligibility requires current decisions before dependent actions.

The local adapter and A04 investigation return nomination/eligibility metadata only. They reauthorize stored scoped origins even when policy resolution is unavailable. Organization/project/contract/service application reuses existing reviewed scope adoption and local evidence; it does not install grants for nominated users.

Emergency GLPI schema v1 retains its existing Engineering Lead same-capacity behavior. Explicit v2 includes `role_eligibility: current_D05_bundle`. A shared Security/Engineering actor requires a current explicit D05 bundle and fresh decisions. It adds no approval roles and grants no deployment dispatch, payment exception or financial release authority. Source-verified GLPI receipts are separate from internal human decision authority.

Fixtures and operationally flagged test people are synthetic. No actual nominees, qualification windows or owner policy values are installed by this increment. Actual test/checkpoint status is in BUILD-TESTS.md and BUILD-STATE.md.
