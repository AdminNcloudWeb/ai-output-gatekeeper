"""Core Gatekeeper SDK — proxy/wrapper pattern around OpenAI/Anthropic SDKs."""

from __future__ import annotations

import time
from typing import Any, Optional

from gatekeeper.models import (
    GatekeeperConfig,
    Mode,
    ScanResult,
    Severity,
)
from gatekeeper.utils import aggregate_risk_score
from gatekeeper.scoring import (
    HallucinationDetector,
    BrandScorer,
    PolicyChecker,
    ContentSafetyFilter,
)


class Gatekeeper:
    """Main Gatekeeper SDK class. Wraps LLM API calls with pre-delivery scanning.

    Usage:
        gk = Gatekeeper(api_key="your-key", knowledge_base=docs)
        response, scan_result = gk.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "What's our refund policy?"}]
        )
    """

    def __init__(
        self,
        api_key: str,
        mode: str = "flag",
        risk_threshold: float = 80.0,
        knowledge_base: Optional[list[str]] = None,
        brand_guidelines: Optional[str] = None,
        policy_rules: Optional[dict[str, list[str]]] = None,
        safety_blocklist: Optional[list[str]] = None,
        scorer_model: str = "gpt-4o-mini",
        redis_url: Optional[str] = None,
        enable_hallucination: bool = True,
        enable_brand: bool = True,
        enable_policy: bool = True,
        enable_safety: bool = True,
    ):
        self.config = GatekeeperConfig(
            api_key=api_key,
            mode=Mode(mode),
            risk_threshold=risk_threshold,
            knowledge_base=knowledge_base,
            brand_guidelines=brand_guidelines,
            policy_rules=policy_rules,
            safety_blocklist=safety_blocklist,
            scorer_model=scorer_model,
            redis_url=redis_url,
            enable_hallucination=enable_hallucination,
            enable_brand=enable_brand,
            enable_policy=enable_policy,
            enable_safety=enable_safety,
        )

        # Initialize scorers
        self._scorers = []
        if enable_hallucination:
            self._scorers.append(HallucinationDetector(self.config))
        if enable_brand:
            self._scorers.append(BrandScorer(self.config))
        if enable_policy:
            self._scorers.append(PolicyChecker(self.config))
        if enable_safety:
            self._scorers.append(ContentSafetyFilter(self.config))

        # Initialize OpenAI client
        import openai
        self._openai_client = openai.OpenAI(api_key=api_key)
        self._async_openai_client = openai.AsyncOpenAI(api_key=api_key)

    @property
    def chat(self):
        """Access the chat completions proxy."""
        return _ChatProxy(self)

    def _extract_output_text(self, response: Any) -> str:
        """Extract the text output from an OpenAI chat completion response."""
        try:
            return response.choices[0].message.content or ""
        except (AttributeError, IndexError):
            return str(response)

    async def _async_extract_output_text(self, response: Any) -> str:
        """Extract the text output from an async OpenAI chat completion response."""
        try:
            return response.choices[0].message.content or ""
        except (AttributeError, IndexError):
            return str(response)

    def _should_block(self, scan_result: ScanResult) -> bool:
        """Determine if the response should be blocked based on config and scan result."""
        if self.config.mode == Mode.BLOCK:
            if scan_result.risk_score >= self.config.risk_threshold:
                return True
            if scan_result.severity == Severity.CRITICAL:
                return True
        return False


class _ChatProxy:
    """Proxy for OpenAI chat.completions with Gatekeeper scanning."""

    def __init__(self, gatekeeper: Gatekeeper):
        self._gk = gatekeeper

    def create(
        self,
        model: str = "gpt-4o",
        messages: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> tuple[Any, ScanResult]:
        """Make a synchronous OpenAI chat completion call with Gatekeeper scanning."""
        import asyncio

        # Call OpenAI
        call_kwargs: dict = {
            "model": model,
            "messages": messages or [],
            "temperature": temperature,
        }
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        call_kwargs.update(kwargs)

        response = self._gk._openai_client.chat.completions.create(**call_kwargs)

        # Scan the output
        output_text = self._gk._extract_output_text(response)

        try:
            scan_result = asyncio.run(self._async_scan(output_text))
        except Exception:
            scan_result = ScanResult(
                risk_score=0.0,
                severity=Severity.INFO,
                details="Scanning failed — passing through unblocked.",
            )

        if self._gk._should_block(scan_result):
            scan_result.blocked = True

        return response, scan_result

    async def async_create(
        self,
        model: str = "gpt-4o",
        messages: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> tuple[Any, ScanResult]:
        """Make an async OpenAI chat completion call with Gatekeeper scanning."""
        call_kwargs: dict = {
            "model": model,
            "messages": messages or [],
            "temperature": temperature,
        }
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        call_kwargs.update(kwargs)

        response = await self._gk._async_openai_client.chat.completions.create(**call_kwargs)
        output_text = self._gk._async_extract_output_text(response)
        scan_result = await self._async_scan(output_text)

        if self._gk._should_block(scan_result):
            scan_result.blocked = True

        return response, scan_result

    async def _async_scan(self, output: str) -> ScanResult:
        """Run all enabled scoring modules asynchronously."""
        import asyncio

        start = time.monotonic()

        tasks = [scorer.async_score(output) for scorer in self._gk._scorers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        dimensions: dict = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            dimensions[result.dimension] = result

        score, severity = aggregate_risk_score(dimensions)
        elapsed_ms = (time.monotonic() - start) * 1000

        return ScanResult(
            risk_score=score,
            severity=severity,
            dimensions=dimensions,
            raw_output=output,
            scan_time_ms=round(elapsed_ms, 1),
        )
