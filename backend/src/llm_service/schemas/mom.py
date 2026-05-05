from pydantic import BaseModel


class ActionItemSchema(BaseModel):
    description: str
    due_date: str | None = None


class MomDraftSchema(BaseModel):
    summary: str
    key_discussion_points: list[str]
    action_items: list[ActionItemSchema]
    follow_ups: list[str]
    hc_closing_note: str

    def to_draft_text(self) -> str:
        lines = [
            f"SUMMARY:\n{self.summary}",
            "\nKEY DISCUSSION POINTS:",
            *[f"- {p}" for p in self.key_discussion_points],
            "\nACTION ITEMS:",
            *[
                f"- {a.description}" + (f" (due: {a.due_date})" if a.due_date else "")
                for a in self.action_items
            ],
            "\nFOLLOW-UPS:",
            *[f"- {f}" for f in self.follow_ups],
            f"\nNOTE:\n{self.hc_closing_note}",
        ]
        return "\n".join(lines)
