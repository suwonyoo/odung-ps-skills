---
name: hackathon-build
description: Implement one bounded feature or fix in a timed coding task using the current project's acceptance conditions. Use during preparation or an explicitly AI-permitted implementation phase; do not use for a no-AI follow-up assessment.
---

Read the actual task, project instructions, and `.harness/GUIDE.md` when present. Check `.harness/work/state.json` before working; if its phase is closed, do not resume implementation through this workflow. If no harness exists, work within the task's instructions without inventing tool availability.

1. Select one required behavior and its acceptance condition. State the files you will own and the expected observable result.
2. Preserve the existing stack and implement the smallest complete input-to-output path. Do not add a model API unless the task supplies and permits it.
3. Keep one writer per file. Only delegate when the user requests it or applicable instructions explicitly call for delegation, and the provided environment supports it. Prefer a read-only reviewer. Never enable features by changing platform restrictions or authentication. Check that all agents use permitted models.
4. Define shared interfaces before parallel implementation. A single writer owns package manifests, lockfiles, shared types, and root configuration. Use worktrees only when understood and available; integrate results into the designated submission directory before final checks.
5. Run a relevant local check, preferably using `python3 .harness/runner.py check CHECK_ID` when configured. Read the result and log. Do not equate a build or HTTP success with full behavior validation.
6. If a check fails, reproduce the symptom, test a specific cause, make a focused change, and rerun the same check plus affected normal cases. Preserve failed evidence. Do not manufacture a failure to create a process narrative.
7. Record the change, actual reason, evidence reference, and remaining limitation briefly. Ask the user to operate the internal Browser for any required manual UI check. Do not claim to have performed that interaction yourself.

Return changed behavior, actual validation result, and next action. Stop expanding scope when verification and submission time are at risk. Do not automate submission or provide answers during a no-AI follow-up phase.

With flow.py installed, register session ownership and update the board at task start/change/end. Wrap expensive commands in a timed run. Maintain model-spec.md, architecture.md, decisions.md and AI_collaboration.md with the actual change, rationale, accepted cost and real evidence as you work. Route an actual candidate to integration, and failures to focused diagnosis. Preserve solver-native status and input version; never publish merely because a process returned zero.

## v3 coordination

Before each slice read status and HR blockers. If joins, units, shared constraints or a user-visible edge case are ambiguous, use stakeholder-bridge immediately. Continue independent tasks with disjoint ownership. Preserve contract revision across sessions; its owner integrates changes. Keep the first slice end-to-end; parallel UI must consume the frozen contract and use real output early.

For a bug, establish a small command that detects the actual failure, isolate a cause, fix it and rerun affected behavior. Avoid a long debugging ceremony for a trivial typo. Mark a session done only after handing off changes and real evidence; process exit 0 leaves a timed worker waiting.
