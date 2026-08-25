import pytest
from pydantic import ValidationError

from src.llm_service.schemas.lead_test_recommendation import LeadTestRecommendationSchema

VALID_JSON = (
    '{"additions": ['
    '{"test": "Hormonal Panel (LH, FSH, AMH)", "rationale": "Lead reports irregular cycles consistent with PCOD."},'
    '{"test": "Vitamin D", "rationale": "Lead reports chronic fatigue and low sun exposure."}'
    ']}'
)

EMPTY_ADDITIONS_JSON = '{"additions": []}'


def test_schema_parses_valid_payload():
    schema = LeadTestRecommendationSchema.model_validate_json(VALID_JSON)
    assert len(schema.additions) == 2
    assert schema.additions[0].test == "Hormonal Panel (LH, FSH, AMH)"
    assert schema.additions[0].rationale == "Lead reports irregular cycles consistent with PCOD."
    assert schema.additions[1].test == "Vitamin D"
    assert schema.additions[1].rationale == "Lead reports chronic fatigue and low sun exposure."


def test_empty_additions_list_is_valid():
    schema = LeadTestRecommendationSchema.model_validate_json(EMPTY_ADDITIONS_JSON)
    assert schema.additions == []


def test_missing_additions_field_rejected():
    with pytest.raises(ValidationError):
        LeadTestRecommendationSchema.model_validate_json("{}")


def test_addition_item_missing_rationale_rejected():
    with pytest.raises(ValidationError):
        LeadTestRecommendationSchema.model_validate_json(
            '{"additions": [{"test": "Vitamin D"}]}'
        )


def test_addition_item_missing_test_rejected():
    with pytest.raises(ValidationError):
        LeadTestRecommendationSchema.model_validate_json(
            '{"additions": [{"rationale": "Some rationale."}]}'
        )


def test_addition_item_wrong_type_rejected():
    with pytest.raises(ValidationError):
        LeadTestRecommendationSchema.model_validate_json(
            '{"additions": [{"test": 123, "rationale": "Some rationale."}]}'
        )


def test_additions_not_a_list_rejected():
    with pytest.raises(ValidationError):
        LeadTestRecommendationSchema.model_validate_json(
            '{"additions": {"test": "Vitamin D", "rationale": "Some rationale."}}'
        )
