VERDICT: PASS
COMMIT: 35189b4503a76ae516ba153f77434a9a562bdc0d
REVIEWER: design engineer (hunchoweb), accepted in batch, delegated under D-184
AUTHORITY: D-182 (batch 1 answers), D-184 (batch-approved board changes count as product acceptance)

## Basis
F-85's only product decisions are board changes the design engineer accepted in question batch 1 (`delivery/connect/questions-batch.md`, "Answers, batch 1"; `delivery/OVERNIGHT-DECISIONS.md` D-182):
- LC-Q1 (station track, six facts strip and agent steps): the design engineer answered "Hide until backend". The page shows the state, next step, blocker, current activity and output link.
- LC-Q4, LC-Q5, LC-Q6 (history counts and paging, write controls not drawn here, reference/started-by/amount dropped): "Hide, accept all recs", the recommended option of every question.

Recorded by the lane C coordinator under D-184 ("accepted in batch, delegated under D-184"). This is not a fresh review of the running screen by the design engineer; D-184 says they check merged screens on port 3000 afterwards, and anything they dislike becomes a fix.

## Not covered
- The merge: F-85 has a security surface (case file upload), so under D-184 its merge goes to `delivery/connect/merge-batch.md` for the design engineer.
- Live proof: criteria 2, 19 and the live half of 22 are mock-proved, live pending (PMO-1-1).

## Findings
