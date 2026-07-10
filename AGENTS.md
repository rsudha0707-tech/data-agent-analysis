# Hermes Agent — Entry Point (zero-shot SDD harness, Hermes port)

This is a spec-driven AI agent boilerplate, **ported for Hermes Agent**. Read this
file first, then follow the instructions below. This is the Hermes-native equivalent
of the original `CLAUDE.md`; the source of truth for behaviour is the `harness/`
directory and the skills under `harness/skills/`.

## What This Repo Is

A starting template for building AI agents spec-first. The spec in `spec/` is either:

- **Partially or fully filled in** — you are implementing an agent from a completed spec
- **Empty / placeholder** — you are in the build phase; run `/zero-shot-build` (the
  Hermes skill `harness/skills/zero-shot-build/SKILL.md`) to drive the spec and build

## Your First Action Every Session

1. Read `harness/rules/ai-agents.md` — mandatory rules for all AI sessions
2. Check whether `spec/roadmap.md` has been filled in:
   - If it still contains `<!-- FILL IN -->` placeholders → the spec is not ready; do not write application code yet
   - If it is filled in → proceed to read the full spec manifest below before touching any code

> **Hermes note:** Hermes auto-loads this file (root-level `AGENTS.md`) plus `.hermes.md`
> as project context. No manual "open this file" step is needed — the rules below are
> already in your system prompt when you work in this repo.

## Spec Manifest (read in this order when spec is complete)

```
spec/roadmap.md
spec/architecture.md
spec/capabilities/          ← all files
spec/data.md
spec/api.md
spec/ui.md
spec/agent.md     ← REQUIRED for any agent framework project
harness/rules/ai-agents.md
harness/patterns/spec-driven.md
harness/patterns/phases.md
harness/patterns/project-layout.md
harness/patterns/engineering-practices.md
harness/patterns/test-driven.md
harness/patterns/ui-ux.md
harness/patterns/tech-stack.md     ← generic stack rules (chosen stack is in spec/architecture.md)
harness/patterns/code.md           ← generic code conventions
harness/patterns/agentic-ai.md     ← catalogue of agentic patterns (chosen graph is in spec/agent.md)
harness/rules/git.md
```

**`spec/agent.md` is mandatory** for any project using LangGraph, CrewAI, AutoGen, or any agent orchestration framework. If it does not exist when you reach Phase 2, stop and raise it as a blocker. (The reusable catalogue of agentic-AI patterns to choose from lives in `harness/patterns/agentic-ai.md`.)

## If the Spec Is Not Ready

Tell the user to run **`/zero-shot-build [their idea]`** — load the skill at
`harness/skills/zero-shot-build/SKILL.md` and follow it. That skill runs one intake
round — the only interactive setup step — using the Hermes `clarify` tool (multiple-choice)
instead of Claude Code's `AskUserQuestion`. It asks the user to fill `.env` with the
required API keys/secrets. Once intake completes, the **agent-builder** orchestrator runs
design → scaffold → build, one phase per invocation. It is autonomous *within* a phase and
stops at each phase boundary for a **human testing gate** — the user tests the increment
before the next phase starts. Each phase delivers the smallest user-testable win, built
first-time-right on the tested path.

## Skills (entry points)

These are the entry points. They are Hermes skills living under `harness/skills/`. Each is
also documented as a slash-command-style entry in `.hermes.md` so a chat session can invoke
them by name. The skill file is the source of truth.

| Skill | Purpose |
|-------|---------|
| `zero-shot-build [idea]` | Idea → working, verified skeleton (drives agent-builder). Also adds a new capability. |
| `zero-shot-fix [target]` | Diagnose + fix a bug, error, failing test, or spec/code drift, then verify. |
| `zero-shot-sync [scope]` | Reconcile spec ↔ code so they match (spec wins), then verify. |

**How they map to Hermes mechanics:**

