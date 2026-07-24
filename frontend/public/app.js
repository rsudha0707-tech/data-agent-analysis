// CrimAnalyze frontend — multi-file CSV upload + investigator question + cache telemetry.
"use strict";

const $ = (id) => document.getElementById(id);

async function loadHealth() {
  const badge = $("provider-badge");
  const mssqlBadge = $("mssql-badge");
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
    if (mssqlBadge) {
      mssqlBadge.textContent = keyed ? "provider ready" : "provider missing";
      mssqlBadge.classList.toggle("stub", !keyed);
    }
  } catch {
    badge.textContent = "backend unreachable";
    badge.classList.add("stub");
    if (mssqlBadge) mssqlBadge.classList.add("stub");
  }
}

function _tryParseChartSpec(outputText) {
  if (!outputText || typeof outputText !== "string") return null;
  try {
    const candidate = outputText.match(/\{[\s\S]*"chart_spec"[\s\S]*\}/);
    if (!candidate) return null;
    return JSON.parse(candidate[0]);
  } catch {
    return null;
  }
}

function renderChart(spec) {
  if (!spec || typeof spec !== "object") return;
  const wrap = $("chart-wrap");
  const canvas = $("chart");
  if (!wrap || !canvas || !window.Chart) return;
  wrap.hidden = false;
  if (canvas._chart) canvas._chart.destroy();
  canvas._chart = new Chart(canvas, {
    type: spec.type || "bar",
    data: {
      labels: spec.labels || [],
      datasets: [
        {
          label: spec.label || "Value",
          data: spec.values || [],
        }
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
    },
  });
}

function _displayResult(outputText, provider, model, fileCount, cacheHit, queryHash) {
  $({
    "result": "raw-output",      /* fallback to raw text if structured view is unavailable */
  });
  $("result").textContent = run.insight || run.output_text || "";
  const meta = ["run output"];
  if (provider) meta.push(`${provider} · ${model}`);
  if (typeof file_count !== "undefined") meta.push(`${file_count || 0} file(s)`);
  if (query_hash) meta.push(`hash ${query_hash}`);
  if (typeof cache_hit === "boolean") meta.push(`cache ${cache_hit ? "hit" : "miss"}`);
  $("result-meta").textContent = meta.join(" · ");
}

function appendHistory(run) {
  const empty = $("history-empty");
  const table = $("history-table");
  if (empty) empty.hidden = true;
  table.hidden = false;

  const tbody = $("history-body");
  const tr = document.createElement("tr");
  const created = new Date(run.created_at || Date.now()).toLocaleString();
  const cacheLabel =
    typeof run.cache_hit === "boolean"
      ? run.cache_hit
        ? "hit"
        : "miss"
      : "n/a";
  tr.innerHTML = `
    <td><code>${run.run_id || "—"}</code></td>
    <td>${created}</td>
    <td>${run.file_count ?? "—"}</td>
    <td>${cacheLabel}${run.query_hash ? ` · ${run.query_hash}` : ""}</td>
    <td>
      <span class="status-pill ${run.status === 'completed' ? 'ok' : 'bad'}">
        ${run.status || "unknown"}
      </span>
    </td>
    <td><button class="ghost" data-run="${run.run_id}">Open</button></td>
  `;
  tbody.prepend(tr);
  tr.querySelector("button").addEventListener("click", async () => {
    try {
      const res = await fetch(`/runs/${run.run_id}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body?.detail?.message || `HTTP ${res.status}`);
      const data = body.data;
      $("result").textContent = data.output_text || "";
      $("result-meta").textContent = `run ${data.run_id} · ${data.provider || "?"} · ${data.model || "?"} · ${data.file_count || 0} file(s)`;
      const spec = _tryParseChartSpec(data.output_text);
      renderChart(spec);
      $("result-wrap").hidden = false;
      window.history.replaceState(null, "", `/app#run=${data.run_id}`);
    } catch (err) {
      $("error").textContent = err.message;
      $("error").hidden = false;
    }
  });
}

async function loadHistory() {
  const empty = $("history-empty");
  const table = $("history-table");
  const tbody = $("history-body");
  if (!empty || !table || !tbody) return;
  table.hidden = true;
  empty.hidden = false;
  empty.textContent = "Loading runs...";
  try {
    const res = await fetch("/runs");
    const body = await res.json();
    if (!res.ok) throw new Error(body?.detail?.message || `HTTP ${res.status}`);
    const runs = (body && body.data && Array.isArray(body.data)) ? body.data : [];
    tbody.innerHTML = "";
    if (!runs.length) {
      table.hidden = true;
      empty.textContent = "No runs yet. Run your first analysis above.";
      return;
    }
    runs.forEach((run) => appendHistory(run));
  } catch (err) {
    table.hidden = true;
    empty.textContent = `History unavailable: ${err.message}`;
  }
}

async function runAnalyze() {
  const btn = $("run-btn");
  const status = $("status");
  const errBox = $("error");
  const wrap = $("result-wrap");
  const chartWrap = $("chart-wrap");

  const files = ($("files").files || []);
  const instruction = $("instruction").value.trim();
  const useMssql = Boolean($("use-mssql")?.checked);

  errBox.hidden = true;
  wrap.hidden = true;
  if (chartWrap) chartWrap.hidden = true;

  if (!files.length) {
    errBox.textContent = "Upload at least one CSV file.";
    errBox.hidden = false;
    return;
  }
  if (!instruction) {
    errBox.textContent = "Type an investigator question first.";
    errBox.hidden = false;
    return;
  }
  if (files.length > 12) {
    errBox.textContent = "You can upload at most 12 files in one run.";
    errBox.hidden = false;
    return;
  }

  btn.disabled = true;
  status.textContent = `Analyzing ${files.length} file(s)... (one real LLM call)`;
  status.hidden = false;

  try {
    const form = new FormData();
    form.append("instruction", instruction);
    form.append("use_mssql", String(useMssql));
    for (const file of files) {
      form.append("files", file, file.name || "data.csv");
    }

    const res = await fetch("/runs", {
      method: "POST",
      body: form,
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
    $("result").textContent = run.output_text || "";
    const meta = [];
    meta.push(`run ${run.run_id}`);
    if (run.provider) meta.push(`${run.provider} · ${run.model}`);
    if (typeof run.file_count !== "undefined") meta.push(`${run.file_count} file(s)`);
    if (run.query_hash) meta.push(`hash ${run.query_hash}`);
    if (typeof run.cache_hit === "boolean") meta.push(`cache ${run.cache_hit ? "hit" : "miss"}`);
    $("result-meta").textContent = meta.join(" · ");

    const spec = _tryParseChartSpec(run.output_text);
    renderChart(spec);
    appendHistory(run);
    wrap.hidden = false;
  } catch (err) {
    errBox.textContent = err.message;
    errBox.hidden = false;
  } finally {
    btn.disabled = false;
    status.hidden = true;
  }
}

loadHistory();
$("run-btn").addEventListener("click", runAnalyze);
loadHealth();
