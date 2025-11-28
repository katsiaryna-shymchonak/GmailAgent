/**
 * Conversation Panel Manager
 */
import { FormattingUtils } from '../utils/formatting.js';

export class ConversationPanel {
  constructor(panelEl, toggleBtn, toggleIcon, logEl, inputEl, sendBtn) {
    this.panelEl = panelEl;
    this.toggleBtn = toggleBtn;
    this.toggleIcon = toggleIcon;
    this.logEl = logEl;
    this.inputEl = inputEl;
    this.sendBtn = sendBtn;
    this.isOpen = false;
    this.setupListeners();
  }

  setupListeners() {
    this.toggleBtn.addEventListener('click', () => {
      this.toggle();
    });

    this.sendBtn.addEventListener('click', () => {
      this.sendMessage();
    });

    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
  }

  toggle() {
    this.isOpen = !this.isOpen;
    this.updateVisibility();
  }

  open() {
    this.isOpen = true;
    this.updateVisibility();
  }

  close() {
    this.isOpen = false;
    this.updateVisibility();
  }

  updateVisibility() {
    this.toggleBtn.setAttribute('aria-expanded', this.isOpen.toString());
    this.toggleIcon.textContent = this.isOpen ? '▲' : '▼';
    const body = this.panelEl.querySelector('#conversation-body');
    if (body) {
      body.style.display = this.isOpen ? 'flex' : 'none';
    }
  }

  appendEntry(role, text, toolTip) {
    const entry = document.createElement('div');
    entry.className = 'conversation-entry';
    const safeText = FormattingUtils.escapeHtml(text);
    entry.innerHTML = `<strong>${FormattingUtils.escapeHtml(role)}:</strong> ${safeText}`;
    if (toolTip) {
      entry.innerHTML += `<div class="muted">${FormattingUtils.escapeHtml(toolTip)}</div>`;
    }
    this.logEl.appendChild(entry);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  clear() {
    this.logEl.innerHTML = '';
  }

  setInputPlaceholder(text) {
    this.inputEl.placeholder = text;
  }

  getInputValue() {
    return this.inputEl.value.trim();
  }

  clearInput() {
    this.inputEl.value = '';
  }

  setSendEnabled(enabled) {
    this.sendBtn.disabled = !enabled;
  }

  focusInput() {
    this.inputEl.focus();
  }

  sendMessage() {
    // This will be handled by the App class
    return this.getInputValue();
  }
}
