const state = {
    apiBase: localStorage.getItem("chat_api_base") || "http://127.0.0.1:8000",
    access: localStorage.getItem("chat_access") || "",
    refresh: localStorage.getItem("chat_refresh") || "",
    me: JSON.parse(localStorage.getItem("chat_me") || "null"),
    users: [],
    selectedUser: null,
    currentConversationId: null,
    socket: null,
    typingTimeout: null,
};

const el = {
    apiBase: document.getElementById("apiBase"),
    showLoginBtn: document.getElementById("showLoginBtn"),
    showRegisterBtn: document.getElementById("showRegisterBtn"),
    logoutBtn: document.getElementById("logoutBtn"),
    loginForm: document.getElementById("loginForm"),
    registerForm: document.getElementById("registerForm"),
    reloadUsersBtn: document.getElementById("reloadUsersBtn"),
    meInfo: document.getElementById("meInfo"),
    usersList: document.getElementById("usersList"),
    chatWithTitle: document.getElementById("chatWithTitle"),
    chatMeta: document.getElementById("chatMeta"),
    socketStatus: document.getElementById("socketStatus"),
    messagesBox: document.getElementById("messagesBox"),
    typingText: document.getElementById("typingText"),
    messageForm: document.getElementById("messageForm"),
    messageInput: document.getElementById("messageInput"),
    toastWrap: document.getElementById("toastWrap"),
};

init();

function init() {
    el.apiBase.value = state.apiBase;
    bindEvents();
    if (state.access) {
        loadMeAndUsers();
    }
    updateMePanel();
}

function bindEvents() {
    el.apiBase.addEventListener("change", () => {
        state.apiBase = normalizeBase(el.apiBase.value);
        el.apiBase.value = state.apiBase;
        localStorage.setItem("chat_api_base", state.apiBase);
    });

    el.showLoginBtn.addEventListener("click", () => toggleAuthForm("login"));
    el.showRegisterBtn.addEventListener("click", () => toggleAuthForm("register"));
    el.logoutBtn.addEventListener("click", logout);

    el.loginForm.addEventListener("submit", onLogin);
    el.registerForm.addEventListener("submit", onRegister);
    el.reloadUsersBtn.addEventListener("click", () => loadUsers());

    el.messageForm.addEventListener("submit", onSendMessage);
    el.messageInput.addEventListener("input", onTypingInput);
}

function toggleAuthForm(mode) {
    const login = mode === "login";
    el.loginForm.classList.toggle("d-none", !login);
    el.registerForm.classList.toggle("d-none", login);
    el.showLoginBtn.classList.toggle("active", login);
    el.showRegisterBtn.classList.toggle("active", !login);
}

async function onLogin(event) {
    event.preventDefault();
    const payload = {
        username: document.getElementById("loginUsername").value.trim(),
        password: document.getElementById("loginPassword").value,
    };

    try {
        const data = await apiCall("/api/auth/login/", {
            method: "POST",
            body: JSON.stringify(payload),
            noAuth: true,
        });

        const access = data?.access || data?.tokens?.access || data?.user?.access || "";
        const refresh = data?.refresh || data?.tokens?.refresh || "";
        const me = data?.user || data?.data || null;

        if (!access) {
            throw new Error("Login success but access token missing");
        }

        state.access = access;
        state.refresh = refresh;
        state.me = me;
        persistAuth();
        updateMePanel();
        toast("Login successful");
        await loadUsers();
    } catch (error) {
        toast(error.message || "Login failed");
    }
}

async function onRegister(event) {
    event.preventDefault();
    const payload = {
        username: document.getElementById("regUsername").value.trim(),
        email: document.getElementById("regEmail").value.trim(),
        first_name: document.getElementById("regFirstName").value.trim(),
        last_name: document.getElementById("regLastName").value.trim(),
        password: document.getElementById("regPassword").value,
        password2: document.getElementById("regPassword2").value,
    };

    try {
        await apiCall("/api/auth/register/", {
            method: "POST",
            body: JSON.stringify(payload),
            noAuth: true,
        });
        toast("Registration complete. Login now.");
        toggleAuthForm("login");
    } catch (error) {
        toast(error.message || "Registration failed");
    }
}

function logout() {
    closeSocket();
    state.access = "";
    state.refresh = "";
    state.me = null;
    state.selectedUser = null;
    state.currentConversationId = null;
    state.users = [];
    localStorage.removeItem("chat_access");
    localStorage.removeItem("chat_refresh");
    localStorage.removeItem("chat_me");
    el.usersList.innerHTML = "";
    el.messagesBox.innerHTML = "";
    el.chatWithTitle.textContent = "No conversation selected";
    el.chatMeta.textContent = "Select a user to start chatting";
    updateMePanel();
    setSocketStatus(false);
    toast("Logged out");
}

