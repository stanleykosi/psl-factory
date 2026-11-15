VERDICT: CHANGES
COMMIT: 798c17f8b0b30f6aabf94dc0ff621a901b6df7e4
REVIEWER: reviewer-ux
AUTHORITY: delegated UX review

## Verified
- UX-1-1 | not verified | The mechanism is right (untouched cites are not sent, a test pins it) but the new hint is not honest. It says "Records you cited in the saved draft stay on it until you choose new ones." Nobody has confirmed that the server keeps omitted cites, and the builder says Send on a saved draft without re-picking still gets the 422 "cite at least one record". So on the Send path the hint says the opposite of what happens, and the PM is told a thing is safe that the page itself then rejects. Also the pickers still open empty, so the PM cannot see what is kept. See UX-2-1 for the wording I would accept.
- UX-1-2 | verified | Still open as agreed: labels come from the frame for `required: false`; owner is the frame or design engineer. Stays non-blocking. Impact: no change in this diff.
- UX-1-3 | verified | Still open, shared design-system button, not touched by this diff. Stays non-blocking.
- UX-1-4 | verified | Read from the diff and the component, not walked in a browser. `data-form-open` is set on the Decide panel only while a `ws:` step form is open, and the CSS hides it inside the phone media block only. The step forms are rendered after the panel, outside it (`workspaceSteps.map(form)`), so hiding the panel does not hide the form, and the form's own Send is the single action. Desktop is unaffected. Small note: the opener button is hidden while the form is open, so focus return on Escape depends on the panel being shown again in the same render; the existing Escape e2e tests passed per build.md.
- UX-1-5 | verified | Shared F-09/F-17 reconcile layout, not touched by this diff. Stays a note for the frame owner.
- UX-1-6 | verified | Approved exceptions (D-71 Conflict 5), unchanged.

## Findings
- UX-2-1 | blocking | high | builder | The cite hint promises server behaviour that is unconfirmed, and contradicts the Send 422. Decision: it is not honest as worded, and the empty pickers beside it leave the PM unable to tell what is saved. I would accept a hint that promises nothing about the server and tells the PM what to do on this page, on all eight cite fields (W-2201 has two sets): "Saved records are not shown here. Choose at least one record for this part before you send." Also acceptable: drop the hint and keep the existing "Your update" section above, which already lists the saved cites, plus a single line under the form heading with the same sentence. Do not say "stay on it" or "kept" until the backend confirms that omitted cites are kept on Save draft and counted on Send; if the backend confirms both, the original sentence is then fine and Send on a saved draft no longer 422s. Update the hint test to assert the new sentence. Also record the list-valued `records` `value` contract question for the coordinator as the real fix (prefill), so the hint can be removed later.
