from pydantic import BaseModel


class BriefSchema(BaseModel):
    context_summary: str
    open_action_items: list[str]
    triage_flags: list[str]
    suggested_topics: list[str]

    def to_brief_text(self) -> str:
        open_items = [f"- {i}" for i in self.open_action_items] or ["- None"]
        triage = [f"- {f}" for f in self.triage_flags] or ["- None"]
        topics = [f"- {t}" for t in self.suggested_topics]
        lines = [
            f"CONTEXT:\n{self.context_summary}",
            "\nOPEN ACTION ITEMS:",
            *open_items,
            "\nTRIAGE FLAGS:",
            *triage,
            "\nSUGGESTED TOPICS:",
            *topics,
        ]
        return "\n".join(lines)
