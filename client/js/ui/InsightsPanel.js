/**
 * Insights Panel Manager
 */
import { FormattingUtils } from '../utils/formatting.js';

export class InsightsPanel {
  constructor(filterEl, newsletterEl, weeklyReportEl, autoReplyEl) {
    // Принимаем либо DOM-элементы, либо id-строки (поддержка гибкости)
    this.filterEl = typeof filterEl === 'string' ? document.getElementById(filterEl) : filterEl;
    this.newsletterEl = typeof newsletterEl === 'string' ? document.getElementById(newsletterEl) : newsletterEl;
    this.weeklyReportEl = typeof weeklyReportEl === 'string' ? document.getElementById(weeklyReportEl) : weeklyReportEl;
    this.autoReplyEl = typeof autoReplyEl === 'string' ? document.getElementById(autoReplyEl) : autoReplyEl;

    // Дополнительные секции (могут отсутствовать)
    this.summaryEl = document.getElementById('summary-content') || null;
    this.keyPointsEl = document.getElementById('key-points-content') || null;
    this.keyTasksEl = document.getElementById('key-tasks-content') || null;
    this.deadlinesEl = document.getElementById('deadlines-content') || null;

    // Защита: если какой-то элемент не найден, методы просто ничего не рендерят
  }

  // --- Утилиты ---
  _toArray(value) {
    if (Array.isArray(value)) return value;
    if (typeof value === 'string') {
      return value.split('\n').map((s) => s.trim()).filter(Boolean);
    }
    if (value == null) return [];
    return [value];
  }

  _normalizePriority(raw) {
    if (!raw && raw !== 0) return 'low';
    const p = String(raw).toLowerCase();
    if (p === 'high' || p === 'высокая' || p === 'urgent') return 'high';
    if (p === 'medium' || p === 'средняя' || p === 'normal') return 'medium';
    if (p === 'low' || p === 'низкая') return 'low';
    if (p.includes('high') || p.includes('высок')) return 'high';
    if (p.includes('med') || p.includes('сред')) return 'medium';
    if (p.includes('low') || p.includes('низ')) return 'low';
    return 'low';
  }

  update(data) {
    const safe = data && typeof data === 'object' ? data : {};

    try {
      // Summary: string preferred; if array of objects (emails) -> render as filter results fallback
      if (typeof safe.summary === 'string') {
        this.renderSummary(safe.summary);
      } else if (Array.isArray(safe.summary)) {
        const arr = safe.summary;
        const isObjects = arr.length > 0 && typeof arr[0] === 'object';
        if (isObjects) {
          this.renderSummary('');
          this.renderFilterResults(arr);
        } else {
          this.renderSummary(arr.map((s) => String(s)).join('<br>'));
        }
      } else {
        this.renderSummary('');
      }
    } catch (e) {
      console.error('InsightsPanel.update: summary render failed', e);
    }

    try {
      // filter_results
      this.renderFilterResults(Array.isArray(safe.filter_results) ? safe.filter_results : []);
    } catch (e) {
      console.error('InsightsPanel.update: filter_results render failed', e);
    }

    try {
      // newsletter insights
      const newsletterInsights = safe.newsletter_insights && typeof safe.newsletter_insights === 'object'
        ? safe.newsletter_insights
        : {};
      const weeklyReport = (newsletterInsights && typeof newsletterInsights.weekly_report === 'string')
        ? newsletterInsights.weekly_report
        : (typeof safe.weekly_report === 'string' ? safe.weekly_report : '');
      this.renderNewsletterInsights(newsletterInsights, weeklyReport);
    } catch (e) {
      console.error('InsightsPanel.update: newsletter render failed', e);
    }

    try {
      this.renderAutoReplies(Array.isArray(safe.auto_replies) ? safe.auto_replies : []);
    } catch (e) {
      console.error('InsightsPanel.update: auto replies render failed', e);
    }

    try {
      // key_points
      this.renderKeyPoints(Array.isArray(safe.key_points) ? safe.key_points : []);
    } catch (e) {
      console.error('InsightsPanel.update: key points render failed', e);
    }

    try {
      // key_tasks, deadlines
      this.renderKeyTasks(Array.isArray(safe.key_tasks) ? safe.key_tasks : []);
      this.renderDeadlines(Array.isArray(safe.deadlines) ? safe.deadlines : []);
    } catch (e) {
      console.error('InsightsPanel.update: tasks/deadlines render failed', e);
    }
  }

