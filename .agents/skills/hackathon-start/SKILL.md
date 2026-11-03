---
name: hackathon-start
description: Start or resume an AI-permitted timed coding task and maintain phase, solver choice, manual stakeholder questions, parallel session ownership, time limits, and evidence-backed working notes. Use when the user says to start, continue, or coordinate hackathon work without naming every skill. Stop for an active no-AI assessment.
---

Read actual project instructions and supplied task files first. Preserve the supplied stack and submission paths. Use this workflow only during preparation or an explicitly AI-permitted work phase. Never generate answers for an active no-AI follow-up.

1. If `.harness/flow.py` exists, read `.harness/WORKFLOW_KO.md`, run `python3 .harness/flow.py start --minutes N` using the actual allowed budget (180 only when unknown and clearly stated), then read `.harness/work/STATUS.md`. Start is idempotent and must not reset a running deadline. Respect a closed `.harness/work/state.json`.
2. Read the skill named by the workflow's next route in `.agents/skills/NAME/SKILL.md`. If the CLI does not discover skills automatically, read the file directly. The user should not have to call each skill. If the kit is missing, explain the missing setup, use the same procedure in text, and do not invent commands or claim a running status board.
3. Route from actual events, not just keyword matches:
   - new brief -> hackathon-intake;
   - input facts collected or material requirements changed -> solver-modeling;
   - manual stakeholder question/answer -> stakeholder-bridge;
   - accepted model and I/O contract -> hackathon-build;
   - failure -> reproduce, isolate one cause, focused fix through hackathon-build;
   - integration or a completion claim -> hackathon-verify;
   - current evidence satisfied -> hackathon-finish.
4. Emit the corresponding `flow.py event NAME --note ACTUAL_REASON` and read the indicated instructions. This routes work; it does not launch another agent. Do not claim native hooks, automatic subagents, or actions that did not happen.
5. At each significant update report only current phase, session task, blocker/decision, next action, and time budget. Use `flow.py worker` at start/change/end for manually operated sessions. Use `flow.py run` around long commands for automatic heartbeats, actual duration and outer timeout. State that manual session elapsed time is wall time since its task began, not continuous active work.
6. Before parallel work, define the actual input/output/failure contract and one owner for shared files. Assign core and integration disjoint paths. Only launch parallel agents if the user or applicable project instructions authorize it and the environment supports it. Multiple terminals and solver threads are different resources. Integrate early; never overwrite a whole finished folder with another session's version.
7. Keep ordinary engineering records as work happens, not an end-of-task story: model-spec.md, architecture.md, decisions.md, questions.md, AI_collaboration.md, limits.md. Read the checklist in `references/working-records.md`. Record user decisions only after a real reply; distinguish AI defaults, proposals and user observations.
8. Ask only material decisions in this short format: decision; term + plain meaning; two options + cost; recommendation + reason; verification method. Wait on required business priority/hard-constraint decisions, while progressing independent work. Do not ask for every reversible implementation detail.
9. Separate solver return, business feasibility, optimality proof, and publish eligibility. Preserve unknown/failed/stale evidence. If source or requirements change, update the relevant records and rerun affected checks before claiming readiness.

Use the deadline to narrow scope, not to fabricate confidence. Keep real task data and work records out of the public preparation repo. The user manually asks stakeholders and manually performs any required official submission.
