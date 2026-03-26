"""
Unit tests for app/services/plan_templates.py.

Validates that all templates are structurally sound — correct fields, valid
enum values, and coverage of all 7 layers — without touching the database.
"""

import pytest

from app.models.enums import PlanLayer, RuleType
from app.services.plan_templates import get_template, list_templates

_VALID_LAYERS = {layer.value for layer in PlanLayer}
_VALID_RULE_TYPES = {rt.value for rt in RuleType}
_VALID_WEIGHTS = {1, 2, 3}


def test_list_templates_returns_five():
    assert len(list_templates()) == 5


def test_expected_template_ids_present():
    ids = {t["id"] for t in list_templates()}
    assert ids == {
        "trend_pullback",
        "break_retest",
        "range_reversal",
        "failed_breakout",
        "inside_bar_breakout",
    }


def test_get_template_returns_correct_template():
    tmpl = get_template("trend_pullback")
    assert tmpl is not None
    assert tmpl["id"] == "trend_pullback"
    assert tmpl["name"] == "Trend Pullback"


def test_get_template_returns_none_for_unknown():
    assert get_template("nonexistent") is None
    assert get_template("trend_following") is None  # old ID no longer exists
    assert get_template("mean_reversion") is None   # old ID no longer exists


@pytest.mark.parametrize("tmpl", list_templates())
def test_template_has_required_fields(tmpl):
    assert "id" in tmpl
    assert "name" in tmpl
    assert "description" in tmpl
    assert "icon" in tmpl
    assert "rules" in tmpl
    assert isinstance(tmpl["rules"], list)
    assert len(tmpl["rules"]) > 0


@pytest.mark.parametrize("tmpl", list_templates())
def test_template_icon_is_non_empty_string(tmpl):
    assert isinstance(tmpl["icon"], str)
    assert len(tmpl["icon"]) > 0


@pytest.mark.parametrize("tmpl", list_templates())
def test_all_rules_have_valid_layers(tmpl):
    for rule in tmpl["rules"]:
        assert rule["layer"] in _VALID_LAYERS, (
            f"Template '{tmpl['id']}' rule '{rule['name']}' has invalid layer '{rule['layer']}'"
        )


@pytest.mark.parametrize("tmpl", list_templates())
def test_all_rules_have_valid_types(tmpl):
    for rule in tmpl["rules"]:
        assert rule["rule_type"] in _VALID_RULE_TYPES, (
            f"Template '{tmpl['id']}' rule '{rule['name']}' has invalid rule_type '{rule['rule_type']}'"
        )


@pytest.mark.parametrize("tmpl", list_templates())
def test_all_rules_have_valid_weights(tmpl):
    for rule in tmpl["rules"]:
        assert rule["weight"] in _VALID_WEIGHTS, (
            f"Template '{tmpl['id']}' rule '{rule['name']}' has invalid weight {rule['weight']}"
        )


@pytest.mark.parametrize("tmpl", list_templates())
def test_all_rules_have_non_empty_name_and_description(tmpl):
    for rule in tmpl["rules"]:
        assert rule["name"].strip(), f"Template '{tmpl['id']}' has a rule with an empty name"
        assert rule["description"].strip(), (
            f"Template '{tmpl['id']}' rule '{rule['name']}' has an empty description"
        )


@pytest.mark.parametrize("tmpl", list_templates())
def test_every_template_covers_all_seven_layers(tmpl):
    layers_present = {rule["layer"] for rule in tmpl["rules"]}
    missing = _VALID_LAYERS - layers_present
    assert not missing, (
        f"Template '{tmpl['id']}' is missing rules for layers: {missing}"
    )


@pytest.mark.parametrize("tmpl", list_templates())
def test_every_template_has_at_least_one_required_rule_per_layer(tmpl):
    from collections import defaultdict
    required_by_layer: dict[str, list] = defaultdict(list)
    for rule in tmpl["rules"]:
        if rule["rule_type"] == "REQUIRED":
            required_by_layer[rule["layer"]].append(rule["name"])
    for layer in _VALID_LAYERS:
        assert required_by_layer[layer], (
            f"Template '{tmpl['id']}' layer '{layer}' has no REQUIRED rules"
        )
