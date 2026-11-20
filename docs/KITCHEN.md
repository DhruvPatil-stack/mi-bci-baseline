KITCHEN RULES (v3, model-agnostic)

Rule 1: Choose the cook by the cost of a mistake,
not by the size of the task.

TIER TABLE (edit this table when models change)
Role        Claude                       Codex          Effort
Head chef   Opus 5.5 + fable-thinking    GPT-6.2 Astra  xhigh
Sous chef   Opus 5.5                     GPT-6.2 Sol    xhigh
Line cook   Sonnet 5.5                   GPT-6.2 Sol    medium
Prep cook   Haiku 5.5                    GPT-6 Luna     low

NOTE: Fable 5.2 is not on my plan. The Head chef uses
the fable-thinking skill on Opus 5.5 in its place.
The skill gives a plan structure. It adds no model
capacity.

ORDER OF SERVICE
1. TICKET. Write the goal, the done-condition, and the
   files in scope. For science work, add one physical
   check (an analytic result or a published value).
2. PLAN. The Head chef loads the fable-thinking skill.
   It reads this file and writes the plan.
   The Head chef writes no code.
3. LOCK THE CHECKS. The Head chef writes each check as
   a script or test that runs without a person.
   Save the checks in tests/locked/. After this step,
   no cook and no Sous chef can edit them.
4. PLAN REVIEW. For a hard-station ticket, the other
   vendor's Head chef reviews the plan and the checks
   before the build starts. For other tickets, skip
   this step.
5. PREP. Prep cooks search the codebase and do renames
   and boilerplate.
6. BUILD. Line cooks write the code from the plan.
   They do not change the plan or the locked checks.
7. HARD STATIONS. The Sous chef owns auth, payments,
   FEBio boundary conditions, and unit conversions.
   A bug that nobody can find goes to the Sous chef
   at max effort.
8. CHECK. The Sous chef starts a NEW session. It reads
   only the ticket, the plan, and the diff. It does
   not read the Head chef reasoning. It runs the
   locked checks. A failed check goes back to the cook
   with the exact error text. Return a job 2 times
   at most.
9. ESCALATE. If a cook fails 2 times, move the job up
   one tier. If the Head chef plan fails, or the Sous
   chef fails at max effort, stop and ask the human.
   Do not retry at the same tier.
10. INSPECT. Use a new session and the OTHER vendor.
    If Claude built the code, Codex reviews it.
    If Codex built the code, Claude reviews it.
11. CLOSE. Update docs/ (progress, decisions, issues).
    Add one lesson to this file.

LIMITS
- Run 3 cooks in parallel at most.
- Compact the context at 40%.
- Use AGENTS.md for Codex and CLAUDE.md for Claude.
  Keep one file and link the other name to it.

LESSONS
- v0.2: Before freezing a time budget, multiply the fit count by a measured fit time. A frozen 40 min budget against 820 calibration fits made every model time out, and the gates that skip non-ok results then passed with nothing checked.
- v0.3: Give each agent a heartbeat file with a timestamp and check it at the first marker. Codex stopped after its first step and never acted on P0_DONE; nobody knew until the 45-minute review deadline, and the whole Codex half (responders, ERD) was lost.
