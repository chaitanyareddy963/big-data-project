import math

import pytest

from api.scoring import linear_probability


MODEL = {"feature_names": ["x", "y"], "coefficients": [1.0, -0.5], "intercept": 0.25}


def test_linear_probability_matches_logistic_formula() -> None:
    expected = 1 / (1 + math.exp(-1.25))
    assert linear_probability({"x": 2.0, "y": 2.0}, MODEL) == pytest.approx(expected)


def test_linear_probability_reports_missing_features() -> None:
    with pytest.raises(ValueError, match="Missing model features"):
        linear_probability({"x": 1.0}, MODEL)
