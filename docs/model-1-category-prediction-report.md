# Model 1 Category Prediction Report

## 1. Overview

Model 1 is the category prediction component used to suggest a transaction category from free-text transaction descriptions.

In the current BizMoneyAI backend, it is used through `POST /ml/predict-category` in `backend/app/api/ml.py`. The route accepts a text description, attempts supervised prediction through the saved classifier, maps the prediction to the authenticated user's own categories, and falls back to embedding similarity when the classifier cannot return a safe result.

## 2. Problem Definition

- Type: supervised text classification
- Input: transaction description text such as `"Uber ride to airport"` or `"Team lunch at pizza place"`
- Output: a category label, later mapped to a concrete user-owned category record

At the ML level, the model predicts one of a fixed set of canonical category names. At the API level, the system returns:

- `suggested_category_id`
- `suggested_category_name`
- `confidence`

This separation matters because the model predicts labels, but the product must return the matching category inside the current user's database records.

## 3. Dataset

The training dataset is stored at `backend/app/ml/training/training_data.csv`.

In the current repository state, the dataset contains:

- 5,000 rows total
- 10 categories
- 500 rows per category

The categories used are:

- `Shopping`
- `Food & Dining`
- `Transportation`
- `Utilities`
- `Rent`
- `Software`
- `Marketing`
- `Office Supplies`
- `Professional Services`
- `Income`

The dataset is synthetic rather than extracted from production transactions.

Inference from the repository: no labeled real transaction dataset is included in `app/ml/training`, and the presence of `generate_data.py` indicates that synthetic generation was used because a real labeled corpus was not available inside the project at implementation time.

This has practical limitations:

- The model learns from generated language patterns, not real user behavior.
- The label space is fixed to the categories defined by the generator.
- Accuracy on this dataset does not directly measure production accuracy.

## 4. Data Generation

`backend/app/ml/training/generate_data.py` builds the dataset step by step.

1. It defines a deterministic setup:
   - `RANDOM_SEED = 42`
   - `ROWS_PER_CATEGORY = 500`
   - output path `training_data.csv`

2. It defines category-specific vocabularies in `CATEGORY_CONFIG`:
   - merchants
   - objects
   - contexts

3. It defines shared noise sources that can appear across many categories:
   - `card purchase`
   - `POS`
   - `online payment`
   - `invoice`
   - `subscription`
   - `refund`
   - `transfer`
   - and related terms

4. It defines deliberate ambiguity through `AMBIGUOUS_EXAMPLES`.
   - Example: `"grabbed coffee for client meeting"` for `Food & Dining`
   - Example: `"office lease april payment"` for `Rent`
   - Example: `"paid meta campaign invoice"` for `Marketing`

5. It generates randomized references and merchant variants.
   - `_random_reference()` creates transaction-like ids such as `ref 12345` or `txn AB12CD`
   - `_random_merchant()` injects neutral merchant names such as `northstar llc` or `EVERGREEN MARKET`

6. It applies linguistic variation:
   - `_apply_abbreviations()` changes words such as `payment` to `pmt`
   - `_apply_typo()` introduces occasional character drops, swaps, or doubles
   - `_apply_case_variation()` randomly lowercases, uppercases, or title-cases text
   - `_shuffle_tail()` changes local word order in some descriptions

7. It composes final descriptions from multiple templates.
   - Examples include merchant-first, object-first, month/noise-first, and reference-based patterns

8. It enforces uniqueness.
   - `seen` prevents duplicate `(description, category)` pairs
   - generation retries until each category reaches 500 unique rows

### Why overfitting was a risk

Synthetic financial text can become too easy if each category is represented by a small set of repeated keywords or merchants. In that situation, the model memorizes obvious lexical markers instead of learning a more general decision boundary.

### How overfitting risk was reduced

The current generator reduces memorization by adding:

- neutral merchant names not tied to one category
- shared noisy financial terms across categories
- abbreviations
- typos
- casing changes
- reordered phrasing
- ambiguous examples
- uniqueness checks instead of simple duplication

This does not remove the synthetic-data limitation, but it makes the training distribution less clean and less repetitive.

## 5. Preprocessing

The model uses `TfidfVectorizer` inside an sklearn `Pipeline`.

Configuration:

- `ngram_range=(1, 2)`
- `max_features=5000`

This means the vectorizer learns:

- unigrams such as `uber`, `invoice`, `rent`
- bigrams such as `airport ride`, `cloud bill`, `team lunch`

