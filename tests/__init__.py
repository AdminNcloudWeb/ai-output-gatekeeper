"""Tests for Gatekeeper AI SDK."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gatekeeper.models import (
    DimensionScore,
    FlaggedSpan,
    GatekeeperConfig,
    Mode,
    ScanResult,
    Severity,
)
from gatekeeper.utils import aggregate_risk_score, find_spans


# ─── Models Tests ───────────────────────────────────────────────

class TestSeverity:
    def test_severity_values(self):
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.CRITICAL.value == "critical"

class TestMode:
    def test_mode_values(self):
        assert Mode.BLOCK.value == "block"
        assert Mode.FLAG.value == "flag"

class TestScanResult:
    def test_to_dict(self):
        result = ScanResult(
            risk_score=85.0,
            severity=Severity.CRITICAL,
            blocked=True,
            scan_time_ms=12.5,
        )
        d = result.to_dict()
        assert d["risk_score"] == 85.0
        assert d["severity"] == "critical"
        assert d["blocked"] is True
        assert d["scan_time_ms"] == 12.5

class TestDimensionScore:
    def test_to_dict(self):
        score = DimensionScore(
            dimension="hallucination",
            score=92.0,
            severity=Severity.CRITICAL,
            flagged_spans=[
                FlaggedSpan(start=0, end=10, text="fake claim", reason="No source", severity=Severity.CRITICAL),
            ],
            details="Test explanation",
        )
        d = score.to_dict()
        assert d["dimension"] == "hallucination"
        assert d["score"] == 92.0
        assert d["severity"] == "critical"
        assert len(d["flagged_spans"]) == 1
        assert d["flagged_spans"][0]["text"] == "fake claim"

class TestGatekeeperConfig:
    def test_defaults(self):
        config = GatekeeperConfig(api_key="test-key")
        assert config.mode == Mode.FLAG
        assert config.risk_threshold == 80.0
        assert config.scorer_model == "gpt-4o-mini"
        assert config.enable_hallucination is True
        assert config.enable_brand is True
        assert config.enable_policy is True
        assert config.enable_safety is True


# ─── Utility Tests ──────────────────────────────────────────────

class TestFindSpans:
    def test_finds_single_pattern(self):
        text = "Our refund policy allows returns within 365 days"
        spans = find_spans(text, [r"365 days"], "Policy claim")
        assert len(spans) == 1
        assert spans[0].text == "365 days"

    def test_finds_multiple_patterns(self):
        text = "This is guaranteed results with zero risk"
        spans = find_spans(text, [r"guaranteed", r"zero risk"], "Claim")
        assert len(spans) == 2

    def test_no_match(self):
        text = "This is a safe response"
        spans = find_spans(text, [r"bomb", r"hack"], "Safety")
        assert len(spans) == 0

    def test_empty_patterns(self):
        spans = find_spans("hello", [], "Test")
        assert len(spans) == 0


class TestAggregateRiskScore:
    def test_empty_dimensions(self):
        score, severity = aggregate_risk_score({})
        assert score == 0.0
        assert severity == Severity.INFO

    def test_critical_risk(self):
        dims = {
            "hallucination": DimensionScore("hallucination", 90.0, Severity.CRITICAL),
        }
        score, severity = aggregate_risk_score(dims)
        assert score >= 80.0
        assert severity == Severity.CRITICAL

    def test_warning_risk(self):
        dims = {
            "hallucination": DimensionScore("hallucination", 60.0, Severity.WARNING),
        }
        score, severity = aggregate_risk_score(dims)
        assert 50.0 <= score < 80.0
        assert severity == Severity.WARNING

    def test_low_risk(self):
        dims = {
            "hallucination": DimensionScore("hallucination", 10.0, Severity.INFO),
            "brand": DimensionScore("brand", 5.0, Severity.INFO),
        }
        score, severity = aggregate_risk_score(dims)
        assert score < 50.0
        assert severity == Severity.INFO


# ─── Scorer Tests (with mocked LLM) ─────────────────────────────

class TestHallucinationDetector:
    def test_no_knowledge_base(self):
        from gatekeeper.scoring.hallucination import HallucinationDetector
        config = GatekeeperConfig(api_key="test")
        scorer = HallucinationDetector(config)

        async def run():
            result = await scorer.async_score("test output")
            assert result.score == 0.0
            assert result.severity == Severity.INFO
            assert "skipped" in result.details.lower()

        asyncio.run(run())

    @patch("openai.AsyncOpenAI")
    def test_with_llm_response(self, mock_openai_class):
        from gatekeeper.scoring.hallucination import HallucinationDetector

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content='{"hallucination_detected": true, "risk_score": 75, "flagged_claims": [{"claim": "fake policy", "reason": "not in KB", "severity": "warning"}], "explanation": "Found unverifiable claim"}'))]
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_class.return_value = mock_client

        config = GatekeeperConfig(api_key="test", knowledge_base=["Our refund policy is 30 days."])
        scorer = HallucinationDetector(config)

        async def run():
            result = await scorer.async_score("Our refund policy is fake policy days.")
            assert result.score == 75.0
            assert result.severity == Severity.WARNING
            assert len(result.flagged_spans) == 1

        asyncio.run(run())

    def test_heuristic_fallback(self):
        from gatekeeper.scoring.hallucination import HallucinationDetector
        config = GatekeeperConfig(api_key="test", knowledge_base=["context doc"])
        scorer = HallucinationDetector(config)

        async def run():
            # Output with hedging markers
            result = await scorer.async_score("I think that this is certainly true and I am 100 percent sure.")
            assert result.score > 0  # Should detect markers
            assert "heuristic" in result.details.lower()

        asyncio.run(run())


class TestBrandScorer:
    def test_no_guidelines(self):
        from gatekeeper.scoring.brand import BrandScorer
        config = GatekeeperConfig(api_key="test")
        scorer = BrandScorer(config)

        async def run():
            result = await scorer.async_score("This is a test response.")
            assert result.score == 0.0
            assert result.severity == Severity.INFO

        asyncio.run(run())

    def test_with_rules(self):
        from gatekeeper.scoring.brand import BrandScorer
        config = GatekeeperConfig(
            api_key="test",
            policy_rules={"brand": [r"gonna", r"wanna", r"yeah[, ]"]},
        )
        scorer = BrandScorer(config)

        async def run():
            result = await scorer.async_score("Yeah, gonna do that for you.")
            assert result.score > 0
            assert len(result.flagged_spans) >= 1

        asyncio.run(run())


class TestPolicyChecker:
    def test_no_rules(self):
        from gatekeeper.scoring.policy import PolicyChecker
        config = GatekeeperConfig(api_key="test")
        scorer = PolicyChecker(config)

        async def run():
            result = await scorer.async_score("This is a normal response about your order.")
            assert result.score == 0.0
            assert result.severity == Severity.INFO

        asyncio.run(run())

    def test_with_policy_rules(self):
        from gatekeeper.scoring.policy import PolicyChecker
        config = GatekeeperConfig(
            api_key="test",
            policy_rules={
                "financial": [r"guaranteed returns", r"risk.?free investment"],
                "medical": [r"cures? (?:all|every)", r"guaranteed results"],
            },
        )
        scorer = PolicyChecker(config)

        async def run():
            result = await scorer.async_score("This product guarantees returns on all investments.")
            assert result.score > 0
            assert len(result.flagged_spans) >= 1

        asyncio.run(run())

    def test_compliance_rules_are_critical(self):
        from gatekeeper.scoring.policy import PolicyChecker
        config = GatekeeperConfig(
            api_key="test",
            policy_rules={"compliance": [r"guaranteed"]},
        )
        scorer = PolicyChecker(config)

        async def run():
            result = await scorer.async_score("This is a guaranteed outcome.")
            if result.flagged_spans:
                assert all(s.severity == Severity.CRITICAL for s in result.flagged_spans)

        asyncio.run(run())


class TestContentSafetyFilter:
    def test_no_issues(self):
        from gatekeeper.scoring.safety import ContentSafetyFilter
        config = GatekeeperConfig(api_key="test")
        scorer = ContentSafetyFilter(config)

        async def run():
            result = await scorer.async_score("Your order ships tomorrow via UPS.")
            assert result.score == 0.0
            assert result.severity == Severity.INFO
            assert "passed" in result.details.lower()

        asyncio.run(run())

    def test_blocklist_match(self):
        from gatekeeper.scoring.safety import ContentSafetyFilter
        config = GatekeeperConfig(
            api_key="test",
            safety_blocklist=["exploit vulnerability", "sql injection"],
        )
        scorer = ContentSafetyFilter(config)

        async def run():
            result = await scorer.async_score("Here is how to exploit vulnerability in your system.")
            assert result.score > 0
            assert result.severity == Severity.CRITICAL
            assert len(result.flagged_spans) >= 1

        asyncio.run(run())


# ─── Gatekeeper Core Tests ──────────────────────────────────────

class TestGatekeeperInit:
    def test_default_config(self):
        gk = Gatekeeper.__new__(Gatekeeper)
        # Just test config creation
        config = GatekeeperConfig(api_key="test-key")
        assert len([s for s in [config.enable_hallucination, config.enable_brand, config.enable_policy, config.enable_safety] if s]) == 4

    def test_disable_scorers(self):
        from gatekeeper.scoring import HallucinationDetector, BrandScorer, PolicyChecker, ContentSafetyFilter
        config = GatekeeperConfig(
            api_key="test",
            enable_hallucination=True,
            enable_brand=False,
            enable_policy=False,
            enable_safety=False,
        )
        scorers = []
        if config.enable_hallucination:
            scorers.append(HallucinationDetector(config))
        if config.enable_brand:
            scorers.append(BrandScorer(config))
        if config.enable_policy:
            scorers.append(PolicyChecker(config))
        if config.enable_safety:
            scorers.append(ContentSafetyFilter(config))
        assert len(scorers) == 1
        assert isinstance(scorers[0], HallucinationDetector)
