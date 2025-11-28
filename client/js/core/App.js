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
      'draft-replies-content',
      'spinner',
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

    this.conversationPanel.sendBtn.addEventListener('click', async () => {
      const query = this.conversationPanel.getInputValue();
      if (query) await this.sendFollowUp(query);
    });
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
    this.conversationPanel.setSendEnabled(count > 0);
  }

  async sendSelectedToAi() {
    const selectedIds = this.emailList.getSelectedIds();
    if (selectedIds.size === 0) return;

    const sendToAiBtn = document.getElementById('send-to-ai');
    if (sendToAiBtn) sendToAiBtn.disabled = true;
    this.conversationPanel.setSendEnabled(false);
    this.conversationPanel.appendEntry('System', 'Preparing selected emails...');
    this.conversationPanel.open();

    DOMUtils.setListLoading(this.spinner, true);
    try {
      const messages = await this.emailList.gatherSelectedMessages();
      this.lastSelectedMessagesDetails = messages;
      const senderEmail = FormattingUtils.parseSenderEmail(this.activeSenderKey) || null;

      this.conversationPanel.appendEntry('System', 'Analyzing with AI agent...');
      // теперь вызываем initialSummary
      const data = await this.apiClient.initialSummary(messages, senderEmail);
      this.renderAgentResponse(data);
    } catch (error) {
      let errorMsg = error.message || 'Failed to contact AI agent.';
      if (
        error.message &&
        (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))
      ) {
        errorMsg = 'Cannot reach backend. Is the server running?';
      }
      this.conversationPanel.appendEntry('Error', errorMsg);
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      if (sendToAiBtn) sendToAiBtn.disabled = this.emailList.getSelectedIds().size === 0;
      this.conversationPanel.setSendEnabled(true);
      this.conversationPanel.setInputPlaceholder('Ask a follow-up question...');
    }
  }

  async sendFollowUp(query) {
    if (!query) return;
    this.conversationPanel.setSendEnabled(false);
    this.conversationPanel.appendEntry('You', query);
    this.conversationPanel.clearInput();

    DOMUtils.setListLoading(this.spinner, true);
    try {
      const messages = this.lastSelectedMessagesDetails.length
        ? this.lastSelectedMessagesDetails
        : [];
      const senderEmail = FormattingUtils.parseSenderEmail(this.activeSenderKey) || null;
      // теперь вызываем followUp
      const data = await this.apiClient.followUp(query, messages, senderEmail);
      this.renderAgentResponse(data);
    } catch (error) {
      let errorMsg = error.message || 'Failed to contact AI agent.';
      if (
        error.message &&
        (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))
      ) {
        errorMsg = 'Cannot reach backend. Is the server running?';
      }
      this.conversationPanel.appendEntry('Error', errorMsg);
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      this.conversationPanel.setSendEnabled(true);
      this.conversationPanel.focusInput();
    }
  }

  async selectLastWeekMessages() {
    this.conversationPanel.appendEntry('System', "Loading last week's emails...");
    this.conversationPanel.open();
    this.conversationPanel.setSendEnabled(false);

    DOMUtils.setListLoading(this.spinner, true);
    try {
      const messages = await GmailService.getWeeklyMessages(500);
      if (messages.length === 0) {
        this.conversationPanel.appendEntry('System', 'No emails found for last week.');
        this.conversationPanel.setSendEnabled(true);
        return;
      }
      this.conversationPanel.appendEntry(
        'System',
        `Loaded ${messages.length} emails. Displaying in list...`
      );
      this.emailList.render(messages);
      this.emailList.updatePaginationControls();
    } catch (error) {
      this.conversationPanel.appendEntry('Error', error.message || 'Failed to load emails.');
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      this.conversationPanel.setSendEnabled(true);
    }
  }

  renderAgentResponse(data) {
    const safe = ensureDataShape(data);

    if (safe.summary) {
      this.conversationPanel.appendEntry('Agent', safe.summary, summarizeToolUsage(safe));
    }

    if (this.insightsPanel) {
      this.insightsPanel.update(safe);
    }

    this.lastAgentInsights = safe;
  }
}
