# Project instructions

This repository is a preparation toolkit, not a contest solution.

## Starting a task from this checkout

If the user provides a new problem and says to start (rather than asking to develop this toolkit), use `.agents/skills/hackathon-start/SKILL.md`. Locate the actual task directory from the user's supplied paths. Install additively with `python3 scripts/install.py --target ABSOLUTE_TASK_DIRECTORY --apply` when permitted, then work there. If only this kit exists, create a separate sibling `task-workspace` and tell the user where it is; do not copy confidential task content into this public checkout. Do not start the task clock while merely preparing the toolkit. Never infer that connecting a repository executes code: the agent must read these instructions and invoke the workflow.

## Developing this toolkit

- Keep the harness and workflow runtime compatible with Python 3.10+ and use only the standard library. Optional solver examples may depend on pinned OR-Tools or Timefold packages in isolated environments.
- Preserve actual command exit codes, evidence, and unverified states.
- Do not add external model calls, telemetry, browser automation, remote deployment, or credential handling.
- Do not copy real task material, private guides, work records, or answers into this repository.
- Change only the requested files and run `python3 -m unittest discover -s tests -v` after runtime changes.
- Refresh `release-manifest.json` with `python3 scripts/build_manifest.py` after changing installable files.
- Keep public preparation files separate from the task workspace and its evidence.
- Never describe user-reported observations as independently verified.
