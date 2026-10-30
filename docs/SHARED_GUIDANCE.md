# Local preparation harness

Use this toolkit only during preparation and a phase in which AI assistance is allowed. The actual task, supplied project instructions, and current organizer guidance take priority. This toolkit does not certify compliance or a score.

- Read requirements before modifying the supplied project.
- Preserve the supplied code, instructions, authentication, and platform settings.
- Work on one observable behavior at a time. Keep time for verification and submission.
- Prefer one code writer and a read-only reviewer when parallel work is requested and available. Never assume a subagent feature or model is enabled.
- Use only permitted models and tools. Do not introduce external AI calls, private API keys, remote deployment, or task-data transmission.
- Do not automate browser, messenger, or submission controls when Computer Use is prohibited.
- Record actual commands, exit codes, expected values, observations, decisions, and limits. Keep failures. Do not fabricate an activity history.
- Attribute user observations as user-reported. AI-generated tests and AI review are not user-operated UI checks.
- Use the actual submission paths. Internal notes in `.harness/work` are working records and are not guaranteed submission artifacts.
- At the no-AI phase, stop all AI assistance. The `close` command only closes this tool's work records; it does not control the platform or other AI processes.

Run `python3 .harness/runner.py --help` for local commands. Read `.harness/START_HERE_KO.md` for the task schema and examples.

The runtime uses no network API, browser automation, or AI SDK. Commands that you configure can themselves use network or secrets; inspect them. This toolkit is not a sandbox, firewall, tamper-proof ledger, or authority on exam rules.

Source snapshots exclude `.git`, `.harness`, dependency directories, common caches, and generated build output. Keep task source files outside those directories. A changed source file or task.json makes earlier results stale. A passing command proves only what its assertions check.
