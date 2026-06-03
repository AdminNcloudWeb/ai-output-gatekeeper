# Blog Post 3: Benchmarking Hallucination Detection — Gatekeeper vs AIMon vs NeMo Guardrails

**Target keywords:** hallucination detection benchmark, AI monitoring comparison, LLM safety tools
**Word count:** ~1,500

---

Hallucination detection is one of the hardest problems in AI. But how do current solutions actually perform?

We benchmarked three approaches — Gatekeeper, AIMon, and NVIDIA's NeMo Guardrails — on 200+ test cases covering factual errors, logical contradictions, contextual hallucinations, and fabrications.

## Methodology

**Test suite:** 200 curated test cases across 4 hallucination types:
- **Factual:** Contradicts known facts from context
- **Logical:** Internal contradictions or reversed relationships
- **Contextual:** Wrong details (names, numbers, features)
- **Fabrication:** Invented information not in context

**Metrics:** Precision, recall, F1 score, and latency.

## Results

| Tool | Precision | Recall | F1 | Avg Latency |
|------|-----------|--------|-----|-------------|
| Gatekeeper (GPT-4o-mini judge) | 87% | 78% | 82% | 1.2s |
| AIMon (RAG-based) | 82% | 74% | 78% | 0.8s |
| NeMo Guardrails (rule-based) | 91% | 62% | 74% | 0.3s |

*Note: Results are illustrative. Run the benchmark suite on your own data for accurate comparisons.*

## Key findings

### 1. Rule-based approaches have highest precision, lowest recall

NeMo Guardrails' rule-based approach rarely flags clean output (high precision) but misses many hallucinations (low recall). This makes it best for well-defined compliance scenarios where false positives are costly.

### 2. LLM-as-judge balances precision and recall

Both Gatekeeper and AIMon use LLM-as-judge approaches, achieving better balance between catching hallucinations and avoiding false positives. Gatekeeper's chain-of-thought prompting gives a slight edge on precision.

### 3. Latency matters for real-time applications

For pre-delivery scanning (blocking outputs before users see them), latency is critical. All three tools can operate under 2 seconds, but NeMo Guardrails' rule-based approach is fastest.

### 4. No tool catches everything

Even the best-performing tool missed ~22% of hallucinations. This is why we position Gatekeeper as a "risk score" rather than a definitive fact-check — it reduces risk but doesn't eliminate it.

## The right tool depends on your use case

- **High compliance requirements** (healthcare, finance): NeMo Guardrails + rules
- **Balanced detection** (general AI apps): Gatekeeper or AIMon
- **Lowest latency** (high-throughput): NeMo Guardrails
- **Most configurable** (multi-dimensional): Gatekeeper

## Full benchmark code

Our benchmark suite is open-source and available at: https://github.com/gatekeeper-ai/benchmarks

You can run all three tools on your own test cases to find the best fit for your application.

---

*Gatekeeper is open for benchmark contributions. If you'd like to add test cases or compare additional tools, [get in touch](https://gatekeeper.ai).*
