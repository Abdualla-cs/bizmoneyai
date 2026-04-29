# Model 2 Fraud Detection Report

## Introduction

Model 2 is the BizMoneyAI Fraud Detection Model. Its purpose is to identify potentially unusual or fraudulent transactions and support the product with non-blocking risk warnings. The model is built as a supervised binary classifier using labeled PaySim data, then integrated into the backend service layer, the ML API, transaction creation, AI insights, system logs, the admin dashboard, and a simple frontend warning flow.

The model is currently suitable for project-stage anomaly visibility and fraud warning behavior. It should not be presented as a final production-grade fraud system because the PaySim dataset contains strong balance-derived fraud signals and BizMoneyAI runtime transactions do not yet provide all PaySim-style balance fields.

## Dataset

The PaySim dataset is a synthetic dataset designed to simulate real financial transaction behavior. It provides realistic transaction patterns and fraud scenarios suitable for training machine learning models when real user data is not available.

Dataset details:

- Dataset name: PaySim mobile money transaction simulation dataset
- Raw dataset path: `backend/data/raw/paysim/PS_20174392719_1491204439457_log.csv`
- Processed dataset path: `backend/data/processed/paysim_fraud_processed.csv`
- Raw rows: `6,362,620`
- Raw columns: `11`
- Processed rows: `6,362,620`
- Processed columns: `16`
- Feature count: `15`
- Target variable: `isFraud`
- Normal rows: `6,354,407`
- Fraud rows: `8,213`
- Fraud percentage: `0.1291%`

Raw dataset columns:

- `step`
- `type`
- `amount`
- `nameOrig`
- `oldbalanceOrg`
- `newbalanceOrig`
- `nameDest`
- `oldbalanceDest`
- `newbalanceDest`
- `isFraud`
- `isFlaggedFraud`

Transaction type distribution:

- `CASH_OUT`: `2,237,500`
- `PAYMENT`: `2,151,495`
- `CASH_IN`: `1,399,284`
- `TRANSFER`: `532,909`
- `DEBIT`: `41,432`

Amount statistics:

- Minimum: `0.00`
- Maximum: `92,445,516.64`
- Mean: `179,861.90`
- Median: `74,871.94`

## Preprocessing

Preprocessing is implemented in:

```text
backend/app/ml/anomaly/prepare_paysim_data.py
```

The preprocessing pipeline:

- Loads the raw PaySim CSV file.
- Validates required columns.
- Drops unusable identifier columns:
  - `nameOrig`
  - `nameDest`
- Keeps numeric transaction and balance columns.
- Engineers balance-derived features.
- One-hot encodes transaction type.
- Writes the processed dataset to `backend/data/processed/paysim_fraud_processed.csv`.

Required preprocessing columns:

- `step`
- `type`
- `amount`
- `oldbalanceOrg`
- `newbalanceOrig`
- `oldbalanceDest`
- `newbalanceDest`
- `isFraud`

Processed feature columns:

- `amount`
- `step`
- `oldbalanceOrg`
- `newbalanceOrig`
- `oldbalanceDest`
- `newbalanceDest`
- `orig_balance_delta`
- `dest_balance_delta`
- `orig_error`
- `dest_error`
- `type_CASH_IN`
- `type_CASH_OUT`
- `type_DEBIT`
- `type_PAYMENT`
- `type_TRANSFER`

Target column:

- `isFraud`

## Feature Engineering

Engineered features:

- `orig_balance_delta = oldbalanceOrg - newbalanceOrig`
- `dest_balance_delta = newbalanceDest - oldbalanceDest`
- `orig_error = oldbalanceOrg - amount - newbalanceOrig`
- `dest_error = oldbalanceDest + amount - newbalanceDest`

Transaction type encoding:

- The categorical `type` column is converted using one-hot encoding.
- The resulting binary features are:
  - `type_CASH_IN`
  - `type_CASH_OUT`
  - `type_DEBIT`
  - `type_PAYMENT`
  - `type_TRANSFER`

Why these features are useful:

