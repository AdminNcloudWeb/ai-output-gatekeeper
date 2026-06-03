"""Base class for scoring modules."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from gatekeeper.models import DimensionScore, GatekeeperConfig, Severity


class BaseScorer(ABC):
    """Base class for all scoring modules."""

    def __init__(self, config: GatekeeperConfig):
        self.config = config

    @property
    @abstractmethod
    def dimension(self) -> str:
        """Return the dimension name."""
        ...

    @abstractmethod
    async def async_score(self, output: str, context: Optional[dict] = None) -> DimensionScore:
        """Score an output asynchronously."""
        ...

    def score(self, output: str, context: Optional[dict] = None) -> DimensionScore:
        """Score an output synchronously (fallback)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, can't use run_until_complete
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.async_score(output, context)).result()
            else:
                return loop.run_until_complete(self.async_score(output, context))
        except RuntimeError:
            import asyncio
            return asyncio.run(self.async_score(output, context))
