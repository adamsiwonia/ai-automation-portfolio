# AI Email Support Assistant — Demo Upgrade Spec

## 🎯 Goal

Transform the current demo into a **client-facing sales demo** for small businesses.

The demo should:
- clearly communicate business value
- feel trustworthy and simple
- require zero technical knowledge to understand

---

## 👤 Target Audience

Small business owners (e-commerce, local shops) who:
- receive repetitive customer emails
- want to save time
- are not technical

---

## 💰 Core Value Proposition

- Save 5–15 hours per week on customer emails
- Automatically generate reply drafts in seconds
- Improve response speed

---

## 🧩 Required Features

### 1. Hero Section (Top of Page)
- Headline focused on time savings / automation
- Short supporting text
- Trust note:
  - nothing is sent automatically
  - replies are drafts for review

---

### 2. Sample Scenarios (Buttons)

Add 3 buttons that auto-fill input:
- Order not arrived
- Return request
- Product question

---

### 3. Simplified Output (Demo Mode)

Default visible:
- Suggested reply
- Next step

Hidden (Advanced section):
- request id
- latency
- tokens
- category

---

### 4. Trust & Safety

Must communicate:
- AI does NOT send emails automatically
- user always reviews before sending
- low-confidence responses → manual review

---

### 5. “How It Works” Section

Simple 3-step explanation:
1. Connect your email
2. AI reads incoming messages
3. Draft replies are generated

---

### 6. “Before vs After” Section

Compare:
- manual replies (time-consuming)
- AI-assisted workflow (fast)

---

### 7. “Works With” Section

- Gmail (live)
- Outlook (coming soon)
- SMS (coming soon)
- WhatsApp (future)

---

### 8. CTA (Bottom of Page)

Clear call to action:
- “Book a free setup call”
- or contact form

---

## 🌍 Language Support

The demo should support 2 interface languages:
- English
- Polish

### Requirement
Add a simple language switcher:
- EN / PL

### Behavior
- All visible UI text should change with the selected language
- This includes:
  - headline
  - supporting copy
  - buttons
  - labels
  - trust messaging
  - section titles
  - CTA
  - output labels such as "Suggested reply", "Next step", "Advanced details"

### Important
- UI language and reply language are separate concerns
- UI language is selected by the user
- Reply language must follow the language of the customer's message, regardless of UI language

### Notes
- English can remain the default language
- Keep implementation simple and maintainable
- Prefer a single source of translation strings instead of duplicating the whole page

---

## 🌐 Reply Language Behavior

The language of the generated reply must follow the language of the customer's message.

### Rule
- The AI reply should always be generated in the same language as the incoming message
- This must be independent from the UI language selected on the page

### Examples
- UI in Polish + customer email in English → reply in English
- UI in English + customer email in Polish → reply in Polish
- UI in Polish + customer email in German → reply in German

### Notes
- UI language controls only visible interface text
- Reply language is determined from the input message language
- If language detection is uncertain, prefer the dominant language of the message

---


## ⚙️ Constraints

- Do NOT break existing functionality
- Do NOT change backend unless necessary
- Keep UI clean and simple
- Avoid technical language
- Prioritize clarity and trust
- Do not duplicate the page into separate hardcoded English and Polish versions
- Use a simple maintainable translation structure

---

## 🎨 Design Guidelines

- minimal and clean
- easy to scan in 10 seconds
- mobile-friendly if possible
- no “developer dashboard” feel

---

## 🧠 UX Principles

- user should understand value in <10 seconds
- avoid overwhelming with data
- guide user with clear actions (buttons)

---

## 🚫 What to Avoid

- technical jargon
- too many metrics on screen
- complex layouts
- exposing internal system details by default

