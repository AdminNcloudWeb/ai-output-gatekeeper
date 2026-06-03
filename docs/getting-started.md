# Gatekeeper AI — Documentation

## Getting Started

### Installation

```bash
pip install gatekeeper-ai
```

### 5-Minute Quickstart

```python
from gatekeeper import Gatekeeper

# Initialize with your OpenAI key and knowledge base
gk = Gatekeeper(
    api_key="sk-...",
    knowledge_base=[
        "Our company refund policy allows returns within 30 days of purchase.",
        "We ship via UPS Ground (3-5 business days) and FedEx Express (1-2 days).",
        "Our product supports Python 3.10+, Node.js 18+, and Go 1.21+.",
    ],
    brand_guidelines="""
    - Professional but friendly tone
    - Use 'we' not 'I' or 'me'
    - Never use slang or overly casual language
    - Always be accurate about product capabilities
    - Do not make promises about timelines
    """,
    policy_rules={
        "financial": [r"guaranteed returns", r"risk.?free investment"],
        "medical": [r"cures? all", r"guaranteed results"],
        "compliance": [r"fda approved", r"legally binding"],
    },
)

# Make a scanned API call
response, scan = gk.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's your refund policy?"}]
)

# Check the scan result
if scan.severity.value == "critical":
    print("⚠️ High-risk output detected!")
    for dim in scan.dimensions.values():
        if dim.score > 50:
            print(f"  {dim.dimension}: {dim.score} - {dim.details}")
else:
    print(f"✅ Output passed all checks (risk: {scan.risk_score})")
```

## SDK Reference

### Gatekeeper Class

The main entry point. Wraps OpenAI chat completions with pre-delivery scanning.

#### Constructor

```python
Gatekeeper(
    api_key: str,                    # OpenAI API key (required)
    mode: str = "flag",               # "flag" or "block"
    risk_threshold: float = 80.0,     # Block/flag above this score
    knowledge_base: list[str] = None, # Ground truth documents
    brand_guidelines: str = None,     # Brand voice guidelines
    policy_rules: dict = None,        # Regex rules by category
    safety_blocklist: list = None,    # Blocked phrases
    scorer_model: str = "gpt-4o-mini", # LLM for scoring
    redis_url: str = None,            # Redis URL for async queue
    enable_hallucination: bool = True,
    enable_brand: bool = True,
    enable_policy: bool = True,
    enable_safety: bool = True,
)
```

#### Methods

- `gk.chat.completions.create(**kwargs)` — Sync call, returns `(response, ScanResult)`
- `await gk.chat.async_completions.create(**kwargs)` — Async call

### ScanResult

```python
@dataclass
class ScanResult:
    risk_score: float          # 0-100 aggregate risk
    severity: Severity         # info, warning, or critical
    dimensions: dict           # Per-dimension scores
    blocked: bool              # Whether delivery was blocked
    raw_output: str            # The scanned text
    scan_time_ms: float        # Time taken to scan
```

### DimensionScore

```python
@dataclass
class DimensionScore:
    dimension: str             # hallucination, brand, policy, safety
    score: float               # 0-100
    severity: Severity
    flagged_spans: list        # Highlighted problematic spans
    details: str               # Human-readable explanation
```

## Scoring Modules

### Hallucination Detector

Compares LLM output against your knowledge base using LLM-as-judge with chain-of-thought reasoning.

**Requires:** `knowledge_base` parameter

**How it works:**
1. Sends output + knowledge base to LLM judge
2. LLM identifies unsupported claims, fabrications, contradictions
3. Returns risk score + flagged spans

### Brand Scorer

Evaluates tone, voice, terminology, and style against brand guidelines.

**Requires:** `brand_guidelines` or `policy_rules['brand']`

**How it works:**
1. Regex rules check for prohibited terms
2. LLM judge evaluates overall tone alignment
3. Combined score from both approaches

### Policy Checker

Regex + keyword rules for compliance violations.

**Requires:** `policy_rules` dict (e.g., `{"financial": [r"guaranteed returns"]}`)

### Content Safety Filter

Blocklist + LLM classifier for harmful content.

**Configurable:** `safety_blocklist` parameter (defaults to common harmful patterns)

## Configuration Guide

### Mode: Flag vs Block

**Flag mode** (default): All outputs are delivered, but annotated with risk scores. Use this for monitoring and establishing baseline.

**Block mode**: Outputs above `risk_threshold` severity are blocked. Use this for high-stakes applications.

### Risk Threshold

Adjust `risk_threshold` based on your risk tolerance:
- **90+**: Only block/w flag truly dangerous outputs
- **70-89**: Balanced — catches most issues without excessive false positives
- **50-69**: Aggressive — more false positives but higher safety

### Per-Customer Calibration

Recommended approach:
1. Start with flag mode for 2 weeks
2. Review false positive rates per customer
3. Adjust thresholds based on their tolerance
4. Switch to block mode once calibrated

## Troubleshooting

**High false positive rate?**
- Broaden your knowledge base with more context docs
- Adjust `risk_threshold` upward (85-90)
- Review flagged spans to identify patterns

**Missing hallucinations?**
- Ensure knowledge base is comprehensive and up-to-date
- Use more specific documents rather than general ones
- Consider using a stronger model (`gpt-4o` instead of `gpt-4o-mini`)

**Slow scan times?**
- Enable Redis queue for non-blocking scanning
- Use `gpt-4o-mini` for faster scoring
- Disable unused dimensions
