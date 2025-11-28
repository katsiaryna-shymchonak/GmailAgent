/**
 * API Client for backend communication
 */
export class ApiClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;

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
      draft_reply: {}, // добавим для совместимости
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

  // --- новый метод: только summary ---
  async initialSummary(messages, senderEmail = null) {
    return this._post('/analyze/initial', {
      sender_email: senderEmail,
      messages,
    });
  }

  // --- новый метод: follow-up ---
  async followUp(query, messages, senderEmail = null) {
    return this._post('/analyze/followup', {
      query,
      sender_email: senderEmail,
      messages,
    });
  }

  // старый метод можно оставить для совместимости
  async analyzeEmails(query, messages, senderEmail = null) {
    return this._post('/analyze/emails', {
      query,
      sender_email: senderEmail,
      messages,
    });
  }

  async getWeeklyReport(query, messages) {
    return this._post('/analyze/weekly', {
      query: query || 'Create weekly report',
      messages: messages || [],
    });
  }
}
