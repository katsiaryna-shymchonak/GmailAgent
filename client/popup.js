const themeBtn = document.getElementById('theme-toggle');
const senderListEl = document.getElementById('sender-list');
const emailListEl = document.getElementById('email-list');
const sendToAiBtn = document.getElementById('send-to-ai');
const detailPanel = document.getElementById('detail-panel');
const spinner = document.getElementById('spinner');
const conversationPanel = document.getElementById('conversation-panel');
const conversationToggle = document.getElementById('conversation-toggle');
const conversationToggleIcon = document.getElementById('conversation-toggle-icon');
const conversationBody = document.getElementById('conversation-body');
const conversationLogEl = document.getElementById('conversation-log');
const conversationInput = document.getElementById('conversation-input');
const conversationSendBtn = document.getElementById('conversation-send');
const weeklySummaryBtn = document.getElementById('weekly-summary-btn');
const filterContentEl = document.getElementById('filter-content');
const newsletterContentEl = document.getElementById('newsletter-content');
const weeklyReportEl = document.getElementById('weekly-report');
const autoReplyContentEl = document.getElementById('auto-reply-content');
const agentTipEl = document.getElementById('agent-tip');

let lastEmailResponse = null;
let selectedIds = new Set();
let currentList = [];
let activeSenderKey = '';
let conversationOpen = false;
let lastSelectedMessagesDetails = [];
let lastAgentInsights = null;
let activeToolContext = [];
const messageDetailCache = new Map();
const API_BASE_URL = 'http://localhost:8000';

function setListLoading(isLoading) {
  spinner.style.display = isLoading ? 'block' : 'none';
}

function getVar(variable) {
  return getComputedStyle(document.body).getPropertyValue(variable).trim();
}

function formatEmailView(email) {
  if (!email) return 'Could not get message.';
  const accentLight = getVar('--accent-light');
  const secondary = getVar('--text-secondary');
  const bodyMain = getVar('--text-main');
  let out = '';
  if (email.subject) {
    out += `<div style='font-size:1.09em;font-weight:700;margin-bottom:0.25em;color:${accentLight};'>${escapeHtml(email.subject)}</div>`;
  }
  if (email.from || email.date) {
    out += `<div style='color:${secondary};font-size:0.95em; margin-bottom:0.2em;'>`;
    if (email.from) out += `From: <span style='color:${accentLight};'>${escapeHtml(email.from)}</span>`;
    if (email.from && email.date) out += ' &nbsp; | &nbsp; ';
    if (email.date) out += `<span>${escapeHtml(email.date)}</span>`;
    out += `</div>`;
  }
  if (email.body) {
    out += `<div style='margin-top:0.7em;white-space:pre-line;line-height:1.6;color:${bodyMain};font-size:1.05em;'>${escapeHtml(email.body)}</div>`;
  }
  return out || 'Message received, but nothing to show.';
}

