/**
 * Email List Manager (with pagination + page/global select)
 */
import { FormattingUtils } from '../utils/formatting.js';

export class EmailList {
  constructor(emailListEl, detailPanel, onSelectionChange, options = {}) {
    this.emailListEl = emailListEl;
    this.detailPanel = detailPanel;
    this.onSelectionChange = onSelectionChange;
    this.selectedIds = new Set();
    this.currentList = [];
    this.messageDetailCache = new Map();

    // pagination options
    this.pageSize = options.pageSize || 6;
    this.currentPage = 0;
    this.totalPages = 0;

    this.setupKeyboardNavigation();
  }

  setupKeyboardNavigation() {
    this.emailListEl.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') this.prevPage();
      else if (e.key === 'ArrowRight') this.nextPage();
    });
    this.emailListEl.tabIndex = 0;
  }

  render(messages) {
    this.currentList = messages || [];
    this.selectedIds = new Set(
      [...this.selectedIds].filter((id) => this.currentList.some((m) => m.id === id))
    );
    this.messageDetailCache = this.messageDetailCache || new Map();

    this.currentPage = 0;
    this.totalPages = Math.max(1, Math.ceil((this.currentList.length || 0) / this.pageSize));

    this.redrawCurrentPage();
  }

  redrawCurrentPage() {
    this.emailListEl.innerHTML = '';
    this.emailListEl.classList.remove('no-messages');

    if (!this.currentList || this.currentList.length === 0) {
      this.emailListEl.textContent = 'No messages found for this sender.';
      this.onSelectionChange?.(0);
      this.updatePaginationControls();
      return;
    }

    const header = this.createHeader();
    this.emailListEl.appendChild(header);

    const start = this.currentPage * this.pageSize;
    const end = Math.min(start + this.pageSize, this.currentList.length);
    const pageItems = this.currentList.slice(start, end);

    const container = document.createElement('div');
    container.className = 'email-page-container';
    pageItems.forEach((m) => {
      const row = this.createEmailRow(m);
      container.appendChild(row);
    });
    this.emailListEl.appendChild(container);

    this.updatePaginationControls();
  }

  createHeader() {
    const header = document.createElement('div');
    header.className = 'email-list-header';

    // --- Select page ---
    const selectPageBtn = document.createElement('button');
    selectPageBtn.className = 'secondary-btn';
    selectPageBtn.textContent = 'Select page';
    selectPageBtn.disabled = this.currentList.length === 0;
    selectPageBtn.addEventListener('click', () => {
      const start = this.currentPage * this.pageSize;
      const end = Math.min(start + this.pageSize, this.currentList.length);
      for (let idx = start; idx < end; idx++) {
        const id = this.currentList[idx].id;
        this.selectedIds.add(id);
      }
      this.redrawCurrentPage();
      this.onSelectionChange?.(this.selectedIds.size);
    });
    header.appendChild(selectPageBtn);

    // --- Select all ---
    const selectAllBtn = document.createElement('button');
    selectAllBtn.className = 'secondary-btn';
    selectAllBtn.textContent = 'Select all';
    selectAllBtn.disabled = this.currentList.length === 0;
    selectAllBtn.addEventListener('click', () => {
      this.selectAllGlobal();
      this.onSelectionChange?.(this.selectedIds.size);
    });
    header.appendChild(selectAllBtn);

    return header;
  }

  createEmailRow(message) {
    const row = document.createElement('div');
    row.className = 'email-list-item';
    row.dataset.id = message.id;

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'email-checkbox';
    cb.checked = this.selectedIds.has(message.id);
    cb.addEventListener('click', (e) => {
      e.stopPropagation();
      if (cb.checked) this.selectedIds.add(message.id);
      else this.selectedIds.delete(message.id);
      this.onSelectionChange?.(this.selectedIds.size);
    });

    const info = document.createElement('div');
    info.className = 'email-list-info';
    const subj = document.createElement('div');
    subj.className = 'email-list-subject';
    subj.textContent = message.subject || '(no subject)';
    const meta = document.createElement('div');
    meta.className = 'email-list-meta';
    meta.textContent = `${message.from || ''}  •  ${message.date || ''}`;
    const snip = document.createElement('div');
    snip.className = 'email-list-snippet';
    snip.textContent = message.snippet || '';
    info.appendChild(subj);
    info.appendChild(meta);
    info.appendChild(snip);

    row.appendChild(cb);
    row.appendChild(info);
    row.addEventListener('click', () => this.previewMessage(message.id));

    return row;
  }

  async previewMessage(id) {
    this.detailPanel.textContent = 'Loading message...';
    try {
      const msg = await this.fetchMessageDetail(id);
      this.detailPanel.innerHTML = FormattingUtils.formatEmailView(msg);
    } catch (err) {
      this.detailPanel.textContent = err.message || 'Failed to load message.';
    }
  }

  async fetchMessageDetail(id) {
    if (this.messageDetailCache.has(id)) {
      return Promise.resolve(this.messageDetailCache.get(id));
    }
    const { GmailService } = await import('../services/GmailService.js');
    const message = await GmailService.getMessageById(id);
    this.messageDetailCache.set(id, message);
    return message;
  }

  async gatherSelectedMessages() {
    const details = [];
    for (const id of this.selectedIds) {
      const msg = await this.fetchMessageDetail(id);
      details.push({
        id,
        subject: msg.subject || '',
        snippet: msg.snippet || '',
        from: msg.from || '',
        body: msg.body || msg.snippet || '',
      });
    }
    return details;
  }

  getSelectedIds() {
    return this.selectedIds;
  }

  clearSelection() {
    this.selectedIds.clear();
    this.onSelectionChange?.(0);
  }

  // --- Global select ---
  selectAllGlobal() {
    this.selectedIds = new Set(this.currentList.map((m) => m.id));
    this.redrawCurrentPage();
  }

  // pagination controls
  nextPage() {
    if (this.currentPage < this.totalPages - 1) {
      this.currentPage++;
      this.redrawCurrentPage();
    }
  }

  prevPage() {
    if (this.currentPage > 0) {
      this.currentPage--;
      this.redrawCurrentPage();
    }
  }

  goToPage(pageIdx) {
    if (pageIdx >= 0 && pageIdx < this.totalPages) {
      this.currentPage = pageIdx;
      this.redrawCurrentPage();
    }
  }

  updatePaginationControls() {
    const prevBtn = document.getElementById('email-prev');
    const nextBtn = document.getElementById('email-next');
    const indicator = document.getElementById('email-page-indicator');
    if (prevBtn) prevBtn.disabled = this.currentPage === 0 || this.totalPages <= 1;
    if (nextBtn) nextBtn.disabled = this.currentPage >= this.totalPages - 1 || this.totalPages <= 1;
    if (indicator) indicator.textContent = `Page ${this.currentPage + 1} / ${this.totalPages}`;
  }
}
