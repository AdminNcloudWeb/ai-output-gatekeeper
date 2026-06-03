# Blog Post 2: How to Add Output Monitoring to Your LLM Pipeline in 5 Minutes

**Target keywords:** LLM monitoring, AI output scanning, LLM guardrails, Python SDK
**Word count:** ~1,200

---

You've built an AI feature. It works. Users love it.

But somewhere in the back of your mind, there's a worry: *What if the AI says something wrong?*

Maybe it hallucinates a product feature that doesn't exist. Maybe it uses the wrong tone with a premium customer. Maybe it makes a compliance claim your legal team would never approve.

Here's how to add a safety net in 5 minutes.

## Step 1: Install

```bash
pip install gatekeeper-ai
```

## Step 2: Initialize

```python
from gatekeeper import Gatekeeper

gk = Gatekeeper(
    api_key="sk-your-openai-key",
    knowledge_base=[
        # Your product docs, FAQ, policies — whatever the AI should know
        "Our refund policy: 30-day returns, original packaging required.",
        "We ship via UPS Ground (3-5 days).",
        "Product pricing: Starter $99/mo, Growth $349/mo.",
    ],
    mode="flag",  # Start with flag mode to monitor without blocking
)
```

## Step 3: Wrap your existing calls

Replace your current OpenAI call:

```python
# Before
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": user_message}]
)
```

With this:

```python
# After
response, scan = gk.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": user_message}]
)
```

That's it. Your API calls work exactly the same, but now you get a `scan` object with:

- `scan.risk_score` — 0-100 aggregate risk score
- `scan.severity` — info, warning, or critical
- `scan.dimensions` — Per-dimension breakdown (hallucination, brand, policy, safety)
- `scan.flagged_spans` — Exact text spans that were flagged

## Step 4: Check the results

```python
if scan.severity.value == "critical":
    # Alert your team, log for review, etc.
    print(f"⚠️ High-risk output (score: {scan.risk_score})")
    for dim in scan.dimensions.values():
        if dim.score > 70:
            print(f"  {dim.dimension}: {dim.details}")
```

## Step 5: Review and iterate

Run in flag mode for 1-2 weeks. Review the flagged outputs. Adjust your knowledge base and thresholds based on false positive rates.

Once calibrated, switch to block mode:

```python
gk = Gatekeeper(
    ...,
    mode="block",
    risk_threshold=75,  # Block outputs above this score
)
```

## Why this approach?

Most guardrails solutions require significant engineering effort — custom rule engines, complex evaluation pipelines, manual review queues.

Gatekeeper takes a different approach: **drop-in middleware** that works with your existing OpenAI calls. No new infrastructure. No complex setup. Just 2 lines of code between your app and a safer AI.

---

*Try Gatekeeper today: [Join the waitlist](https://gatekeeper.ai)*