function escapeHtml(text) {
  return (text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function applyTheme(theme) {
  if (theme === 'light') {
    document.body.classList.add('light');
    themeBtn.textContent = '🌞';
    themeBtn.title = 'Switch to dark mode';
  } else {
    document.body.classList.remove('light');
    themeBtn.textContent = '🌙';
    themeBtn.title = 'Switch to light mode';
  }
  if (lastEmailResponse && (lastEmailResponse.body || lastEmailResponse.subject)) {
    detailPanel.innerHTML = formatEmailView(lastEmailResponse);
  }
}

function initializeTheme() {
  let theme = localStorage.getItem('gmail_agent_theme');
  if (!theme) {
    theme = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  applyTheme(theme);
  themeBtn.setAttribute('aria-label', `Switch to ${theme === 'light' ? 'dark' : 'light'} mode`);
}

themeBtn.addEventListener('click', () => {
  const isLight = document.body.classList.contains('light');
  const newTheme = isLight ? 'dark' : 'light';
  localStorage.setItem('gmail_agent_theme', newTheme);
  applyTheme(newTheme);
  themeBtn.setAttribute('aria-label', `Switch to ${isLight ? 'light' : 'dark'} mode`);
});

document.addEventListener('DOMContentLoaded', () => {
  initializeTheme();
  loadSenders();
  setupConversationPanel();
  if (weeklySummaryBtn) {
    weeklySummaryBtn.addEventListener('click', requestWeeklySummary);
  }
});

function loadSenders() {
  senderListEl.textContent = 'Loading senders...';
  setListLoading(true);
  chrome.runtime.sendMessage({ action: 'listSenders', maxResults: 100 }, resp => {
    setListLoading(false);
    if (!resp || resp.error) {
      senderListEl.textContent = resp?.error || 'Failed to load senders.';
      return;
    }
    renderSenders(resp.senders || []);
  });
}

function renderSenders(senders) {
  if (!senders.length) {
    senderListEl.textContent = 'No senders found.';
    return;
  }
  const wrap = document.createElement('div');
  senders.forEach(s => {
    const row = document.createElement('div');
    row.className = 'sender-item';
    const left = document.createElement('div');
    const name = document.createElement('div');
    name.className = 'sender-name';
    name.textContent = parseSenderName(s.from);
    const email = document.createElement('div');
    email.className = 'sender-email';
    email.textContent = parseSenderEmail(s.from);
    left.appendChild(name);
    left.appendChild(email);
    const cnt = document.createElement('div');
    cnt.className = 'sender-count';
    cnt.textContent = s.count;
    row.appendChild(left);
    row.appendChild(cnt);
    row.addEventListener('click', () => selectSender(row, s.from));
    wrap.appendChild(row);
  });
  senderListEl.innerHTML = '';
  senderListEl.appendChild(wrap);
}

function selectSender(rowEl, fromValue) {
  Array.from(senderListEl.querySelectorAll('.sender-item')).forEach(r => r.classList.remove('active'));
  rowEl.classList.add('active');
  activeSenderKey = fromValue;
  emailListEl.textContent = 'Loading messages...';
  selectedIds.clear();
  updateControlsState();
  chrome.runtime.sendMessage(
    { action: 'searchMessagesBySender', sender: parseSenderEmail(fromValue), maxResults: 20 },
    resp => {
      if (!resp || resp.error) {
        emailListEl.textContent = resp?.error || 'Failed to load messages.';
        return;
      }
      renderList(resp.messages || []);
    }
  );
}

function renderList(messages) {
  currentList = messages || [];
  selectedIds.clear();
  updateControlsState();
  emailListEl.innerHTML = '';
  if (!messages || messages.length === 0) {
    emailListEl.textContent = 'No messages found for this sender.';
    return;
  }
  const header = document.createElement('div');
  header.className = 'email-list-header';
  const selectAll = document.createElement('input');
  selectAll.type = 'checkbox';
  selectAll.id = 'select-all';
  selectAll.disabled = currentList.length === 0;
  const label = document.createElement('label');
  label.setAttribute('for', 'select-all');
  label.textContent = 'Select all';
  header.appendChild(selectAll);
  header.appendChild(label);
  emailListEl.appendChild(header);

  const container = document.createElement('div');
  for (const m of messages) {
    const row = document.createElement('div');
    row.className = 'email-list-item';
    row.dataset.id = m.id;
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'email-checkbox';
    cb.addEventListener('click', e => {
      e.stopPropagation();
      if (cb.checked) selectedIds.add(m.id);
      else selectedIds.delete(m.id);
      updateControlsState();
      setSelectAllState(selectAll);
    });
    const info = document.createElement('div');
    info.className = 'email-list-info';
    const subj = document.createElement('div');
    subj.className = 'email-list-subject';
    subj.textContent = m.subject || '(no subject)';
    const meta = document.createElement('div');
    meta.className = 'email-list-meta';
    meta.textContent = `${m.from || ''}  •  ${m.date || ''}`;
    const snip = document.createElement('div');
    snip.className = 'email-list-snippet';
    snip.textContent = m.snippet || '';
    info.appendChild(subj);
    info.appendChild(meta);
    info.appendChild(snip);
    row.appendChild(cb);
    row.appendChild(info);
    row.addEventListener('click', () => previewMessage(m.id));
    container.appendChild(row);
  }
  emailListEl.appendChild(container);

  selectAll.addEventListener('change', () => {
    if (currentList.length === 0) return;
    const check = selectAll.checked;
    selectedIds.clear();
    const boxes = emailListEl.querySelectorAll('.email-checkbox');
    boxes.forEach((box, idx) => {
      box.checked = check;
      if (check) selectedIds.add(currentList[idx].id);
    });
    updateControlsState();
    setSelectAllState(selectAll);
  });
  setSelectAllState(selectAll);
}

function setSelectAllState(selectAllEl) {
  if (!selectAllEl) return;
  if (currentList.length === 0) {
    selectAllEl.checked = false;
    selectAllEl.indeterminate = false;
    return;
  }
  const total = currentList.length;
  const selected = selectedIds.size;
  selectAllEl.checked = selected === total && total > 0;
  selectAllEl.indeterminate = selected > 0 && selected < total;
}

function updateControlsState() {
  sendToAiBtn.disabled = selectedIds.size === 0;
}

function previewMessage(id) {
  detailPanel.textContent = 'Loading message...';
  fetchMessageDetail(id)
    .then(msg => {
      lastEmailResponse = msg;
      detailPanel.innerHTML = formatEmailView(msg);
    })
    .catch(err => {
      detailPanel.textContent = err.message || 'Failed to load message.';
    });
}

function parseSenderEmail(from) {
  const match = /<([^>]+)>/.exec(from || '');
  return match ? match[1] : (from || '').trim();
}
function parseSenderName(from) {
  if (!from) return '';
  const lt = from.indexOf('<');
  return lt > 0 ? from.slice(0, lt).trim().replace(/^"|"$/g, '') : from.trim();
}

function fetchMessageDetail(id) {
  if (messageDetailCache.has(id)) {
    return Promise.resolve(messageDetailCache.get(id));
  }
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ action: 'getMessageById', id }, resp => {
      if (!resp || resp.error) {
        reject(new Error(resp?.error || 'Failed to load message.'));
        return;
      }
      const message = resp.message || resp;
      messageDetailCache.set(id, message);
      resolve(message);
    });
  });
}

