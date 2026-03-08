# ERD

Only 4 tables are used:

1. User
- `user_id` (PK)
- `name`
- `email` (unique)
- `password_hash`
- `created_at`

2. Category
- `category_id` (PK)
- `user_id` (FK -> User.user_id)
- `name`
- `type` (`income|expense|both`)
- `created_at`

3. Transaction
- `transaction_id` (PK)
- `user_id` (FK -> User.user_id)
- `category_id` (FK -> Category.category_id)
- `amount`
- `type` (`income|expense`)
- `description`
- `date`
- `created_at`

4. AIInsight
- `insight_id` (PK)
- `user_id` (FK -> User.user_id)
- `title`
- `message`
- `severity` (`info|warning|critical`)
- `period_start`
- `period_end`
- `created_at`
