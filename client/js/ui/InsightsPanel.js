/**
 * Insights Panel Manager
 */
import { FormattingUtils } from '../utils/formatting.js';

export class InsightsPanel {
  constructor(filterEl, newsletterEl, weeklyReportEl, autoReplyEl) {
    this.filterEl = filterEl;
    this.newsletterEl = newsletterEl;
    this.weeklyReportEl = weeklyReportEl;
    this.autoReplyEl = autoReplyEl;

    // Дополнительные секции
    this.summaryEl = document.getElementById('summary-content');
    this.keyPointsEl = document.getElementById('key-points-content');
    this.keyTasksEl = document.getElementById('key-tasks-content');
    this.deadlinesEl = document.getElementById('deadlines-content');
    this.draftRepliesEl = document.getElementById('draft-replies-content');
  }

  update(data) {
    const safe = data && typeof data === 'object' ? data : {};

    this.renderSummary(typeof safe.summary === 'string' ? safe.summary : '');
    this.renderFilterResults(Array.isArray(safe.filter_results) ? safe.filter_results : []);
    this.renderNewsletterInsights(
      safe.newsletter_insights && typeof safe.newsletter_insights === 'object'
        ? safe.newsletter_insights
        : {},
      typeof safe.weekly_report === 'string' ? safe.weekly_report : ''
    );
    this.renderAutoReplies(Array.isArray(safe.auto_replies) ? safe.auto_replies : []);

    this.renderKeyPoints(Array.isArray(safe.key_points) ? safe.key_points : []);
    this.renderKeyTasks(Array.isArray(safe.key_tasks) ? safe.key_tasks : []);
    this.renderDeadlines(Array.isArray(safe.deadlines) ? safe.deadlines : []);
    this.renderDraftReplies(safe.draft_reply || {});
  }

  renderSummary(text) {
    if (!this.summaryEl) return;
    this.summaryEl.innerHTML =
      text && text.length
        ? `<p>${FormattingUtils.escapeHtml(text)}</p>`
        : '<p class="muted">No summary available.</p>';
  }

  renderFilterResults(items) {
    if (!this.filterEl) return;
    if (!items || !items.length) {
      this.filterEl.innerHTML = '<p class="muted">No filter results. Send emails to the agent.</p>';
      return;
    }
    this.filterEl.innerHTML = '';
    items.forEach((item) => {
      const subject = item.subject || item.id || 'Email';
      const priority = item.priority ? String(item.priority).toLowerCase() : 'normal';
      const action = item.recommended_action
        ? FormattingUtils.escapeHtml(item.recommended_action)
        : 'none';
      const tags =
        (item.tags || [])
          .map((tag) => `<span class="chip">${FormattingUtils.escapeHtml(tag)}</span>`)
          .join('') || '<span class="muted">No tags</span>';

      let priorityClass = '';
      if (priority === 'high') priorityClass = 'priority-high';
      else if (priority === 'medium') priorityClass = 'priority-medium';
      else if (priority === 'low') priorityClass = 'priority-low';

      const card = document.createElement('div');
      card.className = 'insight-item';
      card.innerHTML = `
        <div><strong>${FormattingUtils.escapeHtml(subject)}</strong></div>
        <div class="muted ${priorityClass}">
          Priority: ${FormattingUtils.escapeHtml(priority)} • Action: ${action}
        </div>
        <div>${tags}</div>
      `;
      this.filterEl.appendChild(card);
    });
  }

  renderNewsletterInsights(insights, weeklyReportFallback) {
    if (!this.newsletterEl || !this.weeklyReportEl) return;
    if (!insights || Object.keys(insights).length === 0) {
      this.newsletterEl.innerHTML = '<p class="muted">No newsletter recommendations.</p>';
      this.weeklyReportEl.textContent = weeklyReportFallback || 'No report yet.';
      return;
    }

    // Используем глобальный window.marked
    const digestHtml = insights.digest && window.marked ? window.marked.parse(insights.digest) : '';
    const weeklyHtml =
      insights.weekly_report && window.marked
        ? window.marked.parse(insights.weekly_report)
        : weeklyReportFallback && window.marked
          ? window.marked.parse(weeklyReportFallback)
          : 'No report yet.';

    const unsubscribeItems = (insights.unsubscribe || []).map(
      (item) => `<li>${FormattingUtils.escapeHtml(item)}</li>`
    );
    const keepItems = (insights.keep || []).map(
      (item) => `<li>${FormattingUtils.escapeHtml(item)}</li>`
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
    if (!templates || !templates.length) {
      this.autoReplyEl.innerHTML =
        '<p class="muted">No templates. Agent will prepare them after analysis.</p>';
      return;
    }
    this.autoReplyEl.innerHTML = '';
    templates.forEach((t, idx) => {
      // если объект с полем template
      const id = t && typeof t === 'object' && 'id' in t ? t.id : idx + 1;
      const text = t && typeof t === 'object' && 'template' in t ? t.template : String(t);

      const block = document.createElement('div');
      block.className = 'template-block';
      block.innerHTML = `<strong>#${id}:</strong> <code>${FormattingUtils.escapeHtml(text)}</code>`;
      this.autoReplyEl.appendChild(block);
    });
  }

  renderKeyPoints(points) {
    if (!this.keyPointsEl) return;
    if (!points.length) {
      this.keyPointsEl.innerHTML = '<p class="muted">No key points.</p>';
      return;
    }
    this.keyPointsEl.innerHTML = points
      .map(
        (p) =>
          `<div class="insight-item"><strong>${FormattingUtils.escapeHtml(p.email_id)}</strong><ul>${p.points.map((pt) => `<li>${FormattingUtils.escapeHtml(pt)}</li>`).join('')}</ul></div>`
      )
      .join('');
  }

  renderKeyTasks(tasks) {
    if (!this.keyTasksEl) return;
    if (!tasks.length) {
      this.keyTasksEl.innerHTML = '<p class="muted">No tasks.</p>';
      return;
    }
    this.keyTasksEl.innerHTML = tasks
      .map(
        (t) =>
          `<div class="insight-item">📌 ${FormattingUtils.escapeHtml(t.task)} ${t.deadline ? `— <span class="priority-medium">${FormattingUtils.escapeHtml(t.deadline)}</span>` : ''}</div>`
      )
      .join('');
  }

  renderDeadlines(deadlines) {
    if (!this.deadlinesEl) return;
    if (!deadlines.length) {
      this.deadlinesEl.innerHTML = '<p class="muted">No deadlines.</p>';
      return;
    }
    this.deadlinesEl.innerHTML = deadlines
      .map(
        (d) =>
          `<div class="insight-item">⏰ ${FormattingUtils.escapeHtml(d.description)} — ${FormattingUtils.escapeHtml(d.date)}</div>`
      )
      .join('');
  }

  renderDraftReplies(draftReplies) {
    if (!this.draftRepliesEl) return;
    const keys = Object.keys(draftReplies);
    if (!keys.length) {
      this.draftRepliesEl.innerHTML = '<p class="muted">No draft replies.</p>';
      return;
    }
    this.draftRepliesEl.innerHTML = keys
      .map(
        (id) =>
          `<div class="template-block"><code>${FormattingUtils.escapeHtml(draftReplies[id])}</code></div>`
      )
      .join('');
  }
}
