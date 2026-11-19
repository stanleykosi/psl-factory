# Batch implementation and acceptance

Use the [screen inventory](screen-state-inventory.csv) as the design checklist and the [acceptance ledger](screen-state-acceptance.md) for evidence. A state can be a variant of a shared workflow. Record an assignment or missing feature against the workflow that owns it, then list the affected states. Measure the remaining work by missing behavior and evidence, with both tracked separately.

| Build group | Connect and verify together |
| --- | --- |
| Commercial | Bid outcomes, costing, client-requested revisions, renewed approvals, controlled document delivery and the Finance handoff |
| Project delivery | Standard changes, emergencies, escalations, release, go-live, hypercare, archive and closure, including stopped and uncertain work |
| Finance and reporting | Invoice recovery, human payment exceptions, leadership reporting, accounting close, assets, schedules, forecasts and payroll corrections |
| Shared experience | Role, stale decision, delegation, onboarding, queue, agent progress and recovery variants across the business workflows |

1. Inspect the unclosed design states for a group against the current app. Fix shared causes once and preserve each source-backed exception. Treat missing owner choices as typed configuration and keep the rest of the flow usable.
2. Develop related changes in one candidate. Run a quick focused check for any broken contract, then use the composed PostgreSQL suite to exercise the handoffs and existing behavior together. Keep the test database separate from browser fixtures.
3. Deploy a passing candidate to the test web and worker services once for the entire group. Prepare additive sample cases together using the existing application services with real receipts. Use controlled fixture boundaries for failed or uncertain effects. Document any fixture-simulated steps.
4. In the Codex browser, follow the full journey and cover every distinct decision, recovery, permission and layout variant. Use the resulting visible outcome as evidence. One journey can exercise several states. Record evidence for each applicable state, then repeat failed checks against the corrected candidate.

The runner `python scripts/design_acceptance_batch.py --audit` verifies that the inventory, boards, acceptance ledger and backlog agree. Its output lists open and unseen states. `--list` shows the PostgreSQL test modules. Run all four groups together with `python scripts/design_acceptance_batch.py --settings config.acceptance_settings` in the configured Railway checks container. Add `--suite` to select groups for focused development. The composed run continues through test failures and returns the Django test process result.

The Railway runner can also use `--parallel-groups 2` in place of `--settings`. Each group gets a separate retained test database and a separate exit result. The larger project and Finance groups start first. Finance uses the exact `test_psl` database required by the invoice crash fixture. Subprocess workers connect only to their parent's already prepared PostgreSQL test database and retain their own scope checks. The original retained test database and the preview database stay separate from the group databases.

For the current candidate, `python scripts/design_acceptance_batch.py --candidate-gate` runs the reported failure cases and the new workflow and browser-fixture checks first. Use `--candidate-gate --list` to see the exact selection. After it and the read-only probes pass, the matching source can be deployed to the synthetic preview while the broader regression continues. Keep the gate and full-suite results separate.

After the grouped PostgreSQL result and deployment of the same application source, prepare the synthetic starting records in the Railway design acceptance project and environment:

```sh
PSL_COMPOSED_WALKTHROUGH=1 PSL_COMMERCIAL_CLIENT_FIXTURE=1 python manage.py shell --settings=config.acceptance_settings -c 'from tests.railway_batch_walkthrough_seed import run; run()'
```

Keep its `PSL_BATCH_FIXTURE` results as the sample map. Replay retains existing work. A failing fixture remains open and the other sample results stay available.

Separate a passed test from a passed browser journey in the ledger. Provider activity, owner approvals and release claims require their own evidence.
