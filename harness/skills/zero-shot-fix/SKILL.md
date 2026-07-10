---
name: zero-shot-fix
description: Diagnose and fix a problem in an existing agent — a bug description, a runtime error/stack trace, failing tests, or spec/code drift — then verify the fix (Hermes port). Calls the worker agents directly; runs autonomously to a verified result.
argument-hint: [bug description / error / "tests" / "drift"]
---

You orchestrate a targeted fix by calling worker agents directly — no full agent-builder needed. The
target is in the conversation context / `$ARGUMENTS`. **If empty, ask the user in plain text (open-ended
`clarify`) to describe what's broken — the bug, error, failing test, or drift — and WAIT for their
free-text reply before doing anything else.** Once you have it, proceed to Step 1. Run autonomously:
diagnose+classify → fix → verify, looping until the failure signal is gone. Pause only on a hard blocker.

> **Hermes adaptation:** Port of `.claude/skills/zero-shot-fix/SKILL.md`. The original invoked
> `.claude/agents/*` sub-agents directly; here you spawn them via `delegate_task` (leaf roles) and run
> `git`/`pytest` via the `terminal` tool. The qa-auditor → code-generator routing logic is identical.

**qa-auditor runs FIRST** — it diagnoses, captures the failing signal, and CLASSIFIES the root cause
(SPEC vs CODE, and which surface). Its verdict ROUTES the fix and names which generator. Fixing happens
in the **code-generator**; judging happens in read-only **qa-auditor**; you (the skill) own the commit + push.

## Step 1 — Diagnose + classify (qa-auditor first)

**Skip if already diagnosed:** if the caller passed a qa-auditor verdict with exact `file:line` and
SPEC/CODE classification, use that as the baseline and go straight to Step 2.

Otherwise, invoke **qa-auditor** (via `delegate_task`, leaf) with the target. It captures the current
red state, CLASSIFIES root cause as **SPEC** vs **CODE** and names the **surface** (frontend / backend)
+ file(s), and returns a routed verdict. It stays read-only.

State the classification in one line. If qa-auditor can't reproduce the reported problem, say so and ask
for repro steps rather than guessing.

Done-when, by signal:

| Signal | Done when |
|---|---|
| Failing tests | the gate test is green |
| Bug description | the wrong behavior no longer occurs and a regression test covers it |
| Runtime error / stack trace | the error no longer reproduces when the app runs |
| Spec/code drift | qa-auditor (drift mode) reports CLEAN (see also `zero-shot-sync`) |

## Step 2 — Fix (routed by the verdict)

- **SPEC root cause** → invoke **spec-writer** to rewrite the spec section, then invoke the responsible generator(s) to redo the code toward the corrected spec.
- **CODE root cause** → invoke the responsible generator(s) directly — **code-generator** for `src/` and/or `frontend/`. Both can run concurrently if the fix spans both surfaces (disjoint paths).

Give the generator the precise target, the responsible files, and the spec sections defining correct behavior.
It fixes toward spec intent and adds/updates a regression test (real keys from `.env` for an LLM/API bug). It
must not mute a test or delete an assertion to go green.

## Step 3 — Verify (qa-auditor always; scope tiered by fix size)

**qa-auditor verifies every fix** — independence is the point. What changes by tier is the **scope** of what
qa-auditor runs, not whether it runs.

### Scoped gate (express) — use when ALL hold
- Root cause is **CODE**, not SPEC
- `git diff --name-only HEAD` shows **≤ 3 files changed**
- No DB migration added
- No API contract changed (`spec/api.md` untouched)

Invoke **qa-auditor in scoped gate mode**: verify only the changed surface — targeted tests + new regression
test + one real-key smoke call on the exact broken behavior (plus `pnpm build` only if a frontend file changed).

### Full gate — use when: SPEC root cause / migration added / API contract changed / > 3 files / scoped came back BLOCKED
Invoke **qa-auditor** in full gate mode. Still BLOCKED → re-route per the verdict; loop until VERIFIED. For a
drift fix, also confirm qa-auditor (drift mode) reports CLEAN.

## Step 4 — Ship + report

Commit + push the fix yourself (atomic `git commit … && git push`, staging only the changed files, per
`harness/rules/git.md`). Summarize: classification (SPEC/CODE + surface), root cause, files changed, the
regression test added, the verified before→after, and the pushed SHA.
