/**
 * Background service worker - handles Gmail API requests
 */
import { GmailApiService } from './js/services/GmailApiService.js';

console.log('[GMAIL-AGENT] Background service worker loaded!');

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[GMAIL-AGENT] onMessage fired!', request);

  if (request.action === 'getMessage') {
    GmailApiService.getAuthToken()
      .then((token) => {
        const listUrl = 'https://gmail.googleapis.com/gmail/v1/users/me/messages';
        return fetch(listUrl, { headers: { Authorization: `Bearer ${token}` } })
          .then((res) => res.json())
          .then((data) => {
            const messageId = data.messages?.[0]?.id;
            if (!messageId) throw new Error('No messages');
            const messageUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${messageId}`;
            return fetch(messageUrl, { headers: { Authorization: `Bearer ${token}` } });
          })
          .then((res) => res.json())
          .then((message) => {
            const text = GmailApiService.extractPlainText(message);
            sendResponse({ snippet: text });
          });
      })
      .catch((err) => {
        console.error('[Gmail API] Error while getting message:', err);
        sendResponse({ snippet: 'Error while getting message: ' + err.message });
      });
    return true;
  }

  if (request.action === 'searchMessagesBySender') {
    GmailApiService.searchMessagesBySender(request.sender, request.maxResults || 10)
      .then((messages) => sendResponse({ messages }))
      .catch((e) => {
        console.error('[Gmail API] searchMessagesBySender error:', e);
        sendResponse({ error: String(e) });
      });
    return true;
  }

  if (request.action === 'getMessageById') {
    GmailApiService.getMessageById(request.id)
      .then((data) => sendResponse({ message: data }))
      .catch((e) => {
        console.error('[Gmail API] getMessageById error:', e);
        sendResponse({ error: String(e) });
      });
    return true;
  }

  if (request.action === 'listSenders') {
    GmailApiService.listSenders(request.maxResults || 100)
      .then((senders) => sendResponse({ senders }))
      .catch((e) => {
        console.error('[Gmail API] listSenders error:', e);
        sendResponse({ error: String(e) });
      });
    return true;
  }

  if (request.action === 'getWeeklyMessages') {
    GmailApiService.getWeeklyMessages(request.maxResults || 500)
      .then((messages) => {
        console.log(`[Gmail API] Fetched ${messages.length} messages from past week`);
        sendResponse({ messages });
      })
      .catch((e) => {
        console.error('[Gmail API] getWeeklyMessages error:', e);
        sendResponse({ error: String(e) });
      });
    return true;
  }
});
