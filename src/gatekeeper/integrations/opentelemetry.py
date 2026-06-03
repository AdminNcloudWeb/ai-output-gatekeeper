"""OpenTelemetry exporter for Gatekeeper AI.

Exports Gatekeeper scan metrics and traces to any OpenTelemetry-compatible
observability backend (Jaeger, Zipkin, Datadog, Grafana, etc.).
"""

from __future__ import annotations

import time
from typing import Any, Optional, Sequence

from gatekeeper.models import ScanResult, Severity


class GatekeeperOTelExporter:
    """Export Gatekeeper scan results as OpenTelemetry spans and metrics.

    Usage:
        exporter = GatekeeperOTelExporter(
            service_name="gatekeeper-ai",
            endpoint="http://localhost:4317",
        )

        # After each scan:
        exporter.export_scan(scan_result, attributes={
            "customer_id": "cust_123",
            "model": "gpt-4o",
        })

        exporter.shutdown()
    """

    def __init__(
        self,
        service_name: str = "gatekeeper-ai",
        endpoint: str = "http://localhost:4317",
        headers: Optional[dict] = None,
    ):
        self.service_name = service_name
        self.endpoint = endpoint
        self.headers = headers or {}
        self._tracer = None
        self._meter = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy-initialize OpenTelemetry SDK."""
        if self._initialized:
            return
        try:
            from opentelemetry import trace, metrics
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({"service.name": self.service_name})

            # Traces
            tracer_provider = TracerProvider(resource=resource)
            span_exporter = OTLPSpanExporter(
                endpoint=self.endpoint,
                headers=self.headers,
            )
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(tracer_provider)
            self._tracer = trace.get_tracer(self.service_name)

            # Metrics
            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=self.endpoint, headers=self.headers),
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            metrics.set_meter_provider(meter_provider)
            self._meter = meter_provider.get_meter(self.service_name)

            # Create metrics
            self._scan_counter = self._meter.create_counter(
                "gatekeeper.scans.total",
                description="Total number of scans performed",
            )
            self._risk_histogram = self._meter.create_histogram(
                "gatekeeper.scan.risk_score",
                description="Distribution of risk scores",
            )
            self._dimension_histogram = self._meter.create_histogram(
                "gatekeeper.scan.dimension_score",
                description="Per-dimension risk scores",
            )
            self._latency_histogram = self._meter.create_histogram(
                "gatekeeper.scan.latency_ms",
                description="Scan latency in milliseconds",
            )
            self._block_counter = self._meter.create_counter(
                "gatekeeper.scans.blocked",
                description="Number of scans that resulted in blocking",
            )

            self._initialized = True
        except ImportError:
            # OpenTelemetry SDK not installed — operate in no-op mode
            self._initialized = True  # Mark as initialized to avoid retrying

    def export_scan(
        self,
        scan_result: ScanResult,
        attributes: Optional[dict] = None,
    ) -> Optional[Any]:
        """Export a scan result as an OpenTelemetry span with metrics."""
        self._ensure_initialized()

        attrs = dict(attributes or {})
        attrs.update({
            "gatekeeper.risk_score": scan_result.risk_score,
            "gatekeeper.severity": scan_result.severity.value,
            "gatekeeper.blocked": scan_result.blocked,
            "gatekeeper.scan_time_ms": scan_result.scan_time_ms,
        })

        # Record metrics
        if self._meter:
            self._scan_counter.add(1, attrs)
            self._risk_histogram.record(scan_result.risk_score, attrs)
            self._latency_histogram.record(scan_result.scan_time_ms, attrs)
            if scan_result.blocked:
                self._block_counter.add(1, attrs)

            for dim_name, dim_score in scan_result.dimensions.items():
                dim_attrs = {**attrs, "dimension": dim_name}
                self._dimension_histogram.record(dim_score.score, dim_attrs)

        # Create span
        if self._tracer:
            with self._tracer.start_as_current_span(
                "gatekeeper.scan",
                attributes=attrs,
            ) as span:
                span.set_attribute("gatekeeper.risk_score", scan_result.risk_score)
                span.set_attribute("gatekeeper.severity", scan_result.severity.value)
                span.set_attribute("gatekeeper.blocked", scan_result.blocked)

                for dim_name, dim_score in scan_result.dimensions.items():
                    span.set_attribute(
                        f"gatekeeper.dimension.{dim_name}.score",
                        dim_score.score,
                    )
                    span.set_attribute(
                        f"gatekeeper.dimension.{dim_name}.severity",
                        dim_score.severity.value,
                    )

                if scan_result.severity == Severity.CRITICAL:
                    span.set_status(trace.StatusCode.ERROR, "Critical risk detected")

                return span

        return None

    def shutdown(self):
        """Flush and shutdown the exporter."""
        if self._initialized:
            try:
                from opentelemetry import trace, metrics
                provider = trace.get_tracer_provider()
                if hasattr(provider, 'force_flush'):
                    provider.force_flush()
            except Exception:
                pass


# Convenience function for quick setup
def create_exporter(
    endpoint: str = "http://localhost:4317",
    service_name: str = "gatekeeper-ai",
) -> GatekeeperOTelExporter:
    """Create an OpenTelemetry exporter with sensible defaults."""
    return GatekeeperOTelExporter(
        service_name=service_name,
        endpoint=endpoint,
    )
