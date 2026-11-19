GATE: FAIL
COMMIT: 1457df1c1d4ad44327640da4efcce7d5d85dc9cd
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit 1457df1c1d4a, round 3, attempt 1

## checks.sh (last 80 lines of checks.log)

```
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
          [33mclass[39m=[32m"psl-phonebar psl-on-dark sw-phonebar shell-phonebar--bell"[39m
        [36m>[39m
          [36m<a[39m
            [33maria-label[39m=[32m"Back to Queue"[39m
            [33mhref[39m=[32m"/my-work"[39m
          [36m>[39m
            [0m← Queue[0m
          [36m</a>[39m
        [36m</header>[39m
        [36m<span[39m
          [33mclass[39m=[32m"sw-phoneslot psl-on-dark"[39m
        [36m>[39m
      ...

Expected: "Use a date after go-live."
Received: "Skip to main contentPSL FACTORYMy workProjectsAssistantTunde Bello · PMStart work← QueueStartProjectsLagoon HealthDeliveryHYP-0062HistoryLagoon Health · patient appHypercare · release not recordedJourneyDeliveryMilestonesDocumentsMoneyRegistersActionsPM Tunde Bellorevision 1DRAFTEDEarned01 Apr 23:30REVIEWEDIn progressAPPROVED—Not yetSENT—Not yetRECEIPT RECORDED—Not yetVERIFIED—Not yet01PlanDone02BuildDone03Go-liveDone04HypercareNeeds a person05ArchiveNot startedTolaCannot approve, send or pay.DONE✓Done: Checked the observations so farNext step. A person takes the next step on this page.NextEngineering deploys outside the factory. You record what was released, with the deployment log as proof.What happens next: the hypercare window starts from the release date. Go-live acceptance (02 Apr) is already recorded.Record releaseRecord releaseWhat happens next: the hypercare window starts from the release date. Go-live acceptance (02 Apr) is already recorded.VersionReleased onEnvironmentProofrelease-1.0.0-log.pdf · 1 KB×Add another fileAdd proof to continue.Record releaseCancel"

 ❯ tests/hypercare.test.tsx:354:44
    352|       fireEvent.submit(ws().getByRole('form'));
    353|     });
    354|     await waitFor(() => expect(pageText()).toContain('Use a date after…
       |                                            ^
    355|     expect(ws().getByRole('form')).toBeTruthy();
    356|
 ❯ runWithExpensiveErrorDiagnosticsDisabled node_modules/@testing-library/dom/dist/config.js:47:12
 ❯ checkCallback node_modules/@testing-library/dom/dist/wait-for.js:124:77
 ❯ Timeout.checkRealTimersCallback node_modules/@testing-library/dom/dist/wait-for.js:118:16

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
