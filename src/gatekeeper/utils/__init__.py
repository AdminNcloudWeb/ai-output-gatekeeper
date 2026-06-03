"""Utility functions for Gatekeeper."""

from __future__ import annotations

import re
from typing import Optional

from .models import FlaggedSpan, Severity


def find_spans(text: str, patterns: list[str], reason: str, severity: Severity = Severity.WARNING) -> list[FlaggedSpan]:
    """Find flagged spans in text matching any of the given patterns."""
    spans = []
    for pattern in patterns:
        try:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                spans.append(FlaggedSpan(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    reason=reason,
                    severity=severity,
                ))
        except re.error:
            continue
    return spans


def aggregate_risk_score(dimensions: dict) -> tuple[float, Severity]:
    """Compute aggregate risk score from dimension scores (0-100)."""
    if not dimensions:
        return 0.0, Severity.INFO

    scores = [d.score for d in dimensions.values()]
    # Weighted average: hallucinations count more
    weights = {"hallucination": 1.5, "brand": 1.0, "policy": 1.3, "safety": 1.4}
    weighted_sum = sum(
        d.score * weights.get(d.dimension, 1.0)
        for d in dimensions.values()
    )
    total_weight = sum(weights.get(d.dimension, 1.0) for d in dimensions.values())
    score = weighted_sum / total_weight

    if score >= 80:
        severity = Severity.CRITICAL
    elif score >= 50:
        severity = Severity.WARNING
    else:
        severity = Severity.INFO

    return round(score, 1), severity
