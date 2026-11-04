# Working records

Keep each item short and linked to real source paths or evidence IDs. This is ordinary engineering context, not a prepared assessment answer.

Use `.harness/work/main-session.md` as the entry point for continuity and design handoff. The main session alone updates its latest-summary section and appends important events to its history; corrections are new entries, not erased history. Fill it after the first source pass, then at meaningful decisions, applied replies, contract changes, actual checks, handoffs and interruption/resumption. Keep each entry to the facts, decision/reason, evidence path, impact on design and next action. Do not copy the entire chat or claim that unrecorded conversation was automatically captured. Specialized records below remain authoritative for their detail; link them instead of duplicating long explanations.

Before parallel design starts, record the task's absolute path, screen flow, input/output and failure states, current contract revision/hash or explicit draft status, usable fixtures and their mock status, permitted design work, blocked fields/questions, file ownership and the owner of shared types/configuration/dependencies. If a mock schema is still provisional, do not call it a frozen contract. Require real-output integration early. Main and design terminals must use the same task workspace to see these records; separate checkouts/worktrees do not automatically share ignored work records or chats. Do not publish private task records to solve that coordination problem.

Design/secondary sessions refresh `flow.py status`, read this main record, contract.json and questions before a slice or integration, then register their own worker and disjoint files. Put brief changes, pending interface requests and evidence paths in their worker's `--next` field or report them to the main session; never overwrite main-session.md or unilaterally edit the shared contract. The main session reads worker updates at checkpoints and reconciles them into the main record. These are local files, not automatic inter-terminal chat or a background watcher.

| When | Record |
|---|---|
| Choose structure or solver | context, alternatives actually considered, choice, reason, accepted cost, actor, next check |
| Change module/state | actual file, input/output, responsibility, state owner, failure behavior, revision |
| Implement a rule | source requirement, variable/constraint, implemented scope, independent validator |
| Handle failure/race | trigger, previous state, candidate state, publication/fallback behavior, real check |
| Discover weakness | assumption, counterexample, impact, checked or unknown, next improvement |
| Use AI suggestion | suggestion, accepted/modified/rejected/proposed, who decided, changed code, command/output, remaining limit |

At modeling, integration and verification checkpoints explain the changed behavior, choice, accepted cost, evidence and known limit in 30–60 seconds of plain language. Relate technical terms to the actual input/output. Ask one practical consequence question when the user needs to own a decision, such as what happens if the data changes during planning. Record only their actual response; unanswered means not confirmed, not understood. Do not turn every update into a quiz or invent a perfect chronological narrative after the fact.
