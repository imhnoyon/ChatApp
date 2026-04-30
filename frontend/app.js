const DEFAULT_API_BASE = "http://127.0.0.1:8003";

const state = {
  apiBase: localStorage.getItem("chat_api_base") || DEFAULT_API_BASE,
  access: localStorage.getItem("chat_access") || "",
  refresh: localStorage.getItem("chat_refresh") || "",
  me: JSON.parse(localStorage.getItem("chat_me") || "null"),
  chats: [],
  activeUserId: Number(localStorage.getItem("chat_selected_user_id")) || null,
  activeConversationId: Number(localStorage.getItem("chat_conv_id")) || null,
  socket: null,
  socketConvId: null,
  manualSocketClose: false,
  reconnectTimer: null,
  renderedMessageIds: new Set(),
  stickToBottom: true,
};

const el = {
  authOverlay: document.getElementById("authOverlay"),
  showLoginBtn: document.getElementById("showLoginBtn"),
  showRegisterBtn: document.getElementById("showRegisterBtn"),
  logoutBtn: document.getElementById("logoutBtn"),
  loginForm: document.getElementById("loginForm"),
  registerForm: document.getElementById("registerForm"),
  reloadUsersBtn: document.getElementById("reloadUsersBtn"),
  usersList: document.getElementById("usersList"),
  chatWithTitle: document.getElementById("chatWithTitle"),
  onlineStatus: document.getElementById("onlineStatus"),
  messagesBox: document.getElementById("messagesBox"),
  typingText: document.getElementById("typingText"),
  messageForm: document.getElementById("messageForm"),
  messageInput: document.getElementById("messageInput"),
  toastWrap: document.getElementById("toastWrap"),
  backBtn: document.getElementById("backBtn"),
  shell: document.querySelector(".app-shell"),
  chatAvatar: document.getElementById("chatAvatar"),
  myAvatar: document.getElementById("myAvatar"),
};

init();

function init() {
  bindEvents();
  updateMePanel();
  if (state.access) bootstrapSession();
}

function bindEvents() {
  el.showLoginBtn.addEventListener("click", () => toggleAuthForm("login"));
  el.showRegisterBtn.addEventListener("click", () => toggleAuthForm("register"));
  el.logoutBtn.addEventListener("click", onLogout);
  el.loginForm.addEventListener("submit", onLogin);
  el.registerForm.addEventListener("submit", onRegister);
  el.reloadUsersBtn?.addEventListener("click", () => loadChats({ restoreSelection: true }));
  el.messageForm.addEventListener("submit", onSendMessage);
  el.messageInput.addEventListener("input", onTypingInput);
  el.messagesBox.addEventListener("scroll", onMessagesScroll);
  el.backBtn.addEventListener("click", () => el.shell.classList.remove("chat-open"));
}

function toggleAuthForm(mode) {
  const isLogin = mode === "login";
  el.loginForm.classList.toggle("hidden", !isLogin);
  el.registerForm.classList.toggle("hidden", isLogin);
  el.showLoginBtn.classList.toggle("active", isLogin);
  el.showRegisterBtn.classList.toggle("active", !isLogin);
}

async function bootstrapSession() {
  try {
    const meData = await apiCall("/api/auth/me/");
    state.me = meData?.data || meData;
    persistAuth();
    updateMePanel();
    await loadChats({ restoreSelection: true });
  } catch (_e) { resetSession(); }
}

async function onLogin(event) {
  event.preventDefault();
  const payload = {
    username: document.getElementById("loginUsername").value.trim(),
    password: document.getElementById("loginPassword").value,
  };
  try {
    const data = await apiCall("/api/auth/login/", { method: "POST", body: JSON.stringify(payload), noAuth: true });
    state.access = data?.access || data?.tokens?.access || data?.user?.access || "";
    state.refresh = data?.refresh || data?.tokens?.refresh || "";
    state.me = data?.user || data?.data || null;
    persistAuth();
    updateMePanel();
    toast("Welcome back!");
    await loadChats({ restoreSelection: true });
  } catch (e) { toast(e.message, true); }
}

async function onRegister(event) {
  event.preventDefault();
  const payload = {
    username: document.getElementById("regUsername").value.trim(),
    email: document.getElementById("regEmail").value.trim(),
    password: document.getElementById("regPassword").value,
    password2: document.getElementById("regPassword2").value,
  };
  try {
    await apiCall("/api/auth/register/", { method: "POST", body: JSON.stringify(payload), noAuth: true });
    toast("Account created! Please login.");
    toggleAuthForm("login");
  } catch (e) { toast(e.message, true); }
}

function onLogout() {
  resetSession();
  toast("Logged out");
}

