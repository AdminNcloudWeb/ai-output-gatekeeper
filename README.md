# Gatekeeper AI

**Pre-delivery LLM response monitoring & brand safety.**

Gatekeeper AI is a Python SDK that wraps your OpenAI/Anthropic calls and scans every LLM output before it reaches your users. Detect hallucinations, brand misalignment, policy violations, and harmful content — in real-time.

## Features

- 🔍 **Hallucination Detection** — LLM-as-judge compares output against your knowledge base
- 🎯 **Brand Alignment Scoring** — Configurable rules + LLM-as-judge for tone/voice
- 📋 **Policy Compliance** — Regex rules for compliance violations
- 🛡️ **Content Safety** — Blocklist + classifier for harmful content
- 📊 **Real-time Dashboard** — Scan analytics, violation breakdowns, alerts
- ⚡ **Async Support** — Non-blocking scanning with Redis-backed queue
- 🔧 **Configurable** — Blocking or flagging mode, adjustable thresholds

## Quickstart

```bash
pip install gatekeeper-ai
```

```python
from gatekeeper import Gatekeeper

gk = Gatekeeper(
    api_key="your-openai-key",
    knowledge_base=["Our refund policy is 30 days.", "We ship via UPS Ground."],
    brand_guidelines="Professional tone. Use 'we' not 'I'. No slang.",
    mode="flag",  # or "block" to halt delivery above threshold
)

response, scan = gk.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's your refund policy?"}]
)

print(f"Risk score: {scan.risk_score}")
print(f"Severity: {scan.severity.value}")
for dim_name, dim in scan.dimensions.items():
    print(f"  {dim_name}: {dim.score} - {dim.details}")
```

## Async Usage

```python
response, scan = await gk.chat.async_completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | str | required | OpenAI API key |
| `mode` | str | "flag" | "flag" (annotate) or "block" (halt delivery) |
| `risk_threshold` | float | 80.0 | Score above which to block/flag |
| `knowledge_base` | list[str] | None | Ground truth docs for hallucination detection |
| `brand_guidelines` | str | None | Brand voice/tone guidelines |
| `policy_rules` | dict | None | Regex rules by category |
| `safety_blocklist` | list[str] | None | Blocked phrases |
| `scorer_model` | str | "gpt-4o-mini" | LLM model for scoring |

## Pricing

- **Starter**: $99/mo — 50K scans/mo
- **Growth**: $349/mo — 500K scans/mo
- **Enterprise**: Custom — Unlimited scans, on-prem, SOC-2

## License

MIT
