VERDICT: CHANGES
COMMIT: 48221d25fe73354c183109e18cfaaa5c621ae4d1
REVIEWER: qa
AUTHORITY: integrated QA (incomplete: handover)

## Summary
- Incomplete: handover. The session ended before every item was closed, so the verdict is CHANGES until the items under Findings are done. No product defect was found.
- Mock journeys passed at 1440 and 390 (mock 4993, `next dev` 4992). Scripts were my own Playwright (playwright-core) scripts, not the repo e2e suite. They covered:
  - empty form and checklist strip, with no "draft" text;
  - first save with one POST and the toast "Saved HH:MM WAT, version 1." only after the re-read;
  - follow-up action on case 2002 (one `actions/create`, `meeting_id` 301, `due_at` null, "No owner / No deadline set", no link call, duplicate reference 422 under Reference);
  - unplaced 422 ("Pick people who are on the project.", no generic text, Save re-enabled, message above the bar at 390: bottom 689 against bar top 762);
  - field 422 on a duplicate reference;
  - 409 stale (typed values kept, next press succeeds);
  - 503 on case 2005 ("We couldn't confirm it saved.", one POST, then "It was not saved. Press Save again.");
  - double click sends one POST;
  - injected 403, 404 and 429 on save, and `csrf_failed` giving "Press Save again";
  - 403 and 404 and 503 on action create (503 shows "We couldn't confirm it was created.");
  - 401 sign-in link with `next=`;
  - unknown project and not-yours project show "This record is unavailable.";
  - case 2003 (cannot record) is read-only with no alert;
  - case 2004 (no proofs) explains why Save is off;
  - old version read-only with the "newer version" line;
  - checklist 503 (dossier 5009) hides only the strip;
  - "More" paging (case 2006).
- AC 24 at 390: my own Tab walk, started at scroll 0 with Save enabled, ended above the bar every time.
  - Empty form: 7 stops to Save, with at least an 8px gap above the bar.
  - Case 2002 new version with a carried decision: 10 stops to Save, with at least a 16px gap.
  - Every stop was the element at its own centre point.
  - Negative case: a textarea forced under the bar had its bottom below the bar top and `elementFromPoint` returned another element, so the check does fail.
- Live (Django 8031 on the 55433 database, qa-seed, project `4a228bcb`, no seed command run):
  - Sign-in through the Next proxy worked.
  - Meetings, options, first save (201), new version (201 with a read-only reference) and signed-out 401 behaved as specified at both widths.
  - The 404 for an unknown case and the phone page without horizontal scroll were also confirmed.
  - The save leaves local synthetic data behind: one retrospective on that project, with version 1 at 1440 and further versions at both widths.
- Not proved: the live checklist strip, because no dossier exists (dossier ids 1 to 3 return 404; the page showed "The closure checklist is unavailable."). That means AC 6, AC 18 and AC 21's "checklist references the saved version" have no live evidence. Live 409, 422 and 503 were not reproduced; they are mock-only.

## Findings
- QA-2-1 | blocking | medium | integration | incomplete: handover. Remaining: (a) live checklist strip and its reference to the saved version (AC 21), which needs a delivery dossier and so a seed command that was not run; (b) I did not open the saved screenshots (`shots/*.png` in the scratchpad) for visual review; the check was by DOM and bounding box. Close or waive in the next pass.
- QA-2-2 | non-blocking | low | frontend | A 403 on the follow-up action create shows "You can't record a retrospective on this project." The spec says "errors as Save", so this is arguably right, but the wording does not name the action. Expected: confirm with the UX lens.
- QA-2-3 | non-blocking | low | integration | On the first 390 run, a check of "Save disabled while unconfirmed" read false. I read it after the re-read had already finished, so it is a timing effect in my script. At 1440 it read true, and the repo e2e covers it.
- Script mistakes of mine, not product defects: I assumed Save was enabled on an empty form, the action button showed on every project, and 2001 and 2004 still had empty forms after a save. I corrected these in the second script.

## Verified
- TECH-1-1 | verified | My own full Tab walk at 390 on two forms, plus the negative case, as above.
- TECH-1-2 | verified | The walk showed no stray scroll. The unmount cancel was not separately exercised (code and unit evidence only).
- TECH-1-3 | verified | The negative check detects a control under the bar. The builder's red run at 53c24b19 was not re-run by me.

Processes: started PIDs 6524 (mock), 6526 (next dev, mock-backed), 11289 (Django 8031) and 11983 (next dev, Django-backed). All were stopped by PID and ports 4992, 4993 and 8031 are free. No Railway tools were called. Neither `demo-login.txt` nor `demo-access.txt` was read. The qa-seed login was read by the scripts only and never copied or printed.
