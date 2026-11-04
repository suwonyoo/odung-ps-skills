---
name: task-start
description: Start or resume a structured coding task from supplied problem files and desired outputs. Coordinate analysis, implementation, questions, time and evidence without explicit skill commands. Exclude unrelated small edits and toolkit maintenance; respect actual no-AI rules.
---

Read actual project instructions and files. A brief, desired output and “시작하자” are enough; no event name or AI-permission declaration is needed for ordinary development. Preserve the supplied stack, delivery paths and assessment rules.

1. Locate the actual task workspace. From the public kit, follow AGENTS.md to install into a separate task directory. Do not copy real task data into the public checkout. If the runtime is absent, say so; do not invent executions.
2. Read `.harness/WORKFLOW_KO.md`. Start with the actual minutes (state a provisional 180 if unspecified), or resume the original clock/state. Read STATUS.md and the indicated skill instead of restarting.
3. If the user says there is no stakeholder DM, record `flow.py contact --mode none --note 'user wording'` once and retain it across phases and resumptions. Do not ask them to skip DM repeatedly. If they explicitly have a channel, use manual. If unspecified, ask only when an important unknown actually needs it.
4. Follow intake → modeling → parallel-build → integrate → verify → finish. Transition events record readiness; they do not launch skills or agents. Never bypass intake or verification to make the board green.
5. At new rules, failures and integration boundaries, use stakeholder-bridge for material ambiguity. Check local facts first. In no-DM mode use documented facts, reversible AI defaults and necessary user decisions; never invent an external reply or waive a hard requirement. Pause dependent work only where an unsettled decision changes correctness.
6. Show `[i/6 한글 단계 | 현재 작업 | 남은 예산]`, next action and `사용자 할 일: 없음 / 선택 답변 / 직접 확인`. Explain a technical term in one plain sentence. For important choices give options, cost, recommendation and one check; skip routine permission loops. Never invent an optimality ETA or completion percentage.
7. Build the smallest input→decision→validation→output slice first. Freeze one I/O/failure contract, assign disjoint files and one owner for shared types/dependencies. Only use parallel agents when authorized and supported. Terminals, AI workers and solver CPU workers are different; never integrate by overwriting directories.
8. Register workers at task start/change/end; wrap expensive commands in timed runs. Keep short actual records using references/working-records.md. Preserve failures and distinguish AI defaults, user decisions, copied replies and actual checks.
9. With 30 minutes left, freeze optional features and new solver/stack changes. Verify and hand off exact deliverables. A closed runner does not stop other sessions. Do not automate stakeholder messages or official submission.

On interruption read status and logs; recover only observed dead local processes. Do not turn UNKNOWN into INFEASIBLE or publish an invalid fallback. The runtime checks structure/evidence, while semantic correctness still needs reasoning and real checks.
