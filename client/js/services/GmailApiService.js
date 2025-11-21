/**
 * Gmail API Service for background script
 */
export class GmailApiService {
  static decodeBase64Url(str) {
    const base64 = str
      .replace(/-/g, '+')
      .replace(/_/g, '/')
      .padEnd(str.length + ((4 - (str.length % 4)) % 4), '=');
    try {
      return decodeURIComponent(escape(atob(base64)));
    } catch (e) {
      return '[Could not decode message body]';
    }
  }

  static extractHeader(headers, name) {
    if (!headers || !Array.isArray(headers)) return '';
    const found = headers.find((h) => h.name && h.name.toLowerCase() === name.toLowerCase());
    return found ? found.value : '';
  }

  static extractPlainText(message) {
    if (message.snippet) return message.snippet;
    if (message.payload?.body?.data) {
      return this.decodeBase64Url(message.payload.body.data);
    }
    if (message.payload?.parts) {
      for (const part of message.payload.parts) {
        if (part.mimeType === 'text/plain' && part.body?.data) {
          return this.decodeBase64Url(part.body.data);
        }
      }
    }
    return 'Message received, but no readable body found.';
  }

  static extractEmailSections(message) {
    const headers = message.payload?.headers || [];
    const subject = this.extractHeader(headers, 'Subject');
    const from = this.extractHeader(headers, 'From');
    const date = this.extractHeader(headers, 'Date');
    const snippet = message.snippet || '';
    let body = this.extractPlainText(message);
    if (body === snippet && message.payload?.parts) {
      for (const part of message.payload.parts) {
        if (part.mimeType === 'text/plain' && part.body?.data) {
          body = this.decodeBase64Url(part.body.data);
          break;
        }
      }
    }
    return { subject, from, date, snippet, body };
  }

  static async getAuthToken() {
    return new Promise((resolve, reject) => {
      chrome.identity.getAuthToken({ interactive: true }, (token) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!token) {
          reject(new Error('No auth token'));
          return;
        }
        resolve(token);
      });
    });
  }

  static async getWeeklyMessages(maxResults = 500) {
    const token = await this.getAuthToken();
    const date = new Date();
    date.setDate(date.getDate() - 7);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const afterDate = `${year}/${month}/${day}`;
    const query = encodeURIComponent(`after:${afterDate}`);
    const listUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=${maxResults}&q=${query}`;

    const listRes = await fetch(listUrl, { headers: { Authorization: `Bearer ${token}` } });
    if (!listRes.ok) {
      const txt = await listRes.text();
      throw new Error(`Weekly fetch failed: ${listRes.status} ${txt}`);
    }

    const listData = await listRes.json();
    const ids = (listData.messages || []).map((m) => m.id);
    if (ids.length === 0) {
      return [];
    }

    const messagePromises = ids.map(async (id) => {
      try {
        const url = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok) {
          console.warn(`[Gmail API] Failed to fetch message ${id}: ${res.status}`);
          return null;
        }
        const msg = await res.json();
        const data = this.extractEmailSections(msg);
        return {
          id: msg.id,
          subject: data.subject || '',
          snippet: data.snippet || '',
          from: data.from || '',
          body: data.body || data.snippet || '',
        };
      } catch (err) {
        console.error(`[Gmail API] Error fetching message ${id}:`, err);
        return null;
      }
    });

    return (await Promise.all(messagePromises)).filter((m) => m !== null);
  }

  static async searchMessagesBySender(sender, maxResults = 10) {
    const token = await this.getAuthToken();
    const encodedSender = encodeURIComponent(sender);
    const listUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=${maxResults}&q=from:${encodedSender}`;

    const listRes = await fetch(listUrl, { headers: { Authorization: `Bearer ${token}` } });
    const listData = await listRes.json();
    const ids = (listData.messages || []).map((m) => m.id);
    if (ids.length === 0) {
      return [];
    }

    const summaries = await Promise.all(
      ids.map(async (id) => {
        const url = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}?format=metadata&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=Date`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        const msg = await res.json();
        const headers = msg.payload?.headers || [];
        return {
          id: msg.id,
          subject: this.extractHeader(headers, 'Subject'),
          from: this.extractHeader(headers, 'From'),
          date: this.extractHeader(headers, 'Date'),
          snippet: msg.snippet || '',
        };
      })
    );

    return summaries;
  }

  static async getMessageById(id) {
    const token = await this.getAuthToken();
    const url = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}`;
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    const msg = await res.json();
    return this.extractEmailSections(msg);
  }

  static async listSenders(maxResults = 100) {
    const token = await this.getAuthToken();
    const max = Math.min(maxResults, 100);
    const listUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=${max}`;

    const listRes = await fetch(listUrl, { headers: { Authorization: `Bearer ${token}` } });
    if (!listRes.ok) {
      const txt = await listRes.text();
      throw new Error(`List failed: ${listRes.status} ${txt}`);
    }

    const listData = await listRes.json();
    const ids = (listData.messages || []).map((m) => m.id);
    if (ids.length === 0) {
      return [];
    }

    const metaUrls = ids.map(
      (id) => `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}?format=metadata&metadataHeaders=From`
    );
    const metaFetches = metaUrls.map((url) =>
      fetch(url, { headers: { Authorization: `Bearer ${token}` } })
        .then(async (res) => ({ ok: res.ok, status: res.status, json: await res.json() }))
        .catch((err) => ({ ok: false, status: 0, error: String(err) }))
    );
    const metaResults = await Promise.all(metaFetches);

    const map = new Map();
    for (const r of metaResults) {
      if (!r.ok) continue;
      const msg = r.json;
      const from = this.extractHeader(msg.payload?.headers || [], 'From');
      if (!from) continue;
      const key = from.toLowerCase();
      const cur = map.get(key) || { from, count: 0 };
      cur.count += 1;
      map.set(key, cur);
    }

    return Array.from(map.values())
      .sort((a, b) => b.count - a.count)
      .slice(0, 100);
  }
}

