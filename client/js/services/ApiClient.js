/**
 * API Client for backend communication
 */
export class ApiClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async analyzeEmails(query, messages, senderEmail = null) {
    const response = await fetch(`${this.baseUrl}/analyze/emails`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        sender_email: senderEmail,
        messages,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend error (${response.status}): ${errorText || 'Unknown error'}`);
    }

    return response.json();
  }

  async getWeeklyReport(query, messages) {
    const response = await fetch(`${this.baseUrl}/analyze/weekly`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query || 'Сформируй недельный отчёт',
        messages: messages || [],
      }),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Backend error (${response.status}): ${text || 'Unknown error'}`);
    }

    return response.json();
  }
}

