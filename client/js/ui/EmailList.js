/**
 * Email List Manager (with pagination)
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
    this.pageSize = options.pageSize || 6; // items per page
    this.currentPage = 0;
    this.totalPages = 0;

    // keyboard navigation
    this.setupKeyboardNavigation();
  }

  setupKeyboardNavigation() {
    // Allow left/right keys to change pages when email list has focus/hover
    this.emailListEl.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') {
        this.prevPage();
      } else if (e.key === 'ArrowRight') {
        this.nextPage();
      }
    });

    // Make container focusable
    this.emailListEl.tabIndex = 0;
  }

  render(messages) {
    this.currentList = messages || [];
    this.selectedIds = new Set([...this.selectedIds].filter((id) => this.currentList.some((m) => m.id === id)));
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

    // Header (select all operates per current page)
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

    this.setSelectAllState(header.querySelector('#select-all'));
    this.updatePaginationControls();
  }

  createHeader() {
    const header = document.createElement('div');
    header.className = 'email-list-header';
    const selectAll = document.createElement('input');
    selectAll.type = 'checkbox';
    selectAll.id = 'select-all';
    selectAll.disabled = this.currentList.length === 0;
    const label = document.createElement('label');
    label.setAttribute('for', 'select-all');
    label.textContent = 'Select page';
    header.appendChild(selectAll);
    header.appendChild(label);

    selectAll.addEventListener('change', () => {
      if (this.currentList.length === 0) return;
      const check = selectAll.checked;
      const start = this.currentPage * this.pageSize;
      const end = Math.min(start + this.pageSize, this.currentList.length);
      for (let idx = start; idx < end; idx++) {
        const id = this.currentList[idx].id;
        if (check) this.selectedIds.add(id);
        else this.selectedIds.delete(id);
      }
      // update visible checkboxes
      const boxes = this.emailListEl.querySelectorAll('.email-checkbox');
      boxes.forEach((box, idx) => {
        box.checked = check;
      });
      this.onSelectionChange?.(this.selectedIds.size);
      this.setSelectAllState(selectAll);
    });

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
      this.setSelectAllState(this.emailListEl.querySelector('#select-all'));
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

  setSelectAllState(selectAllEl) {
    if (!selectAllEl) return;
    if (this.currentList.length === 0) {
      selectAllEl.checked = false;
      selectAllEl.indeterminate = false;
      return;
    }
    const start = this.currentPage * this.pageSize;
    const end = Math.min(start + this.pageSize, this.currentList.length);
    const pageIds = this.currentList.slice(start, end).map((m) => m.id);
    const selectedOnPage = pageIds.filter((id) => this.selectedIds.has(id)).length;
    const total = pageIds.length;
    selectAllEl.checked = selectedOnPage === total && total > 0;
    selectAllEl.indeterminate = selectedOnPage > 0 && selectedOnPage < total;
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
    // Update external DOM controls if they exist
    const prevBtn = document.getElementById('email-prev');
    const nextBtn = document.getElementById('email-next');
    const indicator = document.getElementById('email-page-indicator');
    if (prevBtn) prevBtn.disabled = this.currentPage === 0 || this.totalPages <= 1;
    if (nextBtn) nextBtn.disabled = this.currentPage >= this.totalPages - 1 || this.totalPages <= 1;
    if (indicator) indicator.textContent = `Page ${this.currentPage + 1} / ${this.totalPages}`;
  }
}
