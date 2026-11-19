VERDICT: CHANGES
REVIEWER: reviewer-ux
COMMIT: b051cfa790dc4984060e6e236649aefb5c83e764
AUTHORITY: delivery UX review

## Summary
- Four states, hold, publish-then-record, Delivery tab link and no-access paths work at 1440 and 390 with no sideways scroll.
- One blocking item: on the phone, Back from a handover opened from the Delivery tab goes to the Queue, not Delivery.
- Walked as the PM, a persona with no sections (none) and ceo. Mock only; nothing sent.

## Findings
- UX-1-1 | blocking | medium | builder | At 390, opening HND-0048 from /projects/P-0101/delivery shows the bar "← Queue" (/my-work) with History. SCR-48-mobile boards draw "← Delivery". Spec Conflict 7 keeps the built bar, but it must still return the PM to where they came from, and it lands on the Queue (the desktop crumb Delivery is correct). Fix: make the phone Back go to the project's Delivery tab for this line, or record a spec-approved exception that Back means Queue.
- UX-1-2 | non-blocking | low | builder | At 390 on W-3703 the attestation label measures 37px high, the checkbox 20px and the History link 24px. Spec item 17 lists other targets but the attest row is a tap target too; raise to 44px.
- UX-1-3 | non-blocking | low | builder | A ceo cookie opens /work/W-3704 and shows the full handover, while the Delivery tab refuses ceo. The build notes say this is static-fixture behaviour. The backend must refuse the item itself. Recorded for the integration.

## Verified
- Handover row: both "Handover" sub-nav and row link go to /work/W-3704 at 1440; row link at 390 (sub-nav hidden on phone, per F-32).
- W-3701 ready to publish: Publish to Support (44px at 390) leads to the Record Support's reply panel after the re-read. No "sent" or "received" appears before it.
- W-3702 hold: "Review needed?" shows Unknown, no button anywhere in the workspace, at both widths.
- W-3704 gaps and W-3705 acknowledged show their labels, tones and Next text from data; the 1440 gaps page matches the board layout (banner, GAPS panel, Next with Ask Tola to draft v2).
- Refused paths: ceo on the Delivery tab gets a no-access page with no project name at both widths; a persona with no roles gets "No sections are open to your role yet. Ask a Lead or Admin to check your roles."
- Desktop Back is the Delivery crumb link; no horizontal scroll on any page.
- Not walked: record-form submit failures (422/409/uncertain) and keyboard focus order; relied on the build's component tests.