function resetSession() {
  closeSocket(true);
  state.access = state.refresh = "";
  state.me = null;
  state.chats = [];
  state.activeUserId = state.activeConversationId = null;
  state.renderedMessageIds.clear();
  localStorage.clear();
  renderChats();
  updateMePanel();
  renderEmptyChat();
}

async function loadChats(options = {}) {
  if (!state.access) return;
  try {
    const data = await apiCall("/api/conversations/");
    state.chats = Array.isArray(data) ? data : (data?.data || []);
    renderChats();
    if (options.restoreSelection && state.activeUserId) restoreSelection();
  } catch (e) { toast(e.message, true); }
}

function renderChats() {
  el.usersList.innerHTML = "";
  state.chats.forEach(chat => {
    const user = chat.other_user;
    if (!user) return;
    const initials = (user.full_name || user.username).substring(0, 1).toUpperCase();
    const lastMsg = chat.last_message ? chat.last_message.text : "No messages yet";
    const time = chat.last_message ? formatServerDate(chat.last_message.created_at) : "";
    const unread = chat.unread_count || 0;

    const row = document.createElement("button");
    row.className = `conv-item ${state.activeConversationId === chat.id ? "active" : ""}`;
    row.innerHTML = `
      <div class="avatar">${escapeHtml(initials)}</div>
      <div class="conv-info">
        <div class="conv-top">
          <div class="conv-name">${escapeHtml(user.full_name || user.username)}</div>
          <div class="conv-time">${escapeHtml(time)}</div>
        </div>
        <div class="conv-bottom">
          <div class="conv-msg">${escapeHtml(lastMsg)}</div>
          ${unread > 0 ? `<div class="unread-badge">${unread}</div>` : ""}
        </div>
      </div>
    `;
    row.onclick = () => openConversation(chat.id, user);
    el.usersList.appendChild(row);
  });
}

function restoreSelection() {
  const found = state.chats.find(c => c.other_user?.id === state.activeUserId);
  if (found) openConversation(found.id, found.other_user, { restore: true });
}

async function openConversation(convId, user, options = {}) {
  state.activeUserId = user.id;
  state.activeConversationId = convId;
  localStorage.setItem("chat_selected_user_id", String(user.id));
  localStorage.setItem("chat_conv_id", String(convId));
  
  // Clear unread badge locally for immediate UX
  const chatIdx = state.chats.findIndex(c => c.id === convId);
  if (chatIdx !== -1) {
    state.chats[chatIdx].unread_count = 0;
    renderChats();
  }

  if (window.innerWidth <= 800) el.shell.classList.add("chat-open");

  el.chatWithTitle.textContent = user.full_name || user.username;
  el.onlineStatus.textContent = "offline";
  el.onlineStatus.classList.remove("online");
  el.chatAvatar.textContent = (user.full_name || user.username).substring(0, 1).toUpperCase();

  if (!options.restore) await loadMessages(convId);
  connectSocket(convId);
}

async function loadMessages(convId) {
  try {
    const list = await apiCall(`/api/conversations/${convId}/messages/`);
    state.renderedMessageIds.clear();
    el.messagesBox.innerHTML = "";
    (Array.isArray(list) ? list : []).forEach(m => appendMessage({
      id: m.id, text: m.text, sender_id: m.sender?.id, status: m.status, time: formatServerDate(m.created_at)
    }));
    scrollToBottom();
  } catch (e) { toast(e.message, true); }
}

function connectSocket(convId) {
  if (!state.access) return;
  if (state.socket?.readyState < 2 && state.socketConvId === convId) {
    if (state.socket.readyState === 1) state.socket.send(jsonStr({ action: "mark_read" }));
    return;
  }
  if (state.socket) closeSocket(true);
  state.socketConvId = convId;
  const ws = new WebSocket(buildWsUrl(`/ws/chat/${convId}/?token=${encodeURIComponent(state.access)}`));
  state.socket = ws;
  
  ws.onopen = () => {
    ws.send(jsonStr({ action: "mark_read" }));
    // Refresh chats after a short delay to ensure DB is updated
    setTimeout(() => loadChats(), 500);
  };
  ws.onmessage = (e) => handleSocketPayload(JSON.parse(e.data));
  ws.onclose = () => { 
    if (!state.manualSocketClose) setTimeout(() => connectSocket(convId), 3000); 
  };
}

function closeSocket(manual = true) {
  state.manualSocketClose = manual;
  state.socket?.close();
  state.socket = null;
}

