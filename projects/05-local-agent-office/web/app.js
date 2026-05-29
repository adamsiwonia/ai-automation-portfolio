const state = {
  busy: false,
};

const DASHBOARD_LOG_LIMIT = 30;
const FULL_LOG_LIMIT = 500;
const ACTIONABLE_LEAD_STATUSES = ["QUALIFIED", "REVIEW"];
const FINAL_LEAD_STATUSES = ["APPROVED_FOR_OUTREACH", "REJECTED", "DRAFT_CREATED", "DONE"];
const MOCK_SOURCE_MARKERS = ["mock", "mock_search", "demo", "sample", "fake"];
const DEBUG_LINES = [];

function debugLog(message, data = null, isError = false) {
  const line = {
    time: new Date().toLocaleTimeString(),
    message,
    data,
  };
  DEBUG_LINES.push(line);
  if (DEBUG_LINES.length > 16) DEBUG_LINES.shift();

  const output = document.getElementById("debugOutput");
  if (output) {
    output.textContent = DEBUG_LINES.map((item) => {
      const suffix = item.data === null ? "" : ` ${JSON.stringify(item.data)}`;
      return `${item.time} ${item.message}${suffix}`;
    }).join("\n");
  }

  const logger = isError ? console.error : console.log;
  logger("[Project05 UI]", message, data || "");
}

window.addEventListener("error", (event) => {
  debugLog("JS error", { message: event.message, source: event.filename, line: event.lineno }, true);
});

window.addEventListener("unhandledrejection", (event) => {
  debugLog("Unhandled promise rejection", { reason: String(event.reason) }, true);
});

function payloadFromInputs() {
  return {
    niche: document.getElementById("niche").value.trim() || "local businesses needing automation",
    limit: Number(document.getElementById("limit").value || 5),
    model_name: document.getElementById("modelName").value.trim() || "qwen3:8b",
  };
}

async function api(path, options = {}) {
  debugLog("API request", { path });
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  const data = await response.json();
  debugLog("API response", {
    path,
    status: response.status,
    logs: Array.isArray(data.logs) ? data.logs.length : undefined,
    leads: Array.isArray(data.leads) ? data.leads.length : undefined,
  });
  return data;
}

function setText(id, value) {
  document.getElementById(id).textContent = value ?? "";
}

function renderStatus(data) {
  setText("mode", data.current_mode || "STOPPED");
  setText("task", data.current_task || "Idle");
  setText("sourceMode", String(data.lead_source_mode || "mock").toUpperCase());
  setText("minimumScore", data.minimum_qualification_score || 7);

  const counts = data.counts || {};
  setText("countDiscovered", counts.discovered || 0);
  setText("countQualified", counts.qualified || 0);
  setText("countReview", counts.review || 0);
  setText("countRejected", counts.rejected || 0);
  setText("countDuplicates", counts.duplicates || 0);
  setText("countErrors", counts.errors || 0);
}

function renderLogs(tableBodyId, logs) {
  const body = document.getElementById(tableBodyId);
  if (!body) {
    debugLog("Missing logs table body", { tableBodyId }, true);
    return;
  }
  if (!logs.length) {
    body.innerHTML = `<tr><td colspan="6">No logs yet.</td></tr>`;
    debugLog("Rendered logs", { tableBodyId, count: 0 });
    return;
  }

  body.innerHTML = logs
    .map((log) => {
      const level = String(log.level || "INFO").toUpperCase();
      const details = log.details && Object.keys(log.details).length ? log.details : null;
      return `
        <tr>
          <td class="time-cell">${escapeHtml(shortTime(log.created_at))}</td>
          <td><span class="level-badge ${level.toLowerCase()}">${escapeHtml(level)}</span></td>
          <td>${escapeHtml(log.event || "general")}</td>
          <td>${escapeHtml(log.message || "")}</td>
          <td>${escapeHtml(log.company_name || "")}</td>
          <td>${detailsBlock(details)}</td>
        </tr>
      `;
    })
    .join("");
  debugLog("Rendered logs", { tableBodyId, count: logs.length });
}

function renderLeads(leads) {
  const body = document.getElementById("leads");
  if (!body) {
    debugLog("Missing leads table body", null, true);
    return;
  }
  if (!leads.length) {
    body.innerHTML = `<tr><td colspan="8">No leads stored yet.</td></tr>`;
    debugLog("Rendered leads", { count: 0 });
    return;
  }

  body.innerHTML = leads
    .map((lead) => {
      const status = String(lead.status || "DISCOVERED");
      const mockLead = isMockLead(lead);
      const mockBadge = mockLead ? `<span class="source-badge mock">MOCK</span>` : "";
      return `
        <tr>
          <td><div class="company-cell">${escapeHtml(lead.company_name || "")}${mockBadge}</div></td>
          <td>${escapeHtml(lead.normalized_domain || lead.website_url || "")}</td>
          <td>${escapeHtml(lead.contact_email || "")}</td>
          <td>${escapeHtml(lead.niche || "")}</td>
          <td>${escapeHtml(String(lead.score ?? ""))}</td>
          <td><span class="status-pill ${status.toLowerCase()}">${escapeHtml(status)}</span></td>
          <td>
            <div>${escapeHtml(lead.reason || lead.duplicate_reason || lead.sheet_duplicate_reason || "")}</div>
            ${lead.recommended_angle ? `<small>${escapeHtml(lead.recommended_angle)}</small>` : ""}
          </td>
          <td>${leadActionButtons(lead)}</td>
        </tr>
      `;
    })
    .join("");
  debugLog("Rendered leads", { count: leads.length });
}