async function loadMeAndUsers() {
    try {
        const meData = await apiCall("/api/auth/me/");
        state.me = meData?.data || meData;
        persistAuth();
        updateMePanel();
        await loadUsers();
    } catch (_error) {
        logout();
    }
}

async function loadUsers() {
    if (!state.access) {
        toast("Please login first");
        return;
    }

    try {
        const usersData = await apiCall("/api/users/");
        state.users = Array.isArray(usersData) ? usersData : (usersData?.data || []);
        renderUsers();
        toast("Users loaded");
    } catch (error) {
        toast(error.message || "Failed to load users");
    }
}

function renderUsers() {
    el.usersList.innerHTML = "";

    if (!state.users.length) {
        const empty = document.createElement("div");
        empty.className = "text-soft small";
        empty.textContent = "No users found";
        el.usersList.appendChild(empty);
        return;
    }

    for (const user of state.users) {
        const item = document.createElement("button");
        item.className = "list-group-item user-item";
        item.innerHTML = `
      <div class="d-flex justify-content-between align-items-start gap-2">
        <div>
          <div class="fw-semibold">${escapeHtml(user.full_name || user.username)}</div>
          <div class="small text-soft">@${escapeHtml(user.username)}</div>
        </div>
        <span class="badge text-bg-light">id:${user.id}</span>
      </div>
    `;

        item.addEventListener("click", () => selectUser(user));
        el.usersList.appendChild(item);
    }
}

async function selectUser(user) {
    if (!state.access) {
        toast("Please login first");
        return;
    }

    state.selectedUser = user;
    highlightSelectedUser();

    try {
        const conv = await apiCall(`/api/conversations/start/${user.id}/`, {
            method: "POST",
            body: JSON.stringify({}),
        });

        state.currentConversationId = conv.id;
        el.chatWithTitle.textContent = `Chat with ${user.full_name || user.username}`;
        el.chatMeta.textContent = `Conversation #${conv.id}`;

        await loadMessages(conv.id);
        connectSocket(conv.id);
    } catch (error) {
        toast(error.message || "Failed to open conversation");
    }
}

function highlightSelectedUser() {
    const items = el.usersList.querySelectorAll(".user-item");
    items.forEach((it) => it.classList.remove("active"));

    if (!state.selectedUser) {
        return;
    }

    const index = state.users.findIndex((u) => u.id === state.selectedUser.id);
    if (index >= 0 && items[index]) {
        items[index].classList.add("active");
    }
}

async function loadMessages(convId) {
    try {
        const messages = await apiCall(`/api/conversations/${convId}/messages/`);
        el.messagesBox.innerHTML = "";
        for (const message of messages) {
            appendMessage({
                id: message.id,
                text: message.text,
                sender_id: message.sender.id,
                sender_name: message.sender.username,
                status: message.status,
                time: formatServerDate(message.created_at),
            });
        }
        scrollToBottom();
    } catch (error) {
        toast(error.message || "Failed to load messages");
    }
}

function onSendMessage(event) {
    event.preventDefault();
    const text = el.messageInput.value.trim();

    if (!text) {
        return;
    }

    if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
        toast("Socket not connected");
        return;
    }

    state.socket.send(JSON.stringify({
        action: "send_message",
        text,
    }));
    el.messageInput.value = "";
}

function onTypingInput() {
    if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
        return;
    }

    state.socket.send(JSON.stringify({
        action: "typing",
        is_typing: true,
    }));

    clearTimeout(state.typingTimeout);
    state.typingTimeout = setTimeout(() => {
        if (state.socket && state.socket.readyState === WebSocket.OPEN) {
            state.socket.send(JSON.stringify({
                action: "typing",
                is_typing: false,
            }));
        }
    }, 800);
}

function connectSocket(convId) {
    closeSocket();

    if (!state.access) {
        toast("Missing access token. Please login again.");
        return;
    }

    const wsUrl = buildWsUrl(`/ws/chat/${convId}/?token=${encodeURIComponent(state.access)}`);
    state.socket = new WebSocket(wsUrl);

    state.socket.onopen = () => {
        setSocketStatus(true);
        toast("Socket connected");
    };

    state.socket.onclose = (event) => {
        setSocketStatus(false);
        if (event.code === 4401) {
            toast("WebSocket auth failed. Please login again.");
        } else if (event.code && event.code !== 1000) {
            toast(`Socket closed (${event.code})`);
        }
    };

    state.socket.onerror = () => {
        toast("Socket error");
    };

    state.socket.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            handleSocketPayload(payload);
        } catch (_error) {
            toast("Invalid socket payload");
        }
    };
}

