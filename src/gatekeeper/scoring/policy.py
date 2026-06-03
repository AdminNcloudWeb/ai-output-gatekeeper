"""Policy compliance checker — regex + keyword rules for compliance violations."""

from __future__ import annotations

from typing import Optional

from gatekeeper.models import DimensionScore, FlaggedSpan, GatekeeperConfig, Severity
from gatekeeper.scoring.base import BaseScorer
from gatekeeper.utils import find_spans


class PolicyChecker(BaseScorer):
    """Check for policy and compliance violations using regex + keyword rules."""

    dimension = "policy"

    async def async_score(self, output: str, context: Optional[dict] = None) -> DimensionScore:
        spans = []
        rules = self.config.policy_rules or {}

        for rule_name, patterns in rules.items():
            if rule_name == "brand":
                continue  # Handled by BrandScorer
            spans.extend(find_spans(
                output, patterns,
                f"Policy violation: {rule_name}",
                severity=Severity.CRITICAL if "compliance" in rule_name else Severity.WARNING,
            ))

        critical_count = sum(1 for s in spans if s.severity == Severity.CRITICAL)
        warning_count = sum(1 for s in spans if s.severity == Severity.WARNING)
        score = min(critical_count * 30.0 + warning_count * 10.0, 100.0)
        severity = Severity.CRITICAL if score >= 70 else Severity.WARNING if score >= 30 else Severity.INFO

        details = f"Found {len(spans)} policy violations." if spans else "No policy violations detected."
        return DimensionScore(
            dimension=self.dimension, score=score, severity=severity,
            flagged_spans=spans, details=details,
        )
