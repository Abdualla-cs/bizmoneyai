from pydantic import BaseModel


class PredictCategoryRequest(BaseModel):
    text: str


class PredictCategoryResponse(BaseModel):
    suggested_category_id: int | None
    suggested_category_name: str | None
    confidence: float
