"""Usage-based billing for Gatekeeper AI.

Tracks scans per customer, enforces soft/hard limits, handles overage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class BillingTier:
    """Represents a billing tier."""
    name: str
    price_cents: int  # Monthly price in cents
    included_scans: int  # Scans included per month
    overage_rate_cents: float  # Cost per additional scan (in cents)
    features: list[str] = field(default_factory=list)


# Default tiers matching the pricing page
STARTER = BillingTier(
    name="Starter",
    price_cents=9900,
    included_scans=50000,
    overage_rate_cents=0.04,  # $0.00004 per scan = $20 per 500K overage
    features=["1_dashboard_user", "weekly_reports", "email_alerts"],
)

GROWTH = BillingTier(
    name="Growth",
    price_cents=34900,
    included_scans=500000,
    overage_rate_cents=0.01,  # $0.00001 per scan = $10 per 1M overage
    features=["multi_team", "slack_integration", "custom_rules", "realtime_dashboard", "priority_support"],
)

ENTERPRISE = BillingTier(
    name="Enterprise",
    price_cents=100000,
    included_scans=-1,  # Unlimited
    overage_rate_cents=0.0,
    features=["unlimited", "onprem_option", "soc2", "dedicated_csm", "sla", "custom_integrations"],
)


@dataclass
class BillingRecord:
    """Billing record for a single customer in a single billing period."""
    customer_id: str
    tier: BillingTier
    period_start: datetime
    period_end: datetime
    scans_used: int = 0
    soft_limit_reached: bool = False
    hard_limit_reached: bool = False
    overage_scans: int = 0

    @property
    def scans_remaining(self) -> int:
        if self.tier.included_scans == -1:
            return -1  # Unlimited
        return max(0, self.tier.included_scans - self.scans_used)

    @property
    def overage_cost_cents(self) -> float:
        return self.overage_scans * self.tier.overage_rate_cents

    @property
    def total_cost_cents(self) -> int:
        return self.tier.price_cents + int(self.overage_cost_cents)

    def record_scan(self, count: int = 1) -> dict:
        """Record scan usage. Returns status info."""
        self.scans_used += count

        if self.tier.included_scans == -1:
            return {"status": "ok", "remaining": -1}

        if self.scans_used >= self.tier.included_scans and not self.soft_limit_reached:
            self.soft_limit_reached = True
            self.overage_scans = self.scans_used - self.tier.included_scans
            return {
                "status": "overage",
                "message": f"Soft limit reached. {self.overage_scans} overage scans.",
                "overage_scans": self.overage_scans,
            }

        if self.scans_used >= self.tier.included_scans * 1.5 and not self.hard_limit_reached:
            self.hard_limit_reached = True
            return {
                "status": "hard_limit",
                "message": f"Hard limit reached (150% of included). Scan blocked.",
            }

        return {"status": "ok", "remaining": self.scans_remaining}

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "tier": self.tier.name,
            "period": f"{self.period_start.date()} to {self.period_end.date()}",
            "scans_used": self.scans_used,
            "scans_included": self.tier.included_scans,
            "scans_remaining": self.scans_remaining,
            "soft_limit_reached": self.soft_limit_reached,
            "hard_limit_reached": self.hard_limit_reached,
            "overage_scans": self.overage_scans,
            "base_cost": f"${self.tier.price_cents / 100:.2f}",
            "overage_cost": f"${self.overage_cost_cents / 100:.2f}",
            "total_cost": f"${self.total_cost_cents / 100:.2f}",
        }


class BillingManager:
    """Manages billing for all customers."""

    def __init__(self):
        self._records: dict[str, BillingRecord] = {}

    def get_or_create_record(
        self,
        customer_id: str,
        tier: BillingTier,
        period_start: Optional[datetime] = None,
    ) -> BillingRecord:
        """Get or create a billing record for a customer."""
        if customer_id not in self._records:
            now = period_start or datetime.utcnow()
            period_end = now + timedelta(days=30)
            self._records[customer_id] = BillingRecord(
                customer_id=customer_id,
                tier=tier,
                period_start=now,
                period_end=period_end,
            )
        return self._records[customer_id]

    def record_scan(self, customer_id: str, tier: BillingTier) -> dict:
        """Record a scan for a customer and return billing status."""
        record = self.get_or_create_record(customer_id, tier)
        return record.record_scan()

    def get_usage(self, customer_id: str, tier: BillingTier) -> Optional[dict]:
        """Get usage data for a customer."""
        record = self._records.get(customer_id)
        return record.to_dict() if record else None

    def reset_period(self, customer_id: str, tier: BillingTier) -> BillingRecord:
        """Reset billing period for a customer (e.g., monthly renewal)."""
        now = datetime.utcnow()
        period_end = now + timedelta(days=30)
        record = BillingRecord(
            customer_id=customer_id,
            tier=tier,
            period_start=now,
            period_end=period_end,
        )
        self._records[customer_id] = record
        return record