- `amount` captures transaction size.
- `step` captures simulation time progression.
- Original and destination balance fields provide before/after account movement context.
- Balance deltas capture how much money moved from origin and into destination accounts.
- Error features capture whether the observed balance changes match the transaction amount.
- Transaction type helps the model distinguish behavior patterns because fraud in PaySim is concentrated mainly in transfer-like flows.

Important caution:

The balance-derived features are powerful, but they also create leakage risk. In PaySim, fraud behavior is strongly tied to balance transitions, so `orig_error`, `dest_error`, and the balance fields may make the classification task easier than it would be with real BizMoneyAI runtime transaction data.

## Model

Model file:

```text
backend/app/ml/anomaly/train_fraud_model.py
```

Model artifact:

```text
backend/app/ml/models/fraud_detector.joblib
```

Model details:

- Model name: Fraud Detection Model
- Artifact model name: `BizMoneyAI Model 2 Fraud Detector`
- Algorithm: `RandomForestClassifier`
- Task type: supervised binary classification
- Positive class: fraud, represented by `isFraud = 1`
- Negative class: normal, represented by `isFraud = 0`

Training parameters:

- `n_estimators=100`
- `max_depth=None`
- `class_weight="balanced"`
- `random_state=42`
- `n_jobs=-1`
- train/test split: stratified
- `test_size=0.2`
- model threshold saved in artifact: `0.5`

The saved artifact contains:

- trained Random Forest model
- feature column order
- threshold
- model metadata
- training parameters
- target distribution
- evaluation metrics

## Training

Training command:

```powershell
python backend/app/ml/anomaly/train_fraud_model.py
```

Training split:

- Train rows: `5,090,096`
- Test rows: `1,272,524`
- Stratified split: yes
- Class imbalance handling: `class_weight="balanced"`

The dataset is highly imbalanced, with only `0.1291%` fraud rows. The model therefore uses class balancing and stratified splitting to preserve the fraud ratio during evaluation.

## Evaluation

Latest holdout test metrics:

- Accuracy: `0.999997`
- Precision: `1.000000`
- Recall: `0.997565`
- F1-score: `0.998781`
- ROC-AUC: `0.998782`
- Confusion matrix `[[tn, fp], [fn, tp]]`: `[[1270881, 0], [4, 1639]]`
- False positives: `0`
- False negatives: `4`

Train metrics:

- Accuracy: `1.000000`
- Precision: `1.000000`
- Recall: `1.000000`
- F1-score: `1.000000`
- ROC-AUC: `1.000000`
- Confusion matrix `[[tn, fp], [fn, tp]]`: `[[5083526, 0], [0, 6570]]`

Train/test gap:

- Accuracy gap: `0.000003`
- Precision gap: `0.000000`
- Recall gap: `0.002435`
- F1 gap: `0.001219`
- ROC-AUC gap: `0.001218`

Sampled cross-validation:

- Fraud rows included: `8,213`
- Normal rows sampled: `50,000`
- Folds: `3`
- Mean precision: `0.999634`
- Mean recall: `0.995860`
- Mean F1-score: `0.997743`

Evaluation interpretation:

- Accuracy alone is misleading because the fraud class is rare.
- A naive model that always predicts normal would still achieve very high accuracy while detecting no fraud.
- Precision, recall, F1-score, ROC-AUC, false positives, and false negatives are more useful for fraud detection.
- Underfitting is not suspected.
- Classic overfitting is not strongly indicated by the small train/test gap.
- The metrics are likely inflated by PaySim balance-derived signals.

## Backend Integration

Runtime service:

```text
backend/app/services/fraud_detector.py
```

Backend API endpoint:

```text
POST /ml/detect-unusual-transaction
```

Request schema:

- `amount`: required float
- `transaction_type`: optional string
- `step`: optional integer
- `oldbalanceOrg`: optional float
- `newbalanceOrig`: optional float
- `oldbalanceDest`: optional float
- `newbalanceDest`: optional float

Response schema:

- `is_unusual`: boolean
- `fraud_probability`: float
- `risk_level`: string, one of `normal`, `warning`, or `critical`
- `model_name`: optional string

Risk thresholds:

- probability `>= 0.80`: `critical`
- probability `>= 0.50`: `warning`
- probability `< 0.50`: `normal`

