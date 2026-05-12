import pytest
from src.api.diet_charts import _parse_csv_bytes

SIMPLE_CSV = (
    "Day,Breakfast,Lunch,Dinner\n"
    "Monday,Oats · 7:30 AM,Dal rice · 1:00 PM,Soup · 8:00 PM\n"
    "Tuesday,Eggs · 8:00 AM,Roti sabzi · 1:00 PM,Salad · 7:30 PM\n"
)


def test_parses_meal_slots():
    result = _parse_csv_bytes(SIMPLE_CSV.encode())
    assert result["meal_slots"] == ["Breakfast", "Lunch", "Dinner"]


def test_parses_food_and_timing():
    result = _parse_csv_bytes(SIMPLE_CSV.encode())
    assert result["grid"]["Monday"]["Breakfast"] == {"food": "Oats", "timing": "7:30 AM"}
    assert result["grid"]["Monday"]["Lunch"] == {"food": "Dal rice", "timing": "1:00 PM"}


def test_skips_non_day_rows():
    csv = "Day,Breakfast\nMonday,Oats · 8am\nTotal,ignored\n"
    result = _parse_csv_bytes(csv.encode())
    assert list(result["grid"].keys()) == ["Monday"]


def test_raises_on_wrong_first_column():
    csv = "NotDay,Breakfast\nMonday,Oats · 8am\n"
    with pytest.raises(ValueError, match="First column header must be 'Day'"):
        _parse_csv_bytes(csv.encode())


def test_raises_on_no_slots():
    csv = "Day\nMonday\n"
    with pytest.raises(ValueError, match="at least one meal slot"):
        _parse_csv_bytes(csv.encode())


def test_cell_without_separator_gets_empty_timing():
    csv = "Day,Breakfast\nMonday,Oats\n"
    result = _parse_csv_bytes(csv.encode())
    assert result["grid"]["Monday"]["Breakfast"] == {"food": "Oats", "timing": ""}


def test_utf8_bom_stripped():
    csv_bytes = b'\xef\xbb\xbf' + "Day,Breakfast\nMonday,Oats · 8am\n".encode("utf-8")
    result = _parse_csv_bytes(csv_bytes)
    assert result["meal_slots"] == ["Breakfast"]
