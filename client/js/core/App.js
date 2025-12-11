/**
 * Main Application Class
 */
import { ThemeManager } from '../ui/ThemeManager.js';
import { SenderList } from '../ui/SenderList.js';
import { EmailList } from '../ui/EmailList.js';
import { ConversationPanel } from '../ui/ConversationPanel.js';
import { InsightsPanel } from '../ui/InsightsPanel.js';
import { ApiClient } from '../services/ApiClient.js';
import { GmailService } from '../services/GmailService.js';
import { FormattingUtils } from '../utils/formatting.js';
import { DOMUtils } from '../utils/dom.js';
import { summarizeToolUsage, ensureDataShape } from '../utils/agentUtils.js';

export class App {
  constructor() {
    this.apiClient = new ApiClient();
    this.lastSelectedMessagesDetails = [];
    this.lastAgentInsights = null;
    this.activeSenderKey = '';
    this.sessionId = 'default'; // current session key for active emails
    this.spinner = null;
    this.init();
  }

  init() {
    const ids = [
      'theme-toggle',
      'sender-list',
      'email-list',
      'detail-panel',
      'conversation-panel',
      'conversation-toggle',
      'conversation-toggle-icon',
      'conversation-log',
      'conversation-input',
      'conversation-send',
      'filter-content',
      'newsletter-content',
      'weekly-report',
      'auto-reply-content',
      'summary-content',
      'key-points-content',
      'key-tasks-content',
      'deadlines-content',
      // draft-replies-content intentionally removed
      'spinner',
      'send-to-ai',
      'select-last-week-btn',
      'email-prev',
      'email-next',
      'email-page-indicator',
    ];

    const missing = ids.filter((id) => !document.getElementById(id));
    if (missing.length) {
      console.error('Missing DOM elements:', missing);
      const log = document.getElementById('conversation-log');
      if (log) log.textContent = `UI failed to initialize. Missing: ${missing.join(', ')}`;
      return;
    }

    this.themeManager = new ThemeManager(document.getElementById('theme-toggle'));
    this.senderList = new SenderList(document.getElementById('sender-list'), (senderEmail) =>
      this.onSenderSelect(senderEmail)
    );
    this.emailList = new EmailList(
      document.getElementById('email-list'),
      document.getElementById('detail-panel'),
      (count) => this.onEmailSelectionChange(count),
      { pageSize: 6 }
    );
    this.conversationPanel = new ConversationPanel(
      document.getElementById('conversation-panel'),
      document.getElementById('conversation-toggle'),
      document.getElementById('conversation-toggle-icon'),
      document.getElementById('conversation-log'),
      document.getElementById('conversation-input'),
      document.getElementById('conversation-send')
    );
    this.insightsPanel = new InsightsPanel(
      document.getElementById('filter-content'),
      document.getElementById('newsletter-content'),
      document.getElementById('weekly-report'),
      document.getElementById('auto-reply-content')
    );

    this.spinner = document.getElementById('spinner');
    this.setupEventListeners();
    this.senderList.load();
  }

  setupEventListeners() {
    const sendToAiBtn = document.getElementById('send-to-ai');
    const selectLastWeekBtn = document.getElementById('select-last-week-btn');
    const prevBtn = document.getElementById('email-prev');
    const nextBtn = document.getElementById('email-next');

    if (prevBtn)
      prevBtn.addEventListener('click', () => {
        this.emailList.prevPage();
        this.emailList.updatePaginationControls();
      });
    if (nextBtn)
      nextBtn.addEventListener('click', () => {
        this.emailList.nextPage();
        this.emailList.updatePaginationControls();
      });
    if (sendToAiBtn) sendToAiBtn.addEventListener('click', () => this.sendSelectedToAi());
    if (selectLastWeekBtn)
      selectLastWeekBtn.addEventListener('click', () => this.selectLastWeekMessages());

    // safe-guard: ensure conversationPanel.sendBtn exists
    if (this.conversationPanel && this.conversationPanel.sendBtn) {
      this.conversationPanel.sendBtn.addEventListener('click', async () => {
        const query = this.conversationPanel.getInputValue();
        if (query) await this.sendFollowUp(query);
      });
    }
  }

  onSenderSelect(senderEmail) {
    this.activeSenderKey = senderEmail;
    this.emailList.clearSelection();
    DOMUtils.setListLoading(this.spinner, true);
    GmailService.searchMessagesBySender(senderEmail, 20)
      .then((messages) => {
        this.emailList.render(messages);
        this.emailList.updatePaginationControls();
      })
      .catch((error) => {
        document.getElementById('email-list').textContent =
          error.message || 'Failed to load messages.';
      })
      .finally(() => DOMUtils.setListLoading(this.spinner, false));
  }

