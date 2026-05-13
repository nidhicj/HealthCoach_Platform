import pytest
from src.api.diet_charts import _parse_csv_bytes, _parse_tsv_rows

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


# ── _parse_tsv_rows ────────────────────────────────────────────────────────────

def test_tsv_basic():
    tsv = "Meal\tNotes\tOption\nBreakfast\tAim for 35g\tOmelet"
    rows = _parse_tsv_rows(tsv)
    assert rows == [["Meal", "Notes", "Option"], ["Breakfast", "Aim for 35g", "Omelet"]]


def test_tsv_trims_trailing_empty_cells():
    tsv = "Breakfast\tAim for 35g\tOmelet\t\t"
    rows = _parse_tsv_rows(tsv)
    assert rows == [["Breakfast", "Aim for 35g", "Omelet"]]


def test_tsv_skips_fully_empty_lines():
    tsv = "Breakfast\tOmelet\n\n\nLunch\tDal rice"
    rows = _parse_tsv_rows(tsv)
    assert rows == [["Breakfast", "Omelet"], ["Lunch", "Dal rice"]]


def test_tsv_preserves_empty_cells_within_row():
    tsv = "Early Morning\t\tJeera water"
    rows = _parse_tsv_rows(tsv)
    assert rows == [["Early Morning", "", "Jeera water"]]


def test_tsv_empty_string_returns_empty_list():
    assert _parse_tsv_rows("") == []
    assert _parse_tsv_rows("   \n\t\n  ") == []
