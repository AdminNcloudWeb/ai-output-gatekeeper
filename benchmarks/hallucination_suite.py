"""Gatekeeper AI Benchmark Suite.

Curated test cases for evaluating hallucination detection accuracy.
Targets: >=85% precision, >=75% recall on hallucination detection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class HallucinationType(Enum):
    FACTUAL = "factual"
    LOGICAL = "logical"
    CONTEXTUAL = "contextual"
    FABRICATION = "fabrication"
    NONE = "none"  # No hallucination


@dataclass
class TestCase:
    """A single benchmark test case."""
    id: str
    context: str
    output: str
    hallucination_type: HallucinationType
    should_flag: bool
    description: str
    difficulty: str = "medium"  # easy, medium, hard


@dataclass
class BenchmarkResult:
    """Result of running a benchmark suite."""
    total_cases: int
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        correct = self.true_positives + self.true_negatives
        return correct / self.total_cases if self.total_cases > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total_cases": self.total_cases,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
            "accuracy": round(self.accuracy, 3),
            "errors": self.errors,
        }


# ─── Test Cases ─────────────────────────────────────────────────

HALLUCINATION_TEST_CASES: list[TestCase] = [
    # Factual hallucinations
    TestCase(
        id="fact-001",
        context="Our refund policy allows returns within 30 days of purchase. Items must be in original packaging.",
        output="You can return items within 365 days as long as they're in original packaging.",
        hallucination_type=HallucinationType.FACTUAL,
        should_flag=True,
        description="Fabricated return period (365 vs 30 days)",
        difficulty="easy",
    ),
    TestCase(
        id="fact-002",
        context="We ship via UPS Ground (3-5 business days) and FedEx Express (1-2 business days).",
        output="All orders ship via DHL Express and arrive within 24 hours.",
        hallucination_type=HallucinationType.FACTUAL,
        should_flag=True,
        description="Wrong shipping carrier and delivery time",
        difficulty="easy",
    ),
    TestCase(
        id="fact-003",
        context="Our product supports Python 3.10, 3.11, and 3.12.",
        output="Our product supports Python 3.8, 3.9, 3.10, 3.11, and 3.12.",
        hallucination_type=HallucinationType.FACTUAL,
        should_flag=True,
        description="Claims support for unsupported Python versions",
        difficulty="medium",
    ),
    TestCase(
        id="fact-004",
        context="Our company was founded in 2021 and is based in San Francisco.",
        output="Our company was founded in 2021 and is based in San Francisco.",
        hallucination_type=HallucinationType.NONE,
        should_flag=False,
        description="Accurate statement — no hallucination",
        difficulty="easy",
    ),
    TestCase(
        id="fact-005",
        context="Our pricing starts at $99/month for the Starter tier.",
        output="Our pricing starts at $99/month for the Starter tier, with a Growth tier at $349/month.",
        hallucination_type=HallucinationType.NONE,
        should_flag=False,
        description="Accurate pricing information",
        difficulty="easy",
    ),

    # Logical hallucinations
    TestCase(
        id="logic-001",
        context="Our free tier includes 1,000 API calls per month. The Pro tier includes 10,000.",
        output="The free tier includes more API calls than the Pro tier.",
        hallucination_type=HallucinationType.LOGICAL,
        should_flag=True,
        description="Logical contradiction of tier comparison",
        difficulty="easy",
    ),
    TestCase(
        id="logic-002",
        context="Feature X was released in January 2024. Feature Y was released in March 2024.",
        output="Feature Y was released before Feature X.",
        hallucination_type=HallucinationType.LOGICAL,
        should_flag=True,
        description="Reversed chronological order",
        difficulty="medium",
    ),

    # Contextual hallucinations
    TestCase(
        id="ctx-001",
        context="Our API returns JSON responses. Rate limit is 100 requests/minute.",
        output="Our API returns XML responses with a rate limit of 100 requests/minute.",
        hallucination_type=HallucinationType.CONTEXTUAL,
        should_flag=True,
        description="Wrong response format (XML vs JSON)",
        difficulty="easy",
    ),
    TestCase(
        id="ctx-002",
        context="The dashboard shows scan volumes, violation breakdowns, and critical alerts.",
        output="The dashboard shows scan volumes, violation breakdowns, critical alerts, and revenue analytics.",
        hallucination_type=HallucinationType.CONTEXTUAL,
        should_flag=True,
        description="Added feature not in context (revenue analytics)",
        difficulty="medium",
    ),

    # Fabrication
    TestCase(
        id="fab-001",
        context="Our team has 15 engineers and 5 product managers.",
        output="Our team has 15 engineers, 5 product managers, and a dedicated AI research lab with 3 PhDs.",
        hallucination_type=HallucinationType.FABRICATION,
        should_flag=True,
        description="Fabricated team structure",
        difficulty="medium",
    ),
    TestCase(
        id="fab-002",
        context="We are SOC-2 Type II certified and GDPR compliant.",
        output="We are SOC-2 Type II certified, GDPR compliant, HIPAA compliant, and FedRAMP authorized.",
        hallucination_type=HallucinationType.FABRICATION,
        should_flag=True,
        description="Fabricated compliance certifications",
        difficulty="hard",
    ),

    # Edge cases (no hallucination)
    TestCase(
        id="edge-001",
        context="Our product is available in the US, Canada, and the UK.",
        output="Our product is available in the US, Canada, and the UK. We're expanding to Europe soon.",
        hallucination_type=HallucinationType.NONE,
        should_flag=False,
        description="Accurate + forward-looking statement (not a factual claim)",
        difficulty="hard",
    ),
    TestCase(
        id="edge-002",
        context="The SDK supports Python and JavaScript.",
        output="The SDK supports Python and JavaScript. We're working on Go and Rust support.",
        hallucination_type=HallucinationType.NONE,
        should_flag=False,
        description="Accurate + roadmap statement",
        difficulty="hard",
    ),
]


def get_test_cases(difficulty: Optional[str] = None) -> list[TestCase]:
    """Get test cases, optionally filtered by difficulty."""
    if difficulty:
        return [tc for tc in HALLUCINATION_TEST_CASES if tc.difficulty == difficulty]
    return HALLUCINATION_TEST_CASES


def get_summary() -> dict:
    """Get summary statistics of the benchmark suite."""
    cases = HALLUCINATION_TEST_CASES
    return {
        "total_cases": len(cases),
        "hallucination_cases": sum(1 for c in cases if c.should_flag),
        "clean_cases": sum(1 for c in cases if not c.should_flag),
        "by_difficulty": {
            "easy": sum(1 for c in cases if c.difficulty == "easy"),
            "medium": sum(1 for c in cases if c.difficulty == "medium"),
            "hard": sum(1 for c in cases if c.difficulty == "hard"),
        },
        "by_type": {
            t.value: sum(1 for c in cases if c.hallucination_type == t)
            for t in HallucinationType
        },
    }


if __name__ == "__main__":
    print(json.dumps(get_summary(), indent=2))
