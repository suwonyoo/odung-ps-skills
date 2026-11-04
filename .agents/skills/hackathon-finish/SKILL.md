---
name: hackathon-finish
description: Audit local deliverables, align documentation with actual behavior, and prepare a concise handoff before manual submission. Use only during preparation or the AI-permitted work phase; never generate or assist no-AI follow-up answers.
---

Read the task's exact submission requirements, existing project guidance, and `.harness/GUIDE.md` when present. If `.harness/work/state.json` says closed or the user has started a no-AI phase, do not continue this workflow.

1. Stop feature expansion. Integrate any branch or worktree changes into the designated submission directory. Preserve existing task files and resolve editor/disk conflicts before continuing.
2. Match every required filename and path against the actual task. Generic internal notes are not a substitute for a requested deliverable. Do not infer hidden-file inclusion from the preview.
3. Check the run command, actual port/path, data requirements, and known limits. For an internal preview that needs it, bind the server to `0.0.0.0`; use the task's port rather than assuming 3000.
4. Run relevant checks and `python3 .harness/runner.py audit` if installed. Review the source, tests, and evidence. Report omitted requirements and stale or unrun checks. Do not convert gaps into pass states.
5. Produce the required local documents from actual work: purpose; input/process/output; decisions and reasons; validation and attribution; limitations; run instructions. Keep internal verification output in `.harness/work/verification.md` and copy only what the task requests to official paths. Audit again after final source/document edits, because evidence may become stale.
6. Ask the user to verify required UI actions manually. Record their observations only when explicitly reported. Do not operate the browser, messenger, or submit controls.
7. Give the user a short handoff to read while still in the permitted work phase. Do not predict answers to an active no-AI assessment. The user controls official submission and final completion checks.
8. Once work is finished, `python3 .harness/runner.py close` can close local records. Explain that this neither submits the task nor stops other AI sessions. Do not bypass it by rewriting the phase; use a separate practice workspace for another rehearsal.

For any preparation review, require accurate explanations of what was built, which choices were made, what was actually checked, and what remains unknown. The task-specific rules always take priority over this generic toolkit.

If flow.py is installed, inspect STATUS.md for blocked/stale sessions, integrate their actual changes, and reconcile ordinary engineering records with the final code. Keep user decisions distinct from AI defaults and user observations distinct from command results. Finish readiness does not mean an official submission occurred.

## v3 coordination

Do not hide late ambiguity to finish: use stakeholder-bridge, preserve the original phase and return through modeling if rules changed. Audit after final edits. Check workflow_errors, unfinished workers, pending HR, source hashes and contract revision as well as test exits. Distinguish implemented behavior from documented patterns and toy examples. The user performs official submission.
