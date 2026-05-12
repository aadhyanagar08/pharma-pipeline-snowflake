"""
extract_load.py
~~~~~~~~~~~~~~~
Extract adverse drug event records from the FDA FAERS public API and load
them into Snowflake RAW.ADVERSE_EVENTS.

Usage:
    python ingestion/extract_load.py

Environment variables (see .env.example):
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_ORG, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
    SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_ROLE
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

import requests
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FDA_API_URL = "https://api.fda.gov/drug/event.json"
FDA_BATCH_LIMIT = 100
TARGET_TABLE = "RAW.ADVERSE_EVENTS"


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def fetch_adverse_events(limit: int = FDA_BATCH_LIMIT) -> list[dict[str, Any]]:
    """Call the FDA FAERS API and return the raw results list."""
    params = {"limit": limit}
    log.info("Fetching %d records from %s", limit, FDA_API_URL)
    try:
        response = requests.get(FDA_API_URL, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        log.error("HTTP error from FDA API: %s", exc)
        raise
    except requests.exceptions.RequestException as exc:
        log.error("Network error reaching FDA API: %s", exc)
        raise

    payload = response.json()
    results = payload.get("results", [])
    log.info("Received %d results from FDA API", len(results))
    return results


def parse_event(record: dict[str, Any], source_tag: str) -> tuple[Any, ...]:
    """
    Extract the subset of fields we care about from a single FAERS record.

    The FAERS schema nests drug and reaction data inside lists; we take the
    first drug entry only to keep the model flat.
    """
    drugs = record.get("patient", {}).get("drug", [])
    reactions = record.get("patient", {}).get("reaction", [])

    first_drug = drugs[0] if drugs else {}
    first_reaction = reactions[0] if reactions else {}

    return (
        record.get("safetyreportid"),
        record.get("receivedate"),
        record.get("occurcountry"),
        first_drug.get("medicinalproduct"),
        first_drug.get("drugindication"),
        str(first_reaction.get("reactionoutcome", "")) or None,
        str(record.get("serious", "")) or None,
        source_tag,
    )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def get_snowflake_connection() -> snowflake.connector.SnowflakeConnection:
    """Build a Snowflake connection from environment variables."""
    account = os.environ["SNOWFLAKE_ACCOUNT"]
    org = os.environ.get("SNOWFLAKE_ORG", "")
    # Snowflake expects account in the form org-account when using org
    full_account = f"{org}-{account}" if org else account

    return snowflake.connector.connect(
        account=full_account,
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "PHARMA_DB"),
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
        session_parameters={"QUERY_TAG": "pharma-pipeline-ingestion"},
    )


INSERT_SQL = f"""
INSERT INTO {TARGET_TABLE}
    (event_id, receive_date, report_country, drug_name,
     drug_indication, reaction_outcome, serious, source_file)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""


def load_to_snowflake(
    conn: snowflake.connector.SnowflakeConnection,
    rows: list[tuple[Any, ...]],
) -> int:
    """Bulk-insert parsed rows; return the number of rows actually inserted."""
    if not rows:
        log.warning("No rows to insert — skipping load.")
        return 0

    with conn.cursor() as cur:
        cur.executemany(INSERT_SQL, rows)
        inserted = cur.rowcount
    conn.commit()
    log.info("Inserted %d rows into %s", inserted, TARGET_TABLE)
    return inserted


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    source_tag = f"fda_faers_api_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    # --- Extract ---
    raw_records = fetch_adverse_events(limit=FDA_BATCH_LIMIT)

    # --- Transform (light parsing only; heavy transforms live in SQL models) ---
    parsed_rows = [parse_event(r, source_tag) for r in raw_records]
    log.info("Parsed %d events", len(parsed_rows))

    # --- Load ---
    log.info("Connecting to Snowflake…")
    try:
        conn = get_snowflake_connection()
    except KeyError as exc:
        log.error("Missing required environment variable: %s", exc)
        sys.exit(1)
    except snowflake.connector.errors.DatabaseError as exc:
        log.error("Snowflake connection failed: %s", exc)
        sys.exit(1)

    try:
        row_count = load_to_snowflake(conn, parsed_rows)
    finally:
        conn.close()

    print(f"\nRows loaded into {TARGET_TABLE}: {row_count}")


if __name__ == "__main__":
    main()
