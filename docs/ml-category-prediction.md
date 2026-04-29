# ML Category Prediction

## Runtime Flow

`POST /ml/predict-category` predicts a category from transaction description text while preserving user-specific categories.

1. The route loads the authenticated user's current categories.
2. The local TF-IDF + Logistic Regression classifier predicts a canonical label.
3. The classifier only returns a result when confidence is at least `0.50`.
4. The predicted label is matched against the user's categories with normalized and fuzzy matching.
5. If the classifier cannot return a safe match, the route falls back to embedding similarity against the user's live categories.

The public response remains:

```json
{
  "suggested_category_id": 1,
  "suggested_category_name": "Transportation",
  "confidence": 0.8829
}
```

## Matching Rules

Category matching is handled in `app/services/category_classifier.py`.

- Names are lowercased.
- Leading and trailing spaces are stripped.
- `&` is treated as `and`.
- Repeated whitespace is collapsed.
- Exact normalized matches are preferred.
- If exact matching fails, `difflib.get_close_matches` is used for a single fuzzy match.

Examples:

- `Food and Dining` can match `Food & Dining`.
- `Office Supplies` can match `Office Supply`.

## Confidence Threshold

The classifier uses `MIN_CONFIDENCE = 0.50`.

If the classifier's best probability is below this threshold, the classifier returns `None`. The API then falls back to the existing embedding/profile matching logic instead of returning a weak supervised prediction.

## Training

Training data lives at:

```text
backend/app/ml/training/training_data.csv
```

The current dataset is synthetic. It is useful for a baseline model and local demos, but the reported training/test accuracy does not represent real-world accuracy.

Earlier synthetic data produced 100% accuracy because the examples were too clean: category-specific merchants and phrases appeared repeatedly across both train and test splits. That result was a dataset signal, not proof that the model understood real transaction text.

The generator now adds more realistic variation:

- Random neutral merchant names that are not tied to one category.
- Transaction references such as `ref`, `txn`, `auth`, `inv`, and `batch`.
- Shared noisy terms such as `card purchase`, `POS`, `online payment`, `invoice`, `subscription`, `refund`, and `transfer`.
- Abbreviations such as `inv`, `svc`, `sub`, `sw`, and `pmt`.
- Occasional typos, casing variation, and phrase ordering changes.
- A small set of deliberately ambiguous examples per category.

Run from `backend/`:

```bash
python -m app.ml.training.generate_data
python -m app.ml.training.train_model
python -c "from app.services.category_classifier import classifier; print(classifier.is_ready())"
```

The trainer saves a single sklearn Pipeline to:

```text
backend/app/ml/models/classifier.joblib
```

## Evaluation

`train_model.py` reports:

- Train accuracy.
- Test accuracy.
- The train/test accuracy gap.
- A classification report.
- A text confusion matrix.
- A small out-of-distribution validation set that is not part of the train/test split.

Train accuracy near 100% is common for TF-IDF on synthetic text. Test accuracy is more useful, but it is still measured against generated data from the same generator. A large train/test gap is a warning sign for overfitting; a small gap only means the model generalizes within this synthetic distribution.

## Logging

The route writes `ml_category_prediction` events through the existing `system_log` service. Logged metadata includes the user id, truncated input text, predicted label, matched category, confidence, and whether the classifier or fallback was used.

Logging failure is isolated from prediction failure: if the log write fails, the prediction response still returns.

## Limitations

- The supervised classifier only knows the synthetic category labels it was trained on.
- User-specific custom categories are still handled best by the embedding fallback.
- The model does not learn from user corrections yet.
- Confidence values are model probabilities, not guarantees of correctness.
- A perfect score on the synthetic split is expected and should not be interpreted as production accuracy.
- Real production quality requires real transaction history and evaluation against user-corrected labels later.

## Recommended Next ML Feature

The next ML feature should be unusual transaction detection with Isolation Forest. That should be built after the category prediction path remains stable and after there is enough real transaction history to evaluate anomaly quality.
