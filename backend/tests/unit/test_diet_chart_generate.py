import pytest
from src.llm_service.schemas.diet_chart import DietChartGridSchema

VALID_JSON = (
    '{"meal_slots": ["Breakfast", "Lunch"],'
    ' "grid": {"Monday": {"Breakfast": {"food": "Oats", "timing": "7:30 AM"},'
    ' "Lunch": {"food": "Dal rice", "timing": "1:00 PM"}}}}'
)

TEMPLATE_PARAMS = {
    "is_template": True,
    "template_key": "high-protein",
    "meal_slots": ["Breakfast"],
    "grid": {"Monday": {"Breakfast": {"food": "Eggs", "timing": "8:00 AM"}}},
}


def test_schema_parses_valid_json():
    schema = DietChartGridSchema.model_validate_json(VALID_JSON)
    assert schema.meal_slots == ["Breakfast", "Lunch"]
    assert schema.grid["Monday"]["Breakfast"].food == "Oats"


def test_to_parameters_sets_is_template_false():
    schema = DietChartGridSchema.model_validate_json(VALID_JSON)
    assert schema.to_parameters(TEMPLATE_PARAMS)["is_template"] is False


def test_to_parameters_preserves_template_key():
    schema = DietChartGridSchema.model_validate_json(VALID_JSON)
    assert schema.to_parameters(TEMPLATE_PARAMS)["template_key"] == "high-protein"


def test_to_parameters_serialises_cells_as_dicts():
    schema = DietChartGridSchema.model_validate_json(VALID_JSON)
    params = schema.to_parameters(TEMPLATE_PARAMS)
    assert params["grid"]["Monday"]["Breakfast"] == {"food": "Oats", "timing": "7:30 AM"}


def test_template_grid_section_includes_day_and_food():
    from src.llm_service.diet_chart_generate import _template_grid_section
    section = _template_grid_section(TEMPLATE_PARAMS)
    assert "Monday" in section
    assert "Eggs · 8:00 AM" in section


def test_template_grid_section_omits_dot_when_timing_empty():
    from src.llm_service.diet_chart_generate import _template_grid_section
    params = {
        "meal_slots": ["Breakfast"],
        "grid": {"Monday": {"Breakfast": {"food": "Oats", "timing": ""}}},
    }
    section = _template_grid_section(params)
    assert "Oats" in section
    assert "·" not in section
