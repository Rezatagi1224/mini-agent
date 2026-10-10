const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const chat = document.getElementById("chat");
const button = document.getElementById("send-button");

const routeParts = window.location.pathname.split("/").filter(Boolean);
const storeId = routeParts[0] === "s" && routeParts[1] ? routeParts[1] : "default";
const SESSION_KEY = "mini_agent_conversation_id:" + storeId;
let history = [];

function createSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
        return window.crypto.randomUUID();
    }
    if (window.crypto && typeof window.crypto.getRandomValues === "function") {
        const bytes = new Uint8Array(16);
        window.crypto.getRandomValues(bytes);
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;
        const hex = Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
    throw new Error("Secure random IDs are not supported by this browser.");
}

function getSessionId() {
    try {
        const saved = localStorage.getItem(SESSION_KEY);
        if (saved && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(saved)) {
            return saved;
        }
        const created = createSessionId();
        localStorage.setItem(SESSION_KEY, created);
        return created;
    } catch (error) {
        console.error("Conversation session setup failed:", error);
        return createSessionId();
    }
}

const conversationId = getSessionId();

function addMessage(text, type) {
    const element = document.createElement("div");
    element.className = `message ${type}`;
    element.textContent = text;
    chat.appendChild(element);
    chat.scrollTop = chat.scrollHeight;
    return element;
}

function renderHistory() {
    chat.textContent = "";
    if (!history.length) {
        addMessage("سلام 👋\nمن آماده‌ام. چه کاری برات انجام بدم؟", "assistant");
        return;
    }
    for (const item of history) {
        addMessage(item.content, item.role === "user" ? "user" : "assistant");
    }
}

async function loadHistory() {
    const response = await fetch(
        `/chat/history?conversation_id=${encodeURIComponent(conversationId)}&store_id=${encodeURIComponent(storeId)}`,
        { method: "GET", cache: "no-store" }
    );
    if (!response.ok) {
        throw new Error(`History HTTP ${response.status}`);
    }
    const data = await response.json();
    history = Array.isArray(data.history)
        ? data.history.filter(item =>
            item &&
            ["user", "assistant"].includes(item.role) &&
            typeof item.content === "string"
        ).slice(-12)
        : [];
    renderHistory();
}

const historyReady = loadHistory().catch(error => {
    console.error("Server history loading failed:", error);
    history = [];
    renderHistory();
});

form.addEventListener("submit", async event => {
    event.preventDefault();

    const message = input.value.trim();
    if (!message || button.disabled) {
        return;
    }
    if (message.length > 6000) {
        addMessage("پیام نمی‌تواند بیشتر از ۶۰۰۰ نویسه باشد.", "assistant");
        return;
    }

    await historyReady;
    addMessage(message, "user");
    input.value = "";
    button.disabled = true;

    const loading = addMessage("در حال فکر کردن...", "assistant");

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId,
                store_id: storeId
            })
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }
        if (typeof data.answer !== "string") {
            throw new Error("Invalid server response");
        }

        history = Array.isArray(data.history)
            ? data.history.filter(item =>
                item &&
                ["user", "assistant"].includes(item.role) &&
                typeof item.content === "string"
            ).slice(-12)
            : [
                ...history,
                { role: "user", content: message },
                { role: "assistant", content: data.answer }
            ].slice(-12);
        renderHistory();
    } catch (error) {
        loading.textContent = "ارتباط با Agent برقرار نشد. دوباره تلاش کن.";
        console.error("Chat request failed:", error);
    } finally {
        button.disabled = false;
        input.focus();
    }
});
