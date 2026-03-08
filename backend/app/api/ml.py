from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.category import Category
from app.models.user import User
from app.schemas.ml import PredictCategoryRequest, PredictCategoryResponse
from app.services.embeddings import cosine_similarity, embed_texts

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/predict-category", response_model=PredictCategoryResponse)
def predict_category(
    payload: PredictCategoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    categories = db.query(Category).filter(Category.user_id == current_user.user_id).all()
    if not categories:
        return PredictCategoryResponse(
            suggested_category_id=None,
            suggested_category_name=None,
            confidence=0.0,
        )

    texts = [payload.text] + [f"{c.name} {c.type}" for c in categories]
    vectors = embed_texts(texts)
    base = vectors[0]

    best_score = -1.0
    best_idx = 0
    for idx, vec in enumerate(vectors[1:], start=0):
        score = cosine_similarity(base, vec)
        if score > best_score:
            best_score = score
            best_idx = idx

    best = categories[best_idx]
    confidence = max(0.0, min(1.0, (best_score + 1) / 2))
    return PredictCategoryResponse(
        suggested_category_id=best.category_id,
        suggested_category_name=best.name,
        confidence=round(confidence, 4),
    )
