"""Marketing copy shared across pages (home overview + services detail).

A service `id` that matches an option id in leads.SERVICE_OPTIONS lets its
"Discuss this" link preselect that service on the contact form.
"""

SERVICES = [
    {
        "id": "workflow_automation",
        "icon": "workflow",
        "name": "Workflow Automation",
        "summary": "Connect the tools you already pay for and stop moving data between them by hand.",
        "description": (
            "We map how work actually moves through your business, then build reliable automations "
            "between your CRM, inbox, spreadsheets, accounting and project tools. Every automation "
            "includes error handling and alerts, so nothing fails silently."
        ),
        "examples": [
            "New deal in the CRM creates the project, the invoice draft and the kickoff email",
            "Orders sync between Shopify, your warehouse sheet and accounting",
            "Mobile money payments (MTN MoMo, Airtel Money) matched to invoices and recorded automatically",
            "Client onboarding: contract signed, then folders, access and welcome sequence set up",
        ],
        "tools": "Make, n8n, Zapier, mobile money APIs, native APIs and webhooks",
        "timeline": "1–3 weeks per workflow",
    },
    {
        "id": "ai_agents",
        "icon": "agent",
        "name": "AI Agents & Chatbots",
        "summary": "Assistants that answer customers, triage requests and draft replies, trained on your own content.",
        "description": (
            "We build AI assistants that work from your knowledge base, policies and past "
            "conversations, and hand over to a person when they should. We define guardrails and "
            "escalation rules first, then test against real questions before launch."
        ),
        "examples": [
            "Website and WhatsApp assistant that qualifies enquiries and books calls",
            "Support inbox triage: categorise, prioritise and draft replies for review",
            "Internal assistant that answers staff questions from your SOPs and docs",
        ],
        "tools": "OpenAI, Anthropic Claude, vector search, your helpdesk and chat channels",
        "timeline": "2–5 weeks",
    },
    {
        "id": "lead_crm",
        "icon": "funnel",
        "name": "Lead Generation & CRM Automation",
        "summary": "Capture, score and route every lead in seconds, so your sales team only talks to good fits.",
        "description": (
            "Speed to lead wins deals. We automate the path from form fill or ad click to a scored, "
            "enriched CRM record with the right follow-up already running. It's the same kind of "
            "pipeline that handles enquiries from this website."
        ),
        "examples": [
            "Lead scoring on budget, timeline and service fit, with instant alerts for hot leads",
            "Automatic enrichment and deduplication before leads reach your CRM",
            "Personalised follow-up sequences triggered by lead score and behaviour",
        ],
        "tools": "HubSpot, Pipedrive, GoHighLevel, Google Sheets, Make, Tally and Typeform",
        "timeline": "1–3 weeks",
    },
    {
        "id": "document_ai",
        "icon": "document",
        "name": "AI Document Processing",
        "summary": "Pull structured data out of invoices, contracts, forms and emails, with no manual re-typing.",
        "description": (
            "We combine OCR and language models to read the documents your team processes every "
            "day, pull out the fields you need, validate them, and push them into your systems. "
            "Anything with low confidence is flagged for human review."
        ),
        "examples": [
            "Supplier invoices read, coded and queued for approval in your accounting tool",
            "Contracts summarised with key dates and obligations logged to a tracker",
            "Application or intake forms checked for completeness and routed automatically",
        ],
        "tools": "LLM extraction, OCR, Google Drive, SharePoint, Xero and QuickBooks",
        "timeline": "2–4 weeks",
    },
    {
        "id": "reporting",
        "icon": "chart",
        "name": "Reporting & Data Pipelines",
        "summary": "Numbers you trust, delivered automatically, without Monday-morning spreadsheet assembly.",
        "description": (
            "We consolidate data from your ad platforms, CRM, finance and operations tools into one "
            "place and build the reports your team actually reads. AI-written summaries point out "
            "what changed and why it matters."
        ),
        "examples": [
            "Weekly KPI digest in Slack or email with an AI-written commentary",
            "Marketing spend vs. pipeline dashboard across every channel",
            "Automated client reporting for agencies and service businesses",
        ],
        "tools": "Google Sheets, BigQuery, Looker Studio, Airtable and APIs",
        "timeline": "1–3 weeks",
    },
    {
        "id": "care_plan",
        "icon": "support",
        "name": "Care Plans & Ongoing Support",
        "summary": "Monitoring, fixes and continuous improvement for the automations you rely on.",
        "description": (
            "APIs change and businesses grow, so automations need looking after. Our monthly care "
            "plans cover monitoring, fixes, small improvements and a standing block of build hours, "
            "so your systems keep up as you scale."
        ),
        "examples": [
            "Proactive monitoring with alerts when a scenario errors or slows down",
            "Monthly review of run history, costs and new opportunities",
            "Priority fixes and a standing block of hours for new automations",
        ],
        "tools": "Works with anything we've built, and with automations built by others",
        "timeline": "Monthly, cancel anytime",
    },
]

