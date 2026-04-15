# BizMoneyAI Engineering Changelog

[2026-04-15 14:14]

Added a visible selected-user management experience to the admin dashboard.

WHY:
Admins needed a real SaaS-style way to inspect one user at a time instead of relying on hidden filters or weak table context.

PROBLEM:
The admin dashboard could pass `user_id` to analytics endpoints, but the UI did not provide a clear always-visible user selection surface or a focused account overview with financial, activity, and insight details.

SOLUTION:
- Replaced the hidden-style user selector with visible selectable user bubbles/cards and an `All Users` global mode control.
- Added selected-user dashboard state that sends `user_id` to the dashboard analytics requests.
- Added `GET /admin/users/{user_id}/overview` for user basic info, counts, financial summary, recent logs, and recent insights.
- Added a selected-user overview panel that shows status, created date, last activity, account stats, income, expense, balance, over-budget count, recent activity, and recent insights.
- Kept the dashboard global mode intact when no user is selected.

ISSUES:
- The selected user can disappear after deletion or refresh, so the dashboard now clears back to global mode when the user is no longer available.
- The existing analytics endpoints already supported `user_id`, so the backend change stayed focused on the richer user overview payload.

HOW IT WAS SOLVED:
Added a minimal typed overview endpoint, reused existing analytics endpoints for chart scoping, and verified both scoped/global backend behavior plus the admin frontend build.

[2026-04-15 14:03]

Fixed admin list sorting for the user and category management views.

WHY:
The admin frontend requests user and category option lists sorted by name, and those requests need to work without relaxing the API into arbitrary sort fields.

PROBLEM:
Admin users and categories sorting was not backed by an explicit safe column contract, and the backend pagination cap rejected the frontend's `limit=500` option-list requests before the admin pages could load consistently.

SOLUTION:
- Added explicit allowed sort maps for admin users and categories.
- Mapped model-backed sorts such as `name`, `email`, and `created_at` to SQLAlchemy columns or expressions.
- Kept derived metric sorts working through validated in-memory row sort helpers.
- Raised the users/categories admin list limit cap to 500 for existing frontend option loaders.
- Added focused regression coverage for user and category sorting plus invalid sort validation.

ISSUES:
- Invalid `sort_by` values must still fail with a validation-style `422` instead of being passed through to a query.
- The frontend did not need a contract change because it was already sending supported sort keys.

HOW IT WAS SOLVED:
Validated `sort_by` before applying pagination, used safe lookup maps instead of arbitrary attribute access, and covered the exact `limit=500&sort_by=name` request shape used by the admin UI.

[2026-04-14 02:45]

Added the engineering documentation baseline and standardized the `docs` folder around change history, architecture, admin operations, ML status, design decisions, and known issues.

WHY:
We needed documentation to become part of the delivery process instead of something that only gets updated when there is extra time.

PROBLEM:
The repository already had setup and product docs, but it did not have a consistent engineering record for what changed, why it changed, or what operational limitations still exist.

SOLUTION:
Created `changelog.md`, `architecture.md`, `admin-module.md`, `ml-roadmap.md`, `decisions.md`, and `known-issues.md`, then backfilled them from the current backend routes, admin frontend pages, auth flow, analytics service, and ML services.

ISSUES:
- The `docs` folder existed, but it mostly covered setup and product material rather than engineering history.
- Admin analytics behavior and ML training behavior needed to be confirmed from the implementation before documenting them.

HOW IT WAS SOLVED:
Reviewed the active code paths first and wrote the new docs from the current source of truth instead of creating generic placeholders.

[2026-04-14 03:13]

Ran a full regression pass across the user APIs, admin APIs, frontend builds, and a live browser smoke for the user and admin apps.

WHY:
We needed an end-to-end confidence check that covers the product the way a real SaaS system is used, not just isolated unit behavior.

PROBLEM:
The project had strong backend test coverage, but we still needed to confirm full flow behavior across auth, CRUD, imports, budgets, dashboard metrics, AI, ML, admin moderation, system logs, security boundaries, and performance under a heavier dataset.

SOLUTION:
Ran `pytest` for the backend suite, built both Next.js frontends, executed targeted API integration passes for all major user and admin modules, measured dashboard response times under a larger local dataset, and used Playwright against a disposable local stack to smoke-test the live user and admin UIs.

ISSUES:
- Found validation gaps in the backend: case-insensitive duplicate emails were allowed, short passwords were accepted, case-insensitive duplicate categories were allowed, and negative transaction amounts were accepted.
- Found an import integrity gap: duplicate CSV rows were inserted twice instead of being deduplicated or flagged.
- Found an observability gap: transaction create/update/delete actions do not write audit logs.
- Reconfirmed that admin analytics can stay stale after writes until the cache is invalidated.
- Browser smoke passed for register, category creation, transaction creation, admin login, and admin page loads. The first dashboard value assertion failed because of a brittle selector, then was manually rechecked against the rendered page text and confirmed correct.

