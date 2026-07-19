# zero-shot-build — Hermes runtime pitfalls

Durable, generic lessons from real `/zero-shot-build` runs on Hermes. Only things that
change what you do on the *next* build. The architecture in SKILL.md already encodes the
big ones (root-session orchestration, inline fallback, gate-owns-the-run); this file keeps
the sharp edges.

**How lessons get here:** each build keeps a live `NOTES.md` journal on its feature branch
(see SKILL.md → "The build journal"). After the run, the durable generic lesson is
distilled into this file via a separate harness PR; the run-specific war stories stay on
the build branch.

### 1. A delegated worker can return before finishing
- **Symptom:** a `delegate_task` child ends its turn with code written but the last 5%
  (a rename, a failing import, git) skipped — its summary still reads "done".
- **Fix:** the root verifies every handback — files exist, gate re-run cheaply — and
  finishes the remainder inline. Never re-delegate the missing 5%.

### 2. `max_spawn_depth=1` — workers cannot spawn workers
- **Fix:** the ROOT session is the orchestrator (this is the architecture, not a
  workaround). Delegation is for leaf work only; when it's unavailable at all, run the role
  file inline as a checklist. Never wait for a child that cannot spawn.

### 3. `clarify` can fail to load; answers can come back empty
- **Fix:** no load → ask in plain text, one question at a time (never a wall of questions).
  Empty answer → treat as "you decide": lowest-risk default, recorded as `Assumed:`.

### 4. Sub-agent background processes die on return
- **Fix:** only the root session launches servers the user (or the smoke) will touch. A
  worker booting a server "for the handoff" hands the user a dead port.

### 5. Pin the interpreter; boot before you hand off
- **Fix:** launch with `.venv/bin/python -m src` — bare `python`/`uvicorn` can resolve to a
  shared agent venv (silent `ModuleNotFoundError`). Before writing any handoff, actually
  boot the server and hit `/health` — write only verified run commands and URLs.

### 6. A stale dev DB turns a green suite into a live 500
- **Symptom:** tests pass (fresh tmp DB per test) but the live server 500s —
  `table runs has no column named …`. `create_all` never ALTERs an existing table.
- **Fix:** schema changed ⇒ ship the alembic migration in the same slice and apply it (or
  recreate the dev DB) before the boot gate. The boot gate must exercise the same DB the
  user will hit.

### 7. Batch the LLM call — never loop per output line/token
- **Symptom:** one call per generated line silently burned a real monthly spend cap
  (backoff can't fix a cap).
- **Fix:** generate the whole artifact in ONE call; parse and stream the pieces downstream.

### 8. A present key can still be dead
- **Symptom:** `.env` has the key, presence check passes, every real-call gate then fails
  401 ("User not found" — revoked/deleted account).
- **Fix:** at intake, validate the chosen provider's key with one minimal real call before
  building. On 401 mid-build: BLOCKED naming the env var — it's a user step, not a bug.

### 9. Re-verify cheaply — don't re-burn the live API
- **Fix:** after mechanical edits, `py_compile` + `pytest --collect-only` proves imports
  resolve. Reserve full real-key runs for first-green, logic changes, and pre-handoff.
  Free-tier quotas (429) trip fast during builds — retry/backoff belongs in the generated
  code, and cap your own test generations.

### 10. At the human gate, the ROOT owns the run — multi-select, always
- **Fix:** launch (pinned interpreter, free port, retry if busy) → live smoke (health + new
  endpoints + the served UI) → hand the user ONE verified URL + "what to click" → only then
  the multi-select `clarify` checklist (one option per shipped feature + a "nothing worked"
  escape). If it won't boot, that's a BLOCKER to fix, not a question to ask.
