---
name: stakeholder-bridge
description: Prepare questions for a user-operated stakeholder DM and reconcile copied answers into requirements, solver models, decisions and checks. Use when a timed task supplies a separate HR or stakeholder chat that cannot be accessed from the CLI, during preparation or AI-permitted work.
---

Read the task and existing `.harness/work/questions.md`. The user sends questions through the separate interface and copies answers back. Do not send messages or automate the DM, and never claim to have contacted or independently verified the stakeholder.

1. Rank unknowns by whether they change a hard constraint, objective order, input meaning or acceptance. Give a short batch (usually at most three) of ready-to-copy, specific questions. Explain what each answer changes and the temporary assumption if unanswered.
2. Record questions in questions.md as pending. Preserve the user's transmitted answer verbatim in its own entry with the actual received time. Put AI interpretation separately; avoid invented wording, timestamps or authority.
3. Link answer -> requirement ID -> model constraint/objective -> implementation -> independent check. If an answer conflicts with source material or remains ambiguous, expose the conflict and draft the smallest follow-up.
4. Use `flow.py event hr-answer --note ...` if installed. When the answer materially changes requirements, update task.json/model-spec/contract and emit `requirements-changed`; then revalidate affected evidence. Do not treat an old passing test as current proof.
5. For user choices ask: decision, technical term with a simple explanation, options and tradeoffs, recommended option and reason, and how to verify. Keep the choice proposed until the user replies. Record accepted/modified/rejected decisions in decisions.md and relevant AI_collaboration.md entries only when they happened.
6. Continue tasks independent of the answer. Do not silently relax mandatory rules or substitute an arbitrary weighted sum for an unresolved business priority.