HOW IT WAS SOLVED:
- Captured the failing scenarios with repeatable API calls and local browser repro steps.
- Logged the unresolved defects in `known-issues.md` so they stay visible for follow-up work.

[2026-04-14 04:08]

Hardened core validation and cache consistency across auth, transactions, budgets, insights, and admin mutations.

WHY:
The regression pass found three production-facing mismatches right away: transactions accepted non-positive amounts, backend registration was weaker than the frontend password policy, and admin analytics could stay stale for up to the cache TTL after writes.

PROBLEM:
Those gaps were hitting different layers at once. The UI already treated transaction amounts as positive values, the register form already enforced a six-character password, and the admin dashboard looked live but was sometimes serving cached numbers after user, budget, category, transaction, or insight changes.

SOLUTION:
- Added backend validation so transaction create and update now reject `amount <= 0`.
- Enforced the six-character minimum password policy in the backend schema to match the web register flow.
- Wired admin analytics cache invalidation into successful write paths for auth events, admin user actions, category writes, transaction writes and imports, budget writes, and insight generation.
- Made auth cookies environment-aware so local HTTP keeps working while production-style environments default to `Secure=true`.

ISSUES:
- One older auth regression test still used a five-character password and started failing as soon as the backend policy became real.
- Cache invalidation had to be added carefully after successful commits instead of blindly on every attempted write.

HOW IT WAS SOLVED:
- Updated the affected tests to reflect the actual password policy.
- Kept invalidation tied to committed writes so admin analytics refresh immediately without throwing away cache entries for rolled-back requests.

[2026-04-14 04:24]

Normalized identity and category handling, and filled the audit gap around transaction CRUD.

WHY:
The system was still inconsistent about case-sensitive identity and naming rules, and the admin log stream was missing one of the most important classes of financial changes.

PROBLEM:
Users could register duplicate accounts that only differed by email casing, the same user could create categories that only differed by case, and transaction create/update/delete actions left no audit trail in `system_log`.

SOLUTION:
- Normalized email lookups to lowercase for registration and login, and persist new user emails in normalized form.
- Added user-scoped case-insensitive category uniqueness checks while still allowing different users to reuse the same category names.
- Added `create_transaction`, `update_transaction`, and `delete_transaction` audit events with linked user, category, amount, type, date, and description metadata.
- Updated the admin logs UI filter options so those new transaction events are visible in the log explorer.

ISSUES:
- We wanted the category rule to be strict for one user without changing behavior across tenants.
- Existing API error handling in the user frontend was too generic for the new validation paths.

HOW IT WAS SOLVED:
- Scoped the category uniqueness check by `user_id` and a normalized lowercase name comparison.
- Updated the user transactions and categories pages to surface backend validation details instead of falling back to a generic "Failed to save" message.

[2026-04-14 04:39]

Added import duplicate handling, expanded regression coverage, and documented the remaining ML warm-start limitation instead of overengineering it.

WHY:
Repeated rows in the same upload were still inflating financial totals, and the import flow needed a clear contract for what gets skipped versus what gets rejected.

PROBLEM:
Importing the same row twice in one CSV or XLSX created duplicate transactions. At the same time, trying to deduplicate against the whole historical transaction table would have risked rejecting legitimate recurring expenses or repeated monthly entries.

SOLUTION:
- Added duplicate-row detection within a single uploaded file and return an import summary with `imported_count`, `skipped_count`, `rejected_rows`, and the created transactions.
- Kept malformed rows as hard validation failures so broken imports still fail loudly, but duplicate rows inside the same file now get skipped with an explicit reason.
- Added backend regression coverage for positive transaction validation, normalized auth, secure cookies, category uniqueness, transaction audit logs, import dedupe, and admin dashboard cache refresh after writes.
- Reviewed the ML cold-start path and kept the current lightweight mitigation: the sentence-transformer model is already cached in-process after first load, so we documented the first-request latency rather than adding a startup warmup path right now.

ISSUES:
- The import response shape had been a bare transaction list, so the tests had to be updated to assert the new summary contract.
- The main tradeoff was choosing a duplicate rule that improves safety without blocking legitimate repeated transactions already in the database.

HOW IT WAS SOLVED:
- Updated the import tests and frontend import feedback together so the behavior stays clear.
- Recorded the import dedupe policy in `docs/decisions.md` and the remaining ML cold-start note in `docs/ml-roadmap.md` and `docs/known-issues.md`.