function closeSocket() {
    if (state.socket) {
        state.socket.close();
        state.socket = null;
    }
}

function handleSocketPayload(payload) {
    if (payload.type === "message") {
        appendMessage(payload);
        scrollToBottom();

        const isFromOther = payload.sender_id !== state.me?.id;
        if (isFromOther && state.socket?.readyState === WebSocket.OPEN) {
            state.socket.send(JSON.stringify({
                action: "seen",
                message_id: payload.id,
            }));
        }
        return;
    }

    if (payload.type === "typing") {
        if (payload.is_typing) {
            el.typingText.textContent = "The other user is typing...";
        } else {
            el.typingText.textContent = "";
        }
        return;
    }

    if (payload.type === "seen") {
        updateSeenStatus(payload.message_id);
    }
}

function appendMessage(message) {
    const mine = message.sender_id === state.me?.id;
    const item = document.createElement("div");
    item.className = `message-bubble ${mine ? "mine" : "other"}`;
    item.dataset.messageId = String(message.id || "");

    const senderLabel = mine ? "You" : message.sender_name || "User";
    item.innerHTML = `
    <div>${escapeHtml(message.text || "")}</div>
    <div class="meta">
      ${escapeHtml(senderLabel)} • ${escapeHtml(message.time || "")}
      <span class="status-tag">${escapeHtml(message.status || "")}</span>
    </div>
  `;

    el.messagesBox.appendChild(item);
}

function updateSeenStatus(messageId) {
    const bubble = el.messagesBox.querySelector(`[data-message-id='${messageId}']`);
    if (!bubble) {
        return;
    }
    const tag = bubble.querySelector(".status-tag");
    if (tag) {
        tag.textContent = "seen";
    }
}

function setSocketStatus(isConnected) {
    el.socketStatus.textContent = isConnected ? "Connected" : "Disconnected";
    el.socketStatus.className = `badge ${isConnected ? "text-bg-success" : "text-bg-secondary"}`;
}

function updateMePanel() {
    if (!state.me) {
        el.meInfo.textContent = "Not logged in";
        return;
    }

    const text = `${state.me.username} (id:${state.me.id})`;
    el.meInfo.textContent = text;
}

async function apiCall(path, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
    };

    if (!options.noAuth && state.access) {
        headers.Authorization = `Bearer ${state.access}`;
    }

    const response = await fetch(`${normalizeBase(state.apiBase)}${path}`, {
        method: options.method || "GET",
        headers,
        body: options.body,
    });

    const data = await safeJson(response);

    if (!response.ok) {
        const message =
            data?.detail ||
            data?.error ||
            stringifyValidationErrors(data) ||
            `Request failed (${response.status})`;
        throw new Error(message);
    }

    return data;
}

function buildWsUrl(path) {
    const url = new URL(normalizeBase(state.apiBase));
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return `${url.origin}${path}`;
}

function persistAuth() {
    localStorage.setItem("chat_access", state.access || "");
    localStorage.setItem("chat_refresh", state.refresh || "");
    localStorage.setItem("chat_me", JSON.stringify(state.me || null));
}

function normalizeBase(value) {
    return String(value || "").trim().replace(/\/+$/, "");
}

function formatServerDate(isoDate) {
    if (!isoDate) {
        return "";
    }
    const date = new Date(isoDate);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function toast(text) {
    const node = document.createElement("div");
    node.className = "toast-lite";
    node.textContent = text;
    el.toastWrap.appendChild(node);

    setTimeout(() => {
        node.remove();
    }, 2600);
}

function scrollToBottom() {
    el.messagesBox.scrollTop = el.messagesBox.scrollHeight;
}

function stringifyValidationErrors(data) {
    if (!data || typeof data !== "object") {
        return "";
    }

    const first = Object.entries(data)[0];
    if (!first) {
        return "";
    }

    const [field, value] = first;
    if (Array.isArray(value) && value.length) {
        return `${field}: ${value[0]}`;
    }

    if (typeof value === "string") {
        return `${field}: ${value}`;
    }

    return "";
}

function safeJson(response) {
    return response
        .text()
        .then((text) => {
            if (!text) {
                return {};
            }
            try {
                return JSON.parse(text);
            } catch (_error) {
                return {};
            }
        })
        .catch(() => ({}));
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
