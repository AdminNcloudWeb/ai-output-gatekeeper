"""Hallucination detection scorer — LLM-as-judge comparing output against context."""

from __future__ import annotations

import json
import re
from typing import Optional

from gatekeeper.models import DimensionScore, FlaggedSpan, GatekeeperConfig, Severity
from gatekeeper.scoring.base import BaseScorer


class HallucinationDetector(BaseScorer):
    """Detect factual hallucinations by comparing output against provided context/ground truth."""

    dimension = "hallucination"

    HALLUCINATION_PROMPT = """You are a hallucination detector. Compare the AI's OUTPUT against the PROVIDED CONTEXT (knowledge base / ground truth).

Identify any claims in the OUTPUT that are:
1. Factually incorrect based on the context
2. Not supported by the context (fabricated details)
3. Contradicted by the context
4. Logical inconsistencies

Respond in JSON format:
{{
  "hallucination_detected": true/false,
  "risk_score": 0-100,
  "flagged_claims": [
    {{"claim": "...", "reason": "...", "severity": "critical|warning|info"}}
  ],
  "explanation": "Brief summary"
}}

CONTEXT:
---
{context}
---

AI OUTPUT:
---
{output}
---

JSON Response:"""

    async def async_score(self, output: str, context: Optional[dict] = None) -> DimensionScore:
        if not self.config.knowledge_base:
            return DimensionScore(
                dimension=self.dimension, score=0.0, severity=Severity.INFO,
                details="No knowledge base provided - hallucination detection skipped."
            )

        context_text = "\n".join(self.config.knowledge_base[:10])

        try:
            result = await self._call_judge(self.HALLUCINATION_PROMPT.format(
                context=context_text, output=output
            ))
            return self._parse_result(result, output)
        except Exception:
            return self._heuristic_score(output)

    async def _call_judge(self, prompt: str) -> str:
        import openai
        client = openai.AsyncOpenAI(api_key=self.config.api_key)
        resp = await client.chat.completions.create(
            model=self.config.scorer_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""

    def _parse_result(self, raw: str, output: str) -> DimensionScore:
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            data = json.loads(json_match.group()) if json_match else json.loads(raw)

            spans = []
            for claim in data.get("flagged_claims", []):
                claim_text = claim.get("claim", "")
                if claim_text and claim_text in output:
                    idx = output.index(claim_text)
                    sev = Severity(claim.get("severity", "warning"))
                    spans.append(FlaggedSpan(
                        start=idx, end=idx + len(claim_text),
                        text=claim_text,
                        reason=claim.get("reason", "Potential hallucination"),
                        severity=sev,
                    ))

            score = float(data.get("risk_score", 0))
            severity = Severity.CRITICAL if score >= 80 else Severity.WARNING if score >= 40 else Severity.INFO

            return DimensionScore(
                dimension=self.dimension, score=score, severity=severity,
                flagged_spans=spans, details=data.get("explanation"),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return DimensionScore(
                dimension=self.dimension, score=30.0, severity=Severity.WARNING,
                details="Failed to parse LLM judge response. Used default score."
            )

    def _heuristic_score(self, output: str) -> DimensionScore:
        hallucination_markers = [
            r"As an AI(?: language model)?[, ]",
            r"I (?:think|believe|feel) that",
            r"(?:almost )?certainly",
            r"(?:100|one hundred) percent",
        ]
        spans = []
        total_risk = 0.0
        for pattern in hallucination_markers:
            for match in re.finditer(pattern, output, re.IGNORECASE):
                spans.append(FlaggedSpan(
                    start=match.start(), end=match.end(),
                    text=match.group(),
                    reason="Hedging or certainty marker - potential hallucination signal",
                    severity=Severity.INFO,
                ))
                total_risk += 10

        score = min(total_risk, 50.0)
        return DimensionScore(
            dimension=self.dimension, score=score,
            severity=Severity.WARNING if score > 0 else Severity.INFO,
            flagged_spans=spans,
            details="Heuristic-based scoring (LLM judge unavailable).",
        )
