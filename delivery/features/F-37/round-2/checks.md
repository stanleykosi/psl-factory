GATE: FAIL
COMMIT: bad2bb2dd6f6d198aa7c72719cec51a8c1db6c11
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit bad2bb2dd6f6, round 2, attempt 1

## checks.sh (last 80 lines of checks.log)

```
+                 Delivery
+               </a>
+             </span>
+           </li>
+           <li
+             class="setup-card"
+           >
+             <strong>
+               Invoice payment terms default
+             </strong>
+             <span
+               class="setup-card__line"
+             >
+               From each signed SOW
+                · 
+               <a
+                 class="psl-link"
+                 href="/setup/rules/finance"
+               >
+                 Finance
+               </a>
+             </span>
+           </li>
+           <li
+             class="setup-card"
+           >
+             <strong>
+               Who may record an RFP outcome
+             </strong>
+             <span
+               class="setup-card__line"
+             >
+               Not set
+                · 
+               Pre-sale
+             </span>
+           </li>
+           <li
+             class="setup-card"
+           >
+             <strong>
+               Who may adjust a project's costing
+             </strong>
+             <span
+               class="setup-card__line"
+             >
+               Not set
+                · 
+               Pre-sale
+             </span>
+           </li>
+           <li
+             class="setup-card"
+           >
+             <strong>
+               Costing adjustment limit (per role)
+             </strong>
+             <span
+               class="setup-card__line"
+             >
+               Not set
+                · 
+               Pre-sale
+             </span>
+           </li>
+         </ul>
+       </div>
+     </main>
+   </div>
+ </body>

 ❯ tests/setup-rules.test.tsx:429:36
    427|     await waitFor(() => expect(desktop().getByRole('alert').textConten…
    428|     expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeN…
    429|     expect(document.activeElement).toBe(desktop().getByRole('alert'));
       |                                    ^
    430|     expect(saves()).toHaveLength(1);
    431|     expect(reads()).toHaveLength(2);

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