async function gatherSelectedMessages() {
  const details = [];
  for (const id of selectedIds) {
    const msg = await fetchMessageDetail(id);
    details.push({
      id,
      subject: msg.subject || '',
      snippet: msg.snippet || '',
      from: msg.from || parseSenderEmail(activeSenderKey),
      body: msg.body || msg.snippet || '',
    });
  }
  return details;
}

function setupConversationPanel() {
  conversationToggle.addEventListener('click', () => {
    conversationOpen = !conversationOpen;
    updateConversationVisibility();
  });
  conversationSendBtn.addEventListener('click', () => sendFollowUp());
  updateConversationVisibility();
}

function updateConversationVisibility() {
  conversationToggle.setAttribute('aria-expanded', conversationOpen.toString());
  conversationToggleIcon.textContent = conversationOpen ? '▲' : '▼';
  conversationBody.style.display = conversationOpen ? 'flex' : 'none';
}

function openConversationPanel() {
  if (!conversationOpen) {
    conversationOpen = true;
    updateConversationVisibility();
  }
}

function appendConversationEntry(role, text, toolTip) {
  const entry = document.createElement('div');
  entry.className = 'conversation-entry';
  const safeText = escapeHtml(text);
  entry.innerHTML = `<strong>${escapeHtml(role)}:</strong> ${safeText}`;
  if (toolTip) {
    entry.innerHTML += `<div class="muted">${escapeHtml(toolTip)}</div>`;
  }
  conversationLogEl.appendChild(entry);
  conversationLogEl.scrollTop = conversationLogEl.scrollHeight;
}

