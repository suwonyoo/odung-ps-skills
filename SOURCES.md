# Sources and licenses

Original toolkit code, instructions, templates and synthetic data. No upstream skill package, hook, source code, actual task data, credentials or work transcripts are bundled. References informed selected procedures; they are not installed dependencies.

## Workflow references reviewed 2026-11-04 (KST)

| Public source | Revision / license | Applied / excluded |
|---|---|---|
| [Matt Pocock skills](https://github.com/mattpocock/skills/tree/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d) | `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d`, MIT | Read grilling, domain-modeling, to-spec, to-tickets and diagnosing-bugs. Apply ready questions, vocabulary/decision capture, complete small slices and focused repros. Exclude exhaustive interview/approval loops and tracker setup dependency. |
| [Superpowers](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7) | `22f0b463e7a5e579904dd6211a520321035526f7`, MIT | Review brainstorming, writing-plans, systematic-debugging, verification-before-completion and TDD/subagent procedures. Apply scope clarification, bounded work, cause-driven fixes and fresh evidence. Exclude full-package hooks, universal TDD, per-task review orchestration and separate design/plan approval gates. |
| [OpenAI skills](https://learn.chatgpt.com/docs/build-skills), [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | Official format/reference | Repository instructions and progressive skill loading. Native discovery in the actual managed client must be checked there. |

These are adaptations of principles, not claims that every upstream procedure runs here. If copying upstream code/text later, preserve its license notice and record exact files and changes.

## Optional example dependencies

| Dependency | Pinned version | License |
|---|---|---|
| [OR-Tools](https://github.com/google/or-tools) | Python `9.15.6755` | Apache-2.0 |
| [Timefold Solver](https://github.com/TimefoldAI/timefold-solver) | Java CE `2.7.1`; JDK 21+ | Apache-2.0 |
| [Jackson Databind](https://github.com/FasterXML/jackson-databind) | `2.20.1` | Apache-2.0 |
| [SLF4J](https://github.com/qos-ch/slf4j) | `2.0.17` | MIT |

Install dependencies separately; the installer does not download them. Pinning these versions does not lock every transitive dependency. The archived Timefold Python port and commercial hosted model APIs are not used. Solver-specific behavior and status references are in the solver-selection skill reference. Examples are original, deliberately small models; performance on them does not establish full-size task performance.
