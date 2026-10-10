# Mini Agent

A Persian-language AI sales assistant for a clothing store, with catalog, inventory, order review, and sales dashboard.

## Server-side conversation memory

- The web chat creates a random browser session ID and keeps it in local storage.
- Conversation history is read and written by the server; client-supplied message history is not trusted.
- Only the latest 12 user/assistant messages are retained for model context.
- Conversations inactive for more than 30 days are ignored and removed when normal app requests run cleanup.
- Session history currently follows the same browser profile. Cross-device customer recognition is a separate CRM step and is not inferred from a visitor's name.

## Deploy

Pushes to `main` run the unit tests and then deploy `modal_app.py` to Modal. Modal secrets and access tokens must be stored in Modal/GitHub Secrets, not in source code.
