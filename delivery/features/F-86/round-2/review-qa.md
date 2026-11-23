VERDICT: PASS
COMMIT: 1407fbe72551058290b2303a86580eef05b945c2
REVIEWER: qa
AUTHORITY: integrated QA

## Summary
- QA-1-1 is fixed live. As qa-seed through the real form on Next 4982 and Django 8021 (database 55433), a start for the week 9 to 15 Nov 2026 sent `start_at 2026-11-09T00:00:00+01:00`, `end_at 2026-11-16T00:00:00+01:00` and got 200 `{"work_id": 4, "state": "ready", "revision": 1, "background": "queued"}`. The page landed on `/work/4`.
- The live work item page read it (1440 and 390): "Reviewed weekly client report", READY TO CONTINUE, "Report template needed", next step "Choose a client report template before Tola can prepare the report.". Work id 4, project `4a228bcb-f762-4bc6-858e-74e9ab11ebd3` ("Project delivery", sample, case_revision 12), reference "QA r2 week 46". The 390 read was seen as "Loading..." at 4 s on a cold dev compile and not re-captured.
- Live refusals show as the form's callout with every value kept: a week ending today (18 to 24 Nov) gave 422 "Selected reporting period must have ended; future progress is unknown"; a 10-day week (1 to 10 Nov) gave 422 "Select a positive weekly reporting window of at most eight days; this is not a configured publication cadence". Neither was recorded as a work item and the drawer stayed open with the Reference value intact.
- Mock at 1440 and 390: chooser, picker, missing fields, valid start, 409, 422 mapping, 503 Check again, 404 and 403 all pass. Remaining FAILs in my script were test-script artifacts (straight against curly apostrophe, a short wait at 390, one load timeout) and passed on targeted re-runs.
- Unproved: uploads and file storage, a second user or tenant, live 409 and live uncertain start, `/work/4/history` content, the fidelity tool, and PSL's chosen timezone for a week (the form uses the browser's offset, which the builder flagged as an engineering reading).

## Findings
None.

## Verified
- QA-1-1 | verified | live real form start, week 9 to 15 Nov 2026: POST /api/v1/work answered 200 work_id 4 with offset datetimes (`+01:00` local midnights), page landed on /work/4 and read it. The old failure (date-only value, 422 "Period start requires an explicit timezone offset") no longer occurs; live refusals for a week ending today and a ten-day week return the server's own 422 messages in the callout with values kept.

## Notes
- QA-1-2 (note): earlier the server reused existing work 1 and ignored the new reference; this round a new item (work 4) was created, so reuse depends on state. Backend question for A-24 stands.
- QA-1-3 (note): `/my-work` crashed live at `src/features/my-work/WorkRows.tsx:11` in round 1. Not re-checked this round; not F-86 code.
- Test data created in the local test database: work 4 (this round, through the real form). Items 1 to 3 were made earlier by other runs. Nothing seeded or migrated.
- Processes started (Django, Next with mock, Next against the mock) were stopped by PID; ports 4982, 4983 and 8021 are free. The saved browser session file was deleted.
