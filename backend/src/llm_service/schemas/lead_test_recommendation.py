from pydantic import BaseModel


class AdditionItem(BaseModel):
    test: str
    rationale: str


class LeadTestRecommendationSchema(BaseModel):
    additions: list[AdditionItem]
