# Model 5: Insight Importance Ranker Report

## 1. Title

BizMoneyAI Model 5 is the **Insight Importance Ranker**, a machine learning component that scores and sorts existing AI insights by importance.

## 2. Introduction

BizMoneyAI already includes:

- Model 1 for transaction category prediction
- Model 2 for unusual transaction detection
- Model 3 for spending forecasting
- Model 4 for smart budget recommendation
- a rule-based AI engine that creates `AIInsight` rows

Model 5 extends that stack by ranking the insights that already exist. It does not replace rule-based generation and it does not create new insights. Its purpose is to help both users and admins see the most important insight first.

## 3. Problem Statement

As BizMoneyAI generates more AI insights, the insight list can become harder to scan. If every insight is shown only by creation time or severity, less important messages can appear near urgent ones, and users may miss the most actionable items.

The product therefore needs a model that answers this question:

**Which existing AI insights should appear first because they are most important right now?**

## 4. Purpose of Model 5

The purpose of Model 5 is to predict a `priority_score` for existing insights and use that score to rank them.

Its role inside BizMoneyAI is to:

- reduce noisy dashboards
- surface urgent insights first
- improve scan speed for users and admins
- keep the existing insight generation engine unchanged

## 5. Why Insight Ranking Is Needed

Insight ranking is needed because severity alone is not always enough. Two `warning` insights may not have the same operational importance. A repeated budget issue, a forecast risk, and a fraud-like transaction should not necessarily be treated the same.

Model 5 helps BizMoneyAI put the most meaningful insight first by combining severity, impact, recurrence, recency, and context into one ranking score.

This avoids noisy dashboards by putting the most important insights first without generating duplicate messages.

## 6. Dataset Explanation

Model 5 is trained on a generated BizMoneyAI-style dataset designed specifically for ranking AI insights.

Dataset path:

```text
backend/data/processed/bizmoneyai_insight_ranker.csv
```

Dataset facts:

- rows: `15000`
- task type: insight-level regression
- target column: `priority_score`

The dataset contains structured insight examples that reflect BizMoneyAI concepts such as severity, financial impact, recurrence, ML-generated risk, forecast pressure, and budget-related behavior.

## 7. Why Kaggle Was Not Used

Kaggle was not used for Model 5.

This decision was made because:

- public Kaggle datasets do not match BizMoneyAI's internal `AIInsight` structure
- Model 5 must learn from BizMoneyAI-specific insight concepts rather than generic ranking labels
- the project does not yet have enough real production ranking feedback to train directly on live user interactions

Generated BizMoneyAI-style data was therefore the most practical choice for the current project phase.

## 8. Generated BizMoneyAI-Style Dataset Path

```text
backend/data/processed/bizmoneyai_insight_ranker.csv
```

## 9. Features Used

Model 5 uses only features that can be reproduced safely from runtime `AIInsight` rows and their structured `metadata_json`.

Features used:

- `rule_id`
- `severity`
- `impact_amount`
- `impact_ratio`
- `recurrence_count`
- `days_since_generated`
- `period_days`
- `confidence_score`
- `is_ml_generated`
- `is_budget_related`
- `is_fraud_related`
- `is_forecast_related`
- `is_income_related`
- `is_profit_related`
- `is_expense_related`
- `category_name`

The training pipeline intentionally excludes `business_profile` and `company_size` because the current runtime `AIInsight` data model does not reliably expose those fields.

## 10. Target Variable

The target variable is:

```text
priority_score
```

This is a numeric score used to learn relative importance across existing insights.

## 11. Algorithm

Model 5 uses:

```text
XGBRegressor
```

This makes Model 5 a supervised regression model for insight importance scoring.

## 12. Why XGBoost Was Selected

`XGBRegressor` was selected because:

- it performs well on structured tabular data
- it handles nonlinear relationships between severity, impact, recurrence, and context
- it works well for ranking-oriented score prediction even when the final task is displayed as ordered insights
- it is practical to integrate into the existing backend runtime

For this phase of the project, it is a strong choice for learning a stable priority score from structured BizMoneyAI-style examples.

## 13. Preprocessing

Model 5 uses safe preprocessing with a structured pipeline:

- `OneHotEncoder` for categorical columns
- numeric passthrough with imputation for numeric columns
- strict exclusion of leakage columns

Important leakage protections include excluding:

- `priority_score` from features
- `priority_level`
- `insight_id`
- `title`
- `generated_at`
- `period_start`
- `period_end`
- any direct target-derived fields

This keeps the training contract aligned with the real runtime feature contract.

## 14. Training Process

Training script:

```text
backend/app/ml/insight_ranking/train_insight_ranker.py
```

Training process:

1. Load the generated Model 5 dataset.
2. Validate required columns.
3. Select only runtime-safe features.
4. Split the dataset into train and test sets.
5. Build preprocessing and regression pipeline.
6. Train `XGBRegressor`.
7. Evaluate regression and ranking quality.
8. Save the model artifact.

Artifact path:

```text
backend/app/ml/models/insight_ranker.joblib
```

The artifact stores:

- trained model
- feature columns
- categorical columns
- numeric columns
- preprocessing pipeline
- model family metadata
- training metrics
- validation metrics
- trained timestamp

## 15. Validation Process

Validation script:

```text
backend/app/ml/insight_ranking/validate_insight_ranker.py
```

The validation process checks:

