const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const chat = document.getElementById("chat");
const button = document.getElementById("send-button");


function addMessage(text, type) {

    const message = document.createElement("div");

    message.className = `message ${type}`;

    message.textContent = text;

    chat.appendChild(message);

    chat.scrollTop = chat.scrollHeight;

    return message;
}


form.addEventListener("submit", async (event) => {

    event.preventDefault();

    const message = input.value.trim();

    if (!message) {
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

        const response = await fetch(
            "/chat",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    message: message
                })
            }
        );


        if (!response.ok) {
            throw new Error(
                "Server error"
            );
        }


        const data = await response.json();

        loading.textContent = data.answer;

    } catch (error) {

        loading.textContent =
            "خطایی در ارتباط با Agent رخ داد.";

        console.error(error);

    } finally {

        button.disabled = false;

        input.focus();
    }

});
