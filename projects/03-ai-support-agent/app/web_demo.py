import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Email Support Assistant - Demo</title>
  <style>
    :root {
      --bg: #f1f5f9;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #334155;
      --border: #e2e8f0;
      --primary: #0f766e;
      --primaryHover: #0d9488;
      --success: #16a34a;
      --successHover: #15803d;
      --danger: #dc2626;
      --shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
      --radius: 14px;
      --heroBg: linear-gradient(140deg, #ecfeff 0%, #f8fafc 60%, #f0fdfa 100%);
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
      margin: 28px auto;
      padding: 0 16px 60px;
    }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 18px;
    }

    .hero {
      background: var(--heroBg);
      margin-bottom: 16px;
    }

    .hero-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }

    h1 {
      margin: 0 0 6px 0;
      font-size: 30px;
      letter-spacing: -0.02em;
      max-width: 760px;
    }

    .sub {
      margin: 0;
      color: var(--muted);
      max-width: 720px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.88);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .hero-tools {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .lang-switch {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.88);
      padding: 5px;
    }

    .lang-label {
      font-size: 12px;
      color: var(--muted);
      padding-left: 8px;
      padding-right: 2px;
      white-space: nowrap;
    }

    .lang-btn {
      border: 1px solid transparent;
      background: transparent;
      color: var(--muted);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      line-height: 1;
      cursor: pointer;
    }

    .lang-btn.active {
      border-color: rgba(15, 118, 110, 0.35);
      background: rgba(15, 118, 110, 0.12);
      color: #0f766e;
      font-weight: 700;
    }

    .trust-list {
      margin-top: 14px;
      display: grid;
      gap: 8px;
    }

    .trust-item {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      border-left: 3px solid rgba(15, 118, 110, 0.35);
      padding-left: 10px;
    }

    .hero-points {
      margin-top: 14px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }

    .hero-point {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.75);
      padding: 10px;
    }

    .hero-point strong {
      display: block;
      font-size: 14px;
      margin-bottom: 4px;
      color: var(--text);
    }

    .hero-point span {
      display: block;
      color: var(--muted);
      font-size: 12px;
    }

    .grid {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 16px;
    }

    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
      .hero-points { grid-template-columns: 1fr; }
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
      border-color: rgba(15, 118, 110, 0.6);
      box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12);
    }

    textarea { min-height: 190px; resize: vertical; }

    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
      align-items: center;
    }

    .scenario-shell {
      border: 1px dashed var(--border);
      border-radius: 10px;
      padding: 10px;
      margin-bottom: 10px;
      background: rgba(15, 23, 42, 0.01);
    }

    .scenario-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }

    .scenario-btn {
      padding: 8px 11px;
      font-size: 13px;
    }

    .scenario-btn.active {
      background: rgba(15, 118, 110, 0.1);
      border-color: rgba(15, 118, 110, 0.35);
      color: #0f766e;
      font-weight: 700;
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

    .small-strong {
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
      margin: 0;
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

    .advanced {
      margin-top: 14px;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
      background: rgba(2, 8, 23, 0.015);
    }

    .advanced summary {
      cursor: pointer;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      list-style: none;
    }

    .advanced summary::-webkit-details-marker { display: none; }

    .advanced summary::after {
      content: " +";
      font-weight: 700;
      color: var(--muted);
    }

    .advanced[open] summary::after {
      content: " -";
    }

    .advanced-body {
      margin-top: 10px;
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

    .section-block {
      margin-top: 16px;
    }

    .section-title {
      margin: 0 0 8px;
      font-size: 20px;
      letter-spacing: -0.01em;
    }

    .placeholder-note {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }

    .steps {
      margin: 10px 0 0;
      padding-left: 20px;
    }

    .compare-grid,
    .works-grid {
      margin-top: 12px;
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .works-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    @media (max-width: 900px) {
      .compare-grid { grid-template-columns: 1fr; }
      .works-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    .mini-card {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: rgba(2,8,23,0.02);
      padding: 12px;
    }

    .mini-card h3 {
      margin: 0 0 8px;
      font-size: 14px;
      color: var(--text);
    }

    .mini-card p {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }

    .work-pill {
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 10px 12px;
      text-align: center;
      font-size: 13px;
      color: var(--muted);
      background: rgba(2,8,23,0.02);
    }

    .cta {
      margin-top: 16px;
      background: linear-gradient(140deg, #f0fdfa 0%, #ecfeff 100%);
    }

    .cta h2 {
      margin: 0;
      font-size: 24px;
      letter-spacing: -0.02em;
    }

    .cta p {
      margin: 8px 0 0;
      color: var(--muted);
    }

    .cta .actions { margin-top: 14px; }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card hero">
      <div class="hero-top">
        <div class="hero-tools">
          <div class="badge" id="liveBadge" title="This is a demo UI for your API" data-i18n="meta.live_badge">
            Live API demo
          </div>
          <div class="lang-switch" role="group" aria-label="Language switcher">
            <span class="lang-label" data-i18n="switcher.label">Language</span>
            <button class="lang-btn" type="button" id="langEn" data-lang="en">EN</button>
            <button class="lang-btn" type="button" id="langPl" data-lang="pl">PL</button>
          </div>
        </div>
      </div>
      <h1 data-i18n="hero.headline">Save 5-15 hours per week on repetitive support emails.</h1>
      <p class="sub" data-i18n="hero.sub">
        Turn incoming customer emails into ready-to-review drafts in seconds.
      </p>
      <div class="trust-list">
        <p class="trust-item" data-i18n="hero.trust_1">Nothing is sent automatically. This demo creates draft responses only.</p>
        <p class="trust-item" data-i18n="hero.trust_2">You always review and approve each draft before it is sent.</p>
        <p class="trust-item" data-i18n="hero.trust_3">Low-confidence cases can be flagged for manual review.</p>
      </div>
      <div class="hero-points">
        <div class="hero-point">
          <strong data-i18n="hero.point_1_title">Save time weekly</strong>
          <span data-i18n="hero.point_1_text">Reduce repetitive support drafting every day.</span>
        </div>
        <div class="hero-point">
          <strong data-i18n="hero.point_2_title">Reply drafts in seconds</strong>
          <span data-i18n="hero.point_2_text">Faster response preparation for common questions.</span>
        </div>
        <div class="hero-point">
          <strong data-i18n="hero.point_3_title">Always in control</strong>
          <span data-i18n="hero.point_3_text">Your team reviews drafts before anything is sent.</span>
        </div>
      </div>
    </section>

    <div class="grid">
      <div class="card">
        <h2 data-i18n="input.title">Input</h2>

        <div class="scenario-shell">
          <p class="small-strong" data-i18n="input.scenario_title">Sample customer scenarios</p>
          <p class="small" data-i18n="input.scenario_help">Click any scenario to auto-fill a realistic customer email.</p>
          <div class="scenario-actions">
            <button class="btn-ghost scenario-btn" type="button" data-scenario="order_not_arrived">Order not arrived</button>
            <button class="btn-ghost scenario-btn" type="button" data-scenario="return_request">Return request</button>
            <button class="btn-ghost scenario-btn" type="button" data-scenario="product_question">Product question</button>
          </div>
        </div>

        <label><b data-i18n="input.email_label">Customer email</b></label>
        <textarea id="email">Hi, I want to return my order. What's the process?</textarea>

        <div class="actions">
          <button class="btn-primary" id="btn" data-i18n="input.generate_btn">Generate reply</button>
          <button class="btn-ghost" id="btnFill" data-i18n="input.sample_btn">Use sample email</button>
          <span class="small" id="status"></span>
        </div>

        <p class="hint" data-i18n="input.tip">
          Tip: For a client-facing demo, show only the suggested reply + next step (no JSON).
        </p>
      </div>

      <div class="card">
        <h2 data-i18n="output.title">Output</h2>
        <p class="small" data-i18n="output.primary_note">Primary demo view: suggested reply and next step.</p>

        <label><b data-i18n="output.reply_label">Suggested reply</b></label>
        <pre id="reply">-</pre>

        <div class="actions">
          <button class="btn-success" id="copyReply" data-i18n="output.copy_reply_btn">Copy reply</button>
        </div>

        <label style="margin-top:14px;"><b data-i18n="output.next_label">Next step</b></label>
        <pre id="next">-</pre>

        <div class="actions">
          <button class="btn-success" id="copyNext" data-i18n="output.copy_next_btn">Copy next step</button>
        </div>

        <details class="advanced" id="advancedDetails">
          <summary data-i18n="output.advanced_label">Advanced details</summary>
          <div class="advanced-body">
            <div class="result-title">
              <div class="pill" id="meta">-</div>
              <div class="pill" id="latency">-</div>
            </div>

            <div class="divider"></div>

            <div class="kpi">
              <div class="box">
                <p class="label" data-i18n="output.category_label">Category</p>
                <p class="value" id="category">-</p>
              </div>
              <div class="box">
                <p class="label" data-i18n="output.tokens_label">Tokens</p>
                <p class="value" id="tokens">-</p>
              </div>
            </div>
          </div>
        </details>

        <p class="hint" data-i18n="output.prod_hint">
          In production, this assistant can be integrated with your support inbox and create reply drafts for review.
        </p>
      </div>
    </div>

    <section class="card section-block" id="howItWorksSection">
      <h2 class="section-title" data-i18n="sections.how_title">How it works</h2>
      <p class="placeholder-note" data-i18n="sections.how_note">Three simple steps from incoming email to draft response.</p>
      <ol class="steps">
        <li data-i18n="sections.how_step_1">Connect your support inbox.</li>
        <li data-i18n="sections.how_step_2">AI reads incoming customer messages and prepares a response draft.</li>
        <li data-i18n="sections.how_step_3">Your team reviews, edits if needed, and sends with confidence.</li>
      </ol>
    </section>

    <section class="card section-block" id="beforeAfterSection">
      <h2 class="section-title" data-i18n="sections.before_after_title">Before vs After</h2>
      <p class="placeholder-note" data-i18n="sections.before_after_note">See the shift from manual drafting to assisted workflows.</p>
      <div class="compare-grid">
        <div class="mini-card">
          <h3 data-i18n="sections.before_title">Before: Manual replies</h3>
          <p data-i18n="sections.before_text">Inbox triage, repetitive writing, and inconsistent response speed during busy hours.</p>
        </div>
        <div class="mini-card">
          <h3 data-i18n="sections.after_title">After: AI-assisted drafts</h3>
          <p data-i18n="sections.after_text">Fast first drafts, less repetitive work, and more time for high-value customer issues.</p>
        </div>
      </div>
    </section>

    <section class="card section-block" id="worksWithSection">
      <h2 class="section-title" data-i18n="sections.works_title">Works with</h2>
      <p class="placeholder-note" data-i18n="sections.works_note">Start with Gmail now and expand channels over time.</p>
      <div class="works-grid">
        <div class="work-pill" data-i18n="sections.works_gmail">Gmail (live)</div>
        <div class="work-pill" data-i18n="sections.works_outlook">Outlook (coming soon)</div>
        <div class="work-pill" data-i18n="sections.works_sms">SMS (coming soon)</div>
        <div class="work-pill" data-i18n="sections.works_whatsapp">WhatsApp (future)</div>
      </div>
    </section>

    <section class="card cta" id="ctaSection">
      <h2 data-i18n="sections.cta_title">Get a quick demo for your business</h2>
      <p data-i18n="sections.cta_text">See how this could work with your own inbox and customer emails.</p>
      <div class="actions">
       <a
        class="btn-primary"
        id="ctaButton"
        href="mailto:adam.pawel.siwonia@gmail.com?subject=AI%20Email%20Support%20Demo"
        data-i18n="sections.cta_button"
      >
        Get a quick demo
      </a>
      </div>
    </section>
  </div>

<script>
  const btn = document.getElementById("btn");
  const btnFill = document.getElementById("btnFill");
  const ctaButton = document.getElementById("ctaButton");
  const langEnBtn = document.getElementById("langEn");
  const langPlBtn = document.getElementById("langPl");
  const liveBadge = document.getElementById("liveBadge");
  const emailEl = document.getElementById("email");
  const scenarioButtons = document.querySelectorAll(".scenario-btn");

  const statusEl = document.getElementById("status");
  const replyEl = document.getElementById("reply");
  const nextEl = document.getElementById("next");
  const categoryEl = document.getElementById("category");
  const metaEl = document.getElementById("meta");
  const latencyEl = document.getElementById("latency");
  const tokensEl = document.getElementById("tokens");

  const copyReplyBtn = document.getElementById("copyReply");
  const copyNextBtn = document.getElementById("copyNext");

  const LANGUAGE_STORAGE_KEY = "demo_ui_language";
  const DEFAULT_LANGUAGE = "en";

  const I18N = {
    en: {
      meta: {
        page_title: "AI Email Support Assistant - Demo",
        live_badge: "Live API demo",
        live_badge_title: "This is a demo UI for your API",
      },
      switcher: {
        label: "Language",
      },
      hero: {
        headline: "Reduce time spent on repetitive support emails.",
        sub: "Turn incoming customer emails into ready-to-review drafts in seconds.",
        trust_1: "Nothing is sent automatically. This demo creates draft responses only.",
        trust_2: "You always review and approve each draft before it is sent.",
        trust_3: "Low-confidence cases can be flagged for manual review.",
        point_1_title: "Save time weekly",
        point_1_text: "Reduce repetitive support drafting every day.",
        point_2_title: "Reply drafts in seconds",
        point_2_text: "Faster response preparation for common questions.",
        point_3_title: "Always in control",
        point_3_text: "Your team reviews drafts before anything is sent.",
      },
      input: {
        title: "Input",
        scenario_title: "Sample customer scenarios",
        scenario_help: "Click any scenario to auto-fill a realistic customer email.",
        scenario_labels: {
          order_not_arrived: "Order not arrived",
          return_request: "Return request",
          product_question: "Product question",
        },
        email_label: "Customer email",
        generate_btn: "Generate reply",
        sample_btn: "Use sample email",
        tip: "Tip: For a client-facing demo, show only the suggested reply + next step (no JSON).",
        default_email: "Hi, I want to return my order. What's the process?",
      },
      output: {
        title: "Output",
        primary_note: "Primary demo view: suggested reply and next step.",
        reply_label: "Suggested reply",
        copy_reply_btn: "Copy reply",
        next_label: "Next step",
        copy_next_btn: "Copy next step",
        advanced_label: "Advanced details",
        category_label: "Category",
        tokens_label: "Tokens",
        prod_hint: "In production, this assistant can be integrated with your support inbox and create reply drafts for review.",
      },
      sections: {
        how_title: "How it works",
        how_note: "Three simple steps from incoming email to draft response.",
        how_step_1: "Connect your support inbox.",
        how_step_2: "AI reads incoming customer messages and prepares a response draft.",
        how_step_3: "Your team reviews, edits if needed, and sends with confidence.",
        before_after_title: "Before vs After",
        before_after_note: "See the shift from manual drafting to assisted workflows.",
        before_title: "Before: Manual replies",
        before_text: "Inbox triage, repetitive writing, and inconsistent response speed during busy hours.",
        after_title: "After: AI-assisted drafts",
        after_text: "Fast first drafts, less repetitive work, and more time for high-value customer issues.",
        works_title: "Works with",
        works_note: "Start with Gmail now and expand channels over time.",
        works_gmail: "Gmail (live)",
        works_outlook: "Outlook (coming soon)",
        works_sms: "SMS (coming soon)",
        works_whatsapp: "WhatsApp (future)",
        cta_title: "Get a quick demo for your business",
        cta_text: "See how this could work with your own inbox and customer emails.",
        cta_button: "Get a quick demo",
      },
      status: {
        sample_inserted: "Sample inserted",
        copied: "Copied",
        copy_failed: "Copy failed",
        cta_clicked: "Opening email draft...",
        generating: "Generating...",
        loading: "Loading...",
        done: "Done",
        request_label: "Request",
        latency_label: "Latency",
      },
      samples: {
        order_not_arrived:
`Hello,
I placed order #A-10452 on March 12 and paid for 2-day shipping.
Tracking has not updated since March 14 and the package still has not arrived.
Could you please check where it is and when I can expect delivery?
Thank you,
Maya`,
        return_request:
`Hi,
I received order #A-10917 today, but the shoes are too small.
They are unworn and I still have the original box.
Can you send me the return steps and confirm if a return label is included?
Best,
Daniel`,
        product_question:
`Hello,
I am interested in the TrailLite backpack.
Can you confirm whether it fits a 15-inch laptop and if the fabric is waterproof in heavy rain?
If possible, please also share the warranty length.
Thanks,
Eva`,
      },
    },
    pl: {
      meta: {
        page_title: "Asystent Obsługi E-maili AI - Demo",
        live_badge: "Demo API na żywo",
        live_badge_title: "To jest demonstracyjny interfejs API",
      },
      switcher: {
        label: "Język",
      },
      hero: {
        headline: "Oszczędzaj czas poświęcany na powtarzalnych   e-mailach obsługowych.",
        sub: "Zamieniaj przychodzące wiadomości klientów w szkice odpowiedzi gotowe do weryfikacji w kilka sekund.",
        trust_1: "Nic nie jest wysyłane automatycznie. To demo tworzy tylko szkice odpowiedzi.",
        trust_2: "Każda odpowiedź jest sprawdzana i zatwierdzana przez Twój zespół przed wysyłką.",
        trust_3: "Przypadki o niskiej pewności mogą być kierowane do ręcznego przeglądu.",
        point_1_title: "Oszczędzaj czas co tydzień",
        point_1_text: "Mniej czasu na powtarzalne pisanie odpowiedzi obsługowych.",
        point_2_title: "Szkice odpowiedzi w sekundy",
        point_2_text: "Szybsze przygotowanie odpowiedzi na najczęstsze pytania.",
        point_3_title: "Pełna kontrola",
        point_3_text: "Twój zespół weryfikuje szkice przed wysłaniem.",
      },
      input: {
        title: "Wejście",
        scenario_title: "Przykładowe scenariusze klienta",
        scenario_help: "Kliknij scenariusz, aby automatycznie uzupełnić realistyczny e-mail klienta.",
        scenario_labels: {
          order_not_arrived: "Zamówienie nie dotarło",
          return_request: "Prośba o zwrot",
          product_question: "Pytanie o produkt",
        },
        email_label: "E-mail klienta",
        generate_btn: "Generuj odpowiedź",
        sample_btn: "Użyj przykładu",
        tip: "W wersji demo pokazujemy głównie sugerowaną odpowiedź i kolejny krok (bez JSON).",
        default_email: "Dzień dobry, chcę zwrócić zamówienie. Jaka jest procedura?",
      },
      output: {
        title: "Wynik",
        primary_note: "Widok demo: sugerowana odpowiedź i kolejny krok.",
        reply_label: "Sugerowana odpowiedź",
        copy_reply_btn: "Kopiuj odpowiedź",
        next_label: "Kolejny krok",
        copy_next_btn: "Kopiuj kolejny krok",
        advanced_label: "Szczegóły zaawansowane",
        category_label: "Kategoria",
        tokens_label: "Tokeny",
        prod_hint: "W produkcji asystent może być połączony ze skrzynką wsparcia i tworzyć szkice odpowiedzi do weryfikacji.",
      },
      sections: {
        how_title: "Jak to działa",
        how_note: "Trzy proste kroki od e-maila klienta do szkicu odpowiedzi.",
        how_step_1: "Połącz swoją skrzynkę wsparcia.",
        how_step_2: "AI czyta przychodzące wiadomości klientów i przygotowuje szkic odpowiedzi.",
        how_step_3: "Twój zespół sprawdza, edytuje w razie potrzeby i wysyła.",
        before_after_title: "Przed vs Po",
        before_after_note: "Zobacz różnice między ręcznym pisaniem a wsparciem AI.",
        before_title: "Przed: Odpowiedzi ręczne",
        before_text: "Segregowanie skrzynki, powtarzalne pisanie i nierówne tempo odpowiedzi w godzinach szczytu.",
        after_title: "Po: Szkice wspierane przez AI",
        after_text: "Szybkie pierwsze wersje, mniej powtórzeń i więcej czasu na trudniejsze sprawy klientów.",
        works_title: "Współpracuje z",
        works_note: "Zacznij od Gmail już teraz i rozszerzaj kanały w kolejnym kroku.",
        works_gmail: "Gmail (działa)",
        works_outlook: "Outlook (wkrótce)",
        works_sms: "SMS (wkrótce)",
        works_whatsapp: "WhatsApp (przyszłość)",
        cta_title: "Zobacz szybkie demo dla swojej firmy",
        cta_text: "Sprawdź, jak to mogłoby działać z Twoją skrzynką i wiadomościami od klientów.",
        cta_button: "Zobacz szybkie demo",
      },
      status: {
        sample_inserted: "Wstawiono przykład",
        copied: "Skopiowano",
        copy_failed: "Kopiowanie nieudane",
        cta_clicked: "Otwieranie szkicu wiadomości...",
        generating: "Generowanie...",
        loading: "Ładowanie...",
        done: "Gotowe",
        request_label: "Żądanie",
        latency_label: "Opóźnienie",
      },
      samples: {
        order_not_arrived:
`Dzień dobry,
Złożyłem zamówienie #PL-10452 w dniu 12 marca i wybrałem dostawę ekspresową.
Status przesyłki nie zmienił się od 14 marca, a paczka nadal nie dotarła.
Czy mogą Państwo sprawdzić, gdzie jest zamówienie i kiedy mogę się go spodziewać?
Dziękuję,
Marek`,
        return_request:
`Cześć,
Odebrałem zamówienie #PL-10917, ale buty są za małe.
Produkt nie był używany i mam oryginalne opakowanie.
Proszę o instrukcję zwrotu i informację, czy etykieta jest po Państwa stronie.
Pozdrawiam,
Anna`,
        product_question:
`Dzień dobry,
Czy plecak TrailLite mieści laptop 15 cali i czy materiał jest wodoodporny podczas mocnego deszczu?
Proszę też o informację, ile trwa gwarancja.
Dziękuję,
Kasia`,
      },
    },
  };

  function getStoredLanguage() {
    try {
      const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
      if (stored === "en" || stored === "pl") {
        return stored;
      }
    } catch (e) {}
    return DEFAULT_LANGUAGE;
  }

  function resolveKey(obj, key) {
    return key.split(".").reduce((acc, part) => {
      if (acc && Object.prototype.hasOwnProperty.call(acc, part)) {
        return acc[part];
      }
      return undefined;
    }, obj);
  }

  let activeUILanguage = getStoredLanguage();
  let activeScenarioKey = null;

  function translate(key, langOverride) {
    const lang = langOverride || activeUILanguage;
    const fromSelected = resolveKey(I18N[lang], key);
    if (typeof fromSelected === "string") {
      return fromSelected;
    }
    const fromDefault = resolveKey(I18N[DEFAULT_LANGUAGE], key);
    if (typeof fromDefault === "string") {
      return fromDefault;
    }
    return "";
  }

  function setStatus(msg) {
    statusEl.textContent = msg || "";
  }

  function getScenarioText(scenarioKey, langOverride) {
    const lang = langOverride || activeUILanguage;
    const selected = I18N[lang]?.samples?.[scenarioKey];
    if (selected) {
      return selected;
    }
    return I18N[DEFAULT_LANGUAGE].samples.order_not_arrived;
  }

  function getScenarioLabel(scenarioKey, langOverride) {
    const lang = langOverride || activeUILanguage;
    const selected = I18N[lang]?.input?.scenario_labels?.[scenarioKey];
    if (selected) {
      return selected;
    }
    return I18N[DEFAULT_LANGUAGE].input.scenario_labels.order_not_arrived;
  }

  function setActiveScenarioButton(scenarioKey) {
    scenarioButtons.forEach((button) => {
      const isActive = button.getAttribute("data-scenario") === scenarioKey;
      button.classList.toggle("active", isActive);
    });
  }

  function applyTranslations(previousLanguage) {
    document.documentElement.lang = activeUILanguage;
    document.title = translate("meta.page_title");
    liveBadge.title = translate("meta.live_badge_title");

    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const key = element.getAttribute("data-i18n");
      const value = translate(key);
      if (value) {
        element.textContent = value;
      }
    });

    scenarioButtons.forEach((button) => {
      const scenarioKey = button.getAttribute("data-scenario");
      button.textContent = getScenarioLabel(scenarioKey);
    });

    langEnBtn.classList.toggle("active", activeUILanguage === "en");
    langPlBtn.classList.toggle("active", activeUILanguage === "pl");

    const previousDefault = previousLanguage ? translate("input.default_email", previousLanguage) : "";
    const englishDefault = translate("input.default_email", "en");
    const shouldReplaceDefault = (
      !emailEl.value.trim()
      || (previousLanguage && emailEl.value === previousDefault)
      || (!previousLanguage && emailEl.value === englishDefault)
    );

    if (activeScenarioKey) {
      emailEl.value = getScenarioText(activeScenarioKey);
    } else if (shouldReplaceDefault) {
      emailEl.value = translate("input.default_email");
    }
  }

  function setLanguage(nextLanguage) {
    if (!I18N[nextLanguage] || nextLanguage === activeUILanguage) {
      return;
    }

    const previousLanguage = activeUILanguage;
    activeUILanguage = nextLanguage;

    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
    } catch (e) {}

    applyTranslations(previousLanguage);
  }

  function applyScenario(scenarioKey) {
    activeScenarioKey = scenarioKey;
    emailEl.value = getScenarioText(scenarioKey);
    setActiveScenarioButton(scenarioKey);
    setStatus(`${translate("status.sample_inserted")}: ${getScenarioLabel(scenarioKey)}`);
    setTimeout(() => setStatus(""), 1200);
  }

  function setError(msg) {
    replyEl.innerHTML = `<span class="error">${msg}</span>`;
    nextEl.textContent = "-";
    categoryEl.textContent = "-";
    metaEl.textContent = "-";
    latencyEl.textContent = "-";
    tokensEl.textContent = "-";
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      setStatus(translate("status.copied"));
      setTimeout(() => setStatus(""), 1200);
    } catch (e) {
      setStatus(translate("status.copy_failed"));
      setTimeout(() => setStatus(""), 1200);
    }
  }

  copyReplyBtn.addEventListener("click", () => copyText(replyEl.textContent));
  copyNextBtn.addEventListener("click", () => copyText(nextEl.textContent));
  langEnBtn.addEventListener("click", () => setLanguage("en"));
  langPlBtn.addEventListener("click", () => setLanguage("pl"));

  scenarioButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const scenarioKey = button.getAttribute("data-scenario");
      applyScenario(scenarioKey);
    });
  });

  btnFill.addEventListener("click", () => {
    applyScenario("order_not_arrived");
  });

  ctaButton.addEventListener("click", () => {
    setStatus(translate("status.cta_clicked"));
    setTimeout(() => setStatus(""), 1200);
  });

  emailEl.addEventListener("input", () => {
    if (activeScenarioKey && emailEl.value !== getScenarioText(activeScenarioKey)) {
      activeScenarioKey = null;
      setActiveScenarioButton(null);
    }
  });

  btn.addEventListener("click", async () => {
    const key = "__CLIENT_API_KEY__";
    const email = emailEl.value;

    setStatus(translate("status.generating"));
    replyEl.textContent = translate("status.loading");
    nextEl.textContent = translate("status.loading");
    metaEl.textContent = "-";
    latencyEl.textContent = "-";
    categoryEl.textContent = "-";
    tokensEl.textContent = "-";

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
        const detail = data?.detail
          ? JSON.stringify(data.detail)
          : (data ? JSON.stringify(data, null, 2) : "Request failed");
        setError(`HTTP ${res.status}: ${detail}`);
        setStatus("");
        return;
      }

      const category = data?.result?.category ?? "-";
      const reply = data?.result?.reply ?? "-";
      const next = data?.result?.next_step ?? "-";
      const requestId = data?.request_id ?? "-";
      const latency = data?.latency_ms ?? null;

      const usage = data?.usage ?? {};
      const totalTokens = usage?.total_tokens ?? "-";

      categoryEl.textContent = category;
      replyEl.textContent = reply;
      nextEl.textContent = next;

      metaEl.textContent = `${translate("status.request_label")}: ${requestId}`;
      latencyEl.textContent = latency !== null ? `${translate("status.latency_label")}: ${latency} ms` : `${translate("status.latency_label")}: -`;
      tokensEl.textContent = totalTokens !== undefined ? String(totalTokens) : "-";

      setStatus(translate("status.done"));
      setTimeout(() => setStatus(""), 1500);

    } catch (e) {
      setError(String(e));
      setStatus("");
    }
  });

  applyTranslations();
</script>
</body>
</html>
"""


@router.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_page():
    client_key = os.getenv("DEMO_API_KEY") or os.getenv("API_KEY") or ""
    return HTMLResponse(HTML.replace("__CLIENT_API_KEY__", client_key))
