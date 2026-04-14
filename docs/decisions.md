# BizMoneyAI Engineering Decisions

## 2026-04-14

Decision: Treat documentation updates as part of the Definition of Done for every feature, fix, refactor, performance change, schema change, and API change.

Alternatives considered:
- Keep documentation optional and rely on commit history.
- Update only `README.md` and public API docs when the change feels large enough.

Why this was chosen:
Commit history alone does not explain intent, tradeoffs, or operational impact. A required documentation pass keeps engineering context readable for the next person touching the code.

Decision: Split project documentation by concern instead of keeping a single large markdown file.

Alternatives considered:
- One running engineering journal.
- Put architecture, admin behavior, ML notes, and unresolved issues into the README.

Why this was chosen:
The repo already has setup and product-oriented docs. Separate files make it easier to keep operational history, architecture, admin behavior, ML planning, and technical debt current without turning one document into a dumping ground.

Decision: Deduplicate transaction imports only within the uploaded file, not against the user's entire historical transaction table.

Alternatives considered:
- Reject exact duplicates both inside the file and against existing stored transactions.
- Keep importing every repeated row and leave deduplication to the user.

Why this was chosen:
Duplicate lines inside one upload are usually operator error and should not inflate the books. Historical duplicates are trickier because recurring expenses, repeated invoices, and same-day split records can legitimately look identical. File-local dedupe removes the obvious import mistake without introducing surprising false positives against real historical data.

Decision: Make auth cookie security environment-aware with an explicit override instead of hardcoding one behavior.

Alternatives considered:
- Always set `Secure=true` and require HTTPS everywhere, including local development.
- Keep `secure=False` everywhere and rely on deployment conventions outside the app.

Why this was chosen:
Local development still needs to work over HTTP, but production-style environments should not silently ship non-secure auth cookies. An environment-aware default with an explicit override keeps local setup simple while giving deployment environments the right default posture.