Model loading strategy:

- The service loads `fraud_detector.joblib` once through a module-level detector instance.
- `is_ready()` reports whether a valid model artifact is loaded.
- `predict(payload: dict)` builds a feature row in the saved feature column order.
- Missing feature columns are created with safe default values.
- Unknown transaction types are handled safely by leaving one-hot type indicators as zero.
- If the model file is missing, invalid, or prediction fails, the service returns a safe normal-risk response instead of crashing the backend.

## System Behavior

The model can run in two backend contexts:

- Direct API call through `POST /ml/detect-unusual-transaction`
- Manual transaction creation through `POST /transactions`

Transaction creation behavior:

- The transaction is created and flushed first.
- The fraud detector runs afterward as a non-blocking side effect.
- The transaction creation flow is not blocked if ML fails.
- BizMoneyAI `expense` transactions are mapped to PaySim-like `CASH_OUT`.
- BizMoneyAI `income` transactions are mapped to PaySim-like `CASH_IN`.
- Missing PaySim balance fields are defaulted safely by the runtime service.

Normal transaction:

- `risk_level = normal`
- no unusual AI insight is created
- no `unusual_transaction_detected` system log is written
- transaction creation succeeds normally

Warning transaction:

- `risk_level = warning`
- creates an `AIInsight` with severity `warning`
- insight message: `Unusual transaction detected. This transaction appears higher risk than normal.`
- writes a `system_log` event with event type `unusual_transaction_detected`

Critical transaction:

- `risk_level = critical`
- creates an `AIInsight` with severity `critical`
- insight message: `Critical unusual transaction detected. Review this transaction immediately.`
- writes a `system_log` event with event type `unusual_transaction_detected`

AIInsight creation logic:

- AI insights use `rule_id=ml_unusual_transaction`.
- Metadata includes transaction id, risk level, fraud probability, amount, transaction type, model name, and a transaction-scoped `scope_key`.
- Duplicate protection is transaction scoped to avoid creating repeated insights too aggressively.

System log event:

- Event type: `unusual_transaction_detected`
- Metadata includes:
  - `transaction_id`
  - `risk_level`
  - `probability`

## Frontend/Admin Integration

User frontend:

- File: `frontend/user/src/app/transactions/page.tsx`
- After a transaction is saved, the page calls `POST /ml/detect-unusual-transaction`.
- If the result is `warning` or `critical`, the user sees a small non-blocking warning banner.
- The banner does not prevent saving.
- Normal results show no extra UI.

Admin backend analytics:

- File: `backend/app/services/admin_analytics.py`
- Anomaly metrics are aggregated from existing `AIInsight` records where `rule_id=ml_unusual_transaction`.
- No new table is used.

Admin dashboard metrics:

- `total_unusual_transactions`
- `unusual_warning_count`
- `unusual_critical_count`
- `recent_unusual_transaction_insights`

Admin frontend:

- File: `frontend/admin/src/app/page.tsx`
- Shows an `Unusual Tx` metric card.
- Shows a compact unusual transaction monitoring panel with recent warning/critical insights.

Admin logs:

- File: `frontend/admin/src/app/logs/page.tsx`
- Includes `unusual_transaction_detected` as a filter option.

## Testing and Verification

Model artifact inspection confirmed that `backend/app/ml/models/fraud_detector.joblib` contains:

- trained `RandomForestClassifier`
- `predict_proba` support
- feature column order
- threshold value
- metadata
- saved evaluation metrics

Runtime validation examples:

| Case | Fraud Probability | Risk Level | Is Unusual |
| --- | ---: | --- | --- |
| normal small PAYMENT | `0.000000` | normal | false |
| normal moderate CASH_OUT | `0.000000` | normal | false |
| normal CASH_IN | `0.000000` | normal | false |
| suspicious very large TRANSFER | `0.990000` | critical | true |
| suspicious balance mismatch | `0.000000` | normal | false |
| suspicious origin unchanged after transfer | `0.040000` | normal | false |
| suspicious extreme amount | `1.000000` | critical | true |

Backend tests verified:

