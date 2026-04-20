# ERD

The current operational schema used by the app includes 7 primary tables:

1. User
- `user_id` (PK)
- `name`
- `email` (unique)
- `password_hash`
- `is_active`
- `created_at`

2. Admin
- `admin_id` (PK)
- `name`
- `email` (unique)
- `password_hash`
- `created_at`

3. Category
- `category_id` (PK)
- `user_id` (FK -> User.user_id)
- `name`
- `type` (`income|expense|both`)
- `created_at`

4. Transaction
- `transaction_id` (PK)
- `user_id` (FK -> User.user_id)
- `category_id` (FK -> Category.category_id)
- `amount`
- `type` (`income|expense`)
- `description`
- `date`
- `created_at`

5. Budget
- `budget_id` (PK)
- `user_id` (FK -> User.user_id)
- `category_id` (FK -> Category.category_id)
- `amount`
- `month`
- `note`
- `created_at`

6. AIInsight
- `insight_id` (PK)
- `user_id` (FK -> User.user_id)
- `rule_id`
- `title`
- `message`
- `severity` (`info|warning|critical`)
- `period_start`
- `period_end`
- `metadata_json`
- `created_at`

7. SystemLog
- `log_id` (PK)
- `admin_id` (FK -> Admin.admin_id, nullable)
- `user_id` (FK -> User.user_id, nullable)
- `event_type`
- `message`
- `level`
- `metadata_json`
- `created_at`
