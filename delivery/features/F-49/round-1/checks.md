GATE: FAIL
COMMIT: 3bedb8756740b91d1771dbe8f62f63dd0a3e69d4
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit 3bedb8756740, round 1, attempt 1

## checks.sh (last 80 lines of checks.log)

```
                  [33mtype[39m=[32m"button"[39m
                [36m>[39m
                  [36m<svg[39m
                    [33maria-hidden[39m=[32m"true"[39m
                    [33mclass[39m=[32m"psl-icon"[39m
                    [33mfill[39m=[32m"none"[39m
                    [33mfocusable[39m=[32m"false"[39m
                    [33mheight[39m=[32m"18"[39m
                    [33mstroke[39m=[32m"currentColor"[39m
                    [33mstroke-linecap[39m=[32m"square"[39m
                    [33mstroke-width[39m=[32m"2"[39m
                    [33mviewBox[39m=[32m"0 0 18 18"[39m
                    [33mwidth[39m=[32m"18"[39m
                  [36m>[39m
                    [36m<path[39m
                      [33md[39m=[32m"M9 2v14M2 9h14"[39m
                    [36m/>[39m
                  [36m</svg>[39m
                  [36m<span>[39m
                    [0mStart [0m
                    [36m<span[39m
                      [33mclass[39m=[32m"sw-word"[39m
                    [36m>[39m
                      [0mwork[0m
                    [36m</span>[39m
                  [36m</span>[39m
                [36m</button>[39m
                [36m<button[39m
                  [33maria-expanded[39m=[32m"false"[39m
                  [33maria-haspopup[39m=[32m"dialog"[39m
                  [33maria-label[39m=[32m"More ways to start"[39m
                  [33mclass[39m=[32m"psl-btn psl-btn--start psl-btn--sm psl-split__more"[39m
                  [33mtype[39m=[32m"button"[39m
                [36m>[39m
                  [36m<svg[39m
                    [33maria-hidden[39m=[32m"true"[39m
                    [33mclass[39m=[32m"psl-icon"[39m
                    [33mfill[39m=[32m"none"[39m
                    [33mfocusable[39m=[32m"false"[39m
                    [33mheight[39m=[32m"18"[39m
                    [33mstroke[39m=[32m"currentColor"[39m
                    [33mstroke-linecap[39m=[32m"square"[39m
                    [33mstroke-width[39m=[32m"2"[39m
                    [33mviewBox[39m=[32m"0 0 18 18"[39m
                    [33mwidth[39m=[32m"18"[39m
                  [36m>[39m
                    [36m<path[39m
                      [33md[39m=[32m"M3.5 6.5L9 12l5.5-5.5"[39m
                    [36m/>[39m
                  [36m</svg>[39m
                [36m</button>[39m
              [36m</span>[39m
            [36m</span>[39m
          [36m</div>[39m
        [36m</nav>[39m
      [36m</div>[39m
      [36m<div[39m
        [33mclass[39m=[32m"shell-phone"[39m
      [36m>[39m
        [36m<header[39m
          ...

- Expected
+ Received

- 1
+ 0

 ❯ tests/ledger-source.test.tsx:336:49
    334|     await upload();
    335|     await submit();
    336|     await waitFor(() => expect(posts('/steps')).toHaveLength(1));
       |                                                 ^
    337|     expect(posts('/steps')[0].body!.inputs).toEqual({ found: 'more_tha…
    338|     await waitFor(() => expect(reads('W-4208')).toBeGreaterThan(1));
 ❯ runWithExpensiveErrorDiagnosticsDisabled node_modules/@testing-library/dom/dist/config.js:47:12
 ❯ checkCallback node_modules/@testing-library/dom/dist/wait-for.js:124:77
 ❯ Timeout.checkRealTimersCallback node_modules/@testing-library/dom/dist/wait-for.js:118:16

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
