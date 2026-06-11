import pytest

from cq3d.errors import ValidationError
from cq3d.expressions import evaluate_expression


def test_evaluates_arithmetic_and_functions():
    variables = {"width": 165.0, "depth": 160.0}
    value = evaluate_expression("max(width / 2, depth - 100) + abs(-5)", variables, line=1)
    assert value == pytest.approx(87.5)


def test_rejects_unknown_variable():
    with pytest.raises(ValidationError, match="unknown variable"):
        evaluate_expression("missing + 1", {}, line=3)


def test_rejects_unit_suffixes():
    with pytest.raises(ValidationError, match="units are not allowed"):
        evaluate_expression("10mm", {}, line=4)


def test_rejects_division_by_zero():
    with pytest.raises(ValidationError, match="division by zero"):
        evaluate_expression("3 / 0", {}, line=5)
