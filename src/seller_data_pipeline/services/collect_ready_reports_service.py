from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class CollectReadyReportsService:
    """Check pending reports, download DONE reports, parse, and upsert data."""

    def run(self, *, limit: int) -> None:
        logger.info("collect ready reports placeholder: limit=%s", limit)
        # TODO: read pending report requests, query status, download DONE reports, parse and upsert.