async function sendSelectedToAi() {
  if (!selectedIds.size) return;
  sendToAiBtn.disabled = true;
  conversationSendBtn.disabled = true;
  appendConversationEntry('System', 'Preparing selected emails...');
  openConversationPanel();

  try {
    const messages = await gatherSelectedMessages();
    lastSelectedMessagesDetails = messages;
    const payload = {
      query: 'Summarize the selected emails and highlight key points.',
      sender_email: parseSenderEmail(activeSenderKey) || null,
      messages,
    };
    appendConversationEntry('System', 'Analyzing with AI agent...');
    const response = await fetch(`${API_BASE_URL}/analyze/emails`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend error (${response.status}): ${errorText || 'Unknown error'}`);
    }
    const data = await response.json();
    renderAgentMessages(data);
    updateAgentInsights(data);
    lastAgentInsights = data;
    conversationSendBtn.disabled = false;
    conversationInput.placeholder = 'Ask follow-up question...';
  } catch (error) {
    let errorMsg = error.message || 'Failed to contact AI agent.';
    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
      errorMsg = `Cannot reach backend at ${API_BASE_URL}. Is the server running? Check: uvicorn main:app --reload --port 8000`;
    }
    appendConversationEntry('Error', errorMsg);
  } finally {
    sendToAiBtn.disabled = selectedIds.size === 0;
    conversationSendBtn.disabled = false;
  }
}

async function sendFollowUp() {
  const query = conversationInput.value.trim();
  if (!query) return;
  conversationSendBtn.disabled = true;
  appendConversationEntry('You', query);
  conversationInput.value = '';
  try {
    const messages = lastSelectedMessagesDetails.length ? lastSelectedMessagesDetails : [];
    const payload = {
      query,
      sender_email: parseSenderEmail(activeSenderKey) || null,
      messages,
    };
    const response = await fetch(`${API_BASE_URL}/analyze/emails`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend error (${response.status}): ${errorText || 'Unknown error'}`);
    }
    const data = await response.json();
    renderAgentMessages(data);
    updateAgentInsights(data);
    lastAgentInsights = data;
  } catch (error) {
    let errorMsg = error.message || 'Failed to contact AI agent.';
    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
      errorMsg = `Cannot reach backend at ${API_BASE_URL}. Is the server running?`;
    }
    appendConversationEntry('Error', errorMsg);
  } finally {
    conversationSendBtn.disabled = false;
    conversationInput.focus();
  }
}

sendToAiBtn.addEventListener('click', () => {
  sendSelectedToAi();
});

function requestWeeklySummary() {
  appendConversationEntry('System', 'Загрузка писем за неделю из Gmail...');
  openConversationPanel();
  conversationSendBtn.disabled = true;
  
  // First, fetch messages from Gmail API for the past week
  chrome.runtime.sendMessage({ action: 'getWeeklyMessages', maxResults: 500 }, (gmailResp) => {
    if (!gmailResp || gmailResp.error) {
      appendConversationEntry('Error', gmailResp?.error || 'Не удалось загрузить письма из Gmail.');
      conversationSendBtn.disabled = false;
      return;
    }
    
    const messages = gmailResp.messages || [];
    if (messages.length === 0) {
      appendConversationEntry('System', 'За последнюю неделю писем не найдено.');
      conversationSendBtn.disabled = false;
      return;
    }
    
    appendConversationEntry('System', `Загружено ${messages.length} писем. Отправка агенту...`);
    
    // Send messages to backend for analysis
    fetch(`${API_BASE_URL}/analyze/weekly`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        query: 'Сформируй недельный отчёт',
        messages: messages
      }),
    })
      .then(async resp => {
        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(`Backend error (${resp.status}): ${text || 'Unknown error'}`);
        }
        return resp.json();
      })
      .then(data => {
        renderAgentMessages(data);
        updateAgentInsights(data);
        lastAgentInsights = data;
      })
      .catch(error => {
        appendConversationEntry('Error', error.message || 'Не удалось получить отчёт.');
      })
      .finally(() => {
        conversationSendBtn.disabled = false;
      });
  });
}

function updateAgentInsights(data) {
  if (!data) {
    renderFilterResults([]);
    renderNewsletterInsights({});
    renderAutoReplies([]);
    weeklyReportEl.textContent = 'Ещё нет отчёта.';
    return;
  }
  renderFilterResults(data.filter_results || []);
  renderNewsletterInsights(data.newsletter_insights || {}, data.weekly_report);
  renderAutoReplies(data.auto_replies || []);
  if (data.weekly_report) {
    weeklyReportEl.textContent = data.weekly_report;
  }
  if (data.capabilities_tip && agentTipEl) {
    agentTipEl.textContent = data.capabilities_tip;
  }
}

function renderAgentMessages(data) {
  if (data && Array.isArray(data.messages) && data.messages.length) {
    data.messages.forEach(msg => {
      appendConversationEntry(
        msg.role === 'system' ? 'System' : msg.role === 'user' ? 'You' : 'Agent',
        msg.content || '',
        msg.tool
      );
    });
  } else {
    appendConversationEntry('Agent', data?.summary || 'No summary returned.', summarizeToolUsage(data));
  }
}