- artifact existence
- model family contract
- feature column contract
- leakage safety
- regression performance
- ranking quality
- train versus test gap
- scenario ranking behavior

The validator also checks example scenarios such as:

- critical unusual transaction
- critical profit drop
- repeated budget overspending
- forecast budget risk
- budget recommendation
- small informational insight

## 16. Metrics

Latest verified training output:

- Train MAE: `1.4336`
- Train RMSE: `2.2574`
- Train R2: `0.9682`
- Train MAPE: `0.0175`
- Test MAE: `1.8171`
- Test RMSE: `2.8847`
- Test R2: `0.9479`
- Test MAPE: `0.0224`
- Spearman correlation: `0.8902`
- Top-10 overlap: `0/10`
- Top-25 overlap: `0/25`
- Top-50 overlap: `3/50`

Latest verified validation output:

- Train MAE: `1.3322`
- Train RMSE: `2.2443`
- Train R2: `0.9685`
- Train MAPE: `0.0165`
- Test MAE: `1.7043`
- Test RMSE: `2.8711`
- Test R2: `0.9484`
- Test MAPE: `0.0213`
- Spearman correlation: `0.9064`
- Top-10 overlap: `5/10`
- Top-20 overlap: `11/20`

These results show strong regression performance on generated BizMoneyAI-style data and good ranking agreement overall. They should still be interpreted as current project-phase validation rather than proof of perfect live production ranking.

## 17. Runtime Architecture

At runtime, Model 5 works as follows:

```text
AIInsight rows from DB
-> feature extraction
-> XGBoost priority prediction
-> priority level conversion
-> sorted insights
-> frontend/admin display
```

The runtime service:

- reads existing `AIInsight` rows
- derives runtime-safe features from row fields and `metadata_json`
- predicts `priority_score`
- converts the score into:
  - `critical`
  - `high`
  - `medium`
  - `low`
- sorts insights by predicted importance

Model 5 does not create new insights. It only ranks insights that already exist.

## 18. Backend Integration

Runtime service:

```text
backend/app/services/insight_ranker.py
```

Backend integration includes:

- artifact loading with contract checks
- per-insight scoring
- list ranking
- safe fallback if the model artifact is unavailable

Authenticated API endpoints include:

- `GET /ai/insights`
- `GET /ai/insights/ranked`

The existing `/ai/insights` endpoint remains unchanged. The ranked endpoint adds:

- `priority_score`
- `priority_level`
- `priority_reason`

Ranking does not:

- create duplicate insights
- change severity
- change insight generation logic
- modify database schema

## 19. Frontend Integration

Primary user page:

```text
frontend/user/src/app/insights/page.tsx
```

Frontend behavior:

- uses `GET /ai/insights/ranked` by default
- falls back to `GET /ai/insights` if ranking is unavailable
- displays a user-friendly priority badge
- keeps existing severity badges
- keeps existing filters
- does not expose raw model internals

The page is designed to show the most important insights first while preserving the existing user experience.

## 20. Admin Integration

Primary admin page:

```text
frontend/admin/src/app/insights/page.tsx
```

Admin behavior:

- shows priority badges
- sorts by priority descending by default
- keeps existing user, severity, and date filters
- adds a simple priority filter
- displays priority reason as clean text

This allows admins to monitor the highest-priority insights across users without changing the underlying insight creation system.

## 21. Fallback Behavior When Model Unavailable

If the Model 5 artifact is missing or cannot be used, the backend falls back to deterministic ranking.

Fallback ordering uses:

- severity: `critical > warning > info`
- fraud or unusual transaction first
- repeated budget pressure next
- larger financial impact next
- newest insight next

This ensures the ranked insight experience still works even when the ML artifact is unavailable.

## 22. Limitations

Current limitations include:

- training uses generated data rather than real user click or action feedback
- exact top-k overlap is still imperfect
- some high-risk scenarios saturate near the top score band
- the current priority contract is useful for product ranking, but not a guarantee of perfect business priority in every case
- the model should not be described as production-perfect

For the current project and demo phase, the implementation is ready. Production quality can improve further when real user feedback becomes available.

## 23. Future Improvements

Likely future improvements include:

- retrain on real production ranking feedback once enough history exists
- learn from user interaction signals such as opened, ignored, or resolved insights
- improve calibration inside the top critical band
- enrich runtime-safe metadata where appropriate
- compare alternative ranking-specific objectives if the project later needs finer ordering quality

These improvements would help move the model from strong project-phase performance toward stronger production personalization.

## 24. Conclusion

Model 5 successfully adds intelligent insight ranking to BizMoneyAI for the current project phase.

It is trained on generated BizMoneyAI-style insight data, integrated with the existing backend and frontends, and designed to rank existing insights rather than generate new ones. This keeps the system practical and low-risk while improving the visibility of the most important items.

The current result is ready for the current project, report, and demo phase. It should still be described honestly as an early production-stage ranking system that can improve later when real user feedback is available.

## 25. Short Explanation for Doctor

Model 5 is the part of BizMoneyAI that decides which already-generated AI insight should appear first.

It does not create new insights. Instead, it looks at each existing insight, studies features such as severity, financial impact, recurrence, and recency, and predicts a priority score. The system then places the most important insights at the top of the list for the user and for the admin.

This is useful because it prevents dashboards from becoming noisy and helps important risks stand out first. For the current project phase, the model is trained, validated, integrated, and ready for presentation, while still leaving room for future improvement using real user feedback.
