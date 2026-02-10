/**
 * Insights Panel Manager client/js/ui/InsightsPanel.js
 */
import { FormattingUtils } from '../utils/formatting.js';

export class InsightsPanel {
  constructor(filterEl, newsletterEl, weeklyReportEl, autoReplyEl) {
    this.filterEl = typeof filterEl === 'string' ? document.getElementById(filterEl) : filterEl;
    this.newsletterEl = typeof newsletterEl === 'string' ? document.getElementById(newsletterEl) : newsletterEl;
    this.weeklyReportEl = typeof weeklyReportEl === 'string' ? document.getElementById(weeklyReportEl) : weeklyReportEl;
    this.autoReplyEl = typeof autoReplyEl === 'string' ? document.getElementById(autoReplyEl) : autoReplyEl;

    this.summaryEl = document.getElementById('summary-content') || null;
    this.keyPointsEl = document.getElementById('key-points-content') || null;
    this.keyTasksEl = document.getElementById('key-tasks-content') || null;
    this.deadlinesEl = document.getElementById('deadlines-content') || null;
  }

  update(data) {
    const safe = data && typeof data === 'object' ? data : {};

    try {
      this.renderSummary(typeof safe.summary === 'string' ? safe.summary : '');
    } catch (e) {
      console.error('InsightsPanel.update: summary render failed', e);
    }

    try {
      this.renderFilterResults(Array.isArray(safe.filter_results) ? safe.filter_results : []);
    } catch (e) {
      console.error('InsightsPanel.update: filter_results render failed', e);
    }

    try {
      const insights = safe.newsletter_insights || {};
      const weekly = insights.weekly_report || safe.weekly_report || '';
      this.renderNewsletterInsights(insights, weekly);
    } catch (e) {
      console.error('InsightsPanel.update: newsletter render failed', e);
    }

    try {
      this.renderAutoReplies(Array.isArray(safe.auto_replies) ? safe.auto_replies : []);
    } catch (e) {
      console.error('InsightsPanel.update: auto replies render failed', e);
    }

    try {
      this.renderKeyPoints(safe.key_points || [], safe.executed_tools || []);
    } catch (e) {
      console.error('InsightsPanel.update: key points render failed', e);
    }

    try {
      this.renderKeyTasks(safe.key_tasks || [], safe.executed_tools || []);
      this.renderDeadlines(safe.deadlines || [], safe.executed_tools || []);
    } catch (e) {
      console.error('InsightsPanel.update: tasks/deadlines render failed', e);
    }
  }

  // SUMMARY
  renderSummary(text) {
    if (!this.summaryEl) return;
    this.summaryEl.innerHTML = text
      ? `<p>${FormattingUtils.escapeHtml(text)}</p>`
      : '<p class="muted">No summary available.</p>';
  }

  // FILTER RESULTS
  renderFilterResults(items) {
    if (!this.filterEl) return;
    this.filterEl.innerHTML = '';

    if (!items.length) {
      this.filterEl.innerHTML = '<p class="muted">No filter results.</p>';
      return;
    }

    const frag = document.createDocumentFragment();

    items.forEach((item) => {
      const subject = item.subject || item.id || 'Email';
      const priority = (item.priority || 'low').toLowerCase();
      const action = item.recommended_action || 'none';
      const tags = Array.isArray(item.tags) && item.tags.length
        ? item.tags.map((t) => `<span class="chip">${FormattingUtils.escapeHtml(String(t))}</span>`).join('')
        : '<span class="muted">No tags</span>';

      const snippet = item.body ? FormattingUtils.escapeHtml(String(item.body)).slice(0, 120) : '';

      const card = document.createElement('div');
      card.className = 'insight-item';
      card.innerHTML = `
        <div><strong>${FormattingUtils.escapeHtml(subject)}</strong></div>
        <div class="muted priority-${priority}">
          Priority: ${FormattingUtils.escapeHtml(priority)} • Action: ${FormattingUtils.escapeHtml(action)}
        </div>
        <div class="muted snippet">${snippet}${snippet ? '…' : ''}</div>
        <div>${tags}</div>
      `;
      frag.appendChild(card);
    });

    this.filterEl.appendChild(frag);
  }

  // NEWSLETTERS
  renderNewsletterInsights(insights, weekly) {
    if (!this.newsletterEl || !this.weeklyReportEl) return;

    this.newsletterEl.innerHTML = '';
    this.weeklyReportEl.innerHTML = '';

    if (!insights || Object.keys(insights).length === 0) {
      this.newsletterEl.innerHTML = '<p class="muted">No newsletter recommendations.</p>';
      this.weeklyReportEl.textContent = weekly || 'No report yet.';
      return;
    }

    const digestHtml = insights.digest
      ? (window.marked ? window.marked.parse(insights.digest) : FormattingUtils.escapeHtml(insights.digest))
      : '';

    const unsubscribe = (insights.unsubscribe || []).map(
      (i) => `<li>${FormattingUtils.escapeHtml(String(i))}</li>`
    ).join('') || '<li class="muted">Nothing to unsubscribe</li>';

    const keep = (insights.keep || []).map(
      (i) => `<li>${FormattingUtils.escapeHtml(String(i))}</li>`
    ).join('') || '<li class="muted">No newsletters to keep</li>';

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

    const weeklyHtml = weekly
      ? (window.marked ? window.marked.parse(weekly) : FormattingUtils.escapeHtml(weekly))
      : 'No report yet.';

    this.weeklyReportEl.innerHTML = `
      <div class="newsletter-section">
        <h4>Weekly Report</h4>
        <div class="weekly-block">${weeklyHtml}</div>
      </div>
    `;
  }