  onEmailSelectionChange(count) {
    const sendToAiBtn = document.getElementById('send-to-ai');
    if (sendToAiBtn) sendToAiBtn.disabled = count === 0;
    if (this.conversationPanel) this.conversationPanel.setSendEnabled(count > 0);
  }

  async sendSelectedToAi() {
    const selectedIds = this.emailList.getSelectedIds();
    if (selectedIds.size === 0) return;

    const sendToAiBtn = document.getElementById('send-to-ai');
    if (sendToAiBtn) sendToAiBtn.disabled = true;
    if (this.conversationPanel) this.conversationPanel.setSendEnabled(false);
    if (this.conversationPanel) {
      this.conversationPanel.appendEntry('System', 'Preparing selected emails...');
      this.conversationPanel.open();
    }

    DOMUtils.setListLoading(this.spinner, true);
    try {
      const messages = await this.emailList.gatherSelectedMessages();
      this.lastSelectedMessagesDetails = messages;

      // sessionId is the key used to store active emails on the backend
      this.sessionId = FormattingUtils.parseSenderEmail(this.activeSenderKey) || 'default';

      if (this.conversationPanel) this.conversationPanel.appendEntry('System', 'Analyzing with AI agent...');

      // call initialSummary with sessionId (backend treats it as session key)
      const data = await this.apiClient.initialSummary(messages, this.sessionId);

      // update UI and store last insights
      this.renderAgentResponse(data);
    } catch (error) {
      let errorMsg = error.message || 'Failed to contact AI agent.';
      if (
        error.message &&
        (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))
      ) {
        errorMsg = 'Cannot reach backend. Is the server running?';
      }
      if (this.conversationPanel) this.conversationPanel.appendEntry('Error', errorMsg);
      console.error('sendSelectedToAi error:', error);
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      if (sendToAiBtn) sendToAiBtn.disabled = this.emailList.getSelectedIds().size === 0;
      if (this.conversationPanel) this.conversationPanel.setSendEnabled(true);
      if (this.conversationPanel) this.conversationPanel.setInputPlaceholder('Ask a follow-up question...');
    }
  }

  async sendFollowUp(query) {
    if (!query) return;
    if (this.conversationPanel) this.conversationPanel.setSendEnabled(false);
    if (this.conversationPanel) this.conversationPanel.appendEntry('You', query);
    if (this.conversationPanel) this.conversationPanel.clearInput();

    DOMUtils.setListLoading(this.spinner, true);
    try {
      // Use session id so backend loads active emails from DB.
      const sessionId = this.sessionId || FormattingUtils.parseSenderEmail(this.activeSenderKey) || 'default';

      // call followUp with query and sessionId only (no messages)
      const data = await this.apiClient.followUp(query, sessionId);

      this.renderAgentResponse(data);
    } catch (error) {
      let errorMsg = error.message || 'Failed to contact AI agent.';
      if (
        error.message &&
        (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))
      ) {
        errorMsg = 'Cannot reach backend. Is the server running?';
      }
      if (this.conversationPanel) this.conversationPanel.appendEntry('Error', errorMsg);
      console.error('sendFollowUp error:', error);
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      if (this.conversationPanel) this.conversationPanel.setSendEnabled(true);
      if (this.conversationPanel) this.conversationPanel.focusInput();
    }
  }

  async selectLastWeekMessages() {
    if (this.conversationPanel) {
      this.conversationPanel.appendEntry('System', "Loading last week's emails...");
      this.conversationPanel.open();
      this.conversationPanel.setSendEnabled(false);
    }

    DOMUtils.setListLoading(this.spinner, true);
    try {
      const messages = await GmailService.getWeeklyMessages(500);
      if (messages.length === 0) {
        if (this.conversationPanel) this.conversationPanel.appendEntry('System', 'No emails found for last week.');
        if (this.conversationPanel) this.conversationPanel.setSendEnabled(true);
        return;
      }
      if (this.conversationPanel) this.conversationPanel.appendEntry('System', `Loaded ${messages.length} emails. Displaying in list...`);
      this.emailList.render(messages);
      this.emailList.updatePaginationControls();
    } catch (error) {
      if (this.conversationPanel) this.conversationPanel.appendEntry('Error', error.message || 'Failed to load emails.');
      console.error('selectLastWeekMessages error:', error);
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      if (this.conversationPanel) this.conversationPanel.setSendEnabled(true);
    }
  }

  renderAgentResponse(data) {
    const safe = ensureDataShape(data);

    if (safe.summary && this.conversationPanel) {
      this.conversationPanel.appendEntry('Agent', safe.summary, summarizeToolUsage(safe));
    }

    // Ensure insights panel is updated with the full response
    if (this.insightsPanel) {
      try {
        this.insightsPanel.update(safe);
      } catch (e) {
        console.error('InsightsPanel.update failed:', e);
      }
    }

    this.lastAgentInsights = safe;
  }
}
