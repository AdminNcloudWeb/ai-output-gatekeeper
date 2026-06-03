"""Brand alignment scorer — configurable rules + LLM-as-judge for tone/voice."""

from __future__ import annotations

import json
import re
from typing import Optional

from gatekeeper.models import DimensionScore, FlaggedSpan, GatekeeperConfig, Severity
from gatekeeper.scoring.base import BaseScorer
from gatekeeper.utils import find_spans


class BrandScorer(BaseScorer):
    """Score brand voice/tone alignment using configurable rules + LLM-as-judge."""

    dimension = "brand"

    BRAND_PROMPT = """You are a brand voice evaluator. Evaluate the AI's OUTPUT against the BRAND GUIDELINES.

Check for:
1. Tone violations (too casual, too formal, conflicting with guidelines)
2. Terminology issues (wrong product names, prohibited terms)
3. Style violations (sentence length, formatting, voice)
4. Brand personality misalignment

Respond in JSON format:
{{
  "misalignment_detected": true/false,
  "risk_score": 0-100,
  "flagged_spans": [
    {{"text": "...", "reason": "...", "severity": "critical|warning|info"}}
  ],
  "explanation": "Brief summary"
}}

BRAND GUIDELINES:
---
{guidelines}
---

AI OUTPUT:
---
{output}
---

JSON Response:"""

    async def async_score(self, output: str, context: Optional[dict] = None) -> DimensionScore:
        rule_spans = self._check_rules(output)
        rule_score = min(len(rule_spans) * 15.0, 60.0)

        if not self.config.brand_guidelines:
            return DimensionScore(
                dimension=self.dimension, score=rule_score,
                severity=Severity.WARNING if rule_score > 0 else Severity.INFO,
                flagged_spans=rule_spans,
                details="Brand guidelines not provided - regex rules only."
            )

        try:
            result = await self._call_judge(self.BRAND_PROMPT.format(
                guidelines=self.config.brand_guidelines, output=output
            ))
            judge_score = self._parse_judge_result(result, output, rule_spans)
            combined = max(rule_score, judge_score.score)
            all_spans = list(set(rule_spans + judge_score.flagged_spans))
            severity = Severity.CRITICAL if combined >= 80 else Severity.WARNING if combined >= 40 else Severity.INFO

            return DimensionScore(
                dimension=self.dimension, score=combined, severity=severity,
                flagged_spans=all_spans, details=judge_score.details,
            )
        except Exception:
            severity = Severity.WARNING if rule_score > 0 else Severity.INFO
            return DimensionScore(
                dimension=self.dimension, score=rule_score, severity=severity,
                flagged_spans=rule_spans, details="LLM judge unavailable - regex rules only."
            )

    def _check_rules(self, output: str) -> list:
        spans = []
        rules = self.config.policy_rules or {}
        brand_rules = rules.get("brand", [])
        if brand_rules:
            spans.extend(find_spans(output, brand_rules, "Brand rule violation"))
        return spans

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

    def _parse_judge_result(self, raw: str, output: str, existing_spans: list) -> DimensionScore:
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            data = json.loads(json_match.group()) if json_match else json.loads(raw)

            spans = list(existing_spans)
            for item in data.get("flagged_spans", []):
                text = item.get("text", "")
                if text and text in output:
                    idx = output.index(text)
                    sev = Severity(item.get("severity", "warning"))
                    spans.append(FlaggedSpan(
                        start=idx, end=idx + len(text), text=text,
                        reason=item.get("reason", "Brand misalignment"), severity=sev,
                    ))

            score = float(data.get("risk_score", 0))
            severity = Severity.CRITICAL if score >= 80 else Severity.WARNING if score >= 40 else Severity.INFO

            return DimensionScore(
                dimension=self.dimension, score=score, severity=severity,
                flagged_spans=spans, details=data.get("explanation"),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return DimensionScore(
                dimension=self.dimension, score=20.0, severity=Severity.WARNING,
                flagged_spans=existing_spans, details="Failed to parse brand judge response."
            )
