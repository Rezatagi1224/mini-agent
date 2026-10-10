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

## Admin authentication

- Set a long, unique `ADMIN_PASSWORD` in the Modal Secret named `openrouter-secret`. If it is missing, admin API access fails closed.
- The login route permits five failed attempts per client key in a rolling 15-minute window and returns HTTP 429 with a `Retry-After` header after the threshold. The limiter is process-local defense-in-depth; it is not a globally coordinated rate limit across multiple Modal containers.
- After a successful `POST /admin/login`, the server issues a signed session cookie that expires after eight hours. The cookie is `HttpOnly`, `Secure`, `SameSite=Strict`, and scoped to `/admin`.
- The admin password is not saved in browser `sessionStorage` and is not sent with every admin API request. Logging out clears the cookie; changing `ADMIN_PASSWORD` invalidates existing sessions.
- Admin pages are still served publicly, but product, order, expense, dashboard, and customer data APIs require a valid admin session. Keep the password private and use the app over HTTPS.

## Deploy

Pushes to `main` run the unit tests and then deploy `modal_app.py` to Modal. Modal secrets and access tokens must be stored in Modal/GitHub Secrets, not in source code.


## Instagram messaging webhook

The server endpoint is `/webhooks/instagram`. To enable it, add these environment values to the Modal Secret named `openrouter-secret` (never commit their values): `META_WEBHOOK_VERIFY_TOKEN`, `META_APP_SECRET`, `INSTAGRAM_ACCESS_TOKEN`, and `INSTAGRAM_BUSINESS_ACCOUNT_ID`. Optionally set `META_GRAPH_API_VERSION` and `META_GRAPH_BASE_URL`.

Then configure the callback URL `https://davoudtaghizade--mini-agent-web.modal.run/webhooks/instagram` in the Meta app dashboard and subscribe to the Instagram `messages` webhook field. Use an Instagram professional account and grant the Instagram Messaging permission. This endpoint validates Meta signatures, ignores outgoing echoes/non-text events, reuses the same sales agent and customer conversation history, and deduplicates webhook retries.

The integration remains inactive until the Meta app, permissions, callback verification, and Modal secrets are configured. The API's send/receive requirements are documented in [Meta's Instagram API collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api).


## Multi-store operation

- The `default` store continues using the existing `/data/*.json` files, so the current catalog, orders, inventory, and expenses are not migrated or overwritten. Named stores use isolated files under `/data/stores/<store_id>/` and start with an empty catalog.
- Sign in at `/admin` with the configured `ADMIN_PASSWORD` and store ID `default`. Open **مدیریت فروشگاه‌ها** to create named stores. Each store gets its own administrator password (minimum 12 characters); the registry stores salted PBKDF2-HMAC-SHA256 hashes, not raw passwords.
- Store administrators sign in with their store ID and their own password. Their signed session is bound to that store and the `store_admin` role. They cannot call owner-only store-management APIs. The owner can choose any registered store at login, reset store-admin passwords, or deactivate/reactivate a store without deleting its data.
- A public store is available at `/s/<store_id>`. For example, if the store ID is `shop-02`, share `https://davoudtaghizade--mini-agent-web.modal.run/s/shop-02`. Unknown or disabled store IDs return not found. Web conversation histories are keyed by store so they are not shared across shops.
- Store IDs must be lowercase ASCII letters/digits, hyphens, or underscores, must start with a letter/digit, and are at most 64 characters. The reserved ID `default` cannot be created as a named store. Store-admin passwords must contain at least 12 characters.
- The registry is persisted in `/data/stores/registry.json`; do not manually edit it while the service is running. Deactivation blocks store-admin login and the public storefront but retains tenant data. The master `ADMIN_PASSWORD` remains the authority for owner access and signs the admin-session claims.
- The existing session cookie remains HTTP-only, Secure, SameSite=Strict and eight hours long. Failed-login throttling remains a process-local defense-in-depth limiter, not a globally coordinated rate limit across Modal containers.

### Multiple Instagram accounts

The existing single-account variables (`INSTAGRAM_BUSINESS_ACCOUNT_ID` and `INSTAGRAM_ACCESS_TOKEN`) continue to route that account to the `default` store. To route multiple Instagram professional accounts to separate stores, set `INSTAGRAM_ACCOUNTS_JSON` in the Modal Secret named `openrouter-secret`, using a JSON object keyed by each Instagram business account ID. Each value requires `store_id` and may include an account-specific `access_token`; if omitted, the global `INSTAGRAM_ACCESS_TOKEN` is used. Example structure (use real IDs/tokens only in the Modal Secret, never in Git):

```json
{
  "INSTAGRAM_ACCOUNT_ID_1": {"store_id": "default", "access_token": "ACCESS_TOKEN_1"},
  "INSTAGRAM_ACCOUNT_ID_2": {"store_id": "shop-02", "access_token": "ACCESS_TOKEN_2"}
}
```

All accounts can use the shared Meta webhook callback, app secret, and verification token when configured in the same Meta app. The account ID from each inbound webhook determines the target store; an unknown account is ignored rather than routed into the default store. Add the store through the owner UI before mapping its Instagram account.

## Purchase costs and manual expenses

- Products can optionally record a purchase cost per unit in toman.
- New orders snapshot the product's recorded unit cost so later catalog edits do not rewrite historical order costs.
- The admin dashboard reports recorded gross profit, manually entered expenses, and net profit after those recorded expenses.
- Legacy/completed orders without a saved unit cost are counted separately; the dashboard warns that profit is incomplete while any completed order lacks a cost snapshot.
- Expenses can be added and removed from the admin dashboard. Entered expenses are manual records and should be reconciled with receipts or bookkeeping.
- Payment status is also manually recorded; this app does not verify bank transactions or provide a payment gateway.
