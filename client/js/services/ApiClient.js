/**
 * API Client for backend communication
 */
export class ApiClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl.replace(/\/+$/, ''); // remove trailing slash

    // Unified normalized contract expected by frontend
    this.defaultSchema = {
      summary: '',
      filter_results: [],
      newsletter_insights: {},
      auto_replies: [],
      messages: [],
      capabilities_tip: '',
      // optional analysis fields (some tools may return them)
      key_tasks: [],
      deadlines: [],
      draft_reply: {}, // compatibility
    };
  }

  async _post(endpoint, body) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend error (${response.status}): ${errorText || 'Unknown error'}`);
    }

    const data = await response.json();
    return this._normalize(data);
  }

  _normalize(data) {
    const normalized = { ...this.defaultSchema };

    if (data && typeof data === 'object') {
      for (const key of Object.keys(this.defaultSchema)) {
        const val = data[key];

        switch (key) {
          case 'summary':
          case 'capabilities_tip':
            normalized[key] = typeof val === 'string' ? val : this.defaultSchema[key];
            break;

          case 'filter_results':
          case 'auto_replies':
          case 'messages':
          case 'key_tasks':
          case 'deadlines':
            normalized[key] = Array.isArray(val) ? val : this.defaultSchema[key];
            break;

          case 'newsletter_insights':
          case 'draft_reply':
            normalized[key] =
              val && typeof val === 'object' && !Array.isArray(val) ? val : this.defaultSchema[key];
            break;

          default:
            normalized[key] = val ?? this.defaultSchema[key];
        }
      }

      if (normalized.messages.length) {
        normalized.messages = normalized.messages
          .filter((m) => m && typeof m === 'object')
          .map((m) => ({
            role: typeof m.role === 'string' ? m.role : 'agent',
            tool: typeof m.tool === 'string' ? m.tool : '',
            content: typeof m.content === 'string' ? m.content : '',
          }));
      }
    }

    return normalized;
  }

  // --- initial: save active emails and return summary ---
  async initialSummary(messages, sessionId = null) {
    const payload = {
      session_id: sessionId || 'default',
      messages: Array.isArray(messages) ? messages : [],
    };
    return this._post('/analyze/initial', payload);
  }

  // --- follow-up: only query + session_id (backend loads active emails) ---
  async followUp(query, sessionId = null) {
    const payload = {
      session_id: sessionId || 'default',
      query: typeof query === 'string' ? query : String(query || ''),
    };
    return this._post('/analyze/followup', payload);
  }

  // backward-compatible full analysis endpoint (kept for compatibility)
  async analyzeEmails(query, messages, sessionId = null) {
    const payload = {
      session_id: sessionId || 'default',
      query: typeof query === 'string' ? query : String(query || ''),
      messages: Array.isArray(messages) ? messages : [],
    };
    return this._post('/analyze/emails', payload);
  }

  async getWeeklyReport(query, messages) {
    const payload = {
      query: query || 'Create weekly report',
      messages: Array.isArray(messages) ? messages : [],
    };
    return this._post('/analyze/weekly', payload);
  }
}
