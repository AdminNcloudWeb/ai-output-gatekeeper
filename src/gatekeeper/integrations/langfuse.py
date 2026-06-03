"""Langfuse integration for Gatekeeper AI.

Receives webhook events from Langfuse and sends scan data to Gatekeeper.
Displays Gatekeeper risk scores in Langfuse trace UI.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Optional

from gatekeeper.models import ScanResult


class LangfuseIntegration:
    """Integrates Gatekeeper with Langfuse observability platform.

    Usage:
        integration = LangfuseIntegration(
            gatekeeper_api_key="gk-...",
            langfuse_public_key="pk-...",
            langfuse_secret_key="sk-...",
            webhook_secret="whsec-...",
        )

        # In your webhook handler:
        result = integration.handle_webhook(payload, signature)
    """

    def __init__(
        self,
        gatekeeper_api_key: str,
        langfuse_public_key: str,
        langfuse_secret_key: str,
        webhook_secret: str,
        gatekeeper_base_url: str = "https://api.gatekeeper.ai",
    ):
        self.gatekeeper_api_key = gatekeeper_api_key
        self.langfuse_public_key = langfuse_public_key
        self.langfuse_secret_key = langfuse_secret_key
        self.webhook_secret = webhook_secret
        self.gatekeeper_base_url = gatekeeper_base_url

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify that a webhook request came from Langfuse."""
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    def handle_webhook(self, payload: dict) -> Optional[dict]:
        """Process a Langfuse webhook event.

        Expected event types:
        - trace.created: New trace with LLM generation
        - generation.completed: LLM generation completed
        """
        event_type = payload.get("type", "")

        if event_type == "generation.completed":
            return self._process_generation(payload.get("data", {}))
        elif event_type == "trace.created":
            return self._process_trace(payload.get("data", {}))

        return None

    def _process_generation(self, data: dict) -> dict:
        """Process a completed LLM generation from Langfuse."""
        output = data.get("output", "")
        trace_id = data.get("traceId", "")
        generation_id = data.get("id", "")

        if not output:
            return {"status": "skipped", "reason": "no output"}

        # Send to Gatekeeper for scanning
        scan_result = self._scan_with_gatekeeper(output, trace_id)

        # Return data to be attached to Langfuse trace
        return {
            "status": "scanned",
            "trace_id": trace_id,
            "generation_id": generation_id,
            "gatekeeper": {
                "risk_score": scan_result.get("risk_score", 0),
                "severity": scan_result.get("severity", "info"),
                "dimensions": scan_result.get("dimensions", {}),
            },
        }

    def _process_trace(self, data: dict) -> dict:
        """Process a new trace from Langfuse."""
        return {
            "status": "received",
            "trace_id": data.get("id", ""),
        }

    def _scan_with_gatekeeper(self, output: str, trace_id: str) -> dict:
        """Send output to Gatekeeper for scanning."""
        import urllib.request
        import urllib.error

        url = f"{self.gatekeeper_base_url}/v1/scan"
        payload = json.dumps({
            "output": output,
            "source": "langfuse",
            "trace_id": trace_id,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {self.gatekeeper_api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {
                "risk_score": 0,
                "severity": "info",
                "error": str(e),
            }

    def build_trace_metadata(self, scan_result: dict) -> dict:
        """Build Langfuse trace metadata from Gatekeeper scan result."""
        return {
            "metadata": {
                "gatekeeper_risk_score": scan_result.get("risk_score", 0),
                "gatekeeper_severity": scan_result.get("severity", "info"),
                "gatekeeper_scanned": True,
            },
            "scores": [
                {
                    "name": f"gatekeeper_{dim}",
                    "value": data.get("score", 0),
                    "comment": data.get("details", ""),
                }
                for dim, data in scan_result.get("dimensions", {}).items()
            ],
        }
