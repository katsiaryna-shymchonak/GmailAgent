# Email Analytics Agent Chrome Extension

This project is a Chrome extension that connects to an AI‑powered backend for analyzing corporate emails. The extension helps users quickly understand long or complex messages by summarizing content, extracting key points, detecting deadlines and generating automatic replies. It reduces the time spent on manual email review and helps users stay organized.

## What the extension does

The extension adds an AI assistant directly into the browser. It can:
- read the currently opened email
- clean and normalize the text
- send it to the backend for analysis
- show a summary, key insights, tasks and deadlines
- generate suggested replies
- highlight important parts of the message

The goal is to make email processing faster and easier without changing the user’s workflow.

## Why this was needed

Many employees deal with overloaded inboxes. Important details are often hidden inside long threads, repeated content or poorly formatted messages. The extension solves this by turning unstructured email text into clear, actionable information right inside the browser.

## Technical architecture

The system consists of two main parts: the Chrome extension and the backend AI service.

### Chrome extension
- built with **JavaScript**, **HTML/CSS**
- uses **Manifest V3**
- content script extracts email text from the page
- background service worker handles authentication and API calls
- UI is rendered as a popup or sidebar panel
- communicates with the backend through a secure HTTPS API
- uses **NextAuth** for authentication flow (via backend)

### Backend service
- implemented with **Python**, **FastAPI**, **asyncio**
- uses **LangChain** for tool orchestration
- runs multiple custom LLM tools (summaries, insights, deadlines, newsletter analysis, auto‑replies)
- inference powered by **Groq**
- **PostgreSQL** stores user data and processed results
- **Redis** handles caching and rate‑limit coordination
- normalization pipeline cleans and standardizes email text
- execution layer merges tool outputs into a single structured response
- **Prometheus** and structured logs provide monitoring and observability
- tested with **Pytest**
- deployed via **Docker** on **Google Cloud**

### Frontend integration
Although the extension is the main UI, the project also includes a small **Next.js + React** interface for:
- viewing history of processed emails
- managing authentication
- testing the agent outside the extension

## Data flow

1. User opens an email in the browser.  
2. The extension extracts the visible text and sends it to the backend.  
3. The backend normalizes the text and selects the right analysis tools.  
4. Each tool runs independently and returns structured JSON.  
5. The execution layer merges results into a single response.  
6. The extension displays the summary, insights, tasks and suggested replies.  

This modular design keeps the system stable and easy to extend.

## Quality and evaluation

The system was tested on real email flows, including:
- long threads with repeated content
- quoted messages
- incomplete or noisy emails

Quality checks included:
- correctness of extracted insights
- accuracy of deadlines and tasks
- clarity of summaries
- stability under rate limits
- user feedback from internal testing

Monitoring dashboards track latency, errors and model behavior in production.

## Business impact

The extension helps employees save time, avoid missed commitments and reduce repetitive communication.  
It provides consistent summaries and clear action items directly inside the browser, making email processing faster and more reliable.

## Client JavaScript Structure

The client side of the extension is organized into several small, focused modules.  
Each folder contains logic for a specific part of the UI or the browser‑side functionality.


```aiignore
client/js
├── core/
│   └── App.js
├── lib/
│   └── marked.js
├── services/
│   ├── ApiClient.js
│   └── GmailApiService.js
├── ui/
│   ├── ConversationPanel.js
│   └── EmailList.js
└── utils/
├── agentUtils.js
├── dom.js
└── formatting.js
```
### **core/**
Contains the main application entry point.  
`App.js` initializes the extension UI, sets up event listeners and coordinates interactions between services and UI components.

### **lib/**
Holds third‑party or standalone helper libraries.  
`marked.js` is used for rendering Markdown inside the extension interface.

### **services/**
Implements communication with external APIs and backend services.
- `ApiClient.js` — a small wrapper around HTTP requests, handling authentication and error processing.
- `GmailApiService.js` — extracts email content from the Gmail DOM and prepares it for analysis.

### **ui/**
Contains UI components rendered inside the extension popup or sidebar.
- `ConversationPanel.js` — displays the AI‑generated summary, insights and suggested replies.
- `EmailList.js` — shows the list of processed emails or conversation history.

### **utils/**
Utility functions shared across the client.
- `agentUtils.js` — helper functions for preparing requests to the AI agent.
- `dom.js` — DOM manipulation helpers for extracting and cleaning email text.
- `formatting.js` — formatting helpers for text, dates and UI output.

### How the client works

1. The extension loads `App.js`, which initializes the UI and connects services.  
2. When the user opens an email, `GmailApiService` extracts the visible content.  
3. The text is cleaned and formatted using utilities from `utils/`.  
4. `ApiClient` sends the prepared data to the backend AI agent.  
5. The response is rendered in the UI components inside `ui/`.  
6. Markdown formatting and highlighting are handled by `lib/marked.js`.

### How to load the Chrome extension

1. Open chrome://extensions
2. Enable Developer mode
3. Click Load unpacked
4. Select the project’s client/ directory
5. The extension will appear in the browser and can be pinned to the toolbar

## Server Structure
The server is organized into clear, modular components. Each folder is responsible for a specific part of the backend logic: planning, execution, data processing, metrics and API routing.

```server/
├── api/
│   ├── __init__.py
│   └── routes.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── core/
│   ├── __init__.py
│   ├── executor.py
│   ├── orchestrator.py
│   ├── planner.py
│   └── reviewers.py
├── metrics/
│   ├── __init__.py
│   ├── llm_counters.py
│   └── prometheus_metrics.py
├── models/
│   ├── __init__.py
│   └── schemas.py
├── services/
│   ├── __init__.py
│   ├── database.py
│   └── embeddings.py
├── tools/
│   ├── __init__.py
│   ├── auto_reply.py
│   ├── base.py
│   ├── content_analysis.py
│   ├── deadline_tool.py
│   ├── filtering.py
│   ├── key_points.py
│   ├── newsletter.py
│   └── utils.py
└── utils/
    ├── __init__.py
    └── persist.py
   ```
### api/
Defines the HTTP interface.  
`routes.py` exposes endpoints for email analysis, health checks and internal tooling.

### config/
Centralized configuration.  
`settings.py` loads environment variables, model settings, database URLs and feature flags.

### core/
Implements the main agent logic.  
- `planner.py` decides which tools to run  
- `orchestrator.py` coordinates the workflow  
- `executor.py` runs tools and merges results  
- `reviewers.py` performs validation and consistency checks  

This is the heart of the agent.

### metrics/
Monitoring and observability.  
- `llm_counters.py` tracks model usage  
- `prometheus_metrics.py` exposes metrics for Prometheus  

### models/
Pydantic schemas for requests and responses.

### services/
Backend services and integrations.  
- `database.py` manages PostgreSQL connections  
- `embeddings.py` handles embedding generation and caching  

### tools/
All analytical tools used by the agent.  
Each file implements one capability: summarization, filtering, key points, deadlines, newsletters, auto‑replies, etc.  
`base.py` defines the shared interface for all tools.

### utils/
Low‑level helpers for persistence, caching and shared logic.