TF-IDF is suitable here because transaction descriptions are:

- short
- sparse
- mostly keyword-driven
- often distinguishable by local phrases rather than long semantic context

`max_features=5000` keeps the feature space bounded so training and inference remain lightweight.

## 6. Model Choice

The classifier is `LogisticRegression(max_iter=2000)`.

From the implementation, this is a deliberate lightweight engineering decision:

- it works well with sparse TF-IDF features
- it trains quickly on CPU
- it produces class probabilities through `predict_proba`
- it is easy to serialize with `joblib`
- it is straightforward to load inside a FastAPI service without GPU or transformer runtime overhead

Why not BERT or deep learning at this stage:

- the dataset is synthetic and relatively small
- the inference path needs to be simple and reliable
- the backend only needs a practical baseline classifier, not a heavy language model stack
- a transformer-based solution would add complexity without clear evidence of higher-quality training data

For Model 1, TF-IDF plus Logistic Regression is a sensible baseline because it is fast, understandable, and easy to operate.

## 7. Training Process

`backend/app/ml/training/train_model.py` performs training.

### Split strategy

- data is loaded from `training_data.csv`
- `train_test_split(..., test_size=0.2, random_state=42, stratify=categories)` is used

Stratification ensures that each category keeps the same class balance in train and test splits.

### Pipeline

The training pipeline is:

1. `TfidfVectorizer(ngram_range=(1, 2), max_features=5000)`
2. `LogisticRegression(max_iter=2000)`

### Evaluation outputs

The script prints:

- number of rows
- category names
- train accuracy
- test accuracy
- train/test accuracy gap
- classification report
- confusion matrix

It also defines `OVERFITTING_WARNING_GAP = 0.08`.

If train accuracy exceeds test accuracy by more than `0.08`, the script prints an overfitting warning.

### OOD validation examples

The script includes a small hardcoded out-of-distribution validation set outside the train/test split:

- `"paid meta campaign invoice"` -> `Marketing`
- `"monthly aws cloud bill"` -> `Software`
- `"grabbed coffee for client meeting"` -> `Food & Dining`
- `"uber airport ride"` -> `Transportation`
- `"office lease april payment"` -> `Rent`
- `"printer ink and paper"` -> `Office Supplies`
- `"client invoice payment received"` -> `Income`

For each example, the script prints:

- expected label
- predicted label
- confidence
- `OK` or `MISS`

This OOD check is important because a strong synthetic split alone is not enough to show useful generalization.

## 8. Model Saving

The trained model is saved to:

- `backend/app/ml/models/classifier.joblib`

Inspection of the saved artifact shows that it is a serialized sklearn `Pipeline` with two steps:

- `tfidf`
- `classifier`

The saved pipeline also contains the learned class list:

- `Food & Dining`
- `Income`
- `Marketing`
- `Office Supplies`
- `Professional Services`
- `Rent`
- `Shopping`
- `Software`
- `Transportation`
- `Utilities`

Saving the entire pipeline is important because preprocessing and classification remain coupled. The backend does not need to separately reconstruct vectorization settings at inference time.

## 9. Backend Integration

`backend/app/services/category_classifier.py` is the runtime wrapper around the saved model.

### `is_ready()`

`is_ready()` returns `True` only when:

- the file `classifier.joblib` exists
- `joblib.load()` succeeds
- the loaded object is an sklearn `Pipeline`
- the pipeline exposes `predict_proba`

If the file is missing or invalid, the service logs the issue and keeps the app running.

### `predict(text, user_categories)`

`predict()`:

- rejects empty text
- rejects empty user category lists
- runs `predict_proba([text])`
- selects the highest-probability class
- rounds confidence to 4 decimals
- rejects predictions below `MIN_CONFIDENCE = 0.50`
- maps the predicted canonical label to one of the current user's category names
- returns `CategoryPrediction(predicted_label, matched_category, confidence)`
- returns `None` on failure or unsafe prediction

This keeps the classifier isolated from API formatting and database lookup concerns.

## 10. Prediction Flow

The runtime path in `backend/app/api/ml.py` works step by step as follows.

1. User authentication
   - The route depends on `get_current_user`.
   - The authenticated user is identified from the JWT cookie-based auth layer already used by the backend.

2. Fetch user categories
   - The route queries all `Category` rows for `current_user.user_id`.

