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

export class App {
  constructor() {
    this.apiClient = new ApiClient();
    this.lastSelectedMessagesDetails = [];
    this.lastAgentInsights = null;
    this.activeSenderKey = '';
    this.init();
  }

  init() {
    // Initialize UI components
    this.themeManager = new ThemeManager(document.getElementById('theme-toggle'));
    this.senderList = new SenderList(
      document.getElementById('sender-list'),
      (senderEmail) => this.onSenderSelect(senderEmail)
    );
    // pass pageSize if needed
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

    // Setup event listeners
    this.setupEventListeners();

    // Load initial data
    this.senderList.load();
  }

  setupEventListeners() {
    const sendToAiBtn = document.getElementById('send-to-ai');
    const weeklySummaryBtn = document.getElementById('weekly-summary-btn');
    const spinner = document.getElementById('spinner');

    // Pagination controls
    const prevBtn = document.getElementById('email-prev');
    const nextBtn = document.getElementById('email-next');

    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        this.emailList.prevPage();
        this.emailList.updatePaginationControls();
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        this.emailList.nextPage();
        this.emailList.updatePaginationControls();
      });
    }

    if (sendToAiBtn) {
      sendToAiBtn.addEventListener('click', () => this.sendSelectedToAi());
    }

    if (weeklySummaryBtn) {
      weeklySummaryBtn.addEventListener('click', () => this.requestWeeklySummary());
    }

    // Override conversation panel send handler
    this.conversationPanel.sendBtn.addEventListener('click', async () => {
      const query = this.conversationPanel.getInputValue();
      if (query) {
        await this.sendFollowUp(query);
      }
    });

    // Store spinner reference
    this.spinner = spinner;
  }

  onSenderSelect(senderEmail) {
    this.activeSenderKey = senderEmail;
    this.emailList.clearSelection();
    DOMUtils.setListLoading(this.spinner, true);
    GmailService.searchMessagesBySender(senderEmail, 20)
      .then((messages) => {
        this.emailList.render(messages);
      })
      .catch((error) => {
        document.getElementById('email-list').textContent = error.message || 'Failed to load messages.';
      })
      .finally(() => {
        DOMUtils.setListLoading(this.spinner, false);
      });
  }

  onEmailSelectionChange(count) {
    const sendToAiBtn = document.getElementById('send-to-ai');
    if (sendToAiBtn) {
      sendToAiBtn.disabled = count === 0;
    }
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
      const senderEmail = FormattingUtils.parseSenderEmail(this.senderList.getActiveSenderKey()) || null;

      this.conversationPanel.appendEntry('System', 'Analyzing with AI agent...');
      const data = await this.apiClient.analyzeEmails(
        'Summarize the selected emails and highlight key points.',
        messages,
        senderEmail
      );

      this.renderAgentResponse(data);
    } catch (error) {
      let errorMsg = error.message || 'Failed to contact AI agent.';
      if (error.message && (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))) {
        errorMsg = `Cannot reach backend. Is the server running?`;
      }
      this.conversationPanel.appendEntry('Error', errorMsg);
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      if (sendToAiBtn) sendToAiBtn.disabled = this.emailList.getSelectedIds().size === 0;
      this.conversationPanel.setSendEnabled(true);
      this.conversationPanel.setInputPlaceholder('Ask follow-up question...');
    }
  }

  async sendFollowUp(query) {
    if (!query) return;

    this.conversationPanel.setSendEnabled(false);
    this.conversationPanel.appendEntry('You', query);
    this.conversationPanel.clearInput();

    DOMUtils.setListLoading(this.spinner, true);
    try {
      const messages = this.lastSelectedMessagesDetails.length ? this.lastSelectedMessagesDetails : [];
      const senderEmail = FormattingUtils.parseSenderEmail(this.senderList.getActiveSenderKey()) || null;

      const data = await this.apiClient.analyzeEmails(query, messages, senderEmail);
      this.renderAgentResponse(data);
    } catch (error) {
      let errorMsg = error.message || 'Failed to contact AI agent.';
      if (error.message && (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))) {
        errorMsg = `Cannot reach backend. Is the server running?`;
      }
      this.conversationPanel.appendEntry('Error', errorMsg);
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      this.conversationPanel.setSendEnabled(true);
      this.conversationPanel.focusInput();
    }
  }

  async requestWeeklySummary() {
    this.conversationPanel.appendEntry('System', 'Загрузка писем за неделю из Gmail...');
    this.conversationPanel.open();
    this.conversationPanel.setSendEnabled(false);

    DOMUtils.setListLoading(this.spinner, true);
    try {
      const messages = await GmailService.getWeeklyMessages(500);
      if (messages.length === 0) {
        this.conversationPanel.appendEntry('System', 'За последнюю неделю писем не найдено.');
        this.conversationPanel.setSendEnabled(true);
        return;
      }

      this.conversationPanel.appendEntry('System', `Загружено ${messages.length} писем. Отправка агенту...`);

      const data = await this.apiClient.getWeeklyReport('Сформируй недельный отчёт', messages);
      this.renderAgentResponse(data);
    } catch (error) {
      this.conversationPanel.appendEntry('Error', error.message || 'Не удалось получить отчёт.');
    } finally {
      DOMUtils.setListLoading(this.spinner, false);
      this.conversationPanel.setSendEnabled(true);
    }
  }

  renderAgentResponse(data) {
    this.renderAgentMessages(data);
    this.insightsPanel.update(data);
    this.lastAgentInsights = data;
  }

  renderAgentMessages(data) {
    if (data && Array.isArray(data.messages) && data.messages.length) {
      data.messages.forEach((msg) => {
        this.conversationPanel.appendEntry(
          msg.role === 'system' ? 'System' : msg.role === 'user' ? 'You' : 'Agent',
          msg.content || '',
          msg.tool
        );
      });
    } else {
      this.conversationPanel.appendEntry(
        'Agent',
        data?.summary || 'No summary returned.',
        this.summarizeToolUsage(data)
      );
    }
  }

  summarizeToolUsage(data) {
    if (!data) return '';
    const used = [];
    if (data.filter_results && data.filter_results.length) used.push('Фильтрация');
    if (data.newsletter_insights && Object.keys(data.newsletter_insights).length) used.push('Рассылки');
    if (data.auto_replies && data.auto_replies.length) used.push('Автоответы');
    if (data.key_tasks && data.key_tasks.length) used.push('Задачи');
    if (!used.length) return '';
    return `Использовано: ${used.join(', ')}`;
  }
}
