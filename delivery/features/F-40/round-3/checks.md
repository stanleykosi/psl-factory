GATE: FAIL
COMMIT: 1457df1c1d4ad44327640da4efcce7d5d85dc9cd
ATTEMPT: 2

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit 1457df1c1d4a, round 3, attempt 2

## checks.sh (last 80 lines of checks.log)

```
                [36m/>[39m
              [36m</svg>[39m
              [36m<input[39m
                [33maria-label[39m=[32m"Search"[39m
                [33mclass[39m=[32m"psl-input cmp-search"[39m
                [33mplaceholder[39m=[32m"Search work, client or reference"[39m
                [33mtype[39m=[32m"search"[39m
                [33mvalue[39m=[32m""[39m
              [36m/>[39m
            [36m</div>[39m
            [36m<span[39m
              [33mclass[39m=[32m"cmp-anchor cmp-anchor--inline"[39m
            [36m>[39m
              [36m<button[39m
                [33maria-expanded[39m=[32m"false"[39m
                [33mclass[39m=[32m"psl-btn psl-btn--secondary"[39m
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
                    [33md[39m=[32m"M2 3h14l-5.5 6.5V15l-3 1.5V9.5z"[39m
                    [33mstroke-linejoin[39m=[32m"round"[39m
                  [36m/>[39m
                [36m</svg>[39m
                [0mFilter[0m
              [36m</button>[39m
            [36m</span>[39m
            [36m<span[39m
              [33maria-live[39m=[32m"polite"[39m
              [33mclass[39m=[32m"psl-resultcount"[39m
            [36m>[39m
              [0m6 ITEMS[0m
            [36m</span>[39m
          [36m</div>[39m
        [36m</div>[39m
      [36m</form>[39m
      [36m<div[39m
        [33maria-label[39m=[32m"Unassigned"[39m
        [33mclass[39m=[32m"my-work__panel"[39m
        [33mid[39m=[32m"my-work-panel"[39m
        [33mrole[39m=[32m"tabpanel"[39m
      [36m>[39m
        [36m<div[39m
          [33mclass[39m=[32m"my-work__tablewrap"[39m
        [36m>[39m
          [36m<div[39m
            [33maria-label[39m=[32m"Your work"[39m
            [33mclass[39m=[32m"psl-tablewrap"[39m
            [33mrole[39m=[32m"region"[39m
            [33mtabindex[39m=[32m"0"[39m
       ...

- Expected
+ Received

- assign-pm-proof

 ❯ tests/rfp-assign.test.tsx:371:60
    369|     expect(within(dialog).getByText('1 thing to fix')).toBeTruthy();
    370|     expect(within(dialog).getByRole('link', { name: message }).getAttr…
    371|     await waitFor(() => expect(document.activeElement?.id).toBe(focusI…
       |                                                            ^
    372|     expect(dialog.textContent).not.toMatch(/Check these fields|acting_…
    373|     expect((within(dialog).getByRole('textbox', { name: /Note/ }) as H…
 ❯ runWithExpensiveErrorDiagnosticsDisabled node_modules/@testing-library/dom/dist/config.js:47:12
 ❯ checkCallback node_modules/@testing-library/dom/dist/wait-for.js:124:77
 ❯ Timeout.checkRealTimersCallback node_modules/@testing-library/dom/dist/wait-for.js:118:16

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
