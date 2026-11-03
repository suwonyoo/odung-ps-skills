# Sources and authorship

The toolkit code, skill instructions, templates, and synthetic practice data were written for this project. No contest tasks, private attachments, credentials, transcripts, or third-party source files are bundled.

Public references consulted for format and workflow concepts on 2026-10-30:

- OpenAI Build skills: https://learn.chatgpt.com/docs/build-skills
- OpenAI project instructions: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- OpenAI Subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
- OpenAI skill evaluations: https://developers.openai.com/blog/eval-skills
- OpenAI execution plans: https://developers.openai.com/cookbook/articles/codex_exec_plans
- Git worktree: https://git-scm.com/docs/git-worktree
- GitHub Spec Kit: https://github.com/github/spec-kit
- Superpowers verification and debugging: https://github.com/obra/superpowers

These sources informed general design. No upstream skill implementation was copied. Superpowers is referenced for clarification, bounded tasks, systematic debugging and evidence before completion; its package and hooks are not installed. The installer does not download any dependencies. Optional solver examples depend on the separately installed packages listed below. Their licenses do not become the license of this original implementation. If you later copy code or a skill, record its exact URL, revision, files, license, and modifications here.

Solver/workflow references checked on 2026-11-04 (KST):

| Source | Version / status | Use | License |
|---|---|---|---|
| https://github.com/google/or-tools | Python 9.15.6755 pinned | Optional CP-SAT example dependency | Apache-2.0 |
| https://github.com/TimefoldAI/timefold-solver | Java 2.7.1 pinned; 2.8.0 newly published, not used in this prepared baseline | Optional local solver dependency | Apache-2.0 |
| https://github.com/TimefoldAI/timefold-solver-python | Archived 2025-10-06 | Excluded from preparation path | Apache-2.0 |
| https://github.com/FasterXML/jackson-databind | 2.20.1 pinned | Java example JSON input/output | Apache-2.0 |
| https://github.com/qos-ch/slf4j | 2.0.17 pinned | Java example runtime logging | MIT |

- https://developers.google.com/optimization/cp/cp_solver — integer models and native statuses.
- https://developers.google.com/optimization/scheduling/employee_scheduling — CP-SAT also supports employee scheduling.
- https://developers.google.com/optimization/routing/routing_options — Routing uses its own limits and statuses.
- https://docs.timefold.ai/timefold-solver/latest/frequently-asked-questions — Java 21 baseline for 2.x; Community vs commercial products.
- https://docs.timefold.ai/timefold-solver/latest/running-timefold-solver/overview — domain modeling and library/service use.
- https://docs.timefold.ai/timefold-solver/latest/optimization-algorithms/overview — time/quality tradeoff and optimality limitations.

Examples are original, deliberately small synthetic models. Solver binaries, upstream source archives, task data and actual work logs are not bundled. Installed transitive dependencies retain their own licenses. Pinning the top-level dependency does not lock every transitive dependency; record the resolved environment during rehearsal.

Use the actual event rules and project instructions at runtime. Public documentation does not establish the capabilities or permissions of a particular managed environment.
