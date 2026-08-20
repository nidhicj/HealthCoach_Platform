from pydantic import BaseModel


class LeadBriefSchema(BaseModel):
    questionnaire_findings: str
    blood_report_highlights: str
    suggested_discussion_points: list[str]
    flags: list[str]

    def to_brief_text(self) -> str:
        discussion_points = [f"- {p}" for p in self.suggested_discussion_points] or ["- None"]
        flags = [f"- {f}" for f in self.flags] or ["- None"]
        lines = [
            f"QUESTIONNAIRE FINDINGS:\n{self.questionnaire_findings}",
            f"\nBLOOD REPORT HIGHLIGHTS:\n{self.blood_report_highlights}",
            "\nSUGGESTED DISCUSSION POINTS:",
            *discussion_points,
            "\nFLAGS:",
            *flags,
        ]
        return "\n".join(lines)
