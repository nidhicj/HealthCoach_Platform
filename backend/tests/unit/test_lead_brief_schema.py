import pytest
from pydantic import ValidationError

from src.llm_service.schemas.lead_brief import LeadBriefSchema

VALID_JSON = (
    '{"questionnaire_findings": "Client reports low energy and irregular sleep.",'
    ' "blood_report_highlights": "TSH slightly elevated at 5.2 mIU/L.",'
    ' "suggested_discussion_points": ["Discuss sleep hygiene", "Review thyroid history"],'
    ' "flags": ["elevated_tsh"]}'
)

EMPTY_LISTS_JSON = (
    '{"questionnaire_findings": "No major concerns reported.",'
    ' "blood_report_highlights": "All values within normal range.",'
    ' "suggested_discussion_points": [],'
    ' "flags": []}'
)


def test_schema_parses_valid_json():
    schema = LeadBriefSchema.model_validate_json(VALID_JSON)
    assert schema.questionnaire_findings == "Client reports low energy and irregular sleep."
    assert schema.blood_report_highlights == "TSH slightly elevated at 5.2 mIU/L."
    assert schema.suggested_discussion_points == ["Discuss sleep hygiene", "Review thyroid history"]
    assert schema.flags == ["elevated_tsh"]


def test_schema_requires_all_fields():
    with pytest.raises(ValidationError):
        LeadBriefSchema.model_validate_json('{"questionnaire_findings": "Missing other fields."}')


def test_to_brief_text_includes_all_section_headings():
    schema = LeadBriefSchema.model_validate_json(VALID_JSON)
    text = schema.to_brief_text()
    assert "QUESTIONNAIRE FINDINGS:" in text
    assert "BLOOD REPORT HIGHLIGHTS:" in text
    assert "SUGGESTED DISCUSSION POINTS:" in text
    assert "FLAGS:" in text


def test_to_brief_text_includes_field_values():
    schema = LeadBriefSchema.model_validate_json(VALID_JSON)
    text = schema.to_brief_text()
    assert "Client reports low energy and irregular sleep." in text
    assert "TSH slightly elevated at 5.2 mIU/L." in text
    assert "- Discuss sleep hygiene" in text
    assert "- Review thyroid history" in text
    assert "- elevated_tsh" in text


def test_to_brief_text_shows_none_for_empty_lists():
    schema = LeadBriefSchema.model_validate_json(EMPTY_LISTS_JSON)
    text = schema.to_brief_text()
    assert "SUGGESTED DISCUSSION POINTS:\n- None" in text
    assert "FLAGS:\n- None" in text


def test_to_brief_text_handles_empty_blood_report_gap_note():
    schema = LeadBriefSchema(
        questionnaire_findings="Client reports fatigue.",
        blood_report_highlights=(
            "Blood report text could not be extracted from the uploaded file. "
            "Please review the report directly from the Lead's uploaded files."
        ),
        suggested_discussion_points=["Discuss fatigue"],
        flags=[],
    )
    text = schema.to_brief_text()
    assert "could not be extracted" in text
    assert "FLAGS:\n- None" in text