  renderSummary(text) {
    if (!this.summaryEl) return;
    const safeText = text && text.length ? String(text) : '';
    this.summaryEl.innerHTML = safeText
      ? `<p>${FormattingUtils.escapeHtml(safeText)}</p>`
      : '<p class="muted">No summary available.</p>';
  }

  renderFilterResults(items) {
    if (!this.filterEl) return;
    // Очистка контейнера
    this.filterEl.innerHTML = '';
    if (!items || !items.length) {
      this.filterEl.innerHTML = '<p class="muted">No filter results. Send emails to the agent.</p>';
      return;
    }

    const frag = document.createDocumentFragment();
    items.forEach((item) => {
      const subject = item && (item.subject || item.id || item.email_id) ? (item.subject || item.id || item.email_id) : 'Email';
      const rawPriority = item && (item.priority || item.priority === 0) ? item.priority : 'low';
      const priority = this._normalizePriority(rawPriority);
      const action = item && item.recommended_action ? FormattingUtils.escapeHtml(String(item.recommended_action)) : 'none';
      const tagsArr = (item && Array.isArray(item.tags)) ? item.tags : [];
      const tags = (tagsArr.length > 0)
        ? tagsArr.map((tag) => `<span class="chip">${FormattingUtils.escapeHtml(String(tag))}</span>`).join('')
        : '<span class="muted">No tags</span>';

      let priorityClass = '';
      if (priority === 'high') priorityClass = 'priority-high';
      else if (priority === 'medium') priorityClass = 'priority-medium';
      else if (priority === 'low') priorityClass = 'priority-low';

      const snippet = item && item.body ? FormattingUtils.escapeHtml(String(item.body)).slice(0, 300) : '';

      const card = document.createElement('div');
      card.className = 'insight-item';
      card.innerHTML = `
        <div><strong>${FormattingUtils.escapeHtml(subject)}</strong></div>
        <div class="muted ${priorityClass}">
          Priority: ${FormattingUtils.escapeHtml(priority)} • Action: ${action}
        </div>
        <div class="muted snippet">${snippet}${snippet ? '…' : ''}</div>
        <div>${tags}</div>
      `;
      frag.appendChild(card);
    });
    this.filterEl.appendChild(frag);
  }

  renderNewsletterInsights(insights, weeklyReportFallback) {
    if (!this.newsletterEl || !this.weeklyReportEl) return;

    // Очистка
    this.newsletterEl.innerHTML = '';
    this.weeklyReportEl.innerHTML = '';

    if (!insights || Object.keys(insights).length === 0) {
      this.newsletterEl.innerHTML = '<p class="muted">No newsletter recommendations.</p>';
      this.weeklyReportEl.textContent = weeklyReportFallback || 'No report yet.';
      return;
    }

    const digestHtml = insights.digest && window.marked ? window.marked.parse(insights.digest) : (insights.digest ? FormattingUtils.escapeHtml(String(insights.digest)) : '');
    const weeklyHtml =
      insights.weekly_report && window.marked
        ? window.marked.parse(insights.weekly_report)
        : (weeklyReportFallback && window.marked
          ? window.marked.parse(weeklyReportFallback)
          : (weeklyReportFallback ? FormattingUtils.escapeHtml(String(weeklyReportFallback)) : 'No report yet.'));

    const unsubscribeItems = (insights.unsubscribe || []).map(
      (item) => `<li>${FormattingUtils.escapeHtml(String(item))}</li>`
    );
    const keepItems = (insights.keep || []).map(
      (item) => `<li>${FormattingUtils.escapeHtml(String(item))}</li>`
    );

    const unsubscribe =
      unsubscribeItems.length > 0
        ? unsubscribeItems.join('')
        : '<li class="muted">Nothing to unsubscribe</li>';
    const keep =
      keepItems.length > 0 ? keepItems.join('') : '<li class="muted">No newsletters to keep</li>';

    this.newsletterEl.innerHTML = `
      <div class="newsletter-section">
        <h4>Digest</h4>
        <div class="digest-block">${digestHtml}</div>
      </div>
      <div class="newsletter-section">
        <h4>Unsubscribe</h4>
        <ul class="insight-list">${unsubscribe}</ul>
      </div>
      <div class="newsletter-section">
        <h4>Keep</h4>
        <ul class="insight-list">${keep}</ul>
      </div>
    `;
    this.weeklyReportEl.innerHTML = `
      <div class="newsletter-section">
        <h4>Weekly Report</h4>
        <div class="weekly-block">${weeklyHtml}</div>
      </div>
    `;
  }