function handleSocketPayload(p) {
  if (p.type === "message") {
    appendMessage(p);
    if (state.stickToBottom) scrollToBottom();
    if (p.sender_id !== state.me?.id) {
      state.socket.send(jsonStr({ action: "seen", message_id: p.id }));
      state.socket.send(jsonStr({ action: "mark_read" }));
    }
    loadChats();
  } else if (p.type === "typing") {
    el.typingText.textContent = p.is_typing ? "typing..." : "";
  } else if (p.type === "seen") {
    updateSeenStatus(p.message_id);
  } else if (p.type === "status") {
    if (p.user_id !== state.me?.id) {
      const isOnline = p.status === "online";
      el.onlineStatus.textContent = isOnline ? "online" : "offline";
      el.onlineStatus.classList.toggle("online", isOnline);
    }
  }
}

function onSendMessage(e) {
  e.preventDefault();
  const text = el.messageInput.value.trim();
  if (!text || state.socket?.readyState !== 1) return;
  state.socket.send(jsonStr({ action: "send_message", text }));
  el.messageInput.value = "";
}

function onTypingInput() {
  if (state.socket?.readyState !== 1) return;
  state.socket.send(jsonStr({ action: "typing", is_typing: true }));
  clearTimeout(state.typingTimer);
  state.typingTimer = setTimeout(() => state.socket?.send(jsonStr({ action: "typing", is_typing: false })), 1500);
}

function appendMessage(m) {
  const id = Number(m.id);
  if (id && state.renderedMessageIds.has(id)) return;
  if (id) state.renderedMessageIds.add(id);
  const mine = m.sender_id === state.me?.id;
  const row = document.createElement("div");
  row.className = `message ${mine ? "mine" : "other"}`;
  row.dataset.messageId = String(id || "");
  const time = m.time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  row.innerHTML = `
    <div class="msg-text">${escapeHtml(m.text || "")}</div>
    <div class="msg-meta">
      <span>${escapeHtml(time)}</span>
      ${mine ? `<span class="status-icon" style="color: ${m.status === 'seen' ? 'var(--seen-blue)' : 'inherit'}">${m.status === 'seen' ? '✓✓' : '✓'}</span>` : ""}
    </div>
  `;
  el.messagesBox.appendChild(row);
}

function onMessagesScroll() {
  const { scrollTop, scrollHeight, clientHeight } = el.messagesBox;
  state.stickToBottom = (scrollHeight - scrollTop - clientHeight) < 80;
}

// Throttled chat loading to prevent flickering when many seen events arrive
let loadChatsTimeout = null;
function throttledLoadChats() {
  if (loadChatsTimeout) return;
  loadChatsTimeout = setTimeout(() => {
    loadChats();
    loadChatsTimeout = null;
  }, 300);
}

function updateSeenStatus(mid) {
  const icon = el.messagesBox.querySelector(`[data-message-id='${mid}'] .status-icon`);
  if (icon) { 
    icon.textContent = "✓✓"; 
    icon.style.color = "var(--seen-blue)"; 
  }
  throttledLoadChats();
}

function renderEmptyChat() {
  el.messagesBox.innerHTML = `
    <div class="welcome-screen">
      <div class="welcome-center">
        <h1>WhatsApp Web</h1>
        <p>Send and receive messages without keeping your phone online.</p>
      </div>
    </div>
  `;
  el.onlineStatus.textContent = "";
  el.onlineStatus.classList.remove("online");
}

function updateMePanel() {
  const loggedIn = !!state.me;
  el.authOverlay.classList.toggle("hidden", loggedIn);
  if (loggedIn) el.myAvatar.textContent = state.me.username.substring(0, 1).toUpperCase();
}

async function apiCall(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (!options.noAuth && state.access) headers.Authorization = `Bearer ${state.access}`;
  const res = await fetch(`${state.apiBase}${path}`, { method: options.method || "GET", headers, body: options.body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.error || "Request failed");
  return data;
}

function buildWsUrl(p) { const u = new URL(state.apiBase); u.protocol = u.protocol === "https:" ? "wss:" : "ws:"; return `${u.origin}${p}`; }
function persistAuth() { localStorage.setItem("chat_access", state.access); localStorage.setItem("chat_refresh", state.refresh); localStorage.setItem("chat_me", JSON.stringify(state.me)); }
function formatServerDate(d) { return d ? new Date(d).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""; }
function scrollToBottom() { el.messagesBox.scrollTop = el.messagesBox.scrollHeight; }
function toast(t, e = false) { const i = document.createElement("div"); i.className = `toast${e ? " error" : ""}`; i.textContent = t; el.toastWrap.appendChild(i); setTimeout(() => i.remove(), 3000); }
function escapeHtml(v) { return String(v).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])); }
function jsonStr(o) { return JSON.stringify(o); }
