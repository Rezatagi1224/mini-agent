
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const chat = document.getElementById("chat");
const button = document.getElementById("send-button");

const HISTORY_KEY = "mini_agent_history";
const SESSION_KEY = "mini_agent_session";

let sessionId = localStorage.getItem(SESSION_KEY);

if (!sessionId) {
    sessionId =
        typeof crypto.randomUUID === "function"
            ? crypto.randomUUID()
            : `${Date.now()}-${Math.random()}`;

    localStorage.setItem(SESSION_KEY, sessionId);
}

let history = [];

try {
    const saved = localStorage.getItem(HISTORY_KEY);
    const parsed = saved ? JSON.parse(saved) : [];

    if (Array.isArray(parsed)) {
        history = parsed.filter(
            item =>
                item &&
                ["user", "assistant"].includes(item.role) &&
                typeof item.content === "string"
        );
    }
} catch {
    history = [];
}


function addMessage(text, type) {
    const element = document.createElement("div");

    element.className = `message ${type}`;
    element.textContent = text;

    chat.appendChild(element);
    chat.scrollTop = chat.scrollHeight;

    return element;
}


function saveHistory() {
    try {
        localStorage.setItem(
            HISTORY_KEY,
            JSON.stringify(history.slice(-12))
        );
    } catch (error) {
        console.error("History save failed:", error);
    }
}


// Restore the visible conversation.
for (const item of history) {
    addMessage(
        item.content,
        item.role === "user" ? "user" : "assistant"
    );
}


form.addEventListener("submit", async event => {
    event.preventDefault();

    const message = input.value.trim();

    if (!message || button.disabled) {
        return;
    }

    if (message.length > 6000) {
        addMessage(
            "پیام نمی‌تواند بیشتر از ۶۰۰۰ کاراکتر باشد.",
            "assistant"
        );
        return;
    }

    addMessage(message, "user");

    input.value = "";
    button.disabled = true;

    const loading = addMessage(
        "در حال فکر کردن...",
        "assistant"
    );

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });

        const data = await response.json();

        if (data.session_id) {
            sessionId = data.session_id;

            localStorage.setItem(
                SESSION_KEY,
                sessionId
            );
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        if (typeof data.answer !== "string") {
            throw new Error("Invalid server response");
        }

        loading.textContent = data.answer;

        history.push(
            { role: "user", content: message },
            { role: "assistant", content: data.answer }
        );

        history = history.slice(-12);
        saveHistory();

    } catch (error) {
        loading.textContent =
            "ارتباط با Agent برقرار نشد. دوباره تلاش کن.";

        console.error("Chat request failed:", error);

    } finally {
        button.disabled = false;
        input.focus();
    }
});
