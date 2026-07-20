// Zero-build baseline frontend. Single-origin: the page is served by the
// backend at /app, so API calls are same-origin relative paths.
"use strict";

const $ = (id) => document.getElementById(id);

async function loadHealth() {
  const badge = $("provider-badge");
  try {
    const res = await fetch("/health");
    const body = await res.json();
    const { provider, model, key_configured: keyed } = body.data;
    if (!keyed) {
      badge.textContent = "no API key — set one in .env";
      badge.classList.add("stub");
    } else {
      badge.textContent = `${provider} · ${model}`;
    }
  } catch {
    badge.textContent = "backend unreachable";
    badge.classList.add("stub");
  }
}

async function runTransform() {
  const btn = $("run-btn");
  const status = $("status");
  const errBox = $("error");
  const wrap = $("result-wrap");

  const text = $("text").value.trim();
  const instruction = $("instruction").value.trim();

  errBox.hidden = true;
  wrap.hidden = true;

  if (!text) {
    errBox.textContent = "Paste some text first — the input can't be empty.";
    errBox.hidden = false;
    return;
  }

  btn.disabled = true;
  status.textContent = "Running… (one real LLM call)";
  status.hidden = false;

  try {
    const res = await fetch("/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, instruction }),
    });
    const body = await res.json();

    if (!res.ok) {
      const msg = body?.detail?.message || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    const run = body.data;
    if (run.status === "failed") {
      throw new Error(run.error_message || "The agent run failed.");
    }
    $("result").textContent = run.output_text;
    $("result-meta").textContent =
      `run ${run.run_id} · ${run.provider} · ${run.model}`;
    wrap.hidden = false;
  } catch (err) {
    errBox.textContent = err.message;
    errBox.hidden = false;
  } finally {
    btn.disabled = false;
    status.hidden = true;
  }
}

$("run-btn").addEventListener("click", runTransform);
loadHealth();
