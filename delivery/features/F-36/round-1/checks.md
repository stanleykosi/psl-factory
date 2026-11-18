GATE: FAIL
COMMIT: 023ad69ede328ce092a5c2d2cd91ec3b462ac6bd
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit 023ad69ede32, round 1, attempt 1

## checks.sh (last 80 lines of checks.log)

```
                [36m>[39m
                  [0mChoose a file[0m
                [36m</button>[39m
              [36m</div>[39m
            [36m</div>[39m
            [36m<div[39m
              [33mclass[39m=[32m"psl-field"[39m
            [36m>[39m
              [36m<label[39m
                [33mclass[39m=[32m"psl-label"[39m
                [33mfor[39m=[32m"assign-note"[39m
                [33mid[39m=[32m"assign-note-label"[39m
              [36m>[39m
                [0mNote[0m
                [0m [0m
                [36m<span[39m
                  [33mclass[39m=[32m"psl-opt"[39m
                [36m>[39m
                  [0m(optional)[0m
                [36m</span>[39m
              [36m</label>[39m
              [36m<textarea[39m
                [33maria-describedby[39m=[32m"assign-note-count"[39m
                [33mclass[39m=[32m"psl-input psl-input--area"[39m
                [33mid[39m=[32m"assign-note"[39m
                [33mstyle[39m=[32m"height: auto;"[39m
              [36m/>[39m
              [36m<span[39m
                [33mclass[39m=[32m"psl-count"[39m
                [33mid[39m=[32m"assign-note-count"[39m
              [36m>[39m
                [0m0[0m
                [0m / [0m
                [0m2000[0m
              [36m</span>[39m
            [36m</div>[39m
            [36m<p[39m
              [33mclass[39m=[32m"rfp-assign__next"[39m
            [36m>[39m
              [36m<strong>[39m
                [0mWhat happens next:[0m
              [36m</strong>[39m
              [0m [0m
              [0mThe PM you choose is alerted by WhatsApp and email and sees it in Needs me. They start the RFP response. Tola starts reading the RFP once the PM opens it.[0m
            [36m</p>[39m
          [36m</form>[39m
        [36m</div>[39m
      [36m</div>[39m
      [36m<div[39m
        [33mclass[39m=[32m"psl-drawer__foot"[39m
      [36m>[39m
        [36m<button[39m
          [33mclass[39m=[32m"psl-btn psl-btn--secondary"[39m
          [33mtype[39m=[32m"button"[39m
        [36m>[39m
          [0mCancel[0m
        [36m</button>[39m
        [36m<button[39m
          [33mclass[39m=[32m"psl-btn psl-btn--start"[39m
          [33mform[39m=[32m"assign-pm-form"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mAssign PM[0m
        [36m</button>[39m
      [36m</div>[39m
    [36m</aside>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ Object.getElementError node_modules/@testing-library/dom/dist/config.js:37:19
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:76:38
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:109:15
 ❯ tests/rfp-assign.test.tsx:121:19
    119|     const dialog = await open('W-3302');
    120|     expect(within(dialog).getByText('Tamarind Loans · TL-RFP-2026-014'…
    121|     expect(screen.getAllByText(/loan origination RFP/).length).toBeGre…
       |                   ^
    122|     expect(screen.getByRole('tab', { name: /Unassigned/ })).toBeTruthy…
    123|     // opening the panel changes the URL only: the list was read once

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
