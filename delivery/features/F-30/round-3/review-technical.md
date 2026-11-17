VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 3a2884d4707522db814305db68b78dc6e4fc682a

Scope: diff 48ba8f7a..3a2884d4.

- StepForm focus change: controlOf now picks the first input/textarea/button/select inside the field wrapper. It no longer targets aria-invalid, which fixes the invalid choice-field wrapper case. The summary is opt-in (`summary` prop, passed only when issueLine(workspace)), so other lines draw nothing new. Control ids are assigned only when missing.
- Targeted vitest passed: issue-detail, minutes, weekly, weekly-returned-received, workspace-step and workspace. No regression in the weekly or minutes step forms.
- AssignForm: duplicate kind/role hint is suppressed. Small and safe.
- No blocking findings.