PROCESS = [
    {
        "name": "Discovery call",
        "duration": "30 minutes",
        "body": "We learn how your team works today, where time is lost, and what a win looks like. You leave with an honest view of what's worth automating, even if you don't hire us.",
    },
    {
        "name": "Automation blueprint",
        "duration": "3–5 days",
        "body": "A written plan: the workflows, the tools, the edge cases, the expected time saved, and a fixed-price quote. No open-ended hourly billing.",
    },
    {
        "name": "Build & test",
        "duration": "1–5 weeks",
        "body": "We build in your accounts, not ours, and share progress every week. Everything is tested against real data and failure cases before it goes live.",
    },
    {
        "name": "Launch & handover",
        "duration": "1 week",
        "body": "We go live alongside your team, and you get documentation and a recorded walkthrough of every automation. You own all of it.",
    },
    {
        "name": "Support & improve",
        "duration": "Ongoing",
        "body": "Every project includes 30 days of post-launch support. After that, an optional care plan keeps things running and improving.",
    },
]

FAQS = [
    {
        "q": "Do you work with local clients as well as international ones?",
        "a": "Yes. For businesses in Kampala and across East Africa we can meet in person and we're in your time zone. We also build for local tools and channels, such as WhatsApp Business and mobile money. International clients work with us remotely, and get the same process, pricing structure and standards.",
    },
    {
        "q": "How do you work with clients in a different time zone?",
        "a": "We're based in Kampala (EAT, UTC+3). That gives us a full-day overlap with the UK and Europe, morning overlap with the US East Coast, and afternoon overlap with Australia. Day-to-day we communicate async through Slack or email plus a weekly video update, and we schedule live calls at times that suit you.",
    },
    {
        "q": "Who owns the automations and accounts?",
        "a": "You do. We build inside your own Make, n8n, CRM and AI provider accounts, and when the project ends you keep everything, including documentation and walkthrough videos.",
    },
    {
        "q": "How is pricing structured?",
        "a": "Build projects are fixed-price, based on the scope in your automation blueprint, so you know the full cost before we start. Ongoing support is a flat monthly care plan.",
    },
    {
        "q": "How do you handle our data and access?",
        "a": "We ask for the minimum access each workflow needs, use your own accounts rather than shared credentials, and are happy to sign an NDA or DPA. When the project is done, you can revoke our access in one step.",
    },
    {
        "q": "What if an automation breaks after launch?",
        "a": "Every automation we build alerts someone when it fails. Fixes are covered for 30 days after launch, and care plan clients get priority fixes as part of their plan.",
    },
]

TOOLS = ["Make", "n8n", "Zapier", "OpenAI", "Anthropic Claude", "HubSpot", "Airtable", "Google Workspace", "Slack", "WhatsApp Business", "MTN MoMo", "Shopify"]
