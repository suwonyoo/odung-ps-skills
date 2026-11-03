---
name: hackathon-intake
description: Read a timed coding task, identify required outputs and acceptance checks, and configure a local preparation harness. Use for hackathon preparation or an explicitly AI-permitted implementation phase. Do not use to answer a no-AI follow-up assessment.
---

Read the task's README, existing project instructions, and relevant task files before changing code. Use the actual task and its constraints as the source of truth. Do not infer required filenames, ports, APIs, deployment, or a tech stack from a generic example.

If present, read `.harness/GUIDE.md`. Use `python3 .harness/runner.py` only when that file exists. Do not create a substitute runner or change platform settings. If the kit is absent, perform the intake in text and state which setup remains missing.

1. Identify the user, required behavior, input/output, constraints, and exact deliverable paths. Separate confirmed requirements from assumptions.
2. Inspect the existing run command and dependency files. Preserve the supplied project. Ask only questions that change implementation or verification. Draft questions for the user to ask the provided stakeholder; do not automate messenger UI.
3. Set a short plan with one runnable input-to-output path first. Include time for verification, documentation, and submission review.
4. Initialize local records with `python3 .harness/runner.py init` if the runner exists. Populate `.harness/work/task.json` from the actual task. Follow the schema in `.harness/START_HERE_KO.md`; do not leave example requirements or paths in place.
5. For every required requirement, specify an observable acceptance condition and at least one relevant command or manual check. Test logic must check the behavior; an unconditional successful command is not evidence of functionality.
6. Record expected values from the specification or an independent calculation. Do not derive both implementation and expected values from the same unverified assumption.
7. Keep actual decisions in `.harness/work/decisions.md`. Do not invent alternatives, failures, timestamps, or stakeholder answers.

Return a brief plan, any material question, and the next bounded implementation step. Keep code edits for the build step. Never claim official compliance, acceptance, or a score.

Do not transmit task files, use private keys or external AI, change supervision, push task content, deploy remotely, or use browser/computer automation when the task forbids those actions. If the user indicates a no-AI phase has begun, stop assistance with the assessment.

When `.harness/flow.py` is installed, keep the `hackathon-start` workflow active: run start once, record pending manual questions, and route `inputs-reviewed` to solver-modeling before core optimization code. Review solver fit, not a fixed OR-Tools default.