function renderFilterResults(items) {
  if (!items || !items.length) {
    filterContentEl.innerHTML = '<p class="muted">Нет данных. Отправьте письма агенту.</p>';
    return;
  }
  filterContentEl.innerHTML = items
    .map(item => {
      const tags = (item.tags || [])
        .map(tag => `<span class="chip">${escapeHtml(tag)}</span>`)
        .join('') || '<span class="muted">Нет тегов</span>';
      const actions = (item.actions || [])
        .map(action => `<li>${escapeHtml(action)}</li>`)
        .join('') || '<li class="muted">Нет действий</li>';
      const subject = item.subject || item.notes || item.id || 'Письмо';
      const type = item.type ? `<span class="chip">${escapeHtml(item.type)}</span>` : '';
      const priority = item.priority ? escapeHtml(item.priority) : 'normal';
      const replyText = item.requires_reply ? 'Нужен ответ' : 'Информационное';
      const notes = item.notes ? `<div class="muted">${escapeHtml(item.notes)}</div>` : '';
      return `
        <div class="insight-item">
          <div><strong>${escapeHtml(subject)}</strong> ${type}</div>
          <div class="muted">Приоритет: ${priority} • ${replyText}</div>
          <div>${tags}</div>
          <ul class="insight-list">${actions}</ul>
          ${notes}
        </div>`;
    })
    .join('');
}

function renderNewsletterInsights(insights, weeklyReportFallback) {
  if (!insights || Object.keys(insights).length === 0) {
    newsletterContentEl.innerHTML = '<p class="muted">Нет рекомендаций по рассылкам.</p>';
    weeklyReportEl.textContent = weeklyReportFallback || 'Ещё нет отчёта.';
    return;
  }
  const digest = insights.digest ? `<p>${escapeHtml(insights.digest)}</p>` : '';
  const unsubscribe = (insights.unsubscribe || [])
    .map(item => `<li>${escapeHtml(item)}</li>`)
    .join('') || '<li class="muted">Нечего отключать</li>';
  const keep = (insights.keep || [])
    .map(item => `<li>${escapeHtml(item)}</li>`)
    .join('') || '<li class="muted">Нет избранных рассылок</li>';
  const metrics =
    insights.metrics_used && Object.keys(insights.metrics_used).length
      ? `<div class="muted">Метрики: ${escapeHtml(JSON.stringify(insights.metrics_used))}</div>`
      : '';

  newsletterContentEl.innerHTML = `
    ${digest}
    <div><strong>Отписаться:</strong><ul class="insight-list">${unsubscribe}</ul></div>
    <div><strong>Оставить:</strong><ul class="insight-list">${keep}</ul></div>
    ${metrics}
  `;
  weeklyReportEl.textContent = insights.weekly_report || weeklyReportFallback || 'Ещё нет отчёта.';
}

function renderAutoReplies(templates) {
  if (!templates || !templates.length) {
    autoReplyContentEl.innerHTML = '<p class="muted">Нет шаблонов. Агент подготовит их после анализа.</p>';
    return;
  }
  autoReplyContentEl.innerHTML = templates
    .map(template => {
      const title = template.subject || template.notes || `Шаблон #${template.id || ''}`;
      const type = template.type ? `<span class="chip">${escapeHtml(template.type)}</span>` : '';
      const notes = template.notes ? `<div class="muted">${escapeHtml(template.notes)}</div>` : '';
      return `
        <div class="template-block">
          <div><strong>${escapeHtml(title)}</strong> ${type}</div>
          <code>${escapeHtml(template.template || '')}</code>
          ${notes}
        </div>
      `;
    })
    .join('');
}

function summarizeToolUsage(data) {
  if (!data) return '';
  const used = [];
  if (data.filter_results && data.filter_results.length) used.push('Фильтрация');
  if (data.newsletter_insights && Object.keys(data.newsletter_insights).length) used.push('Рассылки');
  if (data.auto_replies && data.auto_replies.length) used.push('Автоответы');
  if (data.key_tasks && data.key_tasks.length) used.push('Задачи');
  if (!used.length) return '';
  return `Использовано: ${used.join(', ')}`;
}