  // AUTO REPLIES
  renderAutoReplies(templates) {
    if (!this.autoReplyEl) return;
    this.autoReplyEl.innerHTML = '';

    if (!templates.length) {
      this.autoReplyEl.innerHTML = '<p class="muted">No templates. Agent will prepare them after analysis.</p>';
      return;
    }

    const frag = document.createDocumentFragment();

    templates.forEach((t, idx) => {
      const id = t.id || idx + 1;
      const text = t.template || '';

      const block = document.createElement('div');
      block.className = 'template-block';
      block.innerHTML = `
        <strong>#${FormattingUtils.escapeHtml(String(id))}:</strong>
        <span>${FormattingUtils.escapeHtml(String(text))}</span>
      `;
      frag.appendChild(block);
    });

    this.autoReplyEl.appendChild(frag);
  }

    // KEY POINTS
  renderKeyPoints(points, executedTools) {
    if (!this.keyPointsEl) return;
    this.keyPointsEl.innerHTML = '';

    if (!executedTools.includes('key_points')) {
      this.keyPointsEl.innerHTML = '<p class="muted">Key points tool was not used.</p>';
      return;
    }

    if (!points.length) {
      this.keyPointsEl.innerHTML = '<p class="muted">No key points extracted.</p>';
      return;
    }

    const frag = document.createDocumentFragment();

    points.forEach((p, idx) => {
      const id = p.email_id || `email_${idx}`;
      const pts = Array.isArray(p.points) ? p.points : [];

      const wrapper = document.createElement('div');
      wrapper.className = 'insight-item';

      if (!pts.length) {
        wrapper.innerHTML = `
          <strong>${FormattingUtils.escapeHtml(id)}</strong>
          <p class="muted">No extracted points.</p>
        `;
      } else {
        const listHtml = pts.map(
          (pt) => `<li>${FormattingUtils.escapeHtml(String(pt))}</li>`
        ).join('');

        wrapper.innerHTML = `
          <strong>${FormattingUtils.escapeHtml(id)}</strong>
          <ul>${listHtml}</ul>
        `;
      }

      frag.appendChild(wrapper);
    });

    this.keyPointsEl.appendChild(frag);
  }

  // KEY TASKS
  renderKeyTasks(tasks, executedTools) {
    if (!this.keyTasksEl) return;
    this.keyTasksEl.innerHTML = '';

    if (!executedTools.includes('key_points')) {
      this.keyTasksEl.innerHTML = '<p class="muted">Tasks tool was not used.</p>';
      return;
    }

    if (!tasks.length) {
      this.keyTasksEl.innerHTML = '<p class="muted">No tasks extracted.</p>';
      return;
    }

    const frag = document.createDocumentFragment();

    tasks.forEach((t) => {
      const emailId = t.email_id || '';
      const taskText = t.task || '';
      const deadline = t.deadline || '';

      const node = document.createElement('div');
      node.className = 'insight-item';
      node.innerHTML = `
        ${emailId ? `<div class="muted">${FormattingUtils.escapeHtml(emailId)}</div>` : ''}
        <div>📌 ${FormattingUtils.escapeHtml(taskText)}${deadline ? ` — <span class="priority-medium">${FormattingUtils.escapeHtml(deadline)}</span>` : ''}</div>
      `;
      frag.appendChild(node);
    });

    this.keyTasksEl.appendChild(frag);
  }

  // DEADLINES
  renderDeadlines(deadlines, executedTools) {
    if (!this.deadlinesEl) return;
    this.deadlinesEl.innerHTML = '';

    if (!executedTools.includes('deadlines')) {
      this.deadlinesEl.innerHTML = '<p class="muted">Deadlines tool was not used.</p>';
      return;
    }

    if (!deadlines.length) {
      this.deadlinesEl.innerHTML = '<p class="muted">No deadlines extracted.</p>';
      return;
    }

    const frag = document.createDocumentFragment();

    deadlines.forEach((d) => {
      const emailId = d.email_id || null;
      const date = d.deadline || '';
      const desc = d.description|| '';

      const node = document.createElement('div');
      node.className = 'insight-item';
      node.innerHTML = emailId
        ? `⏰ ${FormattingUtils.escapeHtml(emailId)} — ${FormattingUtils.escapeHtml(date || desc)}`
        : `⏰ ${FormattingUtils.escapeHtml(desc || date)}`;
      frag.appendChild(node);
    });

    this.deadlinesEl.appendChild(frag);
  }
}