- fraud detector service handles missing model safely
- `POST /ml/detect-unusual-transaction` requires authentication
- API response schema is stable
- model unavailable returns a safe response
- normal transaction creation does not create an unusual insight
- warning and critical results create `AIInsight` records with `rule_id=ml_unusual_transaction`
- transaction creation still succeeds if the detector fails
- `system_log` receives `unusual_transaction_detected` for warning and critical detections
- admin analytics expose anomaly metrics

Frontend and admin build checks passed:

- user frontend build passed
- admin frontend build passed
- user warning banner is non-blocking
- admin dashboard renders anomaly metrics

Useful validation commands:

```powershell
cd backend
python -m app.ml.anomaly.validate_fraud_detector
python -m pytest tests/test_fraud_detector_service.py tests/test_ml_fraud_detection_api.py tests/test_transaction_fraud_detection.py tests/test_admin_api.py
python -m compileall app/ml/anomaly app/services/fraud_detector.py app/api/ml.py
```

```powershell
cd frontend/user
npm run build
```

```powershell
cd frontend/admin
npm run build
```

## Advantages

- Uses a real supervised machine learning model rather than only hard-coded rules.
- Handles severe class imbalance with `class_weight="balanced"`.
- Uses stratified train/test evaluation.
- Preserves feature column order in the saved artifact.
- Provides safe runtime fallback if the model is unavailable.
- Does not block transaction creation.
- Integrates with existing AIInsight and system log infrastructure.
- Adds admin visibility without changing the database schema.
- Adds frontend warning visibility without redesigning the UI.

## Limitations

- PaySim is synthetic and may not represent real BizMoneyAI transaction behavior.
- The model relies heavily on PaySim balance fields that are not fully available in current BizMoneyAI transaction creation.
- Balance-derived features may inflate evaluation metrics.
- Runtime transaction creation defaults missing balance fields to zero, creating a training/runtime feature mismatch.
- Thresholds are initial defaults and need tuning.
- The model should currently be treated as a warning support system, not an autonomous fraud decision system.

## Conclusion

Model 2 is implemented and integrated successfully for the current project stage. It trains on PaySim labels using `RandomForestClassifier`, achieves very strong PaySim holdout metrics, loads safely at runtime, exposes a backend API endpoint, creates AI insights for warning and critical detections, logs unusual transaction events, and provides minimal user/admin visibility.

However, the model should not be described as perfect or production-final. The most important limitation is that PaySim balance-derived features create strong fraud signals, while the live BizMoneyAI transaction flow does not yet provide the same level of account-balance context. Before a final production-grade report, threshold tuning and feature alignment should be addressed.

## Report Input for ChatGPT

### Model Summary

- Project: BizMoneyAI
- Model: Model 2, Fraud Detection Model
- Purpose: detect fraudulent or unusual transactions and create non-blocking risk warnings
- Dataset: PaySim synthetic mobile money transaction dataset
- Algorithm: `RandomForestClassifier`
- Task: supervised binary classification
- Target variable: `isFraud`
- Positive class: `1`, fraud
- Negative class: `0`, normal
- Model artifact: `backend/app/ml/models/fraud_detector.joblib`
- Runtime service: `backend/app/services/fraud_detector.py`

### Dataset Summary

- Raw dataset path: `backend/data/raw/paysim/PS_20174392719_1491204439457_log.csv`
- Processed dataset path: `backend/data/processed/paysim_fraud_processed.csv`
- Rows: `6,362,620`
- Processed feature count: `15`
- Processed columns including target: `16`
- Fraud rows: `8,213`
- Normal rows: `6,354,407`
- Fraud percentage: `0.1291%`

The PaySim dataset is a synthetic dataset designed to simulate real financial transaction behavior. It provides realistic transaction patterns and fraud scenarios suitable for training machine learning models when real user data is not available.

### Features

- `amount`
- `step`
- `oldbalanceOrg`
- `newbalanceOrig`
- `oldbalanceDest`
- `newbalanceDest`
- `orig_balance_delta`
- `dest_balance_delta`
- `orig_error`
- `dest_error`
- `type_CASH_IN`
- `type_CASH_OUT`
- `type_DEBIT`
- `type_PAYMENT`
- `type_TRANSFER`

