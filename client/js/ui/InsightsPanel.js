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
  }

  update(data) {
    if (!data) {
      this.renderFilterResults([]);
      this.renderNewsletterInsights({});
      this.renderAutoReplies([]);
      this.weeklyReportEl.textContent = 'Ещё нет отчёта.';
      return;
    }

    this.renderFilterResults(data.filter_results || []);
    this.renderNewsletterInsights(data.newsletter_insights || {}, data.weekly_report);
    this.renderAutoReplies(data.auto_replies || []);
    if (data.weekly_report) {
      this.weeklyReportEl.textContent = data.weekly_report;
    }
  }

  renderFilterResults(items) {
    if (!items || !items.length) {
      this.filterEl.innerHTML = '<p class="muted">Нет данных. Отправьте письма агенту.</p>';
      return;
    }
    this.filterEl.innerHTML = items
      .map((item) => {
        const tags = (item.tags || [])
          .map((tag) => `<span class="chip">${FormattingUtils.escapeHtml(tag)}</span>`)
          .join('') || '<span class="muted">Нет тегов</span>';
        const actions = (item.actions || [])
          .map((action) => `<li>${FormattingUtils.escapeHtml(action)}</li>`)
          .join('') || '<li class="muted">Нет действий</li>';
        const subject = item.subject || item.notes || item.id || 'Письмо';
        const type = item.type ? `<span class="chip">${FormattingUtils.escapeHtml(item.type)}</span>` : '';
        const priority = item.priority ? FormattingUtils.escapeHtml(item.priority) : 'normal';
        const replyText = item.requires_reply ? 'Нужен ответ' : 'Информационное';
        const notes = item.notes ? `<div class="muted">${FormattingUtils.escapeHtml(item.notes)}</div>` : '';
        return `
        <div class="insight-item">
          <div><strong>${FormattingUtils.escapeHtml(subject)}</strong> ${type}</div>
          <div class="muted">Приоритет: ${priority} • ${replyText}</div>
          <div>${tags}</div>
          <ul class="insight-list">${actions}</ul>
          ${notes}
        </div>`;
      })
      .join('');
  }

  renderNewsletterInsights(insights, weeklyReportFallback) {
    if (!insights || Object.keys(insights).length === 0) {
      this.newsletterEl.innerHTML = '<p class="muted">Нет рекомендаций по рассылкам.</p>';
      this.weeklyReportEl.textContent = weeklyReportFallback || 'Ещё нет отчёта.';
      return;
    }
    const digest = insights.digest ? `<p>${FormattingUtils.escapeHtml(insights.digest)}</p>` : '';
    const unsubscribe = (insights.unsubscribe || [])
      .map((item) => `<li>${FormattingUtils.escapeHtml(item)}</li>`)
      .join('') || '<li class="muted">Нечего отключать</li>';
    const keep = (insights.keep || [])
      .map((item) => `<li>${FormattingUtils.escapeHtml(item)}</li>`)
      .join('') || '<li class="muted">Нет избранных рассылок</li>';
    const metrics =
      insights.metrics_used && Object.keys(insights.metrics_used).length
        ? `<div class="muted">Метрики: ${FormattingUtils.escapeHtml(JSON.stringify(insights.metrics_used))}</div>`
        : '';

    this.newsletterEl.innerHTML = `
    ${digest}
    <div><strong>Отписаться:</strong><ul class="insight-list">${unsubscribe}</ul></div>
    <div><strong>Оставить:</strong><ul class="insight-list">${keep}</ul></div>
    ${metrics}
  `;
    this.weeklyReportEl.textContent = insights.weekly_report || weeklyReportFallback || 'Ещё нет отчёта.';
  }

  renderAutoReplies(templates) {
    if (!templates || !templates.length) {
      this.autoReplyEl.innerHTML = '<p class="muted">Нет шаблонов. Агент подготовит их после анализа.</p>';
      return;
    }
    this.autoReplyEl.innerHTML = templates
      .map((template) => {
        const title = template.subject || template.notes || `Шаблон #${template.id || ''}`;
        const type = template.type ? `<span class="chip">${FormattingUtils.escapeHtml(template.type)}</span>` : '';
        const notes = template.notes ? `<div class="muted">${FormattingUtils.escapeHtml(template.notes)}</div>` : '';
        return `
        <div class="template-block">
          <div><strong>${FormattingUtils.escapeHtml(title)}</strong> ${type}</div>
          <code>${FormattingUtils.escapeHtml(template.template || '')}</code>
          ${notes}
        </div>
      `;
      })
      .join('');
  }
}

