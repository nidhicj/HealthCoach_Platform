"""Unit tests: `_build_test_recommendation` — pure function, no DB, no HTTP.

Per PHASE-02 Task 5 brief and SPEC-0001 Stage 3 step 3-5 / "Lab recommendation and
token" acceptance criteria. Matching semantics per PHASE-02 Decision D-4: SPEC-0001's
"ILIKE" language is implemented as Python case-insensitive substring matching against
data already in memory (not a literal SQL query).
"""
from src.api.intake import _build_test_recommendation


def test_standard_tests_always_present_even_with_zero_matching_responses():
    test_panel = {
        "standard_tests": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
        "condition_rules": [
            {"keywords": ["PCOD"], "tests": ["Hormonal Panel (LH, FSH, AMH)"]},
        ],
    }
    responses = {
        "current_health_concerns": "None",
        "primary_health_goal": "General fitness",
    }

    result = _build_test_recommendation(test_panel, responses)

    assert result["standard"] == ["CBC", "HbA1c", "TSH", "Lipid Profile"]
    assert result["additions"] == []
    assert result["all_tests"] == ["CBC", "HbA1c", "TSH", "Lipid Profile"]


def test_single_keyword_match_adds_right_test_with_correct_triggered_by():
    test_panel = {
        "standard_tests": ["CBC", "HbA1c"],
        "condition_rules": [
            {"keywords": ["PCOD"], "tests": ["Hormonal Panel (LH, FSH, AMH)"]},
        ],
    }
    responses = {"current_health_concerns": "I was diagnosed with PCOD last year"}

    result = _build_test_recommendation(test_panel, responses)

    assert result["additions"] == [
        {"test": "Hormonal Panel (LH, FSH, AMH)", "triggered_by": "PCOD"}
    ]
    assert result["all_tests"] == ["CBC", "HbA1c", "Hormonal Panel (LH, FSH, AMH)"]


def test_multiple_different_keywords_in_different_responses_all_match():
    test_panel = {
        "standard_tests": ["CBC"],
        "condition_rules": [
            {"keywords": ["PCOD"], "tests": ["Hormonal Panel (LH, FSH, AMH)"]},
            {"keywords": ["hypothyroid", "thyroid"], "tests": ["TSH", "T3", "T4"]},
        ],
    }
    responses = {
        "current_health_concerns": "PCOD diagnosed in 2022",
        "primary_health_goal": "Manage my hypothyroid condition",
    }

    result = _build_test_recommendation(test_panel, responses)

    triggered_by = {a["triggered_by"] for a in result["additions"]}
    tests_added = {a["test"] for a in result["additions"]}
    assert triggered_by == {"PCOD", "hypothyroid"}
    assert tests_added == {"Hormonal Panel (LH, FSH, AMH)", "TSH", "T3", "T4"}
    assert result["all_tests"] == [
        "CBC",
        "Hormonal Panel (LH, FSH, AMH)",
        "TSH",
        "T3",
        "T4",
    ]


def test_test_in_both_standard_and_matched_condition_rule_deduped_in_all_tests():
    test_panel = {
        "standard_tests": ["CBC", "TSH"],
        "condition_rules": [
            {"keywords": ["thyroid"], "tests": ["TSH", "T3"]},
        ],
    }
    responses = {"current_health_concerns": "thyroid issues since college"}

    result = _build_test_recommendation(test_panel, responses)

    # TSH is in both `standard` and the matched rule's tests -> only once in all_tests.
    assert result["all_tests"].count("TSH") == 1
    assert result["all_tests"] == ["CBC", "TSH", "T3"]
    # additions still records the raw match, even though TSH already existed in standard.
    assert {"test": "TSH", "triggered_by": "thyroid"} in result["additions"]


def test_keyword_substring_match_within_longer_word_is_intended_loose_behavior():
    """Per D-4, matching is plain Python substring containment
    (`keyword.lower() in response_text.lower()`), not word-boundary-aware. A keyword
    like "PCOD" appearing as a substring of a longer token IS intended to match —
    this test documents and locks in that (deliberately loose) behavior."""
    test_panel = {
        "standard_tests": [],
        "condition_rules": [
            {"keywords": ["PCOD"], "tests": ["Hormonal Panel (LH, FSH, AMH)"]},
        ],
    }
    responses = {"current_health_concerns": "superPCODextra"}  # PCOD embedded mid-word

    result = _build_test_recommendation(test_panel, responses)

    assert result["additions"] == [
        {"test": "Hormonal Panel (LH, FSH, AMH)", "triggered_by": "PCOD"}
    ]
    assert result["all_tests"] == ["Hormonal Panel (LH, FSH, AMH)"]


def test_matching_is_case_insensitive():
    test_panel = {
        "standard_tests": [],
        "condition_rules": [
            {"keywords": ["PCOD"], "tests": ["Hormonal Panel (LH, FSH, AMH)"]},
        ],
    }
    responses = {"current_health_concerns": "diagnosed with pcod"}

    result = _build_test_recommendation(test_panel, responses)

    assert result["additions"] == [
        {"test": "Hormonal Panel (LH, FSH, AMH)", "triggered_by": "PCOD"}
    ]


def test_empty_responses_and_empty_condition_rules_produce_only_standard():
    test_panel = {"standard_tests": ["CBC"], "condition_rules": []}

    result = _build_test_recommendation(test_panel, {})

    assert result == {"standard": ["CBC"], "additions": [], "all_tests": ["CBC"]}


def test_no_false_addition_when_keyword_not_present_in_any_response():
    test_panel = {
        "standard_tests": ["CBC"],
        "condition_rules": [
            {"keywords": ["PCOD"], "tests": ["Hormonal Panel (LH, FSH, AMH)"]},
        ],
    }
    responses = {"current_health_concerns": "Just tired a lot, nothing else"}

    result = _build_test_recommendation(test_panel, responses)

    assert result["additions"] == []
    assert result["all_tests"] == ["CBC"]
