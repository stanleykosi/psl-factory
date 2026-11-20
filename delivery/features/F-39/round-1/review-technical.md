VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 356656654596e6bc7295f4cdca4f80a88d4ce2e5
AUTHORITY: delivery technical review

## Summary
- Escalate decision reuses F-33 InlineDecide/useDecision unchanged. Controls come only from you_can_act and required_role (no useMe). The claim goes first, then the decide. Success shows only after the re-read. W-3607 `effect_uncertain` reads "result not confirmed", never drafted or escalated.
- Nothing reaches the client. No `sends` in any W-36xx fixture or sidecar (grep empty). "Send for review" only posts the W-3604 step inside the app.
- `drawsAgentCard` keeps the old behaviour for income (working only) and adds escalation (working or done). Other lines are unchanged. WorkItemOverview keeps its screen-reader copy in the same cases. The "← Project" bar adds only the escalation line to the existing issue_followup/planning rule.
- InlineDecide `asked` is drawn only in the cannot-act branch and only when non-empty. It is already in the generated schema (`schema.d.ts:1421`). Absent means the same render as before; F-33 income tests pass.
- The two widened allow-lists admit only W-36xx (links, verdict overlay). The F-39 specs and F-33 income single-file runs pass (78 tests). The coordinator's four decisions are accepted.

## Findings
None.
