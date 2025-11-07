const themeBtn = document.getElementById('theme-toggle');
const senderListEl = document.getElementById('sender-list');
const emailListEl = document.getElementById('email-list');
const sendToAiBtn = document.getElementById('send-to-ai');
const detailPanel = document.getElementById('detail-panel');
const spinner = document.getElementById('spinner');
let lastEmailResponse = null;
let selectedIds = new Set();
let currentList = [];
let activeSenderKey = '';

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
  chrome.runtime.sendMessage({ action: 'searchMessagesBySender', sender: parseSenderEmail(fromValue), maxResults: 20 }, resp => {
    if (!resp || resp.error) {
      emailListEl.textContent = resp?.error || 'Failed to load messages.';
      return;
    }
    renderList(resp.messages || []);
  });
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
  chrome.runtime.sendMessage({ action: 'getMessageById', id }, resp => {
    if (!resp || resp.error) {
      detailPanel.textContent = resp?.error || 'Failed to load message.';
      return;
    }
    lastEmailResponse = resp.message;
    detailPanel.innerHTML = formatEmailView(resp.message);
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

sendToAiBtn.addEventListener('click', () => {
  alert(`Sending ${selectedIds.size} selected email(s) to AI from ${parseSenderEmail(activeSenderKey)}...`);
});
