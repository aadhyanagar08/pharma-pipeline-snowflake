import logging
import os
import time

import requests

log = logging.getLogger(__name__)


def report_run(status, rows_processed=0, duration_seconds=None, error_message=None):
    """POST a pipeline run report to the ETL monitor service.

    Silently no-ops if ETL_MONITOR_URL is unset. Never raises.
    """
    ETL_MONITOR_URL = os.environ.get("ETL_MONITOR_URL", None)
    ETL_MONITOR_PIPELINE_ID = int(os.environ.get("ETL_MONITOR_PIPELINE_ID", 1))

    if not ETL_MONITOR_URL:
        log.warning("ETL_MONITOR_URL not set — skipping monitor report")
        return

    url = f"{ETL_MONITOR_URL}/pipelines/{ETL_MONITOR_PIPELINE_ID}/runs"
    payload = {
        "status": status,
        "rows_processed": rows_processed,
        "duration_seconds": duration_seconds,
        "error_message": error_message,
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        log.info("Monitor report sent successfully (pipeline_id=%d, status=%s)", ETL_MONITOR_PIPELINE_ID, status)
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to send monitor report: %s", exc)