3. Handle the empty-category case
   - If the user has no categories, the route returns:
     - `suggested_category_id = None`
     - `suggested_category_name = None`
     - `confidence = 0.0`

4. Run the classifier
   - The route calls `classifier.predict(payload.text, [category.name for category in categories])`.

5. Apply confidence threshold
   - The threshold is enforced inside `category_classifier.py`.
   - If the best class probability is below `0.50`, the classifier returns `None`.

6. Normalize category names
   - `normalize_category_name()`:
     - lowercases with `casefold()`
     - replaces `&` with `and`
     - collapses repeated whitespace
     - strips leading and trailing spaces

7. Fuzzy match against the user's actual category names
   - Exact normalized match is attempted first.
   - If exact matching fails, `difflib.get_close_matches()` is used with:
     - `n=1`
     - `cutoff=0.80`

8. Return the classifier result when a safe match exists
   - The route resolves the matched user category to:
     - `category_id`
     - original stored category name
   - It returns `PredictCategoryResponse`.

9. Fallback to embedding similarity if needed
   - If the classifier is unavailable, fails, falls below threshold, or cannot match a user category, the route falls back to `_embedding_prediction()`.
   - The fallback compares the transaction text against `"{category.name} {category.type}"` strings using the existing embedding service.

10. Logging
   - The route writes `ml_category_prediction` events through `log_system_event()`.
   - Logged metadata includes:
     - truncated input text
     - predicted label
     - matched category
     - confidence
     - method used (`classifier`, `embedding_fallback`, or `no_categories`)
   - Logging failure is isolated so prediction still returns.

## 11. Testing and Verification

### Compile checks

This implementation is suitable for lightweight import verification through:

```bash
python -m compileall app/api/ml.py app/services/category_classifier.py app/ml/training
```

### Pytest coverage

The repository includes focused tests in `backend/tests/test_ml_category_prediction.py`.

The test coverage checks that:

- a missing model file does not crash the service
- low-confidence predictions return `None` so fallback can run
- normalized matching works
- fuzzy matching works
- `/ml/predict-category` keeps the public response schema
- classifier-based predictions are logged
- embedding fallback still works

### Sample predictions used for verification

Examples present in code and tests include:

- `"Uber ride to airport"` -> `Transportation`
- `"Office rent for March"` style rent phrases, represented in training validation as `"office lease april payment"` -> `Rent`
- `"Facebook ads campaign"` style marketing phrases, represented in validation as `"paid meta campaign invoice"` -> `Marketing`
- `"Team lunch at pizza place"` -> `Food & Dining`

These examples are used as sanity checks, not as proof of production-level performance.

## 12. Strengths

- Fast inference with a lightweight sklearn pipeline
- Simple deployment because preprocessing and model logic are bundled in one artifact
- Low operational complexity compared with transformer-based serving
- Clear fallback path when the classifier cannot return a safe result
- Compatible with user-specific categories through normalized and fuzzy matching
- Production-safe baseline because missing-model scenarios do not break the API

## 13. Limitations

- The training data is synthetic
- The model is not trained on real user transaction history
- Confidence values come from the classifier and are not calibrated guarantees
- The label space is limited to the categories used during synthetic generation
- The system may fail on unseen wording, domain-specific merchants, or user-created categories far from the canonical labels
- Matching quality still depends on the user's category naming conventions

## 14. Future Improvements

Short, practical next steps for this same model path are:

- retrain on real labeled transaction history when available
- add a user feedback loop so corrections become future training data
- improve confidence calibration so thresholding is better aligned with real-world uncertainty

## Report Summary (For External Use)

Model 1 is a supervised text classification system for predicting transaction categories from description text. It uses a synthetic, balanced training dataset generated inside the repository because no real labeled transaction corpus is included in the current project sources.

The training pipeline is a serialized sklearn `Pipeline` containing `TfidfVectorizer(ngram_range=(1, 2), max_features=5000)` and `LogisticRegression(max_iter=2000)`, saved as `backend/app/ml/models/classifier.joblib`. In production, it is integrated through `category_classifier.py` and exposed by `POST /ml/predict-category`, where predictions are thresholded, normalized, fuzzy-matched to the authenticated user's categories, and backed by an embedding fallback when needed.

Key strengths are speed, low complexity, simple deployment, and safe fallback behavior. Key limitations are the synthetic dataset, lack of real user behavior in training, and weaker reliability on unseen or highly customized transaction patterns.