- **Slash command** — typed in a Hermes chat session (e.g. `/zero-shot-build an agent that ...`).
- **Direct load** — `skill_view(name="...")` or the skill file path `harness/skills/<name>/SKILL.md`.
- **Intake questions** — use the `clarify` tool with `choices` (max 4) for multi-select product
  rounds; for free-text idea capture, ask an open-ended `clarify` question and WAIT for the reply.
- **Sub-agents (the team)** — spawned via Hermes `delegate_task` (or `agent` tool in the agent
  definitions). Each role is defined in `harness/agents/<name>.md`.

## Key Rules (summary — full rules in harness/rules/ai-agents.md)

- Never write application code before reading the full spec
- Never skip a phase — complete phase N before starting phase N+1
- Commit every logical unit of work; never let the working tree stay dirty
- Each phase is tested by the human before the next phase starts — stop at the phase boundary, hand off the test instructions, and wait for the user
- Tight scope, first-time-right — each phase is the smallest user-testable win and must work the first time the user tests it; zero rough edges on the tested path
- Tests and evals run against the real LLM/API using keys from `.env` — never gate the build on offline/stubbed runs
- When in doubt, ask at intake — do not guess requirements; once intake completes, build a phase autonomously and stop for the human testing gate

## The baseline runtime (NOT in this port — follow-up)

> **Note (v0.1 scope):** This PR ports the **harness** — the rules, patterns, skills, agent roles,
> and spec templates that drive a spec-first build. It does **not** yet include the original repo's
> runtime baseline (`src/` FastAPI+LangGraph+SQLite agent, `frontend/` Next.js, `tests/`) — those are
> the *generated app skeleton*, a separate port tracked as a follow-up. When added, the skeleton is:
>
> - `src/graph/nodes.py` — `transform_text` node → replace with your capability logic
> - `src/prompts/transform.md` → replace with your system prompt
> - `frontend/src/app/page.tsx` → replace the transform form with your UI
>
> Until then, a `/zero-shot-build` here produces the app under `<agent-slug>/` from scratch driven by
> `spec/` + `harness/` (no pre-baked `src/` baseline).

## Sub-agents (the team)

`/zero-shot-build` delegates a full build to **agent-builder**, which plans and coordinates the
rest and owns git/PR. `/zero-shot-fix` and `/zero-shot-sync` call the workers directly (no
agent-builder) and own git themselves. Each agent is one full, self-contained role definition at
`harness/agents/<name>.md`.

| Agent | Role | Tools |
|-------|------|-------|
| agent-builder | Orchestrator — plans phases, fans out code-generator instances per slice (in parallel via `delegate_task`), and owns the git/PR surface for a build | read/bash/delegate_task |
| spec-writer | The single design authority — writes the FULL spec (incl. architecture + agent-graph + phased plan) **and** self-reviews it | read/write |
| code-generator | Implements ONE independent slice (backend `src/`, frontend `frontend/`, or both) plus tests — spawned in parallel, one per slice | read/write/bash |
| qa-auditor | Independent review **and** run gates/tests/app **and** audit spec↔code drift; runs FIRST in fix/sync and classifies root cause SPEC-vs-CODE | read-only (bash) |

Pattern: **spec-writer** writes the whole spec and carves each phase into independent slices.
**agent-builder** fans out one **code-generator** per slice (max parallelism — disjoint paths,
never conflict) via `delegate_task`. **qa-auditor** independently gates each slice and audits
drift — it never edits. The **human tests between phases**.

> **Cross-tool note:** The original Claude Code harness lives at
> `/Users/sai/Workspace/Lab/zero-shot-sdd-harness` (also `smallTechOrg/zero-shot-sdd-harness`).
> This repo is the Hermes-native port — same six convictions, same spec discipline, same
> human-gated phased build, expressed with Hermes primitives (`AGENTS.md`/`.hermes.md` instead of
> `CLAUDE.md`, `harness/skills/` instead of `.claude/skills/`, `harness/agents/` + `delegate_task`
> instead of `.claude/agents/`, `clarify` instead of `AskUserQuestion`).
