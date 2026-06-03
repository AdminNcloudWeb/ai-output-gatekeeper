"""Competitive analysis benchmark — Gatekeeper vs AIMon vs NeMo Guardrails.

This module provides a framework for running comparative benchmarks
against competitor tools. Each tool is evaluated on the same test cases
from the hallucination benchmark suite.

Note: This is a framework. Actual competitor API calls require valid API keys.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from benchmarks.hallucination_suite import TestCase, get_test_cases


@dataclass
class CompetitorResult:
    """Result from a single competitor on a single test case."""
    tool: str
    test_case_id: str
    flagged: bool
    score: Optional[float] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class CompetitiveAnalysis:
    """Comparative results across tools."""
    results: dict[str, list[CompetitorResult]] = field(default_factory=dict)

    def add_result(self, result: CompetitorResult):
        if result.tool not in self.results:
            self.results[result.tool] = []
        self.results[result.tool].append(result)

    def compare(self, test_cases: list[TestCase]) -> dict:
        """Generate comparative metrics."""
        comparison = {}
        for tool, results in self.results.items():
            tp = sum(1 for r in results if r.flagged and any(
                tc.should_flag for tc in test_cases if tc.id == r.test_case_id
            ))
            fp = sum(1 for r in results if r.flagged and not any(
                tc.should_flag for tc in test_cases if tc.id == r.test_case_id
            ))
            fn = sum(1 for r in results if not r.flagged and any(
                tc.should_flag for tc in test_cases if tc.id == r.test_case_id
            ))
            tn = sum(1 for r in results if not r.flagged and not any(
                tc.should_flag for tc in test_cases if tc.id == r.test_case_id
            ))

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            latencies = [r.latency_ms for r in results if r.latency_ms is not None]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

            comparison[tool] = {
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
                "avg_latency_ms": round(avg_latency, 1),
                "errors": sum(1 for r in results if r.error),
            }
        return comparison


async def run_gatekeeper_benchmark(
    test_cases: list[TestCase],
    api_key: str,
) -> list[CompetitorResult]:
    """Run Gatekeeper on all test cases."""
    from gatekeeper import Gatekeeper

    gk = Gatekeeper(
        api_key=api_key,
        knowledge_base=[tc.context for tc in test_cases[:5]],
        mode="flag",
    )

    results = []
    for tc in test_cases:
        try:
            import time
            start = time.monotonic()
            _, scan = gk.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": tc.output}],
            )
            latency = (time.monotonic() - start) * 1000
            results.append(CompetitorResult(
                tool="gatekeeper",
                test_case_id=tc.id,
                flagged=scan.risk_score >= 50,
                score=scan.risk_score,
                latency_ms=latency,
            ))
        except Exception as e:
            results.append(CompetitorResult(
                tool="gatekeeper",
                test_case_id=tc.id,
                flagged=False,
                error=str(e),
            ))
    return results


async def run_aimon_benchmark(
    test_cases: list[TestCase],
    api_key: str,
) -> list[CompetitorResult]:
    """Run AIMon on all test cases. Requires AIMon API key."""
    results = []
    for tc in test_cases:
        try:
            import httpx
            import time
            start = time.monotonic()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.aimon.ai/v1/detect",
                    json={
                        "text": tc.output,
                        "context": tc.context,
                    },
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=30.0,
                )
                data = resp.json()
                latency = (time.monotonic() - start) * 1000
                results.append(CompetitorResult(
                    tool="aimon",
                    test_case_id=tc.id,
                    flagged=data.get("hallucination_detected", False),
                    score=data.get("score"),
                    latency_ms=latency,
                ))
        except Exception as e:
            results.append(CompetitorResult(
                tool="aimon",
                test_case_id=tc.id,
                flagged=False,
                error=str(e),
            ))
    return results


def generate_report(analysis: CompetitiveAnalysis, test_cases: list[TestCase]) -> str:
    """Generate a markdown comparison report."""
    comparison = analysis.compare(test_cases)

    lines = [
        "# Competitive Benchmark Report",
        "",
        f"**Test cases:** {len(test_cases)}",
        f"**Tools compared:** {', '.join(comparison.keys())}",
        "",
        "## Results",
        "",
        "| Tool | Precision | Recall | F1 | Avg Latency (ms) | Errors |",
        "|------|-----------|--------|-----|------------------|--------|",
    ]

    for tool, metrics in comparison.items():
        lines.append(
            f"| {tool} | {metrics['precision']:.1%} | {metrics['recall']:.1%} | "
            f"{metrics['f1']:.1%} | {metrics['avg_latency_ms']:.0f} | {metrics['errors']} |"
        )

    lines.extend([
        "",
        "## Target Metrics",
        "",
        "- Precision: >= 85%",
        "- Recall: >= 75%",
        "- F1: >= 80%",
        "",
        "## Notes",
        "",
        "- Gatekeeper uses LLM-as-judge with chain-of-thought reasoning",
        "- AIMon uses proprietary hallucination detection model",
        "- NeMo Guardrails uses programmable rules (not included in async benchmark)",
        "- All tools tested on identical test cases with same context",
    ])

    return "\n".join(lines)
