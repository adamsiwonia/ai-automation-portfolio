from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Email Support Assistant — Demo</title>
  <style>
    :root {
      --bg: #f6f7fb;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #475569;
      --border: #e2e8f0;
      --primary: #2563eb;
      --primaryHover: #1d4ed8;
      --success: #16a34a;
      --successHover: #15803d;
      --danger: #dc2626;
      --shadow: 0 10px 30px rgba(2, 8, 23, 0.08);
      --radius: 14px;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      line-height: 1.45;
    }

    .wrap {
      max-width: 980px;
      margin: 40px auto;
      padding: 0 16px 60px;
    }

    .header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }

    h1 {
      margin: 0 0 6px 0;
      font-size: 28px;
      letter-spacing: -0.02em;
    }

    .sub {
      margin: 0;
      color: var(--muted);
      max-width: 720px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.7);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .grid {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 16px;
      margin-top: 14px;
    }

    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
    }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 18px;
    }

    .card h2 {
      font-size: 14px;
      margin: 0 0 10px 0;
      color: var(--muted);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    label {
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin: 10px 0 6px;
    }

    textarea, input {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      font-size: 14px;
      outline: none;
      background: #fff;
    }

    textarea:focus, input:focus {
      border-color: rgba(37, 99, 235, 0.6);
      box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
    }

    textarea { min-height: 190px; resize: vertical; }

    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
      align-items: center;
    }

    button {
      border: none;
      border-radius: 10px;
      padding: 11px 14px;
      font-size: 14px;
      cursor: pointer;
      transition: 120ms ease;
    }

    .btn-primary { background: var(--primary); color: white; }
    .btn-primary:hover { background: var(--primaryHover); }

    .btn-success { background: var(--success); color: white; }
    .btn-success:hover { background: var(--successHover); }

    .btn-ghost {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--muted);
    }
    .btn-ghost:hover { background: rgba(2,8,23,0.03); }

    .small {
      font-size: 12px;
      color: var(--muted);
    }

    .divider { height: 1px; background: var(--border); margin: 14px 0; }

    .result-title {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-top: 6px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 12px;
      background: rgba(2,8,23,0.02);
    }

    pre {
      margin: 10px 0 0;
      background: #f3f4f6;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      white-space: pre-wrap;
      word-break: break-word;
      min-height: 140px;
    }

    .error {
      color: var(--danger);
      font-weight: 600;
    }

    .hint {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 12px;
    }

    .kpi {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 10px;
    }

    .kpi .box {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
      background: rgba(2,8,23,0.02);
    }

    .kpi .label { font-size: 12px; color: var(--muted); margin: 0 0 6px; }
    .kpi .value { font-size: 14px; font-weight: 700; margin: 0; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <div>
        <h1>AI Email Support Assistant — Demo</h1>
        <p class="sub">
          Paste a customer email and generate a ready-to-review reply draft in seconds.
          Draft mode by default (nothing is sent automatically).
        </p>
      </div>
      <div class="badge" title="This is a demo UI for your API">
        ✅ Live API demo
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Input</h2>

        <label><b>API key</b> (X-API-Key)</label>
        <input id="key" placeholder="demo_... or your key" />

        <label><b>Customer email</b></label>
        <textarea id="email">Hi, I want to return my order. What’s the process?</textarea>

        <div class="actions">
          <button class="btn-primary" id="btn">Generate reply</button>
          <button class="btn-ghost" id="btnFill">Use sample email</button>
          <span class="small" id="status"></span>
        </div>

        <p class="hint">
          Tip: For a client-facing demo, show only the suggested reply + next step (no JSON).
        </p>
      </div>

      <div class="card">
        <h2>Output</h2>

        <div class="result-title">
          <div class="pill" id="meta">—</div>
          <div class="pill" id="latency">—</div>
        </div>

        <div class="divider"></div>

        <label><b>Suggested reply</b></label>
        <pre id="reply">—</pre>

        <div class="actions">
          <button class="btn-success" id="copyReply">Copy reply</button>
        </div>

        <label style="margin-top:14px;"><b>Next step</b></label>
        <pre id="next">—</pre>

        <div class="actions">
          <button class="btn-success" id="copyNext">Copy next step</button>
        </div>

        <div class="kpi">
          <div class="box">
            <p class="label">Category</p>
            <p class="value" id="category">—</p>
          </div>
          <div class="box">
            <p class="label">Tokens</p>
            <p class="value" id="tokens">—</p>
          </div>
        </div>

        <p class="hint">
          In production, this assistant can be integrated with your support inbox and create reply drafts for review.
        </p>
      </div>
    </div>
  </div>

<script>
  const btn = document.getElementById("btn");
  const btnFill = document.getElementById("btnFill");

  const statusEl = document.getElementById("status");
  const replyEl = document.getElementById("reply");
  const nextEl = document.getElementById("next");
  const categoryEl = document.getElementById("category");
  const metaEl = document.getElementById("meta");
  const latencyEl = document.getElementById("latency");
  const tokensEl = document.getElementById("tokens");

  const copyReplyBtn = document.getElementById("copyReply");
  const copyNextBtn = document.getElementById("copyNext");

  function setStatus(msg) {
    statusEl.textContent = msg || "";
  }

  function setError(msg) {
    replyEl.innerHTML = `<span class="error">${msg}</span>`;
    nextEl.textContent = "—";
    categoryEl.textContent = "—";
    metaEl.textContent = "—";
    latencyEl.textContent = "—";
    tokensEl.textContent = "—";
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      setStatus("Copied ✅");
      setTimeout(() => setStatus(""), 1200);
    } catch (e) {
      setStatus("Copy failed");
      setTimeout(() => setStatus(""), 1200);
    }
  }

  copyReplyBtn.addEventListener("click", () => copyText(replyEl.textContent));
  copyNextBtn.addEventListener("click", () => copyText(nextEl.textContent));

  btnFill.addEventListener("click", () => {
    document.getElementById("email").value =
`Hello,
I ordered a jacket last week but it hasn't arrived yet.
Can you help?
Thanks`;
    setStatus("Sample inserted");
    setTimeout(() => setStatus(""), 1200);
  });

  btn.addEventListener("click", async () => {
    const key = document.getElementById("key").value.trim();
    const email = document.getElementById("email").value;

    setStatus("Generating...");
    replyEl.textContent = "Loading...";
    nextEl.textContent = "Loading...";
    metaEl.textContent = "—";
    latencyEl.textContent = "—";
    categoryEl.textContent = "—";
    tokensEl.textContent = "—";

    try {
      const res = await fetch("/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(key ? {"X-API-Key": key} : {})
        },
        body: JSON.stringify({ email, source: "web-demo" })
      });

      let data = null;
      try { data = await res.json(); } catch (e) {}

      if (!res.ok) {
        const detail = data?.detail ? JSON.stringify(data.detail) : (data ? JSON.stringify(data, null, 2) : "Request failed");
        setError(`HTTP ${res.status}: ${detail}`);
        setStatus("");
        return;
      }

      const category = data?.result?.category ?? "—";
      const reply = data?.result?.reply ?? "—";
      const next = data?.result?.next_step ?? "—";
      const requestId = data?.request_id ?? "—";
      const latency = data?.latency_ms ?? null;

      const usage = data?.usage ?? {};
      const totalTokens = usage?.total_tokens ?? "—";

      categoryEl.textContent = category;
      replyEl.textContent = reply;
      nextEl.textContent = next;

      metaEl.textContent = `Request: ${requestId}`;
      latencyEl.textContent = latency !== null ? `Latency: ${latency} ms` : "Latency: —";
      tokensEl.textContent = totalTokens !== undefined ? String(totalTokens) : "—";

      setStatus("Done ✅");
      setTimeout(() => setStatus(""), 1500);

    } catch (e) {
      setError(String(e));
      setStatus("");
    }
  });
</script>
</body>
</html>
"""

@router.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_page():
    return HTMLResponse(HTML)