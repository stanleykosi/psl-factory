VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 264b349260dbbd734eaadcb5228781f83cccccb0
AUTHORITY: delivery UX review

## Summary
- Walked W-3301 to W-3306 as `pmo_lead` at 1440 and 390 in a real browser against the running build (app 4965, mock 4964); reads first, then writes; mock reset afterwards.
- Panel opens over the Unassigned list at `?queue=unassigned&assign=<id>`, Escape closes it back to the list with focus on the row link; no sideways scroll at 390; "Assign PM" pinned at the bottom on the phone, no Cancel there (spec conflict 7).
- PM choice lists exactly the three returned candidates (hint omitted for Ife Okoro, not "0"), nobody pre-chosen; W-3302 shows a role Select (PMO Lead default) and Proof; W-3301 shows the role as text; "What happens next" is the returned text on W-3302 and the fixed, channel-free sentence on W-3301.
- Writes: bodies match the spec (typed only on W-3301; `acting_role`, `evidence_id`, `case_revision: 2` on W-3302 after upload). Success notice "TL-RFP-2026-014 is now with Tunde Bello." appears only after the Drawer closed on a re-read, with the Unassigned count 6 to 5. W-3306 (500, written) shows "Assigned to Tunde Bello" after the re-read, one POST. The 422 keeps the PM and note and shows the message under the field and in the summary.
- W-3304 shows "No one can prepare RFPs here yet." with no control; W-3305 goes to `/work/W-3305` with no assign control. Uploaded-chip remove is 48px on both widths.

## Findings
- UX-1-1 | non-blocking | low | backend | The 422 message reads "Check person_id." (raw field name, in the summary and under the field). It comes from the mock's invalid scenario, not page copy; the real backend should send plain wording, or the page should map known fields to labels such as "Accountable PM".
- UX-1-2 | non-blocking | low | frontend | The assign form carries `aria-label="Assign accountable PM"`, the same name as the dialog, so `getByLabel` and screen readers find the same name three times. Prefer a different or no form label.
- UX-1-3 | non-blocking | low | frontend | On W-3306 the "Not confirmed" sentence is no longer visible once the re-read shows "Assigned to Tunde Bello" (as the spec describes). The person sees no mention that the write was uncertain; consider a one-line "Confirmed after a re-read" note. Taste only. The mock's PM name also differs from the one chosen (Sola), a fixture artefact.
