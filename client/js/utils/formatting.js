/**
 * Formatting utility functions
 */
import { DOMUtils } from './dom.js';

export class FormattingUtils {
  static escapeHtml(text) {
    return (text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  static formatEmailView(email) {
    if (!email) return 'Could not get message.';
    const accentLight = DOMUtils.getVar('--accent-light');
    const secondary = DOMUtils.getVar('--text-secondary');
    const bodyMain = DOMUtils.getVar('--text-main');
    let out = '';
    if (email.subject) {
      out += `<div style='font-size:1.09em;font-weight:700;margin-bottom:0.25em;color:${accentLight};'>${this.escapeHtml(email.subject)}</div>`;
    }
    if (email.from || email.date) {
      out += `<div style='color:${secondary};font-size:0.95em; margin-bottom:0.2em;'>`;
      if (email.from)
        out += `From: <span style='color:${accentLight};'>${this.escapeHtml(email.from)}</span>`;
      if (email.from && email.date) out += ' &nbsp; | &nbsp; ';
      if (email.date) out += `<span>${this.escapeHtml(email.date)}</span>`;
      out += `</div>`;
    }
    if (email.body) {
      out += `<div style='margin-top:0.7em;white-space:pre-line;line-height:1.6;color:${bodyMain};font-size:1.05em;'>${this.escapeHtml(email.body)}</div>`;
    }
    return out || 'Message received, but nothing to show.';
  }

  static parseSenderEmail(from) {
    const match = /<([^>]+)>/.exec(from || '');
    return match ? match[1] : (from || '').trim();
  }

  static parseSenderName(from) {
    if (!from) return '';
    const lt = from.indexOf('<');
    return lt > 0 ? from.slice(0, lt).trim().replace(/^"|"$/g, '') : from.trim();
  }
}
