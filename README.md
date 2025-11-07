# Gmail Reader + AI (RAG with pgVector)

Chrome Extension to browse Gmail by sender, select messages, and (optionally) send them to a Python backend for AI analysis using RAG over PostgreSQL + pgVector.

## Overview
- MV3 extension, OAuth via chrome.identity
- Sender-first flow → list unique senders → pick sender → select emails → preview
- Sticky “Select all” for multi-select
- Light/Dark theme toggle
- Ready for FastAPI backend with pgVector

## Setup
1) Enable Gmail API and configure OAuth Client ID in Google Cloud.
2) Update `manifest.json` oauth2.client_id.
3) Load unpacked at `chrome://extensions` → Developer mode → Load folder.

## Use
- Open popup → wait for “Senders” to load (count = recent sample).
- Click a sender → see messages (subject, from, date, snippet).
- Select individual or “Select all” → click a message to preview body.
- “Send Selected to AI” is a placeholder until backend is wired.

## Troubleshooting
- If popup shows “No response”: Inspect Service Worker at `chrome://extensions`.
- If senders fail to load: verify Gmail API + OAuth config; check background logs.
- Missing body: add HTML part parsing in `getMessageById` flow.