function isMockLead(lead) {
  const source = String(lead.source || "").trim().toLowerCase();
  const sourceMode = String(lead.lead_source_mode || "").trim().toLowerCase();
  const snippet = String(lead.snippet || "").trim().toLowerCase();
  return MOCK_SOURCE_MARKERS.includes(source) || MOCK_SOURCE_MARKERS.includes(sourceMode) || snippet.startsWith("mock result:");
}

function leadActionButtons(lead) {
  const id = Number(lead.id);
  if (!id) return "";
  const status = String(lead.status || "").toUpperCase();
  if (FINAL_LEAD_STATUSES.includes(status)) {
    return `<span class="muted-action">No action</span>`;
  }
  if (!ACTIONABLE_LEAD_STATUSES.includes(status)) {
    return `<span class="muted-action">Not ready</span>`;
  }
  if (isMockLead(lead)) {
    return `
      <div class="lead-actions">
        <button data-lead-action="approve" disabled title="Mock leads cannot be approved for real outreach.">Approve</button>
        <button data-lead-id="${id}" data-lead-action="reject">Reject</button>
      </div>
      <span class="muted-action">Mock only</span>
    `;
  }

  return `
    <div class="lead-actions">
      <button data-lead-id="${id}" data-lead-action="approve">Approve</button>
      <button data-lead-id="${id}" data-lead-action="reject">Reject</button>
    </div>
  `;
}

function detailsBlock(details) {
  if (!details) return "";
  return `
    <details>
      <summary>View</summary>
      <pre>${escapeHtml(JSON.stringify(details, null, 2))}</pre>
    </details>
  `;
}

function shortTime(value) {
  if (!value) return "";
  return String(value).replace("T", " ").replace("+00:00", " UTC");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function refreshAll() {
  debugLog("refreshStatus/data loading started");
  const [status, dashboardLogs, allLogs, leads] = await Promise.all([
    api("/api/status"),
    api(`/api/logs?limit=${DASHBOARD_LOG_LIMIT}`),
    api(`/api/logs?limit=${FULL_LOG_LIMIT}`),
    api("/api/leads"),
  ]);
  debugLog("refreshStatus/data loading completed", {
    dashboardLogs: (dashboardLogs.logs || []).length,
    allLogs: (allLogs.logs || []).length,
    leads: (leads.leads || []).length,
    mode: status.current_mode,
  });
  renderStatus(status);
  renderLogs("dashboardLogs", dashboardLogs.logs || []);
  renderLogs("logs", allLogs.logs || []);
  renderLeads(leads.leads || []);
}

async function postAction(path) {
  if (state.busy) return;
  state.busy = true;
  try {
    await api(path, {
      method: "POST",
      body: JSON.stringify(payloadFromInputs()),
    });
    await refreshAll();
  } catch (error) {
    const errorLog = [
      {
        level: "ERROR",
        event: "browser_request_failed",
        message: `Request failed: ${error.message}`,
        company_name: "",
        created_at: new Date().toISOString(),
        details: {},
      },
    ];
    renderLogs("dashboardLogs", errorLog);
    renderLogs("logs", errorLog);
  } finally {
    state.busy = false;
  }
}

async function handleLeadAction(event) {
  const button = event.target.closest("[data-lead-action]");
  if (!button || state.busy) return;

  const leadId = button.getAttribute("data-lead-id");
  const action = button.getAttribute("data-lead-action");
  state.busy = true;
  try {
    await api(`/api/leads/${leadId}/${action}`, { method: "POST" });
    await refreshAll();
  } catch (error) {
    const errorLog = [
      {
        level: "ERROR",
        event: "lead_action_failed",
        message: `Lead action failed: ${error.message}`,
        company_name: "",
        created_at: new Date().toISOString(),
        details: { lead_id: leadId, action },
      },
    ];
    renderLogs("dashboardLogs", errorLog);
    renderLogs("logs", errorLog);
  } finally {
    state.busy = false;
  }
}

function activateTab(target) {
  debugLog("activateTab called", { target });
  document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
    const isActive = panel.getAttribute("data-tab-panel") === target;
    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
  });
  document.querySelectorAll("[data-tab-target]").forEach((button) => {
    button.classList.toggle("active", button.getAttribute("data-tab-target") === target);
    button.setAttribute("aria-selected", button.getAttribute("data-tab-target") === target ? "true" : "false");
  });
  debugLog("active panels", {
    visible: Array.from(document.querySelectorAll("[data-tab-panel]"))
      .filter((panel) => !panel.hidden)
      .map((panel) => panel.id),
  });
}

function initTabs() {
  debugLog("initTabs running");
  const activeButton = document.querySelector("[data-tab-target].active");
  const defaultTarget = activeButton ? activeButton.getAttribute("data-tab-target") : "tab-dashboard";
  activateTab(defaultTarget);

  document.querySelectorAll("[data-tab-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.getAttribute("data-tab-target");
      if (target) activateTab(target);
    });
  });
}

function initApp() {
  debugLog("initApp running");
  initTabs();
  document.getElementById("startBtn").addEventListener("click", () => postAction("/api/start"));
  document.getElementById("stopBtn").addEventListener("click", () => postAction("/api/stop"));
  document.getElementById("runOnceBtn").addEventListener("click", () => postAction("/api/run-once"));
  document.getElementById("refreshBtn").addEventListener("click", refreshAll);
  document.getElementById("leads").addEventListener("click", handleLeadAction);

  refreshAll().catch((error) => {
    const errorLog = [
      {
        level: "ERROR",
        event: "initial_refresh_failed",
        message: `Initial refresh failed: ${error.message}`,
        company_name: "",
        created_at: new Date().toISOString(),
        details: {},
      },
    ];
    renderLogs("dashboardLogs", errorLog);
    renderLogs("logs", errorLog);
  });
  setInterval(refreshAll, 5000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}
