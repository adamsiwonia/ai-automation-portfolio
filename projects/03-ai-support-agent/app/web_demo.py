from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>AI Support Agent — Demo</title>
  <style>
    body { font-family: system-ui, Arial; max-width: 900px; margin: 40px auto; padding: 0 16px; }
    textarea, input { width: 100%; padding: 10px; box-sizing: border-box; }
    textarea { height: 180px; }
    button { padding: 10px 14px; margin-top: 10px; cursor: pointer; }
    pre { background: #f6f6f6; padding: 12px; overflow: auto; white-space: pre-wrap; }
    .row { margin-top: 12px; }
  </style>
</head>
<body>
  <h1>AI Support Agent — Web Demo</h1>
  <p>Paste an email, add your API key, click Send.</p>

  <div class="row">
    <label><b>API key</b> (X-API-Key)</label>
    <input id="key" placeholder="sk_..." />
  </div>

  <div class="row">
    <label><b>Email text</b></label>
    <textarea id="email">Hi, I want to return my order. What’s the process?</textarea>
  </div>

  <button id="btn">Send</button>

  <div class="row">
    <h3>Response</h3>
    <pre id="out">—</pre>
  </div>

<script>
  const btn = document.getElementById("btn");
  btn.addEventListener("click", async () => {
    const key = document.getElementById("key").value.trim();
    const email = document.getElementById("email").value;

    document.getElementById("out").textContent = "Loading...";

    try {
      const res = await fetch("/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(key ? {"X-API-Key": key} : {})
        },
        body: JSON.stringify({
          email,
          source: "web-demo"
        })
      });

      const text = await res.text();
      document.getElementById("out").textContent = `HTTP ${res.status}\\n\\n${text}`;
    } catch (e) {
      document.getElementById("out").textContent = String(e);
    }
  });
</script>
</body>
</html>
"""

@router.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_page():
    return HTMLResponse(HTML)