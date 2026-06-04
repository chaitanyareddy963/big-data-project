"""Pure scoring helpers shared by BentoML and unit tests."""

from __future__ import annotations

import math


def linear_probability(features: dict[str, float], model: dict) -> float:
    names = model["feature_names"]
    coefficients = model["coefficients"]
    missing = sorted(set(names) - set(features))
    if missing:
        raise ValueError(f"Missing model features: {missing}")
    margin = model["intercept"] + sum(
        float(features[name]) * float(coefficient)
        for name, coefficient in zip(names, coefficients, strict=True)
    )
    if margin >= 0:
        return 1.0 / (1.0 + math.exp(-margin))
    exp_margin = math.exp(margin)
    return exp_margin / (1.0 + exp_margin)
