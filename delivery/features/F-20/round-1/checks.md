GATE: FAIL
COMMIT: c218bf2480b82e3753e88943e25b497f2e959e80
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit c218bf2480b8, round 1, attempt 1

## checks.sh (last 80 lines of checks.log)

```
            [0mStart[0m
          [36m</button>[39m
        [36m</span>[39m
      [36m</div>[39m
      [36m<main[39m
        [33mclass[39m=[32m"shell-main"[39m
        [33mid[39m=[32m"main"[39m
        [33mtabindex[39m=[32m"-1"[39m
      [36m>[39m
        [36m<div[39m
          [33mclass[39m=[32m"psl-panel shell-loading"[39m
        [36m>[39m
          [36m<div[39m
            [33maria-hidden[39m=[32m"true"[39m
            [33mclass[39m=[32m"shell-skel"[39m
          [36m>[39m
            [36m<span[39m
              [33mclass[39m=[32m"psl-skel"[39m
              [33mstyle[39m=[32m"width: 90%;"[39m
            [36m/>[39m
            [36m<span[39m
              [33mclass[39m=[32m"psl-skel"[39m
              [33mstyle[39m=[32m"width: 70%;"[39m
            [36m/>[39m
            [36m<span[39m
              [33mclass[39m=[32m"psl-skel"[39m
              [33mstyle[39m=[32m"width: 80%;"[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<span[39m
            [33mclass[39m=[32m"psl-loading"[39m
            [33mrole[39m=[32m"status"[39m
          [36m>[39m
            [36m<span[39m
              [33maria-hidden[39m=[32m"true"[39m
              [33mclass[39m=[32m"psl-busy"[39m
            [36m>[39m
              [36m<i />[39m
              [36m<i />[39m
              [36m<i />[39m
            [36m</span>[39m
            [0mLoading…[0m
          [36m</span>[39m
        [36m</div>[39m
      [36m</main>[39m
    [36m</div>[39m
  [36m</body>[39m
[36m</html>[39m

- Expected:
null

+ Received:
<span
  class="psl-loading"
  role="status"
>
  <span
    aria-hidden="true"
    class="psl-busy"
  >
    <i />
    <i />
    <i />
  </span>
  Loading…
</span>

 ❯ tests/decide-board.test.tsx:63:62
     61|     </AppShell>,
     62|   );
     63|   await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull(…
       |                                                              ^
     64| }
     65| const button = (name: string | RegExp) => screen.getByRole('button', {…
 ❯ runWithExpensiveErrorDiagnosticsDisabled node_modules/@testing-library/dom/dist/config.js:47:12
 ❯ checkCallback node_modules/@testing-library/dom/dist/wait-for.js:124:77
 ❯ Timeout.checkRealTimersCallback node_modules/@testing-library/dom/dist/wait-for.js:118:16

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
