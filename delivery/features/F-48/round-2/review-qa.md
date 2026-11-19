VERDICT: PASS
REVIEWER: qa
COMMIT: ee9dc46dca9ff40d39148cc4ba1f76572bb35aa7
AUTHORITY: delivery integrated QA

## Summary
Live demo (app 4925, mock 4924), Playwright at 1440 and 390, persona cookie pm. Contract mock only; no real agent or access request exists. Not run: unit suite, speech.
- CV-2404 at 1440: pose zainab-cant.png, sentence "can't do that with your access", agent answer and cannot_reason (separate lines) shown.
- CV-2404 at 390: inline pose card (alt "Zainab, can't do this"), answer and reason shown.
- Whole-page scan, html and text, both widths, before and after reload: the restricted label "ACCESS · payroll (restricted)" is absent.
- The word "payroll" remains only in the person's own context: step "Checked your access to payroll records", project "October payroll", access "PMO · no payroll access". None is a restricted record name or label.
- CV-2401 (normal): done pose, no cant text, no payroll; unchanged. Reload behaves identically.
- finance_lead on CV-2404: API 404, page "could not find that conversation", no refusal or payroll text. Unknown id CV-9999: API 404, page not-found at both widths.

## Findings
- QA-2-1 | non-blocking | low | The literal word "payroll" is on the page in the unrestricted step, title and access lines above. Intended by the fixture; the review brief's "no payroll" check applies to the restricted label only.

## Verified
- TECH-1-1 | verified | Restricted label gone from the step on live CV-2404 at 1440 and 390, and after reload.
- TECH-1-2 | verified | Wrong user and unknown id refused (API and UI).
- UI-1 | verified | Phone pose card shows with the cant image.
