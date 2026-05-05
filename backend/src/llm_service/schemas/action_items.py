from pydantic import BaseModel


class ActionItemSchema(BaseModel):
    description: str
    due_date: str | None = None
    priority: str | None = None
