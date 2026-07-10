---
name: zero-shot-build
description: Turn a zero-shot idea into a perfectly-working, thoroughly-tested, spec-driven agent (Hermes port). One intake round (which also collects the API keys into .env), then the agent-builder builds one phase at a time — autonomous within a phase, with a human testing gate between phases. Also used to add a new capability to an existing agent.
argument-hint: [your idea]
---

You run the human channel — intake, then the testing gate at every phase boundary — and hand the
building off to the **agent-builder** orchestrator (a Hermes `delegate_task` `orchestrator` role).
The idea is in the conversation context / `$ARGUMENTS`. **If no idea is given, ask the user in plain
text (an open-ended `clarify` question) to describe their idea / the problem they want to solve, and
WAIT for their free-text reply before doing anything else.** Do NOT fabricate or pick the idea — it
must come from the user as their own text. Only once you have the idea do you move to Stage 1 intake.
Goal: **one prompt → a perfectly-working, thoroughly-tested agent, one user-testable phase at a time.**

> **Hermes adaptation:** This is the port of `.claude/skills/zero-shot-build/SKILL.md`. The original
> used Claude Code's `AskUserQuestion` / `ToolSearch` for intake. Here, intake uses the Hermes
> **`clarify`** tool (multiple-choice, up to 4 choices) for each product/technical round, and an
> open-ended `clarify` for the free-text idea capture. The build itself is delegated to the
> `agent-builder` role via `delegate_task`.

**Autonomy model:** autonomous *within* a phase; a **human testing gate between phases**. Intake is
the only interactive SETUP step; after it, agent-builder builds a phase end-to-end without pausing,
then returns a test-handoff. You present the handoff, handhold the user through testing, and only
proceed to the next phase on the user's go.

## Stage 1 — Intake (the only interactive setup step)

Intake has **two fixed sections and a variable middle**:

1. **Product rounds (variable, minimum 5)** — all product questions, progressively deeper. Keep going
   until every dimension that would force a design decision in Phase 1 is resolved.
2. **Technical round (fixed, always last)** — one round of build-blockers only (LLM provider, stack, access method).

Each product/technical round is one **`clarify`** call with up to 4 multiple-choice questions
(`multiSelect` style → present each option; the user may pick or type their own). The API key prompt
is the only additional manual step.

**The golden rule: Phase 1 is the smallest user-testable quick win.** Richer intake sharpens *which*
slice to build first — it does not license a bigger Phase 1.

**The cardinal rule across ALL rounds: every question and every option must be specific to THIS idea.**

### Round 1 — What is the idea? (4 questions)

Acknowledge the idea in one sentence, then `clarify` with 4 multiple-choice questions (each can allow
multiple selections where it makes sense):

- **What it works on** *(4 idea-specific options)* — concrete data/content/domain.
- **What it produces** *(4 idea-specific options)* — the output or action.
- **Usage pattern** *(4 options)* — who uses it, how often, in what context.
- **Non-negotiables** *(4 options)* — e.g. "My data can't leave my machine", "Keep costs very low",
  "Must connect to [something mentioned]", "None — just build it well".

### Round 2 — How users interact (4 questions)

- **Session model**, **Memory & state**, **Multi-item handling**, **When things go wrong** — all options
  specific to the idea. Skip any question Round 1 already answered.

### Round 3 — Feature depth (4 questions)

- **Analysis / reasoning depth**, **Output richness**, **Proactive intelligence**, **Integration surface**.

### Round 4 — Constraints & scale (3 questions)

- **Data scale & performance**, **Privacy & data residency**, **Reliability bar**.

### Round 5 — Observability, trust & transparency (3–4 questions)

- **Reasoning visibility**, **Usage & cost awareness**, **Agent health & progress**, **Logging & audit**.

### Additional product rounds (as many as needed)

After Round 5, check: *"Is there any dimension that would force spec-writer to guess?"* If yes, write
another product round. Keep going until the brief would let spec-writer fill every capability file
without a single guess.

### Technical round (3–4 questions, always last)

- **LLM provider** — Anthropic (API key), Gemini (API key), OpenRouter (any model), Other / self-hosted.
- **Stack preference** — language, database? ("No preference" → Python + SQLite defaults for local/prototype, PostgreSQL for production, documented as assumptions.)
- **How will they access it?** — Web UI, CLI, REST API, scheduled job.
- One follow-up from prior rounds only if something would force a mid-build pause.

**API key** (the only manual user step). Read `.env` and check whether the key for the chosen provider
is already set (non-empty): `AGENT_ANTHROPIC_API_KEY`, `AGENT_GEMINI_API_KEY`, or `AGENT_OPENROUTER_API_KEY`.
If present and non-empty, skip silently. Only if missing or empty, tell the user to set it in `.env`
(from `.env.example`) and wait for confirmation. Never echo, print, paste, or commit a secret value.

**Synthesis brief**: write a **2–3 paragraph brief** covering what the agent does and who uses it; the
core interaction model; key capabilities/features; hard constraints; the technical stack and access
model. Name the one core path for Phase 1 explicitly.

## Stage 2 — Design + scaffold + build Phase 1 (delegate)

Invoke the **agent-builder** role once via `delegate_task` (orchestrator), passing the brief and the
populated `.env`. Tell it to run, in order, and return the **Phase-1 test-handoff**:

- **DESIGN** — spec-writer writes the full spec.
- **SCAFFOLD** — branch `feature/<slug>-v0.1`, project dirs, `.env.example`, first commit + push, open the PR.
- **BUILD PHASE 1** — fan out generators per independent slice in parallel, gate each with qa-auditor, return the handoff and STOP.

Relay only hard blockers it escalates.

## Stage 3 — Human testing gate (you own the human channel)

Phase 1 is the smallest working win. **Spoon-feed the user: the ONLY things they do by hand are (a) put
secrets in `.env` and (b) interact with the running app. They must never run a terminal command to test.**

1. **Launch the server** (you own this — agent-builder does NOT start it; sub-agent background processes
   are cleaned up on return). From the project root:
   a. frontend slice: `cd frontend && pnpm build && cd ..`
   b. migrations: `uv run alembic upgrade head`
   c. `uv run python -m src` with `run_in_background: true`
   d. Health-check: `for i in {1..10}; do curl -sf http://localhost:8001/health && break || sleep 2; done`
2. Present the handoff as **phase release notes** (live URL, what was built, what to click/type/look at,
   expected result, stubs vs real, what the next phase adds). No run commands in the handoff.
3. `clarify` two questions: *"Is the app loading at [URL]?"* and *"Your verdict?"* (multiSelect).
4. Route on their answers: app didn't load → qa-auditor (boot failure); negative verdict → delegate to
   **zero-shot-fix**; positive only → *"Ready for Phase 2?"*.

## Stage 4 — Per remaining phase (build → gate, repeat)

For EVERY remaining phase boundary: invoke **agent-builder** (one phase per invocation) passing the
user's feedback, then run the **Stage 3** gate again. Repeat until no phases remain.

## Stage 5 — Ship + report

qa-auditor final whole-tree drift audit (CLEAN); agent-builder ensures pushed + PR body current. Summarize
for the user: what was built, the live URL, what's deferred, and the PR link.

## Adding a capability to an existing agent

If the spec is already filled in and the user is adding a capability: skip scope intake; confirm `.env`
holds the needed keys. Tell agent-builder to run **spec-writer** (add capability to spec + append an
incremental phase to `spec/roadmap.md`) → fan out generators → gate with qa-auditor. Then run the human
testing gate on the new phase.
