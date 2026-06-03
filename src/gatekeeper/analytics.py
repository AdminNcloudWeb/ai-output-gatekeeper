"""Analytics pipeline for Gatekeeper AI.

Tracks per-customer scan volumes, detection accuracy metrics,
time-to-alert, and dashboard engagement.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CustomerAnalytics:
    """Analytics data for a single customer."""
    customer_id: str
    total_scans: int = 0
    blocked_scans: int = 0
    flagged_scans: int = 0
    critical_scans: int = 0
    warning_scans: int = 0
    info_scans: int = 0
    avg_risk_score: float = 0.0
    avg_latency_ms: float = 0.0
    total_flag_count: int = 0
    dimension_counts: dict[str, int] = field(default_factory=dict)
    daily_scans: dict[str, int] = field(default_factory=dict)
    last_scan_at: Optional[float] = None

    def record_scan(self, scan_result) -> None:
        """Record a scan result in the analytics."""
        self.total_scans += 1
        self.last_scan_at = time.time()

        # Severity counts
        if scan_result.severity.value == "critical":
            self.critical_scans += 1
        elif scan_result.severity.value == "warning":
            self.warning_scans += 1
        else:
            self.info_scans += 1

        # Block/flag counts
        if scan_result.blocked:
            self.blocked_scans += 1
        if scan_result.risk_score >= 50:
            self.flagged_scans += 1

        # Running averages
        self.avg_risk_score = (
            (self.avg_risk_score * (self.total_scans - 1) + scan_result.risk_score)
            / self.total_scans
        )
        self.avg_latency_ms = (
            (self.avg_latency_ms * (self.total_scans - 1) + scan_result.scan_time_ms)
            / self.total_scans
        )

        # Dimension counts
        for dim_name, dim_score in scan_result.dimensions.items():
            key = f"{dim_name}_flagged"
            if dim_score.score >= 50:
                self.dimension_counts[key] = self.dimension_counts.get(key, 0) + 1

        # Daily scan count
        from datetime import date
        day = date.today().isoformat()
        self.daily_scans[day] = self.daily_scans.get(day, 0) + 1

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "total_scans": self.total_scans,
            "blocked_scans": self.blocked_scans,
            "flagged_scans": self.flagged_scans,
            "critical_scans": self.critical_scans,
            "warning_scans": self.warning_scans,
            "info_scans": self.info_scans,
            "avg_risk_score": round(self.avg_risk_score, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "dimension_counts": self.dimension_counts,
            "daily_scans": self.daily_scans,
            "last_scan_at": self.last_scan_at,
        }


class AnalyticsPipeline:
    """Manages analytics for all customers.

    In production, this would write to a data warehouse (e.g., ClickHouse, BigQuery).
    This implementation stores in-memory for the MVP.
    """

    def __init__(self):
        self._customers: dict[str, CustomerAnalytics] = {}

    def get_customer(self, customer_id: str) -> CustomerAnalytics:
        """Get or create analytics for a customer."""
        if customer_id not in self._customers:
            self._customers[customer_id] = CustomerAnalytics(customer_id=customer_id)
        return self._customers[customer_id]

    def record_scan(self, customer_id: str, scan_result) -> None:
        """Record a scan result for a customer."""
        customer = self.get_customer(customer_id)
        customer.record_scan(scan_result)

    def get_summary(self, customer_id: str) -> Optional[dict]:
        """Get analytics summary for a customer."""
        customer = self._customers.get(customer_id)
        return customer.to_dict() if customer else None

    def get_all_customers_summary(self) -> list[dict]:
        """Get summary for all customers."""
        return [c.to_dict() for c in self._customers.values()]

    def get_aggregate_stats(self) -> dict:
        """Get aggregate stats across all customers."""
        if not self._customers:
            return {"total_customers": 0}

        all_scans = [c.total_scans for c in self._customers.values()]
        return {
            "total_customers": len(self._customers),
            "total_scans": sum(all_scans),
            "avg_scans_per_customer": round(sum(all_scans) / len(all_scans), 1),
            "total_blocked": sum(c.blocked_scans for c in self._customers.values()),
            "total_flagged": sum(c.flagged_scans for c in self._customers.values()),
        }
