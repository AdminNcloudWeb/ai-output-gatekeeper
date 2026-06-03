"""Data models for Gatekeeper scan results."""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Optional


class Severity(Enum):
    """Risk severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Mode(Enum):
    """Scanning mode: block or flag."""
    BLOCK = "block"
    FLAG = "flag"


@dataclasses.dataclass
class FlaggedSpan:
    """A flagged span within the output text."""
    start: int
    end: int
    text: str
    reason: str
    severity: Severity = Severity.WARNING

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "reason": self.reason,
            "severity": self.severity.value,
        }


@dataclasses.dataclass
class DimensionScore:
    """Score for a single scanning dimension."""
    dimension: str
    score: float  # 0-100, higher = more risky
    severity: Severity
    flagged_spans: list[FlaggedSpan] = dataclasses.field(default_factory=list)
    details: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "severity": self.severity.value,
            "flagged_spans": [s.to_dict() for s in self.flagged_spans],
            "details": self.details,
        }


@dataclasses.dataclass
class ScanResult:
    """Complete scan result for a single LLM output."""
    risk_score: float  # 0-100 aggregate
    severity: Severity
    dimensions: dict[str, DimensionScore] = dataclasses.field(default_factory=dict)
    blocked: bool = False
    raw_output: Optional[str] = None
    scan_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "risk_score": self.risk_score,
            "severity": self.severity.value,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "blocked": self.blocked,
            "raw_output": self.raw_output,
            "scan_time_ms": self.scan_time_ms,
        }


@dataclasses.dataclass
class GatekeeperConfig:
    """Configuration for the Gatekeeper SDK."""
    api_key: str
    mode: Mode = Mode.FLAG
    risk_threshold: float = 80.0  # Block/flag above this score
    knowledge_base: Optional[list[str]] = None
    brand_guidelines: Optional[str] = None
    policy_rules: Optional[dict[str, list[str]]] = None
    safety_blocklist: Optional[list[str]] = None
    scorer_model: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    redis_url: Optional[str] = None
    enable_hallucination: bool = True
    enable_brand: bool = True
    enable_policy: bool = True
    enable_safety: bool = True
