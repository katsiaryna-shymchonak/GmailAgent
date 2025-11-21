/**
 * Gmail API Service
 */
export class GmailService {
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

  static async listSenders(maxResults = 100) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { action: 'listSenders', maxResults },
        (resp) => {
          if (!resp || resp.error) {
            reject(new Error(resp?.error || 'Failed to load senders'));
            return;
          }
          resolve(resp.senders || []);
        }
      );
    });
  }

  static async searchMessagesBySender(sender, maxResults = 20) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { action: 'searchMessagesBySender', sender, maxResults },
        (resp) => {
          if (!resp || resp.error) {
            reject(new Error(resp?.error || 'Failed to load messages'));
            return;
          }
          resolve(resp.messages || []);
        }
      );
    });
  }

  static async getMessageById(id) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ action: 'getMessageById', id }, (resp) => {
        if (!resp || resp.error) {
          reject(new Error(resp?.error || 'Failed to load message'));
          return;
        }
        resolve(resp.message || resp);
      });
    });
  }

  static async getWeeklyMessages(maxResults = 500) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { action: 'getWeeklyMessages', maxResults },
        (resp) => {
          if (!resp || resp.error) {
            reject(new Error(resp?.error || 'Failed to load weekly messages'));
            return;
          }
          resolve(resp.messages || []);
        }
      );
    });
  }
}