  renderAutoReplies(templates) {
    if (!this.autoReplyEl) return;
    this.autoReplyEl.innerHTML = '';
    if (!templates || !templates.length) {
      this.autoReplyEl.innerHTML =
        '<p class="muted">No templates. Agent will prepare them after analysis.</p>';
      return;
    }

    const frag = document.createDocumentFragment();
    templates.forEach((t, idx) => {
      const id = t && typeof t === 'object' && 'id' in t ? t.id : idx + 1;
      const text = t && typeof t === 'object' && 'template' in t ? t.template : String(t);

      const block = document.createElement('div');
      block.className = 'template-block';
      block.innerHTML = `<strong>#${FormattingUtils.escapeHtml(String(id))}:</strong> <code>${FormattingUtils.escapeHtml(String(text))}</code>`;
      frag.appendChild(block);
    });
    this.autoReplyEl.appendChild(frag);
  }
renderKeyPoints(points) {
  if (!this.keyPointsEl) return;

  // Очищаем контейнер
  this.keyPointsEl.innerHTML = '';

  // Если вообще нет key_points — показываем заглушку
  if (!points || !points.length) {
    this.keyPointsEl.innerHTML = '<p class="muted">No key points.</p>';
    return;
  }

  const frag = document.createDocumentFragment();

  points.forEach((p, idx) => {
    const id = p && p.email_id
      ? FormattingUtils.escapeHtml(String(p.email_id))
      : `email_${idx}`;

    // Приводим points к массиву строк
    let pts = [];
    if (Array.isArray(p.points)) {
      pts = p.points
        .map((pt) => (pt != null ? String(pt).trim() : ''))
        .filter((pt) => pt.length > 0);
    } else if (typeof p.points === 'string') {
      pts = p.points
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);
    }

    // Создаём карточку
    const wrapper = document.createElement('div');
    wrapper.className = 'insight-item';

    // Если нет points — рендерим пустой блок, но НЕ прерываем рендер остальных
    if (!pts.length) {
      wrapper.innerHTML = `
        <strong>${id}</strong>
        <p class="muted">No extracted points.</p>
      `;
    } else {
      const listHtml = `<ul>${pts
        .map((pt) => `<li>${FormattingUtils.escapeHtml(pt)}</li>`)
        .join('')}</ul>`;

      wrapper.innerHTML = `
        <strong>${id}</strong>
        ${listHtml}
      `;
    }

    frag.appendChild(wrapper);
  });

  this.keyPointsEl.appendChild(frag);
}


  renderKeyTasks(tasks) {
    if (!this.keyTasksEl) return;
    this.keyTasksEl.innerHTML = '';

    if (!tasks || !tasks.length) {
      this.keyTasksEl.innerHTML = '<p class="muted">No tasks.</p>';
      return;
    }

    const frag = document.createDocumentFragment();
    tasks.forEach((t) => {
      const emailId = t && t.email_id ? FormattingUtils.escapeHtml(String(t.email_id)) : '';
      const taskText = t && t.task ? FormattingUtils.escapeHtml(String(t.task)) : '';
      const deadline = t && (t.deadline || t.due) ? FormattingUtils.escapeHtml(String(t.deadline || t.due)) : '';

      const node = document.createElement('div');
      node.className = 'insight-item';
      node.innerHTML = `
        ${emailId ? `<div class="muted">${emailId}</div>` : ''}
        <div>📌 ${taskText}${deadline ? ` — <span class="priority-medium">${deadline}</span>` : ''}</div>
      `;
      frag.appendChild(node);
    });

    this.keyTasksEl.appendChild(frag);
  }

  renderDeadlines(deadlines) {
    if (!this.deadlinesEl) return;
    this.deadlinesEl.innerHTML = '';

    if (!deadlines || !deadlines.length) {
      this.deadlinesEl.innerHTML = '<p class="muted">No deadlines.</p>';
      return;
    }

    const frag = document.createDocumentFragment();
    deadlines.forEach((d) => {
      const emailId = d && d.email_id ? FormattingUtils.escapeHtml(String(d.email_id)) : null;
      const date = d && (d.deadline || d.date) ? FormattingUtils.escapeHtml(String(d.deadline || d.date)) : '';
      const desc = d && (d.description || d.task) ? FormattingUtils.escapeHtml(String(d.description || d.task)) : '';

      const node = document.createElement('div');
      node.className = 'insight-item';
      if (emailId) {
        node.innerHTML = `⏰ ${emailId} — ${date || desc}`;
      } else {
        node.innerHTML = `⏰ ${desc || date}`;
      }
      frag.appendChild(node);
    });

    this.deadlinesEl.appendChild(frag);
  }
}
