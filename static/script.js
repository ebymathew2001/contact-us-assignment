// static/script.js

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}


// ════════════════════════════════════════════
// CHAT WIDGET (index.html)
// ════════════════════════════════════════════
const chatWidget   = document.getElementById('chat-widget');
const openChatBtn  = document.getElementById('open-chat');
const closeChatBtn = document.getElementById('close-chat');
const chatMessages = document.getElementById('chat-messages');
const chatInput    = document.getElementById('chat-input');
const sendBtn      = document.getElementById('send-btn');

if (chatWidget) {
  let sessionId = null;
  let chatStarted = false;
  let isComplete = false;

  openChatBtn.addEventListener('click', async () => {
    chatWidget.classList.add('open');
    if (!chatStarted) {
      chatStarted = true;
      sessionId = generateUUID();
      await startChat();
    }
  });

  closeChatBtn.addEventListener('click', () => {
    chatWidget.classList.remove('open');
  });

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener('click', sendMessage);

  async function startChat() {
    showTyping();
    try {
      const res = await fetch('/chat/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      const data = await res.json();
      removeTyping();
      appendMessage('bot', data.response);
    } catch (err) {
      removeTyping();
      appendMessage('bot', 'Sorry, could not connect. Please refresh and try again.');
    }
  }

  async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || isComplete) return;

    appendMessage('user', text);
    chatInput.value = '';
    setInputEnabled(false);
    showTyping();

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text })
      });
      const data = await res.json();
      removeTyping();
      appendMessage('bot', data.response);

      if (data.is_complete) {
        isComplete = true;
        chatInput.placeholder = 'Form submitted ✓';
      } else {
        setInputEnabled(true);
      }
    } catch (err) {
      removeTyping();
      appendMessage('bot', 'Something went wrong. Please try again.');
      setInputEnabled(true);
    }
  }

  function appendMessage(sender, text) {
    const div = document.createElement('div');
    div.classList.add('message', sender);
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function showTyping() {
    const el = document.createElement('div');
    el.classList.add('typing-indicator');
    el.id = 'typing';
    el.innerHTML = '<span></span><span></span><span></span>';
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeTyping() {
    const el = document.getElementById('typing');
    if (el) el.remove();
  }

  function setInputEnabled(enabled) {
    chatInput.disabled = !enabled;
    sendBtn.disabled = !enabled;
    if (enabled) chatInput.focus();
  }
}


// ════════════════════════════════════════════
// LOGS PAGE (logs.html)
// ════════════════════════════════════════════
const sessionsTbody = document.getElementById('sessions-tbody');

if (sessionsTbody) {
  let currentPage = 1;
  let totalPages = 1;
  let currentSessionId = null;

  loadSessions(1);

  async function loadSessions(page) {
    currentPage = page;
    try {
      const res = await fetch(`/logs?page=${page}&limit=10`);
      const data = await res.json();
      totalPages = data.total_pages;
      renderTable(data.sessions);
      updatePagination();
    } catch (err) {
      sessionsTbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted);padding:20px">Failed to load sessions.</td></tr>';
    }
  }

  function renderTable(sessions) {
    if (!sessions || sessions.length === 0) {
      sessionsTbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted);padding:20px">No sessions found.</td></tr>';
      return;
    }
    sessionsTbody.innerHTML = sessions.map(s => `
      <tr>
        <td><span class="session-id-text" title="${s.session_id}">${s.session_id}</span></td>
        <td><span class="status-badge ${s.status === 'Completed' ? 'completed' : 'incomplete'}">${s.status}</span></td>
        <td>${new Date(s.created_at).toLocaleString()}</td>
        <td><button class="view-btn" onclick="openPopup('${s.session_id}')">View</button></td>
      </tr>
    `).join('');
  }

  function updatePagination() {
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
    document.getElementById('prev-btn').disabled = currentPage <= 1;
    document.getElementById('next-btn').disabled = currentPage >= totalPages;
  }

  window.changePage = function(direction) {
    const newPage = currentPage + direction;
    if (newPage >= 1 && newPage <= totalPages) loadSessions(newPage);
  };

  window.openPopup = async function(sessionId) {
    currentSessionId = sessionId;
    document.getElementById('popup-session-label').textContent = `Session: ${sessionId.slice(0, 18)}...`;
    document.getElementById('popup-overlay').classList.add('active');
    // Reset to first tab
    document.querySelectorAll('.tab-btn').forEach((b, i) => b.classList.toggle('active', i === 0));
    document.querySelectorAll('.tab-content').forEach((t, i) => t.classList.toggle('active', i === 0));
    await loadConversation(sessionId);
  };

  window.closePopup = function() {
    document.getElementById('popup-overlay').classList.remove('active');
  };

  document.getElementById('popup-overlay').addEventListener('click', function(e) {
    if (e.target === this) closePopup();
  });

  window.switchTab = async function(tabName, btn) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');
    if (!currentSessionId) return;
    if (tabName === 'conversation') await loadConversation(currentSessionId);
    if (tabName === 'errors') await loadErrors(currentSessionId);
    if (tabName === 'details') await loadDetails(currentSessionId);
  };

  async function loadConversation(sessionId) {
    const el = document.getElementById('convo-body');
    el.innerHTML = 'Loading...';
    try {
      const res = await fetch(`/logs/${sessionId}/conversation`);
      const messages = await res.json();
      if (!messages || messages.length === 0) {
        el.innerHTML = '<p class="empty-msg">No messages found.</p>';
        return;
      }
      el.innerHTML = messages.map(m => `
        <div class="convo-message">
          <div class="convo-sender ${m.sender}">${m.sender.toUpperCase()}</div>
          <div>${m.message}</div>
        </div>
      `).join('');
    } catch (err) {
      el.innerHTML = '<p class="empty-msg">Failed to load conversation.</p>';
    }
  }

  async function loadErrors(sessionId) {
    const el = document.getElementById('errors-body');
    el.innerHTML = 'Loading...';
    try {
      const res = await fetch(`/logs/${sessionId}/errors`);
      const errors = await res.json();
      if (!errors || errors.length === 0) {
        el.innerHTML = '<p class="empty-msg">No errors found for this session.</p>';
        return;
      }
      el.innerHTML = `
        <table class="error-table">
          <thead><tr><th>Time</th><th>Node</th><th>Error Type</th><th>Message</th></tr></thead>
          <tbody>
            ${errors.map(e => `
              <tr>
                <td>${new Date(e.timestamp).toLocaleTimeString()}</td>
                <td>${e.node}</td>
                <td>${e.error_type}</td>
                <td>${e.message}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (err) {
      el.innerHTML = '<p class="empty-msg">Failed to load errors.</p>';
    }
  }

  async function loadDetails(sessionId) {
    const el = document.getElementById('details-body');
    el.innerHTML = 'Loading...';
    try {
      const res = await fetch(`/logs/${sessionId}/details`);
      const data = await res.json();
      if (!data) {
        el.innerHTML = '<p class="empty-msg">Form was not fully submitted.</p>';
        return;
      }
      el.innerHTML = `
        <div class="details-grid">
          <div class="detail-row"><span class="detail-label">Name</span><span class="detail-value">${data.name}</span></div>
          <div class="detail-row"><span class="detail-label">Email</span><span class="detail-value">${data.email}</span></div>
          <div class="detail-row"><span class="detail-label">Phone</span><span class="detail-value">${data.phone}</span></div>
          <div class="detail-row"><span class="detail-label">Message</span><span class="detail-value">${data.message}</span></div>
        </div>
      `;
    } catch (err) {
      el.innerHTML = '<p class="empty-msg">Failed to load details.</p>';
    }
  }
}