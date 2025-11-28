/**
 * Sender List Manager
 */
import { FormattingUtils } from '../utils/formatting.js';

export class SenderList {
  constructor(senderListEl, onSenderSelect) {
    this.senderListEl = senderListEl;
    this.onSenderSelect = onSenderSelect;
    this.activeSenderKey = '';
  }

  async load() {
    this.senderListEl.textContent = 'Loading senders...';
    try {
      const { GmailService } = await import('../services/GmailService.js');
      const senders = await GmailService.listSenders(100);
      this.render(senders);
    } catch (error) {
      this.senderListEl.textContent = error.message || 'Failed to load senders.';
    }
  }

  render(senders) {
    if (!senders.length) {
      this.senderListEl.textContent = 'No senders found.';
      return;
    }

    const wrap = document.createElement('div');
    senders.forEach((s) => {
      const row = this.createSenderRow(s);
      wrap.appendChild(row);
    });
    this.senderListEl.innerHTML = '';
    this.senderListEl.appendChild(wrap);
  }

  createSenderRow(sender) {
    const row = document.createElement('div');
    row.className = 'sender-item';
    const left = document.createElement('div');
    const name = document.createElement('div');
    name.className = 'sender-name';
    name.textContent = FormattingUtils.parseSenderName(sender.from);
    const email = document.createElement('div');
    email.className = 'sender-email';
    email.textContent = FormattingUtils.parseSenderEmail(sender.from);
    left.appendChild(name);
    left.appendChild(email);
    const cnt = document.createElement('div');
    cnt.className = 'sender-count';
    cnt.textContent = sender.count;
    row.appendChild(left);
    row.appendChild(cnt);
    row.addEventListener('click', () => this.selectSender(row, sender.from));
    return row;
  }

  selectSender(rowEl, fromValue) {
    Array.from(this.senderListEl.querySelectorAll('.sender-item')).forEach((r) =>
      r.classList.remove('active')
    );
    rowEl.classList.add('active');
    this.activeSenderKey = fromValue;
    this.onSenderSelect?.(FormattingUtils.parseSenderEmail(fromValue));
  }

  getActiveSenderKey() {
    return this.activeSenderKey;
  }
}
