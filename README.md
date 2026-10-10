# Mini Agent

A Persian-language AI sales assistant for a clothing store, with catalog, inventory, order review, and sales dashboard.

## Sales dashboard analytics

- Reports distinguish pending, confirmed, shipped, and cancelled orders.
- Shows seven-day UTC sales, average completed order value, cancellation rate, repeat customers (count only), top products, and inventory alerts.
- Inventory alerts distinguish zero, low, and unverified records; a default low-stock threshold of three is used.

## Inventory-safe recommendations

- Exact size/color stock uses the recorded variant map.
- Total stock alone never proves a specific size or color is available.
- Recommendations skip variants confirmed to have zero stock and mark incomplete inventory as unverified.

## Server-side conversation memory

- The web chat creates a random browser session ID and keeps it in local storage.
- Conversation history is read and written by the server; client-supplied message history is not trusted.
- Only the latest 12 user/assistant messages are retained for model context.
- Conversations inactive for more than 30 days are ignored and removed when normal app requests run cleanup.
- Session history currently follows the same browser profile. Cross-device customer recognition is a separate CRM step and is not inferred from a visitor's name.

## Deploy

Pushes to `main` run the unit tests and then deploy `modal_app.py` to Modal. Modal secrets and access tokens must be stored in Modal/GitHub Secrets, not in source code.


## Instagram messaging webhook

The server endpoint is `/webhooks/instagram`. To enable it, add these environment values to the Modal Secret named `openrouter-secret` (never commit their values): `META_WEBHOOK_VERIFY_TOKEN`, `META_APP_SECRET`, `INSTAGRAM_ACCESS_TOKEN`, and `INSTAGRAM_BUSINESS_ACCOUNT_ID`. Optionally set `META_GRAPH_API_VERSION` and `META_GRAPH_BASE_URL`.

Then configure the callback URL `https://davoudtaghizade--mini-agent-web.modal.run/webhooks/instagram` in the Meta app dashboard and subscribe to the Instagram `messages` webhook field. Use an Instagram professional account and grant the Instagram Messaging permission. This endpoint validates Meta signatures, ignores outgoing echoes/non-text events, reuses the same sales agent and customer conversation history, and deduplicates webhook retries.

The integration remains inactive until the Meta app, permissions, callback verification, and Modal secrets are configured. The API's send/receive requirements are documented in [Meta's Instagram API collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api).


## Purchase costs and manual expenses

- Products can optionally record a purchase cost per unit in toman.
- New orders snapshot the product's recorded unit cost so later catalog edits do not rewrite historical order costs.
- The admin dashboard reports recorded gross profit, manually entered expenses, and net profit after those recorded expenses.
- Legacy/completed orders without a saved unit cost are counted separately; the dashboard warns that profit is incomplete while any completed order lacks a cost snapshot.
- Expenses can be added and removed from the admin dashboard. Entered expenses are manual records and should be reconciled with receipts or bookkeeping.
- Payment status is also manually recorded; this app does not verify bank transactions or provide a payment gateway.
