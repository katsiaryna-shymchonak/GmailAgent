console.log('[GMAIL-AGENT] Background service worker loaded!');

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[GMAIL-AGENT] onMessage fired!', request);
  if (request.action === 'getMessage') {
    chrome.identity.getAuthToken({ interactive: true }, (token) => {
      if (chrome.runtime.lastError) {
        console.error('[Auth] Authorization error:', chrome.runtime.lastError);
        sendResponse({ snippet: 'Authorization error: ' + chrome.runtime.lastError.message });
        return;
      }
      if (!token) {
        console.warn('[Auth] Token not received');
        sendResponse({ snippet: 'Could not get auth token.' });
        return;
      }
      console.log('[Auth] Token received:', token);
      const listUrl = 'https://gmail.googleapis.com/gmail/v1/users/me/messages';
      console.log('[Gmail API] Requesting message list:', listUrl);
      fetch(listUrl, { headers: { Authorization: `Bearer ${token}` } })
        .then((res) => {
          console.log('[Gmail API] Response status for message list:', res.status);
          return res.json();
        })
        .then((data) => {
          console.log('[Gmail API] Message list response:', data);
          const messageId = data.messages?.[0]?.id;
          if (!messageId) {
            console.warn('[Gmail API] No messages in response');
            throw new Error('No messages');
          }
          const messageUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${messageId}`;
          console.log('[Gmail API] Requesting specific message:', messageUrl);
          return fetch(messageUrl, { headers: { Authorization: `Bearer ${token}` } });
        })
        .then((res) => {
          console.log('[Gmail API] Message response status:', res.status);
          return res.json();
        })
        .then((message) => {
          console.log('[Gmail API] Message received (raw):', JSON.stringify(message, null, 2));
          const text = extractPlainText(message);
          sendResponse({ snippet: text });
        })
        .catch((err) => {
          console.error('[Gmail API] Error while getting message:', err);
          sendResponse({ snippet: 'Error while getting message: ' + err.message });
        });
    });
    return true;
  }

  if (request.action === 'searchMessagesBySender') {
    chrome.identity.getAuthToken({ interactive: true }, async (token) => {
      if (chrome.runtime.lastError) {
        sendResponse({ error: chrome.runtime.lastError.message });
        return;
      }
      if (!token) {
        sendResponse({ error: 'No auth token' });
        return;
      }
      try {
        const sender = encodeURIComponent(request.sender || '');
        const maxResults = Number(request.maxResults || 10);
        const listUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=${maxResults}&q=from:${sender}`;
        console.log('[Gmail API] Search by sender URL:', listUrl);
        const listRes = await fetch(listUrl, { headers: { Authorization: `Bearer ${token}` } });
        const listData = await listRes.json();
        const ids = (listData.messages || []).map((m) => m.id);
        if (ids.length === 0) {
          sendResponse({ messages: [] });
          return;
        }
        const summaries = await Promise.all(
          ids.map(async (id) => {
            const url = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}?format=metadata&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=Date`;
            const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
            const msg = await res.json();
            const headers = msg.payload?.headers || [];
            return {
              id: msg.id,
              subject: extractHeader(headers, 'Subject'),
              from: extractHeader(headers, 'From'),
              date: extractHeader(headers, 'Date'),
              snippet: msg.snippet || '',
            };
          })
        );
        sendResponse({ messages: summaries });
      } catch (e) {
        console.error('[Gmail API] searchMessagesBySender error:', e);
        sendResponse({ error: String(e) });
      }
    });
    return true;
  }

  if (request.action === 'getMessageById') {
    chrome.identity.getAuthToken({ interactive: true }, async (token) => {
      if (chrome.runtime.lastError) {
        sendResponse({ error: chrome.runtime.lastError.message });
        return;
      }
      if (!token) {
        sendResponse({ error: 'No auth token' });
        return;
      }
      try {
        const id = request.id;
        const url = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        const msg = await res.json();
        const data = extractEmailSections(msg);
        sendResponse({ message: data });
      } catch (e) {
        console.error('[Gmail API] getMessageById error:', e);
        sendResponse({ error: String(e) });
      }
    });
    return true;
  }

  if (request.action === 'listSenders') {
    chrome.identity.getAuthToken({ interactive: true }, async (token) => {
      if (chrome.runtime.lastError) {
        sendResponse({ error: chrome.runtime.lastError.message });
        return;
      }
      if (!token) {
        sendResponse({ error: 'No auth token' });
        return;
      }
      try {
        const maxResults = Math.min(Number(request.maxResults || 100), 100);
        const listUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=${maxResults}`;
        console.log('[Gmail API] listSenders URL:', listUrl);
        const listRes = await fetch(listUrl, { headers: { Authorization: `Bearer ${token}` } });
        if (!listRes.ok) {
          const txt = await listRes.text();
          sendResponse({ error: `List failed: ${listRes.status} ${txt}` });
          return;
        }
        const listData = await listRes.json();
        const ids = (listData.messages || []).map((m) => m.id);
        if (ids.length === 0) {
          sendResponse({ senders: [] });
          return;
        }

        const metaUrls = ids.map(
          (id) =>
            `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}?format=metadata&metadataHeaders=From`
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
          const from = extractHeader(msg.payload?.headers || [], 'From');
          if (!from) continue;
          const key = from.toLowerCase();
          const cur = map.get(key) || { from, count: 0 };
          cur.count += 1;
          map.set(key, cur);
        }
        const senders = Array.from(map.values())
          .sort((a, b) => b.count - a.count)
          .slice(0, 100);
        sendResponse({ senders });
      } catch (e) {
        console.error('[Gmail API] listSenders error:', e);
        sendResponse({ error: String(e) });
      }
    });
    return true;
  }

  if (request.action === 'getWeeklyMessages') {
    chrome.identity.getAuthToken({ interactive: true }, async (token) => {
      if (chrome.runtime.lastError) {
        sendResponse({ error: chrome.runtime.lastError.message });
        return;
      }
      if (!token) {
        sendResponse({ error: 'No auth token' });
        return;
      }
      try {
        // Calculate date 7 days ago in YYYY/MM/DD format
        const date = new Date();
        date.setDate(date.getDate() - 7);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const afterDate = `${year}/${month}/${day}`;
        
        const maxResults = Number(request.maxResults || 500);
        const query = encodeURIComponent(`after:${afterDate}`);
        const listUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=${maxResults}&q=${query}`;
        console.log('[Gmail API] Weekly messages URL:', listUrl);
        
        const listRes = await fetch(listUrl, { headers: { Authorization: `Bearer ${token}` } });
        if (!listRes.ok) {
          const txt = await listRes.text();
          sendResponse({ error: `Weekly fetch failed: ${listRes.status} ${txt}` });
          return;
        }
        const listData = await listRes.json();
        const ids = (listData.messages || []).map((m) => m.id);
        
        if (ids.length === 0) {
          sendResponse({ messages: [] });
          return;
        }

        // Fetch full message details in parallel
        const messagePromises = ids.map(async (id) => {
          try {
            const url = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}`;
            const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
            if (!res.ok) {
              console.warn(`[Gmail API] Failed to fetch message ${id}: ${res.status}`);
              return null;
            }
            const msg = await res.json();
            const data = extractEmailSections(msg);
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

        const messages = (await Promise.all(messagePromises)).filter((m) => m !== null);
        console.log(`[Gmail API] Fetched ${messages.length} messages from past week`);
        sendResponse({ messages });
      } catch (e) {
        console.error('[Gmail API] getWeeklyMessages error:', e);
        sendResponse({ error: String(e) });
      }
    });
    return true;
  }
});

function decodeBase64Url(str) {
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

function extractHeader(headers, name) {
  if (!headers || !Array.isArray(headers)) return '';
  const found = headers.find((h) => h.name && h.name.toLowerCase() === name.toLowerCase());
  return found ? found.value : '';
}

function extractPlainText(message) {
  if (message.snippet) return message.snippet;
  if (message.payload?.body?.data) {
    return decodeBase64Url(message.payload.body.data);
  }
  if (message.payload?.parts) {
    for (const part of message.payload.parts) {
      if (part.mimeType === 'text/plain' && part.body?.data) {
        return decodeBase64Url(part.body.data);
      }
    }
  }
  return 'Message received, but no readable body found.';
}

function extractEmailSections(message) {
  const headers = message.payload?.headers || [];
  const subject = extractHeader(headers, 'Subject');
  const from = extractHeader(headers, 'From');
  const date = extractHeader(headers, 'Date');
  const snippet = message.snippet || '';
  let body = extractPlainText(message);
  if (body === snippet && message.payload?.parts) {
    for (const part of message.payload.parts) {
      if (part.mimeType === 'text/plain' && part.body?.data) {
        body = decodeBase64Url(part.body.data);
        break;
      }
    }
  }
  return { subject, from, date, snippet, body };
}