Feature engineering:

- `orig_balance_delta = oldbalanceOrg - newbalanceOrig`
- `dest_balance_delta = newbalanceDest - oldbalanceDest`
- `orig_error = oldbalanceOrg - amount - newbalanceOrig`
- `dest_error = oldbalanceDest + amount - newbalanceDest`
- transaction type was encoded using one-hot encoding

### Training Configuration

- Model: `RandomForestClassifier`
- `n_estimators=100`
- `max_depth=None`
- `class_weight="balanced"`
- `random_state=42`
- `n_jobs=-1`
- train/test split: stratified
- test size: `0.2`
- threshold: `0.5`

### Metrics

- Accuracy: `0.999997`
- Precision: `1.000000`
- Recall: `0.997565`
- F1-score: `0.998781`
- ROC-AUC: `0.998782`
- Confusion matrix: `[[1270881, 0], [4, 1639]]`
- False positives: `0`
- False negatives: `4`

Train metrics:

- Accuracy: `1.000000`
- Precision: `1.000000`
- Recall: `1.000000`
- F1-score: `1.000000`
- ROC-AUC: `1.000000`

Validation interpretation:

- Accuracy alone is misleading because fraud is extremely rare.
- Precision, recall, F1-score, ROC-AUC, false positives, and false negatives are more important.
- Underfitting is not suspected.
- Classic overfitting is not strongly indicated by train/test gap.
- Metrics may be inflated because PaySim includes strong balance-derived fraud signals.

### Backend Integration Summary

- API endpoint: `POST /ml/detect-unusual-transaction`
- Request fields: amount, transaction_type, step, oldbalanceOrg, newbalanceOrig, oldbalanceDest, newbalanceDest
- Response fields: is_unusual, fraud_probability, risk_level, model_name
- Warning threshold: probability `>= 0.50`
- Critical threshold: probability `>= 0.80`
- Service loads model once and exposes `is_ready()` and `predict(payload)`
- Missing features default safely
- Unknown transaction types are handled safely
- Missing or invalid model returns a safe normal response

### System Behavior Summary

- Model runs through direct ML API calls.
- Model also runs after manual transaction creation.
- Transaction creation is never blocked by ML failure.
- Normal result: no AIInsight, no unusual system log.
- Warning result: creates warning AIInsight and `unusual_transaction_detected` system log.
- Critical result: creates critical AIInsight and `unusual_transaction_detected` system log.
- AIInsight rule id: `ml_unusual_transaction`

### Admin Integration Summary

- Admin metrics are derived from existing `AIInsight` rows with `rule_id=ml_unusual_transaction`.
- Admin dashboard fields:
  - `total_unusual_transactions`
  - `unusual_warning_count`
  - `unusual_critical_count`
  - `recent_unusual_transaction_insights`
- Admin logs include `unusual_transaction_detected` as a filter option.

### Frontend Integration Summary

- User transaction page calls the unusual transaction endpoint after save.
- Warning/critical results show a small banner.
- The banner is non-blocking.
- Normal results show no extra UI.
- Admin dashboard displays unusual transaction metrics and recent unusual transaction insights.

### Advantages

- Real supervised classifier trained on labeled fraud data.
- Handles class imbalance.
- Strong PaySim evaluation metrics.
- Safe backend fallback behavior.
- Non-blocking transaction flow.
- Integrated with AI insights, system logs, admin analytics, and frontend warnings.
- No database schema change required.

### Limitations

- PaySim is synthetic.
- Balance-derived features may make fraud detection unrealistically easy.
- Runtime BizMoneyAI transaction data lacks full PaySim-style balance fields.
- Current thresholds need tuning.
- Current implementation is best viewed as a project-stage warning system, not a final autonomous fraud prevention system.

### Suggested Final Report Position

The final academic report should state that the Fraud Detection Model works successfully as an integrated supervised ML component, but its unusually high metrics must be interpreted carefully due to PaySim feature leakage risk and synthetic-data limitations. The model is suitable for current non-blocking risk alerts, while future work should focus on feature alignment, threshold tuning, and validation against real transaction behavior.
